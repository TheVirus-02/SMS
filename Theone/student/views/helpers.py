from django.conf import settings


def build_sms_status_context(student=None):
    provider = getattr(settings, "SMS_PROVIDER", "").strip().lower() or "twilio"
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", "").strip()
    default_country_code = getattr(settings, "SMS_DEFAULT_COUNTRY_CODE", "+91").strip()
    enabled = getattr(settings, "SMS_ENABLED", False)
    missing_fields = []

    if provider == "twilio":
        if not getattr(settings, "TWILIO_ACCOUNT_SID", "").strip():
            missing_fields.append("Account SID")
        if not getattr(settings, "TWILIO_AUTH_TOKEN", "").strip():
            missing_fields.append("Auth Token")
        if not from_number:
            missing_fields.append("From Number")

    student_mobile = getattr(student, "mobile_no", "") if student else ""
    normalized_mobile = "".join(ch for ch in student_mobile if ch.isdigit() or ch == "+")
    if normalized_mobile and not normalized_mobile.startswith("+") and len(normalized_mobile) == 10:
        normalized_mobile = f"{default_country_code}{normalized_mobile}"

    status_label = "Ready"
    if not enabled:
        status_label = "Disabled"
    elif missing_fields:
        status_label = "Incomplete"

    return {
        "enabled": enabled,
        "provider": provider,
        "from_number": from_number or "Not set",
        "default_country_code": default_country_code,
        "student_mobile": student_mobile or "Not set",
        "normalized_mobile": normalized_mobile or "Not available",
        "missing_fields": missing_fields,
        "is_ready": enabled and not missing_fields,
        "status_label": status_label,
    }

