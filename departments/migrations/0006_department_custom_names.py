from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ('departments', '0005_alter_department_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='department',
            name='name',
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AddConstraint(
            model_name='department',
            constraint=models.UniqueConstraint(
                Lower('name'),
                name='unique_department_name_ci',
            ),
        ),
    ]
