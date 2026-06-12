from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
import re
from .models import Registration

class RegistrationForm(forms.ModelForm):
    """Form for new user registration"""

    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a strong password',
            'minlength': '8',
        }),
        help_text='Minimum 8 characters'
    )

    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Re-enter your password',
            'minlength': '8',
        })
    )
    
    terms_accepted = forms.BooleanField(
        label='I agree to the Terms and Conditions and Privacy Policy',
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        })
    )

    class Meta:
        model = Registration
        fields = [
            'first_name',
            'last_name',
            'phone',
            'username',
            'designation',
            'department',
            'email',
            'password',
            'confirm_password',
            'terms_accepted'
        ]

        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter first name',
                'minlength': '2',
                'maxlength': '50',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter last name',
                'minlength': '2',
                'maxlength': '50',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter mobile number',
                'type': 'tel',
                'pattern': '[0-9+\\-\\s()]{10,15}',
            }),
      
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Create a unique username',
                'minlength': '3',
                'maxlength': '150',
                'pattern': '[a-zA-Z0-9_]+',
            }),
            'designation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your designation (optional)',
                'required': False,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your email address',
            }),
            'department': forms.Select(attrs={
                'class': 'form-control',
            }),
        }

    def clean_first_name(self):
        """Validate first name"""
        first_name = self.cleaned_data.get('first_name')
        if first_name and len(first_name.strip()) < 2:
            raise ValidationError('First name must be at least 2 characters long.')
        return first_name

    def clean_last_name(self):
        """Validate last name"""
        last_name = self.cleaned_data.get('last_name')
        if last_name and len(last_name.strip()) < 2:
            raise ValidationError('Last name must be at least 2 characters long.')
        return last_name

    def clean_username(self):
        """Validate username"""
        username = self.cleaned_data.get('username')
        
        # Check if username already exists in Registration model
        if Registration.objects.filter(username=username).exists():
            raise ValidationError('This username is already registered.')
        
        # Check username format
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError('Username can only contain letters, numbers, and underscores.')
        
        return username

    def clean_email(self):
        """Validate email"""
        email = self.cleaned_data.get('email')
        
        # Check if email already exists in Registration model
        if Registration.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        
        return email

    def clean_password(self):
        """Validate password strength"""
        password = self.cleaned_data.get('password')
        
        if password:
            if len(password) < 8:
                raise ValidationError('Password must be at least 8 characters long.')
            
            # Check for uppercase
            if not re.search(r'[A-Z]', password):
                raise ValidationError('Password must contain at least one uppercase letter.')
            
            # Check for lowercase
            if not re.search(r'[a-z]', password):
                raise ValidationError('Password must contain at least one lowercase letter.')
            
            # Check for number
            if not re.search(r'[0-9]', password):
                raise ValidationError('Password must contain at least one number.')
        
        return password

    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise ValidationError({
                    'confirm_password': 'Passwords do not match.'
                })
        
        # Validate terms acceptance
        if not cleaned_data.get('terms_accepted'):
            raise ValidationError({
                'terms_accepted': 'You must agree to the terms and conditions.'
            })
        
        return cleaned_data