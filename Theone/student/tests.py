from datetime import date
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from .models import Course, ExamRegistration, SmsLog, Student, StudentCourse
from .sms import build_exam_registration_message, normalize_phone_number, send_exam_registration_sms


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
