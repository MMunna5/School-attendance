import requests
from django.conf import settings


def append_school_name(base_message):
    """
    Uses the short school name (SNHMSC) when it keeps the message within
    one SMS segment (160 chars). If the message is already longer than
    that (multi-part SMS regardless), the fuller school name is used
    instead since there's no length benefit left to protect.
    """
    short_version = f"{base_message}\n{settings.SCHOOL_SHORT_NAME}"
    if len(short_version) <= 160:
        return short_version
    return f"{base_message}\n{settings.SCHOOL_FULL_NAME}"


def build_absent_message(student, date_str):
    base = (
        f"Dear Parents, {student.name}, Class: {student.class_name}, Roll: {student.roll_no} "
        f"was ABSENT on {date_str}. Contact the Authority if this is a mistake."
    )
    return append_school_name(base)


def build_teacher_absent_message(teacher_name, date_str):
    base = (
        f"Dear {teacher_name},\n"
        f"You have been marked ABSENT today on {date_str}. "
        f"Please contact the Authority if this is a mistake."
    )
    return append_school_name(base)


def send_sms(number, message):
    url = "https://api.bdbulksms.net/api.php"
    params = {
        "token": settings.SMS_TOKEN,
        "to": number,
        "message": message,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        return "success" in response.text.lower() or response.status_code == 200, response.text
    except requests.RequestException as e:
        return False, str(e)