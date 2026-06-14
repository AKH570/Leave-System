from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum

class Employee(models.Model):
    employee_id = models.CharField(max_length=20, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee_profile'
    )
    department = models.ForeignKey(
        'departments.Department',
        on_delete=models.SET_NULL,
        null=True,
        related_name='employees'
    )
    designation = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        default='Employee',
        help_text="Job position/designation"
    )
    joining_date = models.DateField(default=timezone.now)
    supervisor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates'
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"

class EmpProfile(models.Model):
    GENDER_CHOICES = (
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
    )
    BLOOD_GROUP_CHOICES = (
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    )

    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name='extended_profile',
    )
    identification_no = models.CharField(
        'Identification number',
        max_length=100,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[A-Za-z0-9][A-Za-z0-9\-/\s]*$',
                message='Enter a valid NID, passport, birth certificate, or other identification number.',
            )
        ],
        help_text='Enter a NID, passport, birth certificate, or other identification number.',
    )
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True,
    )
    profile_picture = models.ImageField(
        upload_to='employee_profiles/pictures/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])],
    )
    date_of_birth = models.DateField(blank=True, null=True)
    blood_group = models.CharField(
        max_length=3,
        choices=BLOOD_GROUP_CHOICES,
        blank=True,
    )
    nationality = models.CharField(max_length=80, blank=True)
    present_address = models.TextField(blank=True)
    permanent_address = models.TextField(blank=True)
    emergency_contact_number = models.CharField(
        max_length=15,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^[0-9+\-\s()]{10,15}$',
                message='Enter a valid emergency contact number (10-15 characters).',
            )
        ],
    )
    emergency_contact_name = models.CharField(max_length=120, blank=True)
    emergency_contact_relationship = models.CharField(max_length=80, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.date_of_birth and self.date_of_birth > timezone.localdate():
            raise ValidationError({'date_of_birth': 'Date of birth cannot be in the future.'})

    def __str__(self):
        return f"Profile - {self.employee}"

class LeaveType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    yearly_limit = models.PositiveIntegerField(
        default=0,
        help_text="Maximum days allowed per year for this leave type"
    )
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class LeaveRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    )

    employee = models.ForeignKey(
        'employees.Employee',
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE
    )
    from_date = models.DateField()
    to_date = models.DateField()
    total_days = models.PositiveIntegerField()
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        'employees.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_requests'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(
        blank=True, 
        null=True,
        help_text="Admin remarks/comments"
    )

    def clean(self):
        if self.from_date and self.to_date:
            if self.from_date > self.to_date:
                raise ValidationError("From Date cannot be greater than To Date.")

            # Calculate total days
            delta = self.to_date - self.from_date
            self.total_days = delta.days + 1

            if not self.employee_id or not self.leave_type_id:
                return

            # Check for overlapping leaves for this employee
            overlapping = LeaveRequest.objects.filter(
                employee=self.employee,
                status__in=['PENDING', 'APPROVED']
            ).exclude(pk=self.pk).filter(
                from_date__lte=self.to_date,
                to_date__gte=self.from_date
            )
            if overlapping.exists():
                raise ValidationError("You have an overlapping leave request for these dates.")

            # Check leave balance for the current year
            current_year = timezone.now().year
            used_days = LeaveRequest.objects.filter(
                employee=self.employee,
                leave_type=self.leave_type,
                status='APPROVED',
                from_date__year=current_year
            ).aggregate(Sum('total_days'))['total_days__sum'] or 0

            if used_days + self.total_days > self.leave_type.yearly_limit:
                raise ValidationError(f"Insufficient balance. You have {self.leave_type.yearly_limit - used_days} days remaining for {self.leave_type.name}.")

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.from_date} to {self.to_date})"

    class Meta:
        ordering = ['-applied_at']
