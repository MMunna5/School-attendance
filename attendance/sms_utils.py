import json
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


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
        f"{student_details} was ABSENT on {date_str}. "
        f"Contact Authority if mistake."
    )
    return append_school_name(base)

def build_teacher_absent_message(teacher_name, date_str):
    base = (
        f"Dear {teacher_name},\n"
        f"You have been marked ABSENT today on {date_str}. "
        f"Please contact the Authority if this is a mistake."
    )
    return append_school_name(base)


def clean_phone_for_storage(raw):
    """
    Normalize any human/Excel-entered phone number into the app's canonical
    STORAGE format: an 11-digit Bangladeshi local number starting with 0
    (e.g. "01712345678"). Used everywhere a phone number is saved
    (manual add/edit forms, bulk Excel upload, CLI import) so that
    every number in the database is in one consistent shape before it
    ever reaches the SMS layer.

    Returns "" if the input is empty, or the best-effort cleaned string
    if it doesn't confidently match a BD mobile pattern (so the value is
    never silently dropped -- but see normalize_sms_number() for the
    strict check used right before actually sending an SMS).
    """
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""

    # Excel sometimes turns "01712345678" into the float 1712345678.0
    if s.endswith(".0"):
        s = s[:-2]

    # Strip everything except digits and a leading +
    s = re.sub(r'[^\d+]', '', s)

    # Drop a leading "+" or international "00" prefix so we can inspect
    # the raw digit string uniformly.
    if s.startswith('+'):
        s = s[1:]
    if s.startswith('00'):
        s = s[2:]

    if s.startswith('880') and len(s) == 13:
        # 8801712345678 -> 01712345678
        s = '0' + s[3:]
    elif s.isdigit() and len(s) == 10 and not s.startswith('0'):
        # 1712345678 -> 01712345678
        s = '0' + s

    return s


def normalize_sms_number(number):
    """
    Convert a stored (or raw) phone number into the exact format the SMS
    gateway needs: "+8801XXXXXXXXX". Returns None if the number can't be
    confidently normalized, so callers can skip/flag it instead of
    silently sending to a malformed destination.
    """
    cleaned = clean_phone_for_storage(number)
    if len(cleaned) == 11 and cleaned.startswith('01') and cleaned.isdigit():
        return f"+880{cleaned[1:]}"
    return None


def send_sms(number, message):
    token = getattr(settings, 'SMS_TOKEN', None)
    if not token:
        return False, "SMS token is not configured in environment variables."

    normalized_number = normalize_sms_number(number)
    if not normalized_number:
        logger.warning("SMS not sent: could not normalize phone number %r", number)
        return False, f"Invalid/unrecognized phone number format: {number!r}"

    url = "https://api.bdbulksms.net/api.php"
    params = {
        "token": token,
        "to": normalized_number,
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

        # Always log the raw provider response (success or failure) so it
        # can be cross-checked against the bdbulksms dashboard later.
        logger.info(
            "SMS to %s -> success=%s status=%s response=%s",
            normalized_number, is_success, response.status_code, response_text[:500],
        )
        return is_success, response.text
    except requests.RequestException as exc:
        logger.error("SMS delivery network error for %s: %s", normalized_number, exc)
        # Avoid exposing token or sensitive parameters in error messages
        return False, "SMS delivery failed due to a network connection error."
