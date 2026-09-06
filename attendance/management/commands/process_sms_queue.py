import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from attendance.models import AbsenceSms
from attendance.sms_utils import build_absent_message, send_sms


class Command(BaseCommand):
    help = 'Deliver queued student absence SMS messages in the background.'

    poll_seconds = 5
    retry_minutes = 5
    claim_minutes = 10
    max_attempts = 5

    def handle(self, *args, **options):
        self.stdout.write('SMS queue worker started.')
        while True:
            message = self.claim_next_message()
            if message is None:
                time.sleep(self.poll_seconds)
                continue

            self.deliver(message)
            time.sleep(1)

    def claim_next_message(self):
        now = timezone.now()
        eligible = Q(status=AbsenceSms.STATUS_PENDING) | Q(
            status=AbsenceSms.STATUS_FAILED,
            attempts__lt=self.max_attempts,
        )
        with transaction.atomic():
            message = (
                AbsenceSms.objects.select_for_update()
                .select_related('student')
                .filter(eligible)
                .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
                .order_by('created_at')
                .first()
            )
            if message is None:
                return None

            message.attempts += 1
            message.next_attempt_at = now + timedelta(minutes=self.claim_minutes)
            message.save(update_fields=['attempts', 'next_attempt_at', 'last_error'])
            return message

    def deliver(self, message):
        student = message.student
        if not student.parent_mobile:
            self.mark_failed(message, 'No parent phone number.')
            return

        date_str = message.date.strftime('%d-%b-%y')
        sms = build_absent_message(
            student.name,
            date_str,
            roll_no=student.roll_no,
            class_name=student.class_name,
        )
        try:
            success, response = send_sms(student.parent_mobile, sms)
        except Exception as exc:
            success = False
            response = str(exc)

        if success:
            AbsenceSms.objects.filter(pk=message.pk).update(
                status=AbsenceSms.STATUS_SENT,
                next_attempt_at=None,
                last_error='',
                sent_at=timezone.now(),
            )
        else:
            self.mark_failed(message, response or 'SMS provider rejected the request.')

    def mark_failed(self, message, error):
        AbsenceSms.objects.filter(pk=message.pk).update(
            status=AbsenceSms.STATUS_FAILED,
            next_attempt_at=(
                timezone.now() + timedelta(minutes=self.retry_minutes)
                if message.attempts < self.max_attempts
                else None
            ),
            last_error=str(error)[:1000],
        )
