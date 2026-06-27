from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0016_empsalary_increment_salary_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='empsalary',
            old_name='increment_salary',
            new_name='increment_amount',
        ),
        migrations.RenameField(
            model_name='empsalary',
            old_name='last_increment_date',
            new_name='increment_date',
        ),
        migrations.AlterField(
            model_name='empsalary',
            name='increment_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                default=Decimal('0.00'),
                max_digits=12,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(
                        Decimal('0.00'),
                    ),
                ],
            ),
        ),
    ]
