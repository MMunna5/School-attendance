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
        if phone and not phone.startswith("0"):
            phone = "0" + phone
        return phone

    def handle(self, *args, **kwargs):
        folder = os.path.join(settings.BASE_DIR, "attendance", "import_data")
        files = [f for f in os.listdir(folder) if f.endswith(".xlsx")]

        if not files:
            self.stdout.write(self.style.ERROR(f"No .xlsx files found in {folder}"))
            return

        total_created, total_updated = 0, 0
        warnings = []

        for filename in files:
            path = os.path.join(folder, filename)
            wb = openpyxl.load_workbook(path, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))

            for row in rows[1:]:
                roll = row[0]
                name = row[1]
                class_name = row[3]
                section = row[4] or ""
                guardian_name = row[6] or ""
                phone = row[7]

                if not roll or not name or not class_name:
                    continue

                student_id = f"{class_name}{section}-{roll}"
                clean_phone = self.fix_phone(phone)

                if not clean_phone:
                    warnings.append(f"{filename}: Roll {roll} ({name}) - no phone number")

                obj, created = Student.objects.update_or_create(
                    student_id=student_id,
                    defaults={
                        "name": name,
                        "class_name": str(class_name),
                        "section": str(section),
                        "roll_no": str(roll),
                        "parent_mobile": clean_phone,
                        "guardian_name": str(guardian_name),
                    }
                )
                if created:
                    total_created += 1
                else:
                    total_updated += 1

            self.stdout.write(self.style.SUCCESS(f"Processed {filename}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Created: {total_created}, Updated: {total_updated}"
        ))
        if warnings:
            self.stdout.write(self.style.WARNING(f"\n{len(warnings)} students missing phone number:"))
            for w in warnings:
                self.stdout.write(f"  - {w}")