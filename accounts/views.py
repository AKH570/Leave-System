from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.shortcuts import render, redirect
from .models import User
from employees.models import EmpDesignation, Employee
from departments.models import Department
from django.utils import timezone
from datetime import datetime
from .forms import RegistrationForm


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('adm_dashboard')
        return redirect('emp_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.is_superuser:
                return redirect('dashboard')
            return redirect('dashboard')

        messages.error(request, 'Invalid username or password.')

    return render(request, 'authentication/login.html')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')

def registration_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('adm_dashboard')
        return redirect('emp_dashboard')

    departments = Department.objects.all()
    context = {
        'departments': departments,
        'designations': EmpDesignation.objects.filter(
            status=EmpDesignation.Status.ACTIVE,
        ),
    }

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create user
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        password=form.cleaned_data['password'],
                        first_name=form.cleaned_data['first_name'],
                        last_name=form.cleaned_data['last_name'],
                        phone=form.cleaned_data['phone'],
                        role='EMPLOYEE'
                    )

                    # Create employee profile
                    Employee.objects.create(
                        user=user,
                        department=form.cleaned_data.get('department'),
                        designation=form.cleaned_data.get('designation'),
                        is_active=True
                    )

                messages.success(request, 'Registration successful! Please log in.')
                return redirect('accounts:login')

            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
                context['form'] = form
                return render(request, 'authentication/registration.html', context)
        else:
            context['form'] = form
    else:
        context['form'] = RegistrationForm()

    return render(request, 'authentication/registration.html', context)
