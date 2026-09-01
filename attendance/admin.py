from django.contrib import admin
from .models import Student, Teacher, Attendance, TeacherAttendance

admin.site.register(Student)
admin.site.register(Teacher)
admin.site.register(Attendance)
admin.site.register(TeacherAttendance)