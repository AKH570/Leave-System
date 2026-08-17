"""Attendance recording helpers used by the authentication flow."""

from django.utils import timezone

from employees.models import Employee

from .models import Attendance


def _employee_for_user(user):
    if not getattr(user, 'is_authenticated', False):
        return None
    try:
        return user.employee_profile
    except Employee.DoesNotExist:
        return None


def _local_time(value):
    return timezone.localtime(value).time().replace(microsecond=0)


def record_check_in(user, *, at=None):
    """Record an employee's first successful login for the local date."""
    employee = _employee_for_user(user)
    if employee is None:
        return None

    occurred_at = at or timezone.now()
    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=timezone.localdate(occurred_at),
        defaults={
            'check_in': _local_time(occurred_at),
            'status': 'PRESENT',
        },
    )

    if not created:
        fields_to_update = []
        if attendance.check_in is None:
            attendance.check_in = _local_time(occurred_at)
            fields_to_update.append('check_in')
        if attendance.status != 'PRESENT':
            attendance.status = 'PRESENT'
            fields_to_update.append('status')
        if fields_to_update:
            attendance.save(update_fields=fields_to_update)
    return attendance


def record_check_out(user, *, at=None):
    """Set today's checkout to the latest successful explicit logout."""
    employee = _employee_for_user(user)
    if employee is None:
        return None

    occurred_at = at or timezone.now()
    attendance = Attendance.objects.filter(
        employee=employee,
        date=timezone.localdate(occurred_at),
    ).first()
    if attendance is None:
        return None

    attendance.check_out = _local_time(occurred_at)
    attendance.save(update_fields=['check_out'])
    return attendance
