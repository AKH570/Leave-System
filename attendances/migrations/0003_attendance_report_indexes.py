from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('attendances', '0002_alter_attendance_employee')]

    operations = [
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['date'], name='attendance_date_idx'),
        ),
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['status', 'date'], name='attendance_status_date_idx'),
        ),
    ]
