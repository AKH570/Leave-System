from datetime import datetime, timedelta

from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def seed_legacy_logs(apps, schema_editor):
    Attendance = apps.get_model('attendances', 'Attendance')
    AttendanceLog = apps.get_model('attendances', 'AttendanceLog')
    timezone_value = timezone.get_current_timezone()
    rows = []
    for attendance in Attendance.objects.exclude(employee_id=None).iterator():
        if attendance.check_in:
            rows.append(AttendanceLog(
                attendance_id=attendance.pk, employee_id=attendance.employee_id,
                event_type='CHECK_IN', event_time=timezone.make_aware(
                    datetime.combine(attendance.date, attendance.check_in), timezone_value),
            ))
        if attendance.check_out:
            value = datetime.combine(attendance.date, attendance.check_out)
            if attendance.check_in and attendance.check_out < attendance.check_in:
                value += timedelta(days=1)
            rows.append(AttendanceLog(
                attendance_id=attendance.pk, employee_id=attendance.employee_id,
                event_type='CHECK_OUT', event_time=timezone.make_aware(value, timezone_value),
            ))
    AttendanceLog.objects.bulk_create(rows, batch_size=1000)


class Migration(migrations.Migration):
    dependencies = [('attendances', '0003_attendance_report_indexes')]
    operations = [
        migrations.CreateModel(
            name='AttendanceLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('CHECK_IN', 'Check-In'), ('CHECK_OUT', 'Check-Out')], max_length=10)),
                ('event_time', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('attendance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='attendances.attendance')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_logs', to='employees.employee')),
            ],
            options={'ordering': ('event_time', 'pk')},
        ),
        migrations.AddIndex(model_name='attendancelog', index=models.Index(fields=['employee', 'event_time'], name='att_log_emp_time_idx')),
        migrations.AddIndex(model_name='attendancelog', index=models.Index(fields=['attendance', 'event_time'], name='att_log_att_time_idx')),
        migrations.RunPython(seed_legacy_logs, migrations.RunPython.noop),
    ]
