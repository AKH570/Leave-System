from django.db import migrations


def uppercase_department_names(apps, schema_editor):
    Department = apps.get_model('departments', 'Department')
    for department in Department.objects.all().only('pk', 'name'):
        normalized_name = ' '.join((department.name or '').split()).upper()
        if department.name != normalized_name:
            Department.objects.filter(pk=department.pk).update(name=normalized_name)


class Migration(migrations.Migration):
    dependencies = [
        ('departments', '0006_department_custom_names'),
    ]

    operations = [
        migrations.RunPython(
            uppercase_department_names,
            migrations.RunPython.noop,
        ),
    ]
