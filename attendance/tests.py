from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
import requests

from .models import Teacher, Student, Attendance, TeacherAttendance
from .sms_utils import send_sms, append_school_name, build_absent_message


class HealthCheckTests(TestCase):
    def test_health_check_endpoint(self):
        client = Client()
        response = client.get(reverse('health_check'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class AuthenticationAndSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = "Secr3tPass!123"
        self.admin_user = User.objects.create_superuser(
            username="admin_test",
            password=self.password,
            email="admin@example.com",
        )
        self.teacher_user = User.objects.create_user(
            username="teacher_test",
            password=self.password,
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            name="Test Teacher",
            mobile="01700000000",
            assigned_classes="Ten",
            employment_type=Teacher.EMPLOYMENT_FULL,
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attendance Register")

    def test_dashboard_redirects_unauthenticated(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_teacher_dashboard_authenticated(self):
        self.client.login(username="teacher_test", password=self.password)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Teacher")

    def test_admin_dashboard_authenticated(self):
        self.client.login(username="admin_test", password=self.password)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin")


class ModelAndAttendanceTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(
            roll_no="01",
            name="Rahim Uddin",
            class_name="Ten",
            section="A",
            parent_mobile="01800000000",
        )
        self.teacher_user = User.objects.create_user(
            username="t_rahim",
            password="password123",
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            name="Master Rahim",
            mobile="01900000000",
            assigned_classes="Ten",
            employment_type=Teacher.EMPLOYMENT_FULL,
        )

    def test_student_str_and_ordering(self):
        self.assertEqual(str(self.student), "01 - Rahim Uddin (Class TenA)")

    def test_teacher_str_and_classes(self):
        self.assertEqual(self.teacher.get_class_list(), ["Ten"])
        self.assertIn("Master Rahim (Ten)", str(self.teacher))

    def test_attendance_creation(self):
        today = timezone.now().date()
        att = Attendance.objects.create(
            student=self.student,
            date=today,
            is_present=True,
        )
        self.assertEqual(att.student, self.student)
        self.assertTrue(att.is_present)

    def test_teacher_attendance_creation(self):
        today = timezone.now().date()
        t_att = TeacherAttendance.objects.create(
            teacher=self.teacher,
            date=today,
            is_present=True,
        )
        self.assertEqual(t_att.teacher, self.teacher)
        self.assertTrue(t_att.is_present)


class ExportAndReportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="admin_export",
            password="password123",
        )
        self.client.login(username="admin_export", password="password123")
        self.student = Student.objects.create(
            roll_no="05",
            name="Karim Khan",
            class_name="Nine",
            section="B",
        )

    def test_export_attendance_excel(self):
        today_str = timezone.now().date().isoformat()
        response = self.client.get(reverse('export_attendance'), {'class': 'Nine', 'date': today_str})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment; filename=", response['Content-Disposition'])

    def test_export_teacher_attendance_excel(self):
        response = self.client.get(reverse('export_teacher_attendance'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


class SMSUtilityTests(TestCase):
    def test_sms_message_builder(self):
        msg = build_absent_message("Rahim", "01-Jan-26")
        self.assertIn("Rahim", msg)
        self.assertIn("ABSENT", msg)

    @patch('attendance.sms_utils.requests.get')
    def test_send_sms_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "Success: SMS queued"

        with self.settings(SMS_TOKEN="test_dummy_token"):
            success, text = send_sms("01700000000", "Test message")
            self.assertTrue(success)
            self.assertIn("Success", text)

    @patch('attendance.sms_utils.requests.get')
    def test_send_sms_network_error_does_not_leak_token(self, mock_get):
        # Simulate RequestException containing sensitive token in error
        mock_get.side_effect = requests.RequestException("Connection error with url: /api.php?token=secret123")

        with self.settings(SMS_TOKEN="secret123"):
            success, text = send_sms("01700000000", "Test message")
            self.assertFalse(success)
            # Ensure the sensitive token is NEVER leaked in the returned error message
            self.assertNotIn("secret123", text)
            self.assertIn("network connection error", text.lower())

    def test_send_sms_without_token(self):
        with self.settings(SMS_TOKEN=""):
            success, text = send_sms("01700000000", "Test message")
            self.assertFalse(success)
            self.assertIn("not configured", text)
