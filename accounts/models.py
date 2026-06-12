from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin/HR'),
        ('EMPLOYEE', 'Employee'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='EMPLOYEE')
    phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Registration(models.Model):
    """Model to handle new user registration requests before approval."""
    STATUS_CHOICES = (
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True, null=True, blank=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=255)
    confirm_password = models.CharField(max_length=255, null=True, blank=True)
    
    phone_regex = RegexValidator(
        regex=r'^[0-9+\-\s()]{10,15}$',
        message='Phone number must be 10-15 digits.'
    )
    phone = models.CharField(max_length=15, validators=[phone_regex])
    
    designation = models.CharField(max_length=100, null=True, blank=True)
    department = models.ForeignKey(
        'departments.Department', 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='account_registrations'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    terms_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    rejection_reason = models.TextField(blank=True, null=True)
    
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_registrations'
    )
    approved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['username']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.username} - {self.status}"