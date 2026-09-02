import os
import openpyxl
from django.core.management.base import BaseCommand
from django.conf import settings
from attendance.models import Student


class Command(BaseCommand):
    help = "Import students from all Excel files in attendance/import_data/"

    def fix_phone(self, phone):
        if not phone:
            return ""
        phone = str(phone).strip()
        phone = phone.replace(" ", "").replace("-", "")
        if phone.endswith(".0"):
            phone = phone[:-2]
        if phone and not phone.startswith("0"):
            phone = "0" + phone
        return phone

    def handle(self, *args, **kwargs):
        folder = os.path.join(settings.BASE_DIR, "attendance", "import_data")
        if not os.path.exists(folder):
            self.stdout.write(self.style.WARNING(f"Directory {folder} does not exist."))
            return

        files = [f for f in os.listdir(folder) if f.endswith(".xlsx")]

        if not files:
            self.stdout.write(self.style.ERROR(f"No .xlsx files found in {folder}"))
            return

        total_created, total_updated = 0, 0
        warnings = []

        for filename in files:
            path = os.path.join(folder, filename)
            try:
                wb = openpyxl.load_workbook(path, data_only=True)
                ws = wb.active
                rows = list(ws.iter_rows(values_only=True))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Could not read {filename}: {e}"))
                continue

            for row in rows[1:]:
                if not row or len(row) < 3:
                    continue

                roll = row[0]
                name = row[1]
                class_name = row[3] if len(row) > 3 else row[2]
                section = row[4] if len(row) > 4 else ""
                phone = row[7] if len(row) > 7 else (row[5] if len(row) > 5 else "")

                if not roll or not name or not class_name:
                    continue

                clean_phone = self.fix_phone(phone)

                if not clean_phone:
                    warnings.append(f"{filename}: Roll {roll} ({name}) - no phone number")

                obj, created = Student.objects.update_or_create(
                    class_name=str(class_name).strip(),
                    section=str(section or "").strip(),
                    roll_no=str(roll).strip(),
                    defaults={
                        "name": str(name).strip(),
                        "parent_mobile": clean_phone,
                    },
                )
                if created:
                    total_created += 1
                else:
                    total_updated += 1

            self.stdout.write(self.style.SUCCESS(f"Processed {filename}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created: {total_created}, Updated: {total_updated}"
            )
        )
        if warnings:
            self.stdout.write(
                self.style.WARNING(f"\n{len(warnings)} students missing phone number:")
            )
            for w in warnings:
                self.stdout.write(f"  - {w}")