from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('attendance/', views.mark_attendance, name='attendance_page'),
    path('change-password/', views.change_password, name='change_password'),

    path('admin-panel/students/', views.student_list, name='student_list'),
    path('admin-panel/students/add/', views.student_add, name='student_add'),
    path('admin-panel/students/<int:student_id>/edit/', views.student_edit, name='student_edit'),
    path('admin-panel/students/<int:student_id>/delete/', views.student_delete, name='student_delete'),
    path('admin-panel/students/upload/', views.student_upload, name='student_upload'),
    path('admin-panel/students/class/<str:class_name>/delete/', views.class_delete, name='class_delete'),

    path('admin-panel/teachers/', views.teacher_list, name='teacher_list'),
    path('admin-panel/teachers/add/', views.teacher_add, name='teacher_add'),
    path('admin-panel/teachers/<int:teacher_id>/edit/', views.teacher_edit, name='teacher_edit'),
    path('admin-panel/teachers/<int:teacher_id>/delete/', views.teacher_delete, name='teacher_delete'),
    path('admin-panel/teachers/upload/', views.teacher_upload, name='teacher_upload'),

    path('admin-panel/teacher-attendance/', views.mark_teacher_attendance, name='mark_teacher_attendance'),
    path('admin-panel/teacher-attendance-history/', views.teacher_attendance_history, name='teacher_attendance_history'),
    path('admin-panel/teacher-attendance-export/', views.export_teacher_attendance, name='export_teacher_attendance'),

    path('admin-panel/attendance-history/', views.attendance_history, name='attendance_history'),
    path('admin-panel/attendance-export/', views.export_attendance, name='export_attendance'),
    
]