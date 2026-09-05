import json

import requests
from django.conf import settings


def append_school_name(base_message):
    """Append the configured short school name to every SMS."""
    short_name = getattr(settings, 'SCHOOL_SHORT_NAME', 'School')
    return f"{base_message}\n{short_name}"


def build_absent_message(student_name, date_str, roll_no=None, class_name=None):
    student_details = student_name
    if roll_no:
        student_details += f" (Roll: {roll_no}"
        if class_name:
            student_details += f", Class: {class_name}"
        student_details += ")"
    elif class_name:
        student_details += f" (Class: {class_name})"
    base = (
        f"Dear Parents,\n"
        f"Your child {student_details} was ABSENT on {date_str}. "
        f"Contact the Authority if this is a mistake."
    )
    return append_school_name(base)


def build_teacher_absent_message(teacher_name, date_str):
    base = (
        f"Dear {teacher_name},\n"
        f"You have been marked ABSENT today on {date_str}. "
        f"Please contact the Authority if this is a mistake."
    )
    return append_school_name(base)


def normalize_sms_number(number):
    normalized = str(number or '').strip().replace(' ', '').replace('-', '')
    if normalized.startswith('00'):
        normalized = f"+{normalized[2:]}"
    elif normalized.startswith('880'):
        normalized = f"+{normalized}"
    elif normalized.startswith('01'):
        normalized = f"+880{normalized[1:]}"
    return normalized


def send_sms(number, message):
    token = getattr(settings, 'SMS_TOKEN', None)
    if not token:
        return False, "SMS token is not configured in environment variables."

    url = "https://api.bdbulksms.net/api.php"
    params = {
        "token": token,
        "to": normalize_sms_number(number),
        "message": message,
        "json": "",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response_text = response.text.strip()
        is_success = False
        try:
            payload = json.loads(response_text)
            results = payload if isinstance(payload, list) else [payload]
            is_success = response.status_code == 200 and any(
                str(result.get("status", "")).upper() == "SENT"
                for result in results
                if isinstance(result, dict)
            )
        except (json.JSONDecodeError, TypeError, AttributeError):
            response_lower = response_text.lower()
            is_success = response.status_code == 200 and (
                "ok:" in response_lower or "success" in response_lower
            )
        return is_success, response.text
    except requests.RequestException:
        # Avoid exposing token or sensitive parameters in error messages
        return False, "SMS delivery failed due to a network connection error."