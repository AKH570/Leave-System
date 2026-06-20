import re
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Sum
from django.db.models.functions import Lower
from django.utils import timezone


def generate_designation_id():
    """Return a compact, collision-resistant designation code."""
    return f'DSG{uuid.uuid4().hex[:9].upper()}'


class EmpDesignation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'

    designation_id = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
        default=generate_designation_id,
    )
    designation_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    department = models.ForeignKey(
        'departments.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='designations',
    )
    status = models.CharField(
        max_length=8,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_employee_designations',
    )

    class Meta:
        verbose_name = 'Employee Designation'
        verbose_name_plural = 'Employee Designations'
        ordering = ['designation_name']
        constraints = [
            models.UniqueConstraint(
                Lower('designation_name'),
                name='unique_emp_designation_name_ci',
            ),
        ]

    def clean(self):
        super().clean()
        self.designation_name = (self.designation_name or '').strip()
        if not self.designation_name:
            return

        duplicate_names = EmpDesignation.objects.filter(
            designation_name__iexact=self.designation_name,
        )
        if self.pk:
            duplicate_names = duplicate_names.exclude(pk=self.pk)
        if duplicate_names.exists():
            raise ValidationError({
                'designation_name': 'A designation with this name already exists.',
            })

    def save(self, *args, **kwargs):
        self.designation_name = (self.designation_name or '').strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.designation_name


class Employee(models.Model):
    EMPLOYEE_ID_PATTERN = re.compile(r'^EMP(\d+)$')
    MAX_EMPLOYEE_NUMBER = 9999

    employee_id = models.CharField(
        max_length=7,
        unique=True,
        editable=False,
        db_index=True,
    )
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
    designation = models.ForeignKey(
        'employees.EmpDesignation',
        on_delete=models.PROTECT,
        related_name='%(class)s_records',
        blank=True,
        null=True,
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
    custom_leave = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Admin-defined total leave balance for this employee. If set, "
            "leave type balances will be ignored."
        ),
    )

    def get_leave_summary(self, year=None):
        """Return the effective allowance, usage, and remaining balance."""
        approved_leaves = self.leave_requests.filter(status='APPROVED')
        if self.custom_leave is not None:
            used_days = approved_leaves.aggregate(
                total=Sum('total_days'),
            )['total'] or 0
            return {
                'allowance': self.custom_leave,
                'used': used_days,
                'balance': self.custom_leave,
                'uses_custom_leave': True,
            }

        year = year or timezone.localdate().year
        used_days = approved_leaves.filter(from_date__year=year).aggregate(
            total=Sum('total_days'),
        )['total'] or 0
        allowance = LeaveType.objects.aggregate(
            total=Sum('yearly_limit'),
        )['total'] or 0
        return {
            'allowance': allowance,
            'used': used_days,
            'balance': max(allowance - used_days, 0),
            'uses_custom_leave': False,
        }

    @classmethod
    def _next_employee_id(cls):
        latest_ids = cls.objects.order_by('-pk').values_list(
            'employee_id',
            flat=True,
        )
        latest_number = 0
        for employee_id in latest_ids:
            match = cls.EMPLOYEE_ID_PATTERN.fullmatch(employee_id or '')
            if match:
                latest_number = int(match.group(1))
                break

        next_number = latest_number + 1
        if next_number > cls.MAX_EMPLOYEE_NUMBER:
            raise ValidationError({
                'employee_id': 'The employee ID sequence has reached EMP9999.',
            })
        return f'EMP{next_number:04d}'

    def save(self, *args, **kwargs):
        if not self._state.adding:
            self.employee_id = Employee.objects.only('employee_id').get(
                pk=self.pk,
            ).employee_id
            return super().save(*args, **kwargs)

        for attempt in range(3):
            try:
                with transaction.atomic():
                    Employee.objects.select_for_update().order_by('-pk').first()
                    self.employee_id = self._next_employee_id()
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.employee_id = ''
                if attempt == 2:
                    raise

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
    CASUAL = 'Casual Leave'
    SICK = 'Sick Leave'
    EARNED = 'Earned Leave'
    OTHER = 'Other'

    LEAVE_TYPE_CHOICES = [
        (CASUAL, 'Casual Leave'),
        (SICK, 'Sick Leave'),
        (EARNED, 'Earned Leave'),
        (OTHER, 'Other'),
    ]

    name = models.CharField(
        max_length=50,
        choices=LEAVE_TYPE_CHOICES,
        default=CASUAL,
    )
    yearly_limit = models.PositiveIntegerField(
        default=0,
        help_text="Maximum days allowed per year for this leave type"
    )
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

            if self.employee.custom_leave is not None:
                if self.total_days > self.employee.custom_leave:
                    raise ValidationError(
                        "Insufficient custom leave balance. You have "
                        f"{self.employee.custom_leave} days remaining."
                    )
            else:
                # Check leave type balance for the current year.
                current_year = timezone.now().year
                used_days = LeaveRequest.objects.filter(
                    employee=self.employee,
                    leave_type=self.leave_type,
                    status='APPROVED',
                    from_date__year=current_year
                ).aggregate(Sum('total_days'))['total_days__sum'] or 0

                if used_days + self.total_days > self.leave_type.yearly_limit:
                    raise ValidationError(f"Insufficient balance. You have {self.leave_type.yearly_limit - used_days} days remaining for {self.leave_type.name}.")

    def approve(self, approved_by=None, remarks=''):
        """Approve this request and atomically consume any custom balance."""
        if not self.pk:
            raise ValidationError('The leave request must be saved before approval.')

        with transaction.atomic():
            leave = LeaveRequest.objects.select_for_update().get(pk=self.pk)
            if leave.status != 'PENDING':
                raise ValidationError('Only pending leave requests can be approved.')

            employee = Employee.objects.select_for_update().get(
                pk=leave.employee_id,
            )
            if employee.custom_leave is not None:
                if leave.total_days > employee.custom_leave:
                    raise ValidationError(
                        "Insufficient custom leave balance. The employee has "
                        f"{employee.custom_leave} days remaining."
                    )
                employee.custom_leave -= leave.total_days
                employee.save(update_fields=['custom_leave'])

            leave.status = 'APPROVED'
            leave.remarks = remarks
            leave.approved_by = approved_by
            leave.approved_at = timezone.now()
            leave.save(update_fields=[
                'status',
                'remarks',
                'approved_by',
                'approved_at',
            ])

        self.refresh_from_db()
        return self

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.from_date} to {self.to_date})"

    class Meta:
        ordering = ['-applied_at']
