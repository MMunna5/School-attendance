from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Student


class EmergencySmsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("emergency_admin", password="password123")
        self.teacher = User.objects.create_user("emergency_teacher", password="password123")
        self.client.force_login(self.admin)
        self.student_one = Student.objects.create(
            roll_no="1", name="Student One", class_name="Eight", section="A",
            parent_mobile="01700000001",
        )
        self.student_two = Student.objects.create(
            roll_no="2", name="Student Two", class_name="Nine", section="B",
            parent_mobile="01700000002",
        )

    def test_admin_can_open_emergency_sms_page(self):
        response = self.client.get(reverse("emergency_sms"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Emergency SMS")
        self.assertContains(response, "All students / all classes")

    def test_teacher_cannot_access_emergency_sms(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("emergency_sms"))
        self.assertEqual(response.status_code, 302)

    @override_settings(SCHOOL_SHORT_NAME="School")
    @patch("attendance.emergency_views.send_sms")
    def test_admin_can_send_notice_to_one_class(self, mock_send_sms):
        mock_send_sms.return_value = (True, "SMS sent")
        response = self.client.post(reverse("emergency_sms"), {
            "target_type": "class", "class_name": "Eight", "message": "School closes early today.",
        })
        self.assertRedirects(response, reverse("emergency_sms"))
        mock_send_sms.assert_called_once_with("01700000001", "School closes early today.\nSchool")

    @override_settings(SCHOOL_SHORT_NAME="School")
    @patch("attendance.emergency_views.send_sms")
    def test_admin_can_send_notice_to_one_student(self, mock_send_sms):
        mock_send_sms.return_value = (True, "SMS sent")
        self.client.post(reverse("emergency_sms"), {
            "target_type": "student", "student_id": str(self.student_two.pk), "message": "Please call school.",
        })
        mock_send_sms.assert_called_once_with("01700000002", "Please call school.\nSchool")
