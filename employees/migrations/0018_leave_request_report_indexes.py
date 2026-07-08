from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('employees', '0017_rename_salary_increment_fields')]

    operations = [
        migrations.AddIndex(
            model_name='leaverequest',
            index=models.Index(fields=['status', 'from_date'], name='leave_status_from_idx'),
        ),
        migrations.AddIndex(
            model_name='leaverequest',
            index=models.Index(fields=['from_date', 'to_date'], name='leave_period_idx'),
        ),
    ]
