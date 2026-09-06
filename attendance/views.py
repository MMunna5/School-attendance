from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count
import time
from django.conf import settings
from .models import AbsenceSms, TeacherAbsenceSms, Teacher, Student, Attendance, TeacherAttendance
from django.urls import reverse
from .sms_utils import build_absent_message, build_teacher_absent_message, send_sms
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

# Expected Excel column headers (in order) for the two bulk-upload forms.
# These must exactly match (case/whitespace-insensitive) the header row
# shown to the admin in student_upload.html / teacher_upload.html.
STUDENT_EXCEL_HEADERS = ["Roll", "Name", "Class", "Section", "Session", "Phone"]
TEACHER_EXCEL_HEADERS = ["Name", "Number", "Class"]

def send_absent_sms(people, message_builder, date_str, number_getter, message_kwargs_getter=None):
    """Send absence alerts sequentially with one retry to avoid rate-limit failures."""
    people_with_numbers = [person for person in people if number_getter(person)]
    people_without_numbers = [f"{person.name} (no phone)" for person in people if not number_getter(person)]

    if not people_with_numbers:
        return 0, people_without_numbers

    results = []
    for index, person in enumerate(people_with_numbers):
        success = False
        try:
            message_kwargs = message_kwargs_getter(person) if message_kwargs_getter else {}
            message = message_builder(person.name, date_str, **message_kwargs)
            for attempt in range(2):
                success, _ = send_sms(number_getter(person), message)
                if success or attempt == 1:
                    break
                time.sleep(1)
        except Exception:
            success = False
        results.append(person.name if success else None)
        if index < len(people_with_numbers) - 1:
            time.sleep(1)

    sent_count = sum(1 for result in results if result)
    failed = people_without_numbers + [
        person.name for person, result in zip(people_with_numbers, results) if not result
    ]
    return sent_count, failed

def is_admin(user):
    return user.is_staff

def check_header(header_row, expected_headers):
    """
    Compares the first row of an uploaded Excel file against the expected
    column headers (case/whitespace-insensitive, order matters).
    Returns None if it matches, otherwise a human-readable error message.
    """
    cells = list(header_row) if header_row else []
    actual = []
    for i in range(len(expected_headers)):
        cell = cells[i] if i < len(cells) else None
        actual.append(str(cell).strip().lower() if cell is not None else "")
    expected = [h.strip().lower() for h in expected_headers]

    if actual != expected:
        expected_display = ", ".join(expected_headers)
        return (
            f"Header row is not in the correct format. The first row must have "
            f"these exact columns, in this order: {expected_display}. "
            f"Please fix the header and upload again."
        )
    return None

def get_class_choices():
    import re

    names = set()
    for c in Student.objects.values_list('class_name', flat=True):
        if c is None:
            continue
        cleaned = str(c).strip()
        if cleaned:
            names.add(cleaned)

    def sort_key(name):
        s = str(name).strip()
        low = s.lower()

        if low.startswith(('play', 'nursery', 'kg', 'pre')):
            group = 0
        elif any(ch.isdigit() for ch in s):
            group = 1
        else:
            group = 2

        m = re.search(r'(\d+)', s)
        num = int(m.group(1)) if m else 0
        return (group, num, low)

    return sorted(names, key=sort_key)

def get_section_choices():
    return list(
        Student.objects.exclude(section='').values_list('section', flat=True).distinct().order_by('section')
    )

def build_choice_options(values, selected_value):
    return [{'value': v, 'is_selected': (str(v) == str(selected_value))} for v in values]

def build_choice_options_multi(values, selected_values):
    selected_set = {str(v) for v in selected_values}
    return [{'value': v, 'is_selected': (str(v) in selected_set)} for v in values]

def get_report_date(value):
    """Return a valid report date, falling back to today for malformed input."""
    parsed = parse_date((value or '').strip())
    return parsed or timezone.now().date()

def get_class_attendance_statuses(class_names, date):
    student_counts = {
        row['class_name']: row['total']
        for row in Student.objects.filter(class_name__in=class_names)
        .values('class_name')
        .annotate(total=Count('id'))
    }
    attendance_counts = {
        row['student__class_name']: row['total']
        for row in Attendance.objects.filter(
            student__class_name__in=class_names,
            date=date,
        )
        .values('student__class_name')
        .annotate(total=Count('student_id'))
    }
    return [
        {
            'name': class_name,
            'student_count': student_counts.get(class_name, 0),
            'attendance_count': attendance_counts.get(class_name, 0),
            'is_complete': (
                student_counts.get(class_name, 0) > 0
                and attendance_counts.get(class_name, 0) == student_counts.get(class_name, 0)
            ),
        }
        for class_name in class_names
    ]

@login_required
def dashboard(request):
    teacher = Teacher.objects.filter(user=request.user).first()
    total_students = 0
    present_count = 0
    absent_count = 0
    today = timezone.now().date()
    teacher_classes = []

    if teacher:
        teacher_classes = teacher.get_class_list()
        students = Student.objects.filter(class_name__in=teacher_classes)
        total_students = students.count()
        attendance_today = Attendance.objects.filter(
            student__class_name__in=teacher_classes,
            date=today
        )
        present_count = attendance_today.filter(is_present=True).count()
        absent_count = attendance_today.filter(is_present=False).count()

    if request.user.is_staff:
        all_today = Attendance.objects.filter(date=today)
        admin_present = all_today.filter(is_present=True).count()
        admin_absent = all_today.filter(is_present=False).count()
        admin_total = Student.objects.count()
    else:
        admin_present = admin_absent = admin_total = 0

    return render(request, 'attendance/dashboard.html', {
        'teacher': teacher,
        'teacher_classes': teacher_classes,
        'total_students': total_students,
        'present_count': present_count,
        'absent_count': absent_count,
        'today': today,
        'admin_present': admin_present,
        'admin_absent': admin_absent,
        'admin_total': admin_total,
    })

@login_required
def change_password(request):
    error = None
    success = False

    if request.method == 'POST':
        old_password = request.POST.get('old_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not request.user.check_password(old_password):
            error = "Current password is incorrect."
        elif len(new_password) < 4:
            error = "New password must be at least 4 characters."
        elif new_password != confirm_password:
            error = "New passwords do not match."
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            success = True

    return render(request, 'attendance/change_password.html', {'error': error, 'success': success})

@login_required
def mark_attendance(request):
    teacher = Teacher.objects.filter(user=request.user).first()
    is_admin_user = request.user.is_staff
    selected_class = request.GET.get('class', '').strip()

    if not is_admin_user and not teacher:
        return render(request, 'attendance/mark_attendance.html', {
            'error': 'Your account is not linked to any teacher. Ask admin to link it.',
            'is_admin_user': False,
            'today': timezone.now().date(),
        })

    if is_admin_user:
        class_choices = get_class_choices()
    else:
        class_choices = teacher.get_class_list()
        if not class_choices:
            return render(request, 'attendance/mark_attendance.html', {
                'error': 'No class has been assigned to you yet. Please ask the admin to assign one.',
                'is_admin_user': False,
                'today': timezone.now().date(),
            })

    show_class_selector = is_admin_user or len(class_choices) > 1

    if not is_admin_user and len(class_choices) == 1:
        current_class = class_choices[0]
    elif selected_class in class_choices:
        current_class = selected_class
    else:
        current_class = None

    all_classes = [{'name': c, 'is_selected': (c == current_class)} for c in class_choices]

    def load_students(class_name):
        if is_admin_user:
            return Student.objects.filter(class_name=class_name).order_by('section', 'roll_no')
        return Student.objects.filter(class_name=class_name).order_by('roll_no')

    students = load_students(current_class) if current_class else Student.objects.none()

    today = timezone.now().date()
    already_marked = False
    if current_class:
        already_marked = Attendance.objects.filter(
            student__class_name=current_class, date=today
        ).exists()

    saved = False
    sms_queued_count = 0
    sms_warning = None

    if request.method == 'POST' and current_class:
        post_class = request.POST.get('class', '').strip()
        if post_class and post_class in class_choices and post_class != current_class:
            current_class = post_class
            students = load_students(current_class)
            all_classes = [{'name': c, 'is_selected': (c == current_class)} for c in class_choices]
            already_marked = Attendance.objects.filter(
                student__class_name=current_class, date=today
            ).exists()

        # Teacher: only once. Admin: always can edit (superpower)
        can_submit = is_admin_user or not already_marked

        if can_submit:
            absent_students = []
            existing = {
                a.student_id: a
                for a in Attendance.objects.filter(
                    student__class_name=current_class, date=today
                )
            }

            to_create = []
            to_update = []

            for student in students:
                status = request.POST.get(f'att_{student.id}', 'present')
                is_present = status == 'present'

                if student.id in existing:
                    att = existing[student.id]
                    if att.is_present != is_present:
                        att.is_present = is_present
                        to_update.append(att)
                else:
                    to_create.append(Attendance(
                        student=student,
                        date=today,
                        is_present=is_present
                    ))

                if not is_present:
                    absent_students.append(student)

            if to_create:
                Attendance.objects.bulk_create(to_create, ignore_conflicts=True)
            if to_update:
                Attendance.objects.bulk_update(to_update, ['is_present'])

            attendance_count = Attendance.objects.filter(
                student__class_name=current_class,
                date=today,
            ).count()
            class_student_count = Student.objects.filter(class_name=current_class).count()

            if class_student_count and attendance_count == class_student_count:
                existing_sms = set(
                    AbsenceSms.objects.filter(
                        student__in=absent_students, date=today
                    ).values_list('student_id', flat=True)
                )
                new_sms = [
                    AbsenceSms(student=s, date=today)
                    for s in absent_students if s.id not in existing_sms
                ]
                if new_sms:
                    queued = AbsenceSms.objects.bulk_create(new_sms, ignore_conflicts=True)
                    sms_queued_count = len(queued)

                saved = True
                already_marked = True
            else:
                saved = True
                already_marked = True
                sms_warning = (
                    f"Attendance saved, but SMS was not queued because only "
                    f"{attendance_count} of {class_student_count} students were marked. "
                    f"Please mark the remaining students."
                )
        else:
            sms_warning = "Attendance already marked for today. Only admin can edit."

    # Build attendance status for template
    attendance_map = {}
    if current_class and already_marked:
        for att in Attendance.objects.filter(student__class_name=current_class, date=today):
            attendance_map[att.student_id] = att.is_present

    present_count = sum(1 for v in attendance_map.values() if v) if attendance_map else 0
    absent_count = sum(1 for v in attendance_map.values() if not v) if attendance_map else 0

    return render(request, 'attendance/mark_attendance.html', {
        'students': students,
        'current_class': current_class,
        'all_classes': all_classes,
        'show_class_selector': show_class_selector,
        'is_admin_user': is_admin_user,
        'today': today,
        'already_marked': already_marked,
        'saved': saved,
        'sms_queued_count': sms_queued_count,
        'sms_warning': sms_warning,
        'attendance_map': attendance_map,
        'present_count': present_count,
        'absent_count': absent_count,
        'total_students': students.count() if hasattr(students, 'count') else len(students),
    })

@login_required
@user_passes_test(is_admin)
def student_list(request):
    query = request.GET.get('q', '').strip()
    class_filter = request.GET.get('class', '').strip()
    section_filter = request.GET.get('section', '').strip()

    students = Student.objects.all().order_by('class_name', 'section', 'roll_no')

    if query:
        students = students.filter(name__icontains=query) | students.filter(roll_no__icontains=query)
    if class_filter:
        students = students.filter(class_name=class_filter)
    if section_filter:
        students = students.filter(section=section_filter)

    paginator = Paginator(students, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    class_choices = get_class_choices()
    section_choices = get_section_choices()

    return render(request, 'attendance/student_list.html', {
        'page_obj': page_obj,
        'query': query,
        'class_filter': class_filter,
        'section_filter': section_filter,
        'class_choices': build_choice_options(class_choices, class_filter),
        'section_choices': build_choice_options(section_choices, section_filter),
        'total_students': paginator.count,
    })

@login_required
@user_passes_test(is_admin)
def student_add(request):
    error = None
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        roll_no = request.POST.get('roll_no', '').strip()
        class_name = request.POST.get('class_name', '').strip()
        section = request.POST.get('section', '').strip()
        session = request.POST.get('session', '').strip()
        phone = request.POST.get('phone', '').strip()

        if not name or not roll_no or not class_name:
            error = "Name, Roll and Class are required."
        else:
            try:
                Student.objects.create(
                    name=name,
                    roll_no=roll_no,
                    class_name=class_name,
                    section=section,
                    session=session,
                    phone=phone,
                )
                return redirect('student_list')
            except IntegrityError:
                error = "A student with this Roll + Class + Section already exists."

    return render(request, 'attendance/student_form.html', {
        'error': error,
        'student': None,
        'title': 'Add Student',
    })

@login_required
@user_passes_test(is_admin)
def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    error = None

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        roll_no = request.POST.get('roll_no', '').strip()
        class_name = request.POST.get('class_name', '').strip()
        section = request.POST.get('section', '').strip()
        session = request.POST.get('session', '').strip()
        phone = request.POST.get('phone', '').strip()

        if not name or not roll_no or not class_name:
            error = "Name, Roll and Class are required."
        else:
            student.name = name
            student.roll_no = roll_no
            student.class_name = class_name
            student.section = section
            student.session = session
            student.phone = phone
            try:
                student.save()
                return redirect('student_list')
            except IntegrityError:
                error = "A student with this Roll + Class + Section already exists."

    return render(request, 'attendance/student_form.html', {
        'error': error,
        'student': student,
        'title': 'Edit Student',
    })

@login_required
@user_passes_test(is_admin)
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.delete()
        return redirect('student_list')
    return render(request, 'attendance/student_confirm_delete.html', {'student': student})

@login_required
@user_passes_test(is_admin)
def student_upload(request):
    file_results = None
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return render(request, 'attendance/student_upload.html', {
                    'file_results': {'error': 'Empty file.'}
                })

            header_error = check_header(rows[0], STUDENT_EXCEL_HEADERS)
            if header_error:
                return render(request, 'attendance/student_upload.html', {
                    'file_results': {'error': header_error}
                })

            created = 0
            updated = 0
            skipped = 0
            errors = []

            for i, row in enumerate(rows[1:], start=2):
                if not row or all(cell is None or str(cell).strip() == '' for cell in row):
                    continue
                try:
                    roll = str(row[0]).strip() if row[0] is not None else ''
                    name = str(row[1]).strip() if row[1] is not None else ''
                    class_name = str(row[2]).strip() if row[2] is not None else ''
                    section = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ''
                    session = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ''
                    phone = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ''

                    if not roll or not name or not class_name:
                        skipped += 1
                        errors.append(f"Row {i}: Missing required fields.")
                        continue

                    obj, was_created = Student.objects.update_or_create(
                        roll_no=roll,
                        class_name=class_name,
                        section=section,
                        defaults={
                            'name': name,
                            'session': session,
                            'phone': phone,
                        }
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                except Exception as e:
                    skipped += 1
                    errors.append(f"Row {i}: {str(e)}")

            file_results = {
                'created': created,
                'updated': updated,
                'skipped': skipped,
                'errors': errors[:20],
            }
        except Exception as e:
            file_results = {'error': str(e)}

    return render(request, 'attendance/student_upload.html', {'file_results': file_results})

@login_required
@user_passes_test(is_admin)
def teacher_list(request):
    full_time = Teacher.objects.select_related('user').filter(
        employment_type=Teacher.EMPLOYMENT_FULL
    ).order_by('id')

    part_time = Teacher.objects.select_related('user').filter(
        employment_type=Teacher.EMPLOYMENT_PART
    ).order_by('id')

    return render(request, 'attendance/teacher_list.html', {
        'full_time_teachers': full_time,
        'part_time_teachers': part_time,
        'full_time_count': full_time.count(),
        'part_time_count': part_time.count(),
    })

@login_required
@user_passes_test(is_admin)
def teacher_add(request):
    error = None
    employment_type = request.GET.get('type', '') or request.POST.get('employment_type', Teacher.EMPLOYMENT_FULL)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        classes = request.POST.get('classes', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        employment_type = request.POST.get('employment_type', Teacher.EMPLOYMENT_FULL)

        if not name:
            error = "Name is required."
        elif employment_type == Teacher.EMPLOYMENT_FULL and (not username or not password):
            error = "Username and password are required for full-time teachers."
        else:
            try:
                with transaction.atomic():
                    user = None
                    if employment_type == Teacher.EMPLOYMENT_FULL:
                        if User.objects.filter(username=username).exists():
                            error = "Username already exists."
                        else:
                            user = User.objects.create_user(username=username, password=password)
                    if not error:
                        Teacher.objects.create(
                            name=name,
                            phone=phone,
                            classes=classes,
                            user=user,
                            employment_type=employment_type,
                        )
                        return redirect('teacher_list')
            except Exception as e:
                error = str(e)

    return render(request, 'attendance/teacher_form.html', {
        'error': error,
        'teacher': None,
        'title': 'Add Teacher',
        'employment_type': employment_type,
    })

@login_required
@user_passes_test(is_admin)
def teacher_edit(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    error = None

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        classes = request.POST.get('classes', '').strip()
        employment_type = request.POST.get('employment_type', teacher.employment_type)
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not name:
            error = "Name is required."
        else:
            try:
                with transaction.atomic():
                    teacher.name = name
                    teacher.phone = phone
                    teacher.classes = classes
                    teacher.employment_type = employment_type

                    if employment_type == Teacher.EMPLOYMENT_FULL:
                        if teacher.user:
                            if username and username != teacher.user.username:
                                if User.objects.filter(username=username).exists():
                                    error = "Username already exists."
                                else:
                                    teacher.user.username = username
                                    teacher.user.save()
                            if password:
                                teacher.user.set_password(password)
                                teacher.user.save()
                        else:
                            if not username or not password:
                                error = "Username and password required for full-time teacher."
                            elif User.objects.filter(username=username).exists():
                                error = "Username already exists."
                            else:
                                user = User.objects.create_user(username=username, password=password)
                                teacher.user = user
                    else:
                        # part-time: optionally remove linked user
                        if teacher.user and request.POST.get('remove_user') == 'on':
                            linked = teacher.user
                            teacher.user = None
                            teacher.save()
                            linked.delete()
                        else:
                            teacher.save()

                    if not error:
                        teacher.save()
                        return redirect('teacher_list')
            except Exception as e:
                error = str(e)

    return render(request, 'attendance/teacher_form.html', {
        'error': error,
        'teacher': teacher,
        'title': 'Edit Teacher',
        'employment_type': teacher.employment_type,
    })

@login_required
@user_passes_test(is_admin)
def teacher_delete(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        linked_user = teacher.user
        teacher.delete()
        if linked_user:
            linked_user.delete()
        return redirect('teacher_list')
    return render(request, 'attendance/teacher_confirm_delete.html', {'teacher': teacher})

@login_required
@user_passes_test(is_admin)
def mark_teacher_attendance(request):
    today = timezone.now().date()
    full_time = list(Teacher.objects.filter(employment_type=Teacher.EMPLOYMENT_FULL).order_by('name'))
    part_time = list(Teacher.objects.filter(employment_type=Teacher.EMPLOYMENT_PART).order_by('name'))

    already_marked = TeacherAttendance.objects.filter(date=today).exists()

    saved = False
    sms_queued_count = 0

    if request.method == 'POST':
        existing = {
            ta.teacher_id: ta
            for ta in TeacherAttendance.objects.filter(date=today)
        }
        to_create = []
        to_update = []
        absent_teachers = []

        for teacher in full_time + part_time:
            status = request.POST.get(f'att_{teacher.id}', 'present')
            is_present = status == 'present'

            if teacher.id in existing:
                ta = existing[teacher.id]
                if ta.is_present != is_present:
                    ta.is_present = is_present
                    to_update.append(ta)
            else:
                to_create.append(TeacherAttendance(
                    teacher=teacher,
                    date=today,
                    is_present=is_present,
                ))

            if not is_present:
                absent_teachers.append(teacher)

        if to_create:
            TeacherAttendance.objects.bulk_create(to_create, ignore_conflicts=True)
        if to_update:
            TeacherAttendance.objects.bulk_update(to_update, ['is_present'])

        # Queue SMS for new absences
        existing_sms = set(
            TeacherAbsenceSms.objects.filter(
                teacher__in=absent_teachers, date=today
            ).values_list('teacher_id', flat=True)
        )
        new_sms = [
            TeacherAbsenceSms(teacher=t, date=today)
            for t in absent_teachers if t.id not in existing_sms
        ]
        if new_sms:
            queued = TeacherAbsenceSms.objects.bulk_create(new_sms, ignore_conflicts=True)
            sms_queued_count = len(queued)

        saved = True
        already_marked = True

    # Build rows for template
    attendance_map = {
        ta.teacher_id: ta.is_present
        for ta in TeacherAttendance.objects.filter(date=today)
    }

    def build_rows(teachers):
        rows = []
        for t in teachers:
            rows.append({
                'teacher': t,
                'is_present': attendance_map.get(t.id, True),
            })
        return rows

    full_time_rows = build_rows(full_time)
    part_time_rows = build_rows(part_time)

    full_already_marked = any(t.id in attendance_map for t in full_time)
    part_already_marked = any(t.id in attendance_map for t in part_time)

    full_present = sum(1 for r in full_time_rows if r['is_present']) if full_already_marked else 0
    full_absent = len(full_time_rows) - full_present if full_already_marked else 0
    part_present = sum(1 for r in part_time_rows if r['is_present']) if part_already_marked else 0
    part_absent = len(part_time_rows) - part_present if part_already_marked else 0

    return render(request, 'attendance/mark_teacher_attendance.html', {
        'today': today,
        'full_time_rows': full_time_rows,
        'part_time_rows': part_time_rows,
        'already_marked': already_marked,
        'saved': saved,
        'sms_queued_count': sms_queued_count,
        'full_present': full_present,
        'full_absent': full_absent,
        'part_present': part_present,
        'part_absent': part_absent,
        'full_total': len(full_time_rows),
        'part_total': len(part_time_rows),
    })

@login_required
@user_passes_test(is_admin)
def teacher_upload(request):
    file_results = None
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return render(request, 'attendance/teacher_upload.html', {
                    'file_results': {'error': 'Empty file.'}
                })

            header_error = check_header(rows[0], TEACHER_EXCEL_HEADERS)
            if header_error:
                return render(request, 'attendance/teacher_upload.html', {
                    'file_results': {'error': header_error}
                })

            created = 0
            skipped = 0
            errors = []

            for i, row in enumerate(rows[1:], start=2):
                if not row or all(cell is None or str(cell).strip() == '' for cell in row):
                    continue
                try:
                    name = str(row[0]).strip() if row[0] is not None else ''
                    phone = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''
                    classes = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ''

                    if not name:
                        skipped += 1
                        errors.append(f"Row {i}: Name is required.")
                        continue

                    Teacher.objects.create(
                        name=name,
                        phone=phone,
                        classes=classes,
                        employment_type=Teacher.EMPLOYMENT_PART,
                    )
                    created += 1
                except Exception as e:
                    skipped += 1
                    errors.append(f"Row {i}: {str(e)}")

            file_results = {
                'created': created,
                'skipped': skipped,
                'errors': errors[:20],
            }
        except Exception as e:
            file_results = {'error': str(e)}

    return render(request, 'attendance/teacher_upload.html', {'file_results': file_results})

@login_required
def attendance_report(request):
    teacher = Teacher.objects.filter(user=request.user).first()
    is_admin_user = request.user.is_staff

    if not is_admin_user and not teacher:
        return render(request, 'attendance/attendance_report.html', {
            'error': 'Your account is not linked to any teacher.',
        })

    if is_admin_user:
        class_choices = get_class_choices()
    else:
        class_choices = teacher.get_class_list()

    selected_class = request.GET.get('class', '').strip()
    selected_date = request.GET.get('date', '').strip()
    report_date = get_report_date(selected_date)

    if selected_class and selected_class in class_choices:
        current_class = selected_class
    elif class_choices:
        current_class = class_choices[0]
    else:
        current_class = None

    students = []
    present_count = 0
    absent_count = 0
    attendance_list = []

    if current_class:
        students = Student.objects.filter(class_name=current_class).order_by('section', 'roll_no')
        att_qs = Attendance.objects.filter(
            student__class_name=current_class,
            date=report_date,
        ).select_related('student')
        att_map = {a.student_id: a.is_present for a in att_qs}

        for s in students:
            is_present = att_map.get(s.id)
            attendance_list.append({
                'student': s,
                'is_present': is_present,
            })
            if is_present is True:
                present_count += 1
            elif is_present is False:
                absent_count += 1

    class_statuses = get_class_attendance_statuses(class_choices, report_date) if is_admin_user else []

    return render(request, 'attendance/attendance_report.html', {
        'is_admin_user': is_admin_user,
        'class_choices': build_choice_options(class_choices, current_class),
        'current_class': current_class,
        'report_date': report_date,
        'attendance_list': attendance_list,
        'present_count': present_count,
        'absent_count': absent_count,
        'total_students': len(students),
        'class_statuses': class_statuses,
    })

@login_required
@user_passes_test(is_admin)
def export_attendance(request):
    selected_class = request.GET.get('class', '').strip()
    selected_date = request.GET.get('date', '').strip()
    report_date = get_report_date(selected_date)

    if not selected_class:
        return redirect('attendance_report')

    students = Student.objects.filter(class_name=selected_class).order_by('section', 'roll_no')
    att_map = {
        a.student_id: a.is_present
        for a in Attendance.objects.filter(
            student__class_name=selected_class,
            date=report_date,
        )
    }

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance"

    headers = ["Roll", "Name", "Section", "Status"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True)

    for i, s in enumerate(students, 2):
        status = "Present" if att_map.get(s.id) is True else ("Absent" if att_map.get(s.id) is False else "Not Marked")
        ws.cell(row=i, column=1, value=s.roll_no)
        ws.cell(row=i, column=2, value=s.name)
        ws.cell(row=i, column=3, value=s.section)
        ws.cell(row=i, column=4, value=status)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"attendance_{selected_class}_{report_date}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response

@login_required
@user_passes_test(is_admin)
def export_teacher_attendance(request):
    selected_date = request.GET.get('date', '').strip()
    report_date = get_report_date(selected_date)

    teachers = Teacher.objects.all().order_by('employment_type', 'name')
    att_map = {
        ta.teacher_id: ta.is_present
        for ta in TeacherAttendance.objects.filter(date=report_date)
    }

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Teacher Attendance"

    headers = ["Name", "Type", "Phone", "Status"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True)

    for i, t in enumerate(teachers, 2):
        status = "Present" if att_map.get(t.id) is True else ("Absent" if att_map.get(t.id) is False else "Not Marked")
        emp = "Full-time" if t.employment_type == Teacher.EMPLOYMENT_FULL else "Part-time"
        ws.cell(row=i, column=1, value=t.name)
        ws.cell(row=i, column=2, value=emp)
        ws.cell(row=i, column=3, value=t.phone or "")
        ws.cell(row=i, column=4, value=status)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"teacher_attendance_{report_date}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response

@login_required
@user_passes_test(is_admin)
def send_pending_sms(request):
    """Manually trigger sending of queued absence SMS (students + teachers)."""
    today = timezone.now().date()
    date_str = today.strftime('%d-%m-%Y')

    # Student SMS
    pending_student = list(
        AbsenceSms.objects.filter(date=today, sent=False).select_related('student')
    )
    students = [ps.student for ps in pending_student]

    def student_number(s):
        return s.phone

    sent_s, failed_s = send_absent_sms(
        students,
        build_absent_message,
        date_str,
        student_number,
    )

    if sent_s:
        AbsenceSms.objects.filter(
            student__in=[s for s in students if s.phone],
            date=today,
            sent=False,
        ).update(sent=True)

    # Teacher SMS
    pending_teacher = list(
        TeacherAbsenceSms.objects.filter(date=today, sent=False).select_related('teacher')
    )
    teachers = [pt.teacher for pt in pending_teacher]

    def teacher_number(t):
        return t.phone

    sent_t, failed_t = send_absent_sms(
        teachers,
        build_teacher_absent_message,
        date_str,
        teacher_number,
    )

    if sent_t:
        TeacherAbsenceSms.objects.filter(
            teacher__in=[t for t in teachers if t.phone],
            date=today,
            sent=False,
        ).update(sent=True)

    return render(request, 'attendance/send_sms_result.html', {
        'sent_students': sent_s,
        'failed_students': failed_s,
        'sent_teachers': sent_t,
        'failed_teachers': failed_t,
        'date': today,
    })

def health(request):
    from django.http import JsonResponse
    return JsonResponse({'status': 'ok'})