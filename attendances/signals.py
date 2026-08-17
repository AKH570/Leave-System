from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .services import record_check_in


@receiver(user_logged_in)
def record_employee_login(sender, request, user, **kwargs):
    """Keep the employee's first successful login time for the current date."""
    record_check_in(user)
