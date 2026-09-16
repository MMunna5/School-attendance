from django.core.management.base import BaseCommand
from django.db import transaction

from attendance.models import Student, Teacher
from attendance.sms_utils import clean_phone_for_storage, normalize_sms_number


class Command(BaseCommand):
    """
    One-time cleanup: re-run every existing Student.parent_mobile and
    Teacher.mobile through clean_phone_for_storage() so numbers entered
    by hand (before this normalization existed) end up in the same
    consistent "01XXXXXXXXX" format as freshly-imported ones.

    Safe to run multiple times -- it only writes a row if the cleaned
    value is actually different from what's already stored.

    Usage:
        python manage.py normalize_phone_numbers            # apply changes
        python manage.py normalize_phone_numbers --dry-run   # preview only
    """

    help = "Normalize all existing student/teacher phone numbers to the standard 01XXXXXXXXX format."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without saving anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        mode = "DRY RUN (no changes will be saved)" if dry_run else "LIVE"
        self.stdout.write(self.style.WARNING(f"Mode: {mode}\n"))

        self._process_students(dry_run)
        self._process_teachers(dry_run)

    def _process_students(self, dry_run):
        self.stdout.write(self.style.MIGRATE_HEADING("Students"))
        changed = 0
        unsendable = []
        to_update = []

        for student in Student.objects.all():
            original = student.parent_mobile or ""
            cleaned = clean_phone_for_storage(original)

            if cleaned != original:
                changed += 1
                self.stdout.write(
                    f"  Roll {student.roll_no} ({student.name}, "
                    f"Class {student.class_name}{student.section}): "
                    f"{original!r} -> {cleaned!r}"
                )
                student.parent_mobile = cleaned
                to_update.append(student)

            final_value = cleaned if cleaned != original else original
            if final_value and not normalize_sms_number(final_value):
                unsendable.append(
                    f"Roll {student.roll_no} ({student.name}, "
                    f"Class {student.class_name}{student.section}): {final_value!r}"
                )
            elif not final_value:
                unsendable.append(
                    f"Roll {student.roll_no} ({student.name}, "
                    f"Class {student.class_name}{student.section}): <no phone on file>"
                )

        if to_update and not dry_run:
            with transaction.atomic():
                Student.objects.bulk_update(to_update, ["parent_mobile"], batch_size=500)

        self.stdout.write(self.style.SUCCESS(f"\n{changed} student number(s) normalized."))
        self._report_unsendable("students", unsendable)

    def _process_teachers(self, dry_run):
        self.stdout.write(self.style.MIGRATE_HEADING("\nTeachers"))
        changed = 0
        unsendable = []
        to_update = []

        for teacher in Teacher.objects.all():
            original = teacher.mobile or ""
            cleaned = clean_phone_for_storage(original)

            if cleaned != original:
                changed += 1
                self.stdout.write(f"  {teacher.name}: {original!r} -> {cleaned!r}")
                teacher.mobile = cleaned
                to_update.append(teacher)

            final_value = cleaned if cleaned != original else original
            if final_value and not normalize_sms_number(final_value):
                unsendable.append(f"{teacher.name}: {final_value!r}")
            elif not final_value:
                unsendable.append(f"{teacher.name}: <no phone on file>")

        if to_update and not dry_run:
            with transaction.atomic():
                Teacher.objects.bulk_update(to_update, ["mobile"], batch_size=500)

        self.stdout.write(self.style.SUCCESS(f"\n{changed} teacher number(s) normalized."))
        self._report_unsendable("teachers", unsendable)

    def _report_unsendable(self, label, unsendable):
        if not unsendable:
            self.stdout.write(self.style.SUCCESS(f"All {label} have a usable, SMS-ready number.\n"))
            return

        self.stdout.write(
            self.style.ERROR(
                f"\n{len(unsendable)} {label} still have a missing/unusable phone number "
                f"even after cleanup -- these will never receive an SMS until fixed by hand:"
            )
        )
        for line in unsendable:
            self.stdout.write(f"  - {line}")
        self.stdout.write("")
