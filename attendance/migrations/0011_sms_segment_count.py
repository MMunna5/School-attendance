from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0010_teacherabsencesms'),
    ]

    operations = [
        migrations.AddField(
            model_name='absencesms',
            name='sms_segments',
            field=models.PositiveIntegerField(default=1, help_text='Estimated billable SMS segments for this message.'),
        ),
        migrations.AddField(
            model_name='teacherabsencesms',
            name='sms_segments',
            field=models.PositiveIntegerField(default=1, help_text='Estimated billable SMS segments for this message.'),
        ),
    ]
