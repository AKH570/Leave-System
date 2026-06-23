from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone

from employees.models import Employee

from .models import Attendance


@receiver(user_logged_in)
def record_employee_login(sender, request, user, **kwargs):
    """Keep the employee's first successful login time for the current date."""
    try:
        employee = user.employee_profile
    except Employee.DoesNotExist:
        return

    login_time = timezone.localtime().time().replace(microsecond=0)
    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=timezone.localdate(),
        defaults={
            'check_in': login_time,
            'status': 'PRESENT',
        },
    )

    if not created:
        fields_to_update = []
        if attendance.check_in is None:
            attendance.check_in = login_time
            fields_to_update.append('check_in')
        if attendance.status != 'PRESENT':
            attendance.status = 'PRESENT'
            fields_to_update.append('status')
        if fields_to_update:
            attendance.save(update_fields=fields_to_update)
