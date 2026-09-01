# Generated manually (no local Django available to auto-generate)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0006_alter_teacher_assigned_class'),
    ]

    operations = [
        # Renaming (not dropping+adding) preserves each teacher's existing
        # single class value — e.g. "9" stays "9", which is already a valid
        # one-item comma list, so no data migration is needed.
        migrations.RenameField(
            model_name='teacher',
            old_name='assigned_class',
            new_name='assigned_classes',
        ),
        migrations.AlterField(
            model_name='teacher',
            name='assigned_classes',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
