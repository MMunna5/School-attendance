from django.db import models
from django.contrib.auth.models import User


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15, blank=True)
    # Comma-separated list of class names, e.g. "9,10,Play" — a teacher can
    # now be assigned to more than one class. Use get_class_list() to read it.
    assigned_classes = models.CharField(max_length=255, blank=True, default="")

    def get_class_list(self):
        """Returns this teacher's assigned classes as a clean, de-duplicated list."""
        if not self.assigned_classes:
            return []
        seen = []
        for part in self.assigned_classes.split(','):
            cleaned = part.strip()
            if cleaned and cleaned not in seen:
                seen.append(cleaned)
        return seen

    def __str__(self):
        classes = ", ".join(self.get_class_list())
        return f"{self.name} ({classes})" if classes else self.name


class Student(models.Model):
    roll_no = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    class_name = models.CharField(max_length=20)
    section = models.CharField(max_length=10, blank=True, default="")
    parent_mobile = models.CharField(max_length=15, blank=True, default="")

    class Meta:
        unique_together = ('class_name', 'section', 'roll_no')
        ordering = ['class_name', 'section', 'roll_no']

    def __str__(self):
        return f"{self.roll_no} - {self.name} (Class {self.class_name}{self.section})"


class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField()
    is_present = models.BooleanField(default=True)

    class Meta:
        unique_together = ('student', 'date')
        ordering = ['-date']

    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.student} - {self.date} - {status}"


class TeacherAttendance(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    date = models.DateField()
    is_present = models.BooleanField(default=True)

    class Meta:
        unique_together = ('teacher', 'date')
        ordering = ['-date']

    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.teacher.name} - {self.date} - {status}"