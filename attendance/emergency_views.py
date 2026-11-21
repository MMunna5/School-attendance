import logging

from django.conf import settings

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import EmergencySmsLog, Student, Teacher
from .sms_utils import append_school_name, send_sms, sms_segment_count

logger = logging.getLogger(__name__)


def _is_admin(user):
    return user.is_staff


@login_required
@user_passes_test(_is_admin)
def emergency_sms(request):
    """Send an administrator-authored notice to all students, one class, or selected students."""
    classes = list(
        Student.objects.exclude(class_name="")
        .values_list("class_name", flat=True)
        .distinct()
        .order_by("class_name")
    )
    students = Student.objects.order_by("class_name", "section", "roll_no")
    selected_class = request.POST.get("class_name", "") if request.method == "POST" else request.GET.get("class_name", "")
    target_type = request.POST.get("target_type", "all") if request.method == "POST" else request.GET.get("target_type", "all")
    selected_student_ids = request.POST.getlist("student_ids") if request.method == "POST" else []

    if request.method == "POST":
        message_text = request.POST.get("message", "").strip()
        if target_type not in {"all", "class", "student", "teachers", "all_with_teachers"}:
            messages.error(request, "Please choose a valid recipient group.")
        elif not message_text:
            messages.error(request, "Please write a notice before sending.")
        elif len(message_text) > 1000:
            messages.error(request, "Notice must be 1000 characters or fewer.")
        else:
            student_recipients = Student.objects.all()
            teacher_recipients = Teacher.objects.all()

            if target_type == "class":
                if selected_class not in classes:
                    messages.error(request, "Please choose a valid class.")
                    return render(request, "attendance/emergency_sms.html", {
                        "classes": classes, "students": students, "school_full_name": getattr(settings, "SCHOOL_FULL_NAME", "School"), "selected_class": selected_class,
                        "target_type": target_type, "selected_student_ids": selected_student_ids,
                        "message_text": message_text,
                    })
                student_recipients = student_recipients.filter(class_name=selected_class)
                teacher_recipients = Teacher.objects.none()
            elif target_type == "student":
                valid_ids = []
                for value in selected_student_ids:
                    try:
                        valid_ids.append(int(value))
                    except (TypeError, ValueError):
                        continue
                student_recipients = student_recipients.filter(pk__in=set(valid_ids))
                teacher_recipients = Teacher.objects.none()
                if not valid_ids or not student_recipients.exists():
                    messages.error(request, "Please search for and select at least one valid student.")
                    return render(request, "attendance/emergency_sms.html", {
                        "classes": classes, "students": students, "school_full_name": getattr(settings, "SCHOOL_FULL_NAME", "School"), "selected_class": selected_class,
                        "target_type": target_type, "selected_student_ids": selected_student_ids,
                        "message_text": message_text,
                    })
            elif target_type == "teachers":
                student_recipients = Student.objects.none()
            # all_with_teachers intentionally keeps both recipient querysets.

            # Students receive the notice on their parent mobile; teachers receive it on their own mobile.
            recipients = (
                [(student.parent_mobile, "student", student.pk) for student in student_recipients]
                + [(teacher.mobile, "teacher", teacher.pk) for teacher in teacher_recipients]
            )
            with_phone = [(number, kind, recipient_id) for number, kind, recipient_id in recipients if number]
            missing_phone = len(recipients) - len(with_phone)
            full_message = append_school_name(message_text, short_if_over_159=False)
            sent = 0
            failed = 0
            billed_segments = 0
            segments_per_message = sms_segment_count(full_message)
            for number, kind, recipient_id in with_phone:
                billing_log = None
                try:
                    # Record the exact billable units before sending; never send an untracked SMS.
                    billing_log = EmergencySmsLog.objects.create(
                        sms_segments=segments_per_message,
                        sent_at=timezone.now(),
                    )
                    success, _detail = send_sms(number, full_message)
                    if success:
                        sent += 1
                        billed_segments += segments_per_message
                    else:
                        billing_log.delete()
                        failed += 1
                except Exception:
                    if billing_log is not None:
                        billing_log.delete()
                    failed += 1
                    logger.exception("Emergency SMS failed or billing log could not be saved for %s id=%s", kind, recipient_id)
            messages.success(
                request,
                f"Emergency SMS finished: {sent} sent, {failed} failed, "
                f"{missing_phone} skipped (no mobile number), {len(recipients)} recipient(s) targeted."
            )
            messages.info(request, str(billed_segments), extra_tags="billable-segments")
            return redirect("emergency_sms")

    return render(request, "attendance/emergency_sms.html", {
        "classes": classes,
        "students": students,
        "school_full_name": getattr(settings, "SCHOOL_FULL_NAME", "School"),
        "selected_class": selected_class,
        "target_type": target_type if target_type in {"all", "class", "student", "teachers", "all_with_teachers"} else "all",
        "selected_student_ids": selected_student_ids,
        "message_text": "",
    })
