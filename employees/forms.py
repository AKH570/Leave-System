from django import forms
from .models import LeaveRequest, LeaveType, Employee
from accounts.models import Registration
from django.contrib.auth import get_user_model

User = get_user_model()

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
        fields = ['name', 'yearly_limit', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'yearly_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

class EmployeeRegistrationForm(forms.ModelForm):
    """Form for the Registration staging model mentioned in text.txt"""
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

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
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
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
    class Meta:
        model = Employee
        fields = ['employee_id', 'designation', 'department', 'supervisor', 'is_active']
        widgets = {
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'supervisor': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
