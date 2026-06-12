# departments/models.py

from django.db import models
# from accounts.models import Employee


class Department(models.Model):
    DEPT_CHOICES = (
        ('MEDICINE', 'Medicine'),
        ('NON-MEDICINE', 'Non-Medicine'),)
    name = models.CharField(max_length=100, choices=DEPT_CHOICES, unique=True)
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

    def __str__(self):
        return self.name