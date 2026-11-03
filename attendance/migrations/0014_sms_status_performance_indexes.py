from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0013_emergency_sms_sent_at'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='absencesms',
            index=models.Index(fields=['status', 'created_at'], name='sms_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='absencesms',
            index=models.Index(fields=['status', 'sent_at'], name='sms_status_sent_idx'),
        ),
        migrations.AddIndex(
            model_name='teacherabsencesms',
            index=models.Index(fields=['status', 'created_at'], name='teacher_sms_created_idx'),
        ),
        migrations.AddIndex(
            model_name='teacherabsencesms',
            index=models.Index(fields=['status', 'sent_at'], name='teacher_sms_sent_idx'),
        ),
        migrations.AddIndex(
            model_name='emergencysmslog',
            index=models.Index(fields=['sent_at'], name='emergency_sms_sent_idx'),
        ),
    ]
