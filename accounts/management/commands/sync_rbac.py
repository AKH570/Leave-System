from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = 'Create/update the Admin role and migrate legacy ADMIN users safely.'

    def handle(self, *args, **options):
        role, _ = Group.objects.get_or_create(name='Admin')
        permissions = Permission.objects.exclude(
            content_type__app_label__in=('admin', 'auth', 'contenttypes', 'sessions'),
        )
        role.permissions.set(permissions)
        users = User.objects.filter(role='ADMIN', is_superuser=False)
        for user in users:
            user.is_staff = False
            user.save(update_fields=('is_staff',))
            user.groups.add(role)
        self.stdout.write(self.style.SUCCESS(f'Synced Admin role for {users.count()} user(s).'))
