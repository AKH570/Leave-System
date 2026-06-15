import django.db.models.deletion
from django.db import migrations, models


def migrate_employee_designations(apps, schema_editor):
    Employee = apps.get_model('employees', 'Employee')
    EmpDesignation = apps.get_model('employees', 'EmpDesignation')

    for employee in Employee.objects.exclude(designation__isnull=True).iterator():
        designation_name = employee.designation.strip()
        if not designation_name:
            continue

        designation = EmpDesignation.objects.filter(
            designation_name__iexact=designation_name,
        ).first()
        if designation is None:
            designation = EmpDesignation.objects.create(
                designation_name=designation_name,
                department_id=employee.department_id,
            )

        Employee.objects.filter(pk=employee.pk).update(
            designation_ref_id=designation.pk,
        )


def restore_employee_designation_text(apps, schema_editor):
    Employee = apps.get_model('employees', 'Employee')

    for employee in Employee.objects.exclude(
        designation_ref__isnull=True,
    ).select_related('designation_ref').iterator():
        Employee.objects.filter(pk=employee.pk).update(
            designation=employee.designation_ref.designation_name,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0006_empdesignation'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='designation_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='employee_records',
                to='employees.empdesignation',
            ),
        ),
        migrations.RunPython(
            migrate_employee_designations,
            restore_employee_designation_text,
        ),
        migrations.RemoveField(
            model_name='employee',
            name='designation',
        ),
        migrations.RenameField(
            model_name='employee',
            old_name='designation_ref',
            new_name='designation',
        ),
    ]
