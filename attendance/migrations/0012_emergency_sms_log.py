from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0011_sms_segment_count'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmergencySmsLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sms_segments', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
