import django.db.models.deletion
from django.db import migrations, models


def migrate_registration_designations(apps, schema_editor):
    Registration = apps.get_model('accounts', 'Registration')
    EmpDesignation = apps.get_model('employees', 'EmpDesignation')

    for registration in Registration.objects.exclude(
        designation__isnull=True,
    ).iterator():
        designation_name = registration.designation.strip()
        if not designation_name:
            continue

        designation = EmpDesignation.objects.filter(
            designation_name__iexact=designation_name,
        ).first()
        if designation is None:
            designation = EmpDesignation.objects.create(
                designation_name=designation_name,
                department_id=registration.department_id,
            )

        Registration.objects.filter(pk=registration.pk).update(
            designation_ref_id=designation.pk,
        )


def restore_registration_designation_text(apps, schema_editor):
    Registration = apps.get_model('accounts', 'Registration')

    for registration in Registration.objects.exclude(
        designation_ref__isnull=True,
    ).select_related('designation_ref').iterator():
        Registration.objects.filter(pk=registration.pk).update(
            designation=registration.designation_ref.designation_name,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_registration_approved_at_registration_approved_by_and_more'),
        ('employees', '0007_employee_designation_foreign_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='designation_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='registration_records',
                to='employees.empdesignation',
            ),
        ),
        migrations.RunPython(
            migrate_registration_designations,
            restore_registration_designation_text,
        ),
        migrations.RemoveField(
            model_name='registration',
            name='designation',
        ),
        migrations.RenameField(
            model_name='registration',
            old_name='designation_ref',
            new_name='designation',
        ),
    ]
