from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .models import Center, CommunicationLog, Counsellor, Course, Enquiry, ExamRegistration, SmsLog, Student, StudentCourse
from .sms import (
    build_enquiry_follow_up_message,
    build_exam_registration_message,
    build_fee_reminder_message,
    normalize_phone_number,
    send_exam_registration_sms,
    send_general_sms,
)


class SmsHelperTests(SimpleTestCase):
    @override_settings(SMS_DEFAULT_COUNTRY_CODE="+91")
    def test_normalize_phone_number_adds_default_country_code(self):
        self.assertEqual(normalize_phone_number("98765 43210"), "+919876543210")

    @override_settings(SMS_DEFAULT_COUNTRY_CODE="+91")
    def test_normalize_phone_number_keeps_existing_plus_prefix(self):
        self.assertEqual(normalize_phone_number("+14155552671"), "+14155552671")

    def test_build_exam_registration_message_contains_course_and_date(self):
        message = build_exam_registration_message("Aman", "Python", date(2026, 4, 26))
        self.assertIn("Python", message)
        self.assertIn("Aman", message)
        self.assertIn("26 Apr 2026", message)


class SmsLogTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(name="Python")
        self.student = Student.objects.create(
            name="Aman",
            mobile_no="9876543210",
            joining_date=date(2026, 4, 1),
            course_fee=1000,
            paid_fee=1000,
        )
        self.student_course = StudentCourse.objects.create(
            student=self.student,
            course=self.course,
            is_completed=True,
            completion_date=date(2026, 4, 20),
        )
        self.registration = ExamRegistration.objects.create(
            student_course=self.student_course,
            exam_date=date(2026, 4, 26),
            receipt_no="R-1001",
            receipt_issued_date=date(2026, 4, 24),
            receipt_amount=300,
            payment_method="cash",
            payment_amount=300,
        )
        self.enquiry = Enquiry.objects.create(
            name="Riya",
            mobile_no="9123456789",
            enquiry_date=date(2026, 4, 10),
            next_follow_up_date=date(2026, 4, 26),
        )

    @override_settings(SMS_ENABLED=False, SMS_PROVIDER="twilio", SMS_DEFAULT_COUNTRY_CODE="+91")
    def test_send_exam_registration_sms_creates_skipped_log_when_disabled(self):
        result = send_exam_registration_sms(self.student, self.registration)

        self.assertFalse(result.sent)
        self.assertTrue(result.skipped)
        log = SmsLog.objects.get()
        self.assertEqual(log.status, SmsLog.STATUS_SKIPPED)
        self.assertEqual(log.exam_registration, self.registration)
        self.assertEqual(log.phone_number, "+919876543210")

    @override_settings(
        SMS_ENABLED=True,
        SMS_PROVIDER="twilio",
        SMS_DEFAULT_COUNTRY_CODE="+91",
        TWILIO_ACCOUNT_SID="AC123",
        TWILIO_AUTH_TOKEN="token",
        TWILIO_FROM_NUMBER="+10000000000",
    )
    @patch("student.sms.request.urlopen")
    def test_send_exam_registration_sms_creates_sent_log_when_provider_succeeds(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.read.return_value = b'{"sid":"SM123"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = send_exam_registration_sms(self.student, self.registration)

        self.assertTrue(result.sent)
        log = SmsLog.objects.get()
        self.assertEqual(log.status, SmsLog.STATUS_SENT)
        self.assertEqual(log.provider_message_id, "SM123")
        self.assertIn("Python", log.message_body)

    @override_settings(SMS_ENABLED=False, SMS_PROVIDER="twilio", SMS_DEFAULT_COUNTRY_CODE="+91")
    def test_send_general_sms_creates_communication_log_when_disabled(self):
        result = send_general_sms(
            student=self.student,
            message_body=build_fee_reminder_message(self.student),
            category=CommunicationLog.CATEGORY_FEE_REMINDER,
        )

        self.assertFalse(result.sent)
        self.assertTrue(result.skipped)
        log = CommunicationLog.objects.get()
        self.assertEqual(log.status, CommunicationLog.STATUS_SKIPPED)
        self.assertEqual(log.category, CommunicationLog.CATEGORY_FEE_REMINDER)
        self.assertEqual(log.phone_number, "+919876543210")

    @override_settings(SMS_ENABLED=False, SMS_PROVIDER="twilio", SMS_DEFAULT_COUNTRY_CODE="+91")
    def test_send_general_sms_supports_enquiry_logs(self):
        result = send_general_sms(
            enquiry=self.enquiry,
            message_body=build_enquiry_follow_up_message(self.enquiry),
            category=CommunicationLog.CATEGORY_ENQUIRY_FOLLOW_UP,
        )

        self.assertFalse(result.sent)
        self.assertTrue(result.skipped)
        log = CommunicationLog.objects.get(category=CommunicationLog.CATEGORY_ENQUIRY_FOLLOW_UP)
        self.assertEqual(log.enquiry, self.enquiry)
        self.assertEqual(log.phone_number, "+9123456789")


class AutomationPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(
            username="admin",
            password="pass1234",
            is_staff=True,
        )
        self.counsellor_user = user_model.objects.create_user(
            username="counsellor",
            password="pass1234",
        )
        self.center = Center.objects.create(name="Main Center")
        self.counsellor = Counsellor.objects.create(
            user=self.counsellor_user,
            name="Counsellor One",
            center=self.center,
        )

    def test_counsellor_cannot_access_automation_dashboard(self):
        self.client.force_login(self.counsellor_user)

        response = self.client.get(reverse("reminder_center"))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("counsellor_dashboard"))

    def test_counsellor_cannot_trigger_fee_reminder(self):
        self.client.force_login(self.counsellor_user)
        student = Student.objects.create(
            name="Blocked Student",
            mobile_no="9876543210",
            joining_date=date(2026, 4, 1),
            course_fee=1000,
            paid_fee=0,
        )

        response = self.client.post(reverse("send_fee_reminder", args=[student.id]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("counsellor_dashboard"))
        self.assertFalse(CommunicationLog.objects.exists())

    def test_admin_can_access_automation_dashboard(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("reminder_center"))

        self.assertEqual(response.status_code, 200)

    @override_settings(SMS_ENABLED=False, SMS_PROVIDER="twilio", SMS_DEFAULT_COUNTRY_CODE="+91")
    def test_counsellor_with_fee_permission_can_access_dashboard_and_send_fee_reminder(self):
        self.counsellor.can_send_fee_reminders = True
        self.counsellor.save(update_fields=["can_send_fee_reminders"])
        self.client.force_login(self.counsellor_user)
        student = Student.objects.create(
            name="Allowed Student",
            mobile_no="9876543210",
            joining_date=date(2026, 4, 1),
            course_fee=1000,
            paid_fee=0,
            center=self.center,
            counsellor=self.counsellor,
        )

        dashboard_response = self.client.get(reverse("reminder_center"))
        send_response = self.client.post(reverse("send_fee_reminder", args=[student.id]))

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "Bulk Fee Reminders")
        self.assertNotContains(dashboard_response, "Bulk Follow-Up Reminders")
        self.assertEqual(send_response.status_code, 302)
        self.assertRedirects(send_response, reverse("reminder_center"))
        log = CommunicationLog.objects.get(category=CommunicationLog.CATEGORY_FEE_REMINDER)
        self.assertEqual(log.student, student)

    @override_settings(SMS_ENABLED=False, SMS_PROVIDER="twilio", SMS_DEFAULT_COUNTRY_CODE="+91")
    def test_counsellor_with_follow_up_permission_can_send_follow_up_reminder(self):
        self.counsellor.can_send_follow_up_reminders = True
        self.counsellor.save(update_fields=["can_send_follow_up_reminders"])
        self.client.force_login(self.counsellor_user)
        enquiry = Enquiry.objects.create(
            name="Follow Up Lead",
            mobile_no="9123456789",
            enquiry_date=date(2026, 4, 10),
            next_follow_up_date=date(2026, 4, 26),
            assigned_counsellor=self.counsellor,
            preferred_center=self.center,
        )

        response = self.client.post(reverse("send_enquiry_follow_up_reminder", args=[enquiry.id]))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("reminder_center"))
        log = CommunicationLog.objects.get(category=CommunicationLog.CATEGORY_ENQUIRY_FOLLOW_UP)
        self.assertEqual(log.enquiry, enquiry)
