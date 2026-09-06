from django.contrib import admin
from .models import AbsenceSms, Student, Teacher, Attendance, TeacherAbsenceSms, TeacherAttendance

admin.site.register(Student)
admin.site.register(Teacher)
admin.site.register(Attendance)
admin.site.register(TeacherAttendance)
admin.site.register(AbsenceSms)
admin.site.register(TeacherAbsenceSms)