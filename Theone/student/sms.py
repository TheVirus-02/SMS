import base64
import json
from dataclasses import dataclass
from urllib import error, parse, request

from django.conf import settings

from .models import SmsLog


@dataclass
class SmsSendResult:
    sent: bool
    skipped: bool = False
    detail: str = ""
    provider_message_id: str = ""


def normalize_phone_number(raw_number: str | None) -> str:
    if not raw_number:
        return ""

    cleaned = "".join(ch for ch in raw_number if ch.isdigit() or ch == "+")
    if not cleaned:
        return ""

    if cleaned.startswith("+"):
        return cleaned

    default_country_code = getattr(settings, "SMS_DEFAULT_COUNTRY_CODE", "+91").strip()
    country_digits = "".join(ch for ch in default_country_code if ch.isdigit())

    if country_digits and cleaned.startswith(country_digits):
        return f"+{cleaned}"

    if len(cleaned) == 10 and default_country_code:
        return f"{default_country_code}{cleaned}"

    return cleaned


def build_exam_registration_message(student_name: str, course_name: str, exam_date) -> str:
    exam_date_label = exam_date.strftime("%d %b %Y") if exam_date else "the scheduled date"
    return (
        f"Hi {student_name}, your registration for the {course_name} exam is complete. "
        f"Your exam is on {exam_date_label}."
    )


def send_exam_registration_sms(student, registration) -> SmsSendResult:
    provider = getattr(settings, "SMS_PROVIDER", "").strip().lower() or "twilio"
    to_number = normalize_phone_number(getattr(student, "mobile_no", ""))
    message_body = build_exam_registration_message(
        student_name=student.name,
        course_name=registration.course_name,
        exam_date=registration.exam_date,
    )
    if not getattr(settings, "SMS_ENABLED", False):
        return create_sms_log(
            student=student,
            registration=registration,
            provider=provider,
            to_number=to_number,
            message_body=message_body,
            status=SmsLog.STATUS_SKIPPED,
            detail="SMS is disabled.",
        )

    if provider != "twilio":
        return create_sms_log(
            student=student,
            registration=registration,
            provider=provider,
            to_number=to_number,
            message_body=message_body,
            status=SmsLog.STATUS_SKIPPED,
            detail="SMS provider is not supported.",
        )

    if not to_number:
        return create_sms_log(
            student=student,
            registration=registration,
            provider=provider,
            to_number="",
            message_body=message_body,
            status=SmsLog.STATUS_SKIPPED,
            detail="Student mobile number is missing.",
        )

    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", "")
    if not all([account_sid, auth_token, from_number]):
        return create_sms_log(
            student=student,
            registration=registration,
            provider=provider,
            to_number=to_number,
            message_body=message_body,
            status=SmsLog.STATUS_SKIPPED,
            detail="Twilio settings are incomplete.",
        )

    result = send_twilio_sms(
        account_sid=account_sid,
        auth_token=auth_token,
        from_number=from_number,
        to_number=to_number,
        message_body=message_body,
    )
    return create_sms_log(
        student=student,
        registration=registration,
        provider=provider,
        to_number=to_number,
        message_body=message_body,
        status=SmsLog.STATUS_SENT if result.sent else SmsLog.STATUS_FAILED,
        detail=result.detail,
        provider_message_id=result.provider_message_id,
    )


def create_sms_log(student, registration, provider, to_number, message_body, status, detail, provider_message_id=""):
    SmsLog.objects.create(
        student=student,
        exam_registration=registration,
        provider=provider,
        phone_number=to_number,
        message_body=message_body,
        status=status,
        provider_message_id=provider_message_id or None,
        response_detail=detail,
    )
    return SmsSendResult(
        sent=status == SmsLog.STATUS_SENT,
        skipped=status == SmsLog.STATUS_SKIPPED,
        detail=detail,
        provider_message_id=provider_message_id,
    )


def send_twilio_sms(account_sid, auth_token, from_number, to_number, message_body) -> SmsSendResult:

    encoded_auth = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    payload = parse.urlencode({
        "To": to_number,
        "From": from_number,
        "Body": message_body,
    }).encode("utf-8")
    sms_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    http_request = request.Request(
        sms_url,
        data=payload,
        headers={
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=15) as response:
            status_code = getattr(response, "status", 200)
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        return SmsSendResult(sent=False, detail=f"Twilio HTTP {exc.code}: {error_body[:180]}")
    except error.URLError as exc:
        return SmsSendResult(sent=False, detail=f"SMS request failed: {exc.reason}")
    except Exception as exc:
        return SmsSendResult(sent=False, detail=f"SMS error: {exc}")

    if 200 <= status_code < 300:
        sid = ""
        try:
            sid = json.loads(response_body).get("sid", "")
        except json.JSONDecodeError:
            pass
        detail = "SMS sent successfully."
        if sid:
            detail = f"SMS sent successfully. SID: {sid}"
        return SmsSendResult(sent=True, detail=detail, provider_message_id=sid)

    return SmsSendResult(sent=False, detail=f"Unexpected SMS response: {status_code}")
