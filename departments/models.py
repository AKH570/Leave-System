# departments/models.py

from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
# from accounts.models import Employee


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)

    manager = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                name='unique_department_name_ci',
            ),
        ]

    def clean(self):
        super().clean()
        self.name = ' '.join((self.name or '').split()).upper()
        if not self.name:
            return
        duplicates = Department.objects.filter(name__iexact=self.name)
        if self.pk:
            duplicates = duplicates.exclude(pk=self.pk)
        if duplicates.exists():
            raise ValidationError({'name': 'A department with this name already exists.'})

    def save(self, *args, **kwargs):
        self.name = ' '.join((self.name or '').split()).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
