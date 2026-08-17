from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from .models import User
from employees.models import EmpDesignation, Employee
from departments.models import Department
from django.utils import timezone
from datetime import datetime
from .forms import AccessUserForm, AdminUserCreationForm, RegistrationForm, RoleForm
from .models import AuditLog
from .rbac import audit
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST


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
    expired = request.GET.get('expired') == '1'
    logout(request)
    if expired:
        messages.warning(
            request,
            'Your session has expired due to inactivity. Please log in again.',
        )
    return redirect('accounts:login')


@login_required
@require_POST
def session_refresh(request):
    """Lightweight endpoint; middleware refreshes expiry before this runs."""
    return JsonResponse({'authenticated': True})

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


def _superuser_only(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={request.path}")
    if not request.user.is_superuser:
        raise PermissionDenied


def access_users(request):
    denied = _superuser_only(request)
    if denied:
        return denied
    return render(request, 'access/users.html', {'users': User.objects.prefetch_related('groups').order_by('username')})


def access_user_create(request):
    denied = _superuser_only(request)
    if denied:
        return denied
    form = AdminUserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        audit(request, 'created', 'users', user)
        messages.success(request, 'Admin user created.')
        return redirect('accounts:access_user_edit', pk=user.pk)
    return render(request, 'access/form.html', {'form': form, 'title': 'Create admin user'})


def access_user_edit(request, pk):
    denied = _superuser_only(request)
    if denied:
        return denied
    user = get_object_or_404(User, pk=pk, is_superuser=False)
    form = AccessUserForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        user.is_staff, user.role = False, 'ADMIN'
        user.save(update_fields=('is_staff', 'role'))
        audit(request, 'updated access', 'users', user, groups=list(user.groups.values_list('name', flat=True)))
        messages.success(request, 'User access updated.')
        return redirect('accounts:access_users')
    return render(request, 'access/form.html', {'form': form, 'title': f'Access for {user.username}', 'effective_permissions': sorted(user.get_all_permissions())})


def access_roles(request):
    denied = _superuser_only(request)
    if denied:
        return denied
    return render(request, 'access/roles.html', {'roles': Group.objects.prefetch_related('permissions').order_by('name')})


def access_role_edit(request, pk=None):
    denied = _superuser_only(request)
    if denied:
        return denied
    role = get_object_or_404(Group, pk=pk) if pk else None
    form = RoleForm(request.POST or None, instance=role)
    if request.method == 'POST' and form.is_valid():
        role = form.save()
        audit(request, 'updated' if pk else 'created', 'roles', role, permissions=list(role.permissions.values_list('codename', flat=True)))
        messages.success(request, 'Role saved.')
        return redirect('accounts:access_roles')
    return render(request, 'access/form.html', {'form': form, 'title': 'Edit role' if pk else 'Create role'})


def access_permissions(request):
    denied = _superuser_only(request)
    if denied:
        return denied
    permissions = Permission.objects.select_related('content_type').order_by('content_type__app_label', 'content_type__model', 'codename')
    return render(request, 'access/permissions.html', {'permissions': permissions})


def access_audit(request):
    denied = _superuser_only(request)
    if denied:
        return denied
    return render(request, 'access/audit.html', {'events': AuditLog.objects.select_related('actor')[:200]})
