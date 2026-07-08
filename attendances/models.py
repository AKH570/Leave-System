# attendance/models.py

from datetime import datetime, timedelta

from django.db import models
# from accounts.models import Employee


class Attendance(models.Model):

    STATUS_CHOICES = (
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('HALF_DAY', 'Half Day'),
    )

    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='attendances',
        null=True # Temporary if you have existing data, otherwise remove
    )

    date = models.DateField()

    check_in = models.TimeField(
        null=True,
        blank=True
    )

    check_out = models.TimeField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES
    )

    remarks = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        unique_together = ('employee', 'date')
        indexes = [
            models.Index(fields=['date'], name='attendance_date_idx'),
            models.Index(fields=['status', 'date'], name='attendance_status_date_idx'),
        ]

    @property
    def working_duration(self):
        """Return the time worked, supporting shifts that cross midnight."""
        if not self.check_in or not self.check_out:
            return None

        start = datetime.combine(self.date, self.check_in)
        end = datetime.combine(self.date, self.check_out)
        if end < start:
            end += timedelta(days=1)
        return end - start

    @property
    def working_hours_display(self):
        duration = self.working_duration
        if duration is None:
            return '—'
        total_minutes = int(duration.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        return f'{hours}h {minutes:02d}m'

    def __str__(self):
        return f"{self.employee} - {self.date}"
