import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect, render

from .models import Student
from .sms_utils import append_school_name, send_sms

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
        if target_type not in {"all", "class", "student"}:
            messages.error(request, "Please choose a valid recipient group.")
        elif not message_text:
            messages.error(request, "Please write a notice before sending.")
        elif len(message_text) > 1000:
            messages.error(request, "Notice must be 1000 characters or fewer.")
        else:
            recipients = Student.objects.all()
            if target_type == "class":
                if selected_class not in classes:
                    messages.error(request, "Please choose a valid class.")
                    return render(request, "attendance/emergency_sms.html", {
                        "classes": classes, "students": students, "selected_class": selected_class,
                        "target_type": target_type, "selected_student_ids": selected_student_ids,
                        "message_text": message_text,
                    })
                recipients = recipients.filter(class_name=selected_class)
            elif target_type == "student":
                valid_ids = []
                for value in selected_student_ids:
                    try:
                        valid_ids.append(int(value))
                    except (TypeError, ValueError):
                        continue
                recipients = recipients.filter(pk__in=set(valid_ids))
                if not valid_ids or not recipients.exists():
                    messages.error(request, "Please search for and select at least one valid student.")
                    return render(request, "attendance/emergency_sms.html", {
                        "classes": classes, "students": students, "selected_class": selected_class,
                        "target_type": target_type, "selected_student_ids": selected_student_ids,
                        "message_text": message_text,
                    })

            recipient_list = list(recipients)
            with_phone = [student for student in recipient_list if student.parent_mobile]
            missing_phone = len(recipient_list) - len(with_phone)
            full_message = append_school_name(message_text)
            sent = 0
            failed = 0
            for student in with_phone:
                try:
                    success, _detail = send_sms(student.parent_mobile, full_message)
                    if success:
                        sent += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                    logger.exception("Emergency SMS failed for student id=%s", student.pk)

            messages.success(
                request,
                f"Emergency SMS finished: {sent} sent, {failed} failed, "
                f"{missing_phone} skipped (no parent phone), {len(recipient_list)} student(s) targeted."
            )
            return redirect("emergency_sms")

    return render(request, "attendance/emergency_sms.html", {
        "classes": classes,
        "students": students,
        "selected_class": selected_class,
        "target_type": target_type if target_type in {"all", "class", "student"} else "all",
        "selected_student_ids": selected_student_ids,
        "message_text": "",
    })
