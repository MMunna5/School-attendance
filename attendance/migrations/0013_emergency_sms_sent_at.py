from django.db import migrations, models
from django.db.models import F


def backfill_sent_at(apps, schema_editor):
    EmergencySmsLog = apps.get_model('attendance', 'EmergencySmsLog')
    EmergencySmsLog.objects.filter(sent_at__isnull=True).update(sent_at=F('created_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0012_emergency_sms_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='emergencysmslog',
            name='sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_sent_at, migrations.RunPython.noop),
    ]
