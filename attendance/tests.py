from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import requests

from .models import Teacher, Student, Attendance, TeacherAttendance
from .sms_utils import send_sms, append_school_name, build_absent_message, normalize_sms_number


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

    def test_class_is_locked_after_partial_attendance(self):
        Attendance.objects.create(
            student=self.student,
            date=timezone.now().date(),
            is_present=True,
        )
        new_student = Student.objects.create(
            roll_no="02",
            name="Amina Rahman",
            class_name="Ten",
            section="A",
            parent_mobile="01800000001",
        )
        client = Client()
        client.login(username="t_rahim", password="password123")

        response = client.get(reverse('attendance_page'))
        self.assertTrue(response.context['already_marked'])
        self.assertContains(response, "Attendance for this class has already been taken today.")
        self.assertFalse(Attendance.objects.filter(student=new_student, date=timezone.now().date()).exists())

    @patch('attendance.views.send_sms')
    def test_same_day_resubmission_does_not_send_duplicate_sms(self, mock_send_sms):
        mock_send_sms.return_value = (True, "Ok: SMS Sent Successfully")
        client = Client()
        client.login(username="t_rahim", password="password123")
        post_data = {f'att_{self.student.id}': 'absent'}

        first_response = client.post(reverse('attendance_page'), post_data)
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(mock_send_sms.call_count, 1)

        second_response = client.post(reverse('attendance_page'), post_data)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(mock_send_sms.call_count, 1)

    def test_previous_day_status_does_not_change_next_day_default_present(self):
        Attendance.objects.create(
            student=self.student,
            date=timezone.now().date() - timedelta(days=1),
            is_present=False,
        )
        client = Client()
        client.login(username="t_rahim", password="password123")

        response = client.get(reverse('attendance_page'))
        self.assertFalse(response.context['already_marked'])
        self.assertEqual(response.context['student_rows'][0]['present_checked'], 'checked')
        self.assertEqual(response.context['student_rows'][0]['absent_checked'], '')


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
        msg = build_absent_message("Rahim", "01-Jan-26", roll_no="01", class_name="Ten")
        self.assertIn("Rahim", msg)
        self.assertIn("Roll: 01", msg)
        self.assertIn("Class: Ten", msg)
        self.assertIn("ABSENT", msg)

    def test_normalize_sms_number(self):
        self.assertEqual(normalize_sms_number("01700000000"), "+8801700000000")
        self.assertEqual(normalize_sms_number("+8801700000000"), "+8801700000000")

    @patch('attendance.sms_utils.requests.get')
    def test_send_sms_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "Success: SMS queued"

        with self.settings(SMS_TOKEN="test_dummy_token"):
            success, text = send_sms("01700000000", "Test message")
            self.assertTrue(success)
            self.assertIn("Success", text)
            self.assertEqual(mock_get.call_args.kwargs["params"]["to"], "+8801700000000")

    @patch('attendance.sms_utils.requests.get')
    def test_send_sms_json_sent_response(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '[{"status": "SENT", "statusmsg": "SMS Sent Successfully"}]'

        with self.settings(SMS_TOKEN="test_dummy_token"):
            success, _ = send_sms("01700000000", "Test message")
            self.assertTrue(success)

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


import io
from openpyxl import Workbook
from django.core.files.uploadedfile import SimpleUploadedFile


class StudentUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="admin_uploader",
            password="password123",
        )
        self.client.login(username="admin_uploader", password="password123")

    def test_student_bulk_upload_create_and_update(self):
        # 1. First upload: create two students
        wb = Workbook()
        ws = wb.active
        ws.append(["Roll", "Name", "Class", "Section", "Session", "Phone"])
        ws.append(["1", "Student One", "8", "A", "2026", "01711111111"])
        ws.append(["2", "Student Two", "8", "A", "2026", "01722222222"])

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)

        uploaded = SimpleUploadedFile(
            "students_class_8.xlsx",
            out.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = self.client.post(
            reverse('student_upload'),
            {'excel_file': [uploaded]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Results")
        self.assertContains(response, "2 added, 0 updated")

        self.assertTrue(Student.objects.filter(class_name="8", section="A", roll_no="1").exists())
        self.assertTrue(Student.objects.filter(class_name="8", section="A", roll_no="2").exists())

        # 2. Second upload: update student 1 name and add student 3
        wb2 = Workbook()
        ws2 = wb2.active
        ws2.append(["Roll", "Name", "Class", "Section", "Session", "Phone"])
        ws2.append(["1", "Student One Updated", "8", "A", "2026", "01711111111"])
        ws2.append(["3", "Student Three", "8", "A", "2026", "01733333333"])

        out2 = io.BytesIO()
        wb2.save(out2)
        out2.seek(0)

        uploaded2 = SimpleUploadedFile(
            "students_class_8_v2.xlsx",
            out2.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response2 = self.client.post(
            reverse('student_upload'),
            {'excel_file': [uploaded2]},
        )
        self.assertEqual(response2.status_code, 200)
        self.assertContains(response2, "1 added, 1 updated")

        s1 = Student.objects.get(class_name="8", section="A", roll_no="1")
        self.assertEqual(s1.name, "Student One Updated")

