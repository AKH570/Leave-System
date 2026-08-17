from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_admins(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    role, _ = Group.objects.get_or_create(name='Admin')
    role.permissions.set(Permission.objects.exclude(content_type__app_label__in=('admin', 'auth', 'contenttypes', 'sessions')))
    for user in User.objects.filter(role='ADMIN', is_superuser=False):
        user.is_staff = False
        user.save(update_fields=('is_staff',))
        user.groups.add(role)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0014_alter_registration_designation')]
    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=80)),
                ('module', models.CharField(max_length=80)),
                ('object_repr', models.CharField(blank=True, max_length=255)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rbac_audit_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ('-created_at',)},
        ),
        migrations.AlterModelOptions(
            name='user',
            options={'permissions': [('manage_users', 'Can manage application users'), ('manage_roles', 'Can manage roles'), ('manage_permissions', 'Can assign roles and permissions'), ('access_settings', 'Can access application settings'), ('approve_leave', 'Can approve leave requests'), ('reject_leave', 'Can reject leave requests'), ('process_salary', 'Can process salary'), ('view_reports', 'Can view reports'), ('export_reports', 'Can export reports')]},
        ),
        migrations.RunPython(migrate_legacy_admins, migrations.RunPython.noop),
    ]
