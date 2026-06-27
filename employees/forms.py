from django import forms
from django.db import models
from django.db import transaction
from django.utils.text import slugify
from .models import EmpDesignation, EmpProfile, LeaveRequest, LeaveType, Employee
from accounts.models import Registration
from departments.models import Department
from django.contrib.auth import get_user_model

User = get_user_model()


class ProfilePictureInput(forms.ClearableFileInput):
    template_name = 'widgets/profile_picture_input.html'


class LeaveRequestForm(forms.ModelForm):
    leave_type = forms.ModelChoiceField(
        queryset=LeaveType.objects.all(),
        empty_label="Select",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, employee=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee is not None:
            self.instance.employee = employee

    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'from_date', 'to_date', 'reason']
        widgets = {
            'from_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-lg'}),
            'to_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Reason for leave...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        # The model's clean() method will handle the core business logic validation
        # when form.save() or instance.full_clean() is called.
        return cleaned_data

class LeaveApprovalForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['status', 'remarks']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Add remarks...'}),
        }

class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ['name', 'yearly_limit']
        widgets = {
            'name': forms.Select(attrs={'class': 'form-select'}),
            'yearly_limit': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'manager']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Human Resources'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. HR'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'manager': forms.Select(attrs={'class': 'form-select'}),
        }


class QuickDepartmentForm(forms.Form):
    name = forms.CharField(
        label='Department Name',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Human Resources',
            'autocomplete': 'off',
        }),
    )

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split()).upper()
        if Department.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError('A department with this name already exists.')
        return name

    def save(self):
        name = self.cleaned_data['name']
        base_code = (slugify(name).upper() or 'DEPARTMENT')[:20]
        code = base_code
        suffix = 2
        while Department.objects.filter(code__iexact=code).exists():
            suffix_text = f'-{suffix}'
            code = f'{base_code[:20 - len(suffix_text)]}{suffix_text}'
            suffix += 1
        return Department.objects.create(name=name, code=code)


class EmpDesignationForm(forms.ModelForm):
    class Meta:
        model = EmpDesignation
        fields = ['designation_name', 'department', 'description', 'status']
        widgets = {
            'designation_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. HR Officer'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class EmployeeAdminUpdateForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ['department', 'designation', 'is_active', 'custom_leave']
        labels = {
            'is_active': 'Status',
            'custom_leave': 'Custom leave entitlement',
        }
        help_texts = {
            'custom_leave': 'Leave blank to use leave type yearly limits.',
        }
        widgets = {
            'department': forms.Select(attrs={'class': 'form-select'}),
            'designation': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'custom_leave': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'placeholder': 'Use default'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_designations = EmpDesignation.objects.filter(status=EmpDesignation.Status.ACTIVE)
        if self.instance and self.instance.designation_id:
            active_designations = EmpDesignation.objects.filter(
                models.Q(status=EmpDesignation.Status.ACTIVE)
                | models.Q(pk=self.instance.designation_id),
            )
        self.fields['designation'].queryset = active_designations.distinct()


class EmployeeAdminEditForm(forms.Form):
    """Update only the employment settings controlled by an administrator."""

    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        required=False,
        empty_label='Select department',
    )
    designation = forms.ModelChoiceField(
        queryset=EmpDesignation.objects.none(),
        required=False,
        empty_label='Select designation',
    )
    role = forms.ChoiceField(choices=(('ADMIN', 'Admin'), ('EMPLOYEE', 'Employee')))
    employment_status = forms.ChoiceField(
        label='Employment Status',
        choices=(('active', 'Active'), ('inactive', 'Inactive')),
    )
    joining_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    leave_balance = forms.IntegerField(
        label='Leave Balance',
        required=False,
        min_value=0,
        help_text='Leave blank to use the standard leave-type allowances.',
    )

    def __init__(self, *args, employee, **kwargs):
        self.employee = employee
        self.user = employee.user
        try:
            self.profile = employee.extended_profile
        except EmpProfile.DoesNotExist:
            self.profile = None

        initial = kwargs.setdefault('initial', {})
        initial.update({
            'department': employee.department_id,
            'designation': employee.designation_id,
            'role': self.user.role,
            'employment_status': 'active' if employee.is_active else 'inactive',
            'joining_date': employee.joining_date,
            'leave_balance': employee.custom_leave,
        })
        super().__init__(*args, **kwargs)

        self.fields['department'].queryset = Department.objects.all()
        designations = EmpDesignation.objects.filter(status=EmpDesignation.Status.ACTIVE)
        if employee.designation_id:
            designations = EmpDesignation.objects.filter(
                models.Q(status=EmpDesignation.Status.ACTIVE)
                | models.Q(pk=employee.designation_id),
            )
        self.fields['designation'].queryset = designations.distinct()

        for field in self.fields.values():
            css_class = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs['class'] = css_class
        if self.is_bound:
            for name, field in self.fields.items():
                if self.errors.get(name):
                    field.widget.attrs['class'] += ' is-invalid'

    @transaction.atomic
    def save(self):
        self.user.role = self.cleaned_data['role']
        self.user.save(update_fields=['role'])

        self.employee.department = self.cleaned_data['department']
        self.employee.designation = self.cleaned_data['designation']
        self.employee.is_active = self.cleaned_data['employment_status'] == 'active'
        self.employee.joining_date = self.cleaned_data['joining_date']
        self.employee.custom_leave = self.cleaned_data['leave_balance']
        self.employee.save(update_fields=[
            'department', 'designation', 'is_active', 'joining_date', 'custom_leave',
        ])

        return self.employee


class EmployeeRegistrationForm(forms.ModelForm):
    """Form for the Registration staging model mentioned in text.txt"""
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['designation'].queryset = EmpDesignation.objects.filter(
            status=EmpDesignation.Status.ACTIVE,
        )

    class Meta:
        model = Registration
        fields = [
            'first_name', 'last_name', 'username', 'email', 
            'phone', 'designation', 'department', 'password'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

class EmployeeProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_designations = EmpDesignation.objects.filter(
            status=EmpDesignation.Status.ACTIVE,
        )
        if self.instance and self.instance.designation_id:
            active_designations = EmpDesignation.objects.filter(
                models.Q(status=EmpDesignation.Status.ACTIVE)
                | models.Q(pk=self.instance.designation_id),
            )
        self.fields['designation'].queryset = active_designations.distinct()

    class Meta:
        model = Employee
        fields = ['designation', 'department', 'supervisor', 'is_active']
        widgets = {
            'designation': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'supervisor': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class EmpProfileForm(forms.ModelForm):
    MAX_PROFILE_PICTURE_SIZE = 5 * 1024 * 1024

    class Meta:
        model = EmpProfile
        fields = [
            'profile_picture',
            'identification_no',
            'gender',
            'date_of_birth',
            'blood_group',
            'nationality',
            'present_address',
            'permanent_address',
            'education',
            'emergency_contact_name',
            'emergency_contact_relationship',
            'emergency_contact_number',
            'job_description',
        ]
        help_texts = {
            'profile_picture': 'Upload a JPG, PNG, or WebP image up to 5 MB.',
        }
        widgets = {
            'profile_picture': ProfilePictureInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/png,image/webp',
                'aria-describedby': 'id_profile_picture-help',
            }),
            'identification_no': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'NID, passport, birth certificate, or other number',
            }),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'blood_group': forms.Select(attrs={'class': 'form-select'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control'}),
            'present_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'permanent_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'education': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_relationship': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. +880 1700 000000',
            }),
            'job_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture and picture.size > self.MAX_PROFILE_PICTURE_SIZE:
            raise forms.ValidationError('Profile picture must be 5 MB or smaller.')
        if picture and getattr(picture, 'content_type', '') not in {
            'image/jpeg',
            'image/png',
            'image/webp',
        }:
            raise forms.ValidationError('Upload a JPG, JPEG, PNG, or WebP image.')
        return picture


class ProfilePictureForm(forms.ModelForm):
    MAX_PROFILE_PICTURE_SIZE = EmpProfileForm.MAX_PROFILE_PICTURE_SIZE

    class Meta:
        model = EmpProfile
        fields = ['profile_picture']

    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if not picture:
            raise forms.ValidationError('Choose a profile picture to upload.')
        if picture.size > self.MAX_PROFILE_PICTURE_SIZE:
            raise forms.ValidationError('Profile picture must be 5 MB or smaller.')
        if getattr(picture, 'content_type', '') not in {
            'image/jpeg',
            'image/png',
            'image/webp',
        }:
            raise forms.ValidationError('Upload a JPG, JPEG, PNG, or WebP image.')
        return picture
