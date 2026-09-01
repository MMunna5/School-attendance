from django.contrib import admin
from .models import Student, Teacher, Attendance

admin.site.register(Student)
admin.site.register(Teacher)
admin.site.register(Attendance)