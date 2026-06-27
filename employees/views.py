from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import OuterRef, Q, Subquery, Sum
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)
from departments.models import Department
from .models import EmpDesignation, EmpProfile, Employee, LeaveRequest, LeaveType
from attendances.models import Attendance
from .forms import (
    DepartmentForm,
    EmpDesignationForm,
    EmployeeAdminEditForm,
    EmployeeAdminUpdateForm,
    EmpProfileForm,
    LeaveRequestForm,
    LeaveApprovalForm,
    LeaveTypeForm,
    ProfilePictureForm,
    QuickDepartmentForm,
)


def get_safe_redirect_url(request, fallback='dashboard'):
    redirect_to = request.POST.get('next') or request.GET.get('next')
    if redirect_to and url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to
    return fallback

class AdminAccessMixin(UserPassesTestMixin):
    """Ensures only Admin/HR can access certain views."""
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_superuser
            or self.request.user.is_staff
            or getattr(self.request.user, 'role', '') == 'ADMIN'
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, 'You do not have permission to access HR settings.')
            return redirect('dashboard')
        return super().handle_no_permission()

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/employee_dashboard.html'
    # 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        try:
            employee = user.employee_profile
            context['employee'] = employee
            context['recent_leaves'] = LeaveRequest.objects.filter(employee=employee).order_by('-applied_at')[:5]
            
            # Check if Admin/HR for more stats
            if user.is_staff or getattr(user, 'role', '') == 'ADMIN':
                context['is_admin'] = True
                context['pending_requests_count'] = LeaveRequest.objects.filter(status='PENDING').count()
                context['total_employees_count'] = Employee.objects.filter(is_active=True).count()
                context['pending_requests'] = LeaveRequest.objects.filter(status='PENDING').order_by('-applied_at')[:5]
            else:
                context['is_admin'] = False
        except Employee.DoesNotExist:
            context['employee'] = None
            context['is_admin'] = user.is_staff or getattr(user, 'role', '') == 'ADMIN'
            
        return context

# --- Employee Views ---

class LeaveApplyView(LoginRequiredMixin, CreateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'leaves/apply_leave.html'
    success_url = reverse_lazy('leave_apply')

    def dispatch(self, request, *args, **kwargs):
        try:
            self.employee = request.user.employee_profile
        except Employee.DoesNotExist:
            messages.error(request, "Employee profile not found. Please contact Admin.")
            return redirect('dashboard')
        if not self.employee.is_active:
            messages.error(request, "Your employee profile is inactive. Please contact Admin.")
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['employee'] = self.employee
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employee'] = self.employee
        context['leave_balance'] = self.employee.get_leave_summary()['balance']
        context['uses_custom_leave'] = self.employee.custom_leave is not None
        context['messages_in_content'] = True
        return context

    def form_valid(self, form):
        form.instance.employee = self.employee
        response = super().form_valid(form)
        messages.success(self.request, "Leave request submitted successfully.")
        return response

class LeaveHistoryView(LoginRequiredMixin, ListView):
    model = LeaveRequest
    template_name = 'leaves/leave_history.html'
    context_object_name = 'leaves'

    def get_queryset(self):
        return LeaveRequest.objects.filter(employee__user=self.request.user)

class LeaveDetailView(LoginRequiredMixin, DetailView):
    model = LeaveRequest
    template_name = 'leaves/leave_detail.html'
    context_object_name = 'leave'

class EmployeeProfileMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        try:
            self.employee = Employee.objects.select_related(
                'user',
                'department',
                'designation',
                'supervisor__user',
            ).get(user=request.user)
        except Employee.DoesNotExist:
            messages.error(request, 'Employee profile not found. Please contact Admin.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

class EmployeeProfileView(EmployeeProfileMixin, TemplateView):
    template_name = 'employees/my_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = EmpProfile.objects.get_or_create(employee=self.employee)
        context['employee'] = self.employee
        context['profile'] = profile
        return context

class EmployeeProfileUpdateView(EmployeeProfileMixin, UpdateView):
    model = EmpProfile
    form_class = EmpProfileForm
    template_name = 'employees/edit_profile.html'
    success_url = reverse_lazy('employee_profile')

    def get_object(self, queryset=None):
        profile, _ = EmpProfile.objects.get_or_create(employee=self.employee)
        return profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employee'] = self.employee
        context['messages_in_content'] = True
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Your profile has been updated successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


@login_required
@require_POST
def profile_picture_upload(request):
    try:
        employee = Employee.objects.get(user=request.user)
    except Employee.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Employee profile not found.'}, status=404)

    profile, _ = EmpProfile.objects.get_or_create(employee=employee)
    form = ProfilePictureForm(
        request.POST,
        request.FILES,
        instance=profile,
    )
    if form.is_valid():
        form.save()
        image_url = profile.profile_picture.url if profile.profile_picture else ''
        return JsonResponse({
            'ok': True,
            'image_url': image_url,
            'fallback_url': request.build_absolute_uri('/static/images/avatar.png'),
        })

    errors = form.errors.get('profile_picture') or form.non_field_errors()
    return JsonResponse({
        'ok': False,
        'error': errors.as_text() if errors else 'Unable to upload profile picture.',
    }, status=400)

class EmployeeDetailView(LoginRequiredMixin, AdminAccessMixin, DetailView):
    model = Employee
    template_name = 'employees/employee_detail.html'
    context_object_name = 'employee'

    def get_queryset(self):
        return Employee.objects.select_related(
            'user',
            'department',
            'designation',
            'supervisor__user',
            'extended_profile',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.object
        profile = getattr(employee, 'extended_profile', None)
        current_year = timezone.now().year
        leave_summary = employee.get_leave_summary(current_year)
        latest_salary = employee.salary_records.filter(
            is_active=True,
        ).order_by('-salary_effective_from', '-pk').first()

        context.update({
            'yearly_leave_allowance': leave_summary['allowance'],
            'used_leave_days': leave_summary['used'],
            'leave_balance': leave_summary['balance'],
            'uses_custom_leave': leave_summary['uses_custom_leave'],
            'current_year': current_year,
            'profile': profile,
            'latest_salary': latest_salary,
            'recent_leaves': employee.leave_requests.select_related(
                'leave_type',
            ).order_by('-applied_at')[:5],
        })
        return context

def leave_cancel(request, pk):
    """Allows employees to cancel only PENDING requests."""
    leave = get_object_or_404(LeaveRequest, pk=pk, employee__user=request.user)
    if leave.status == 'PENDING':
        leave.status = 'CANCELLED'
        leave.save()
        messages.success(request, "Leave request cancelled.")
    else:
        messages.error(request, "Only pending requests can be cancelled.")
    return redirect('emp_dashboard')

# --- Admin/HR Views ---

class AdminLeaveListView(LoginRequiredMixin, AdminAccessMixin, ListView):
    model = LeaveRequest
    template_name = 'leaves/admin_leave_list.html'
    context_object_name = 'leaves'
    queryset = LeaveRequest.objects.all()

def leave_approve(request, pk):
    """Admin action to approve a request."""
    if not (request.user.is_staff or getattr(request.user, 'role', '') == 'ADMIN'):
        return redirect('dashboard')
    
    leave = get_object_or_404(LeaveRequest, pk=pk)
    redirect_to = get_safe_redirect_url(request)
    if request.method == 'POST':
        if leave.status != 'PENDING':
            messages.error(request, "Only pending leave requests can be approved.")
            return redirect(redirect_to)

        remarks = request.POST.get('remarks', '')
        try:
            approved_by = request.user.employee_profile
        except Employee.DoesNotExist:
            approved_by = None
        try:
            leave.approve(approved_by=approved_by, remarks=remarks)
        except ValidationError as error:
            messages.error(request, '; '.join(error.messages))
        else:
            messages.success(request, f"Leave request for {leave.employee} approved.")
    return redirect(redirect_to)

def leave_reject(request, pk):
    """Admin action to reject a request."""
    if not (request.user.is_staff or getattr(request.user, 'role', '') == 'ADMIN'):
        return redirect('dashboard')
    
    leave = get_object_or_404(LeaveRequest, pk=pk)
    redirect_to = get_safe_redirect_url(request)
    if request.method == 'POST':
        if leave.status != 'PENDING':
            messages.error(request, "Only pending leave requests can be rejected.")
            return redirect(redirect_to)

        remarks = request.POST.get('remarks', '')
        leave.status = 'REJECTED'
        leave.remarks = remarks
        try:
            leave.approved_by = request.user.employee_profile
        except Employee.DoesNotExist:
            leave.approved_by = None
        leave.approved_at = timezone.now()
        leave.save()
        messages.warning(request, f"Leave request for {leave.employee} rejected.")
    return redirect(redirect_to)

# --- Management Views ---

class LeaveTypeListView(LoginRequiredMixin, AdminAccessMixin, ListView):
    model = LeaveType
    template_name = 'leaves/leave_type_list.html'
    context_object_name = 'leave_types'

class LeaveTypeCreateView(LoginRequiredMixin, AdminAccessMixin, CreateView):
    model = LeaveType
    form_class = LeaveTypeForm
    template_name = 'leaves/leave_type_form.html'
    success_url = reverse_lazy('leave_type_list')

    def form_valid(self, form):
        messages.success(self.request, 'Leave setting created successfully.')
        return super().form_valid(form)

class LeaveTypeUpdateView(LoginRequiredMixin, AdminAccessMixin, UpdateView):
    model = LeaveType
    form_class = LeaveTypeForm
    template_name = 'leaves/leave_type_form.html'
    success_url = reverse_lazy('leave_type_list')

    def form_valid(self, form):
        messages.success(self.request, 'Leave setting updated successfully.')
        return super().form_valid(form)

class LeaveTypeDeleteView(LoginRequiredMixin, AdminAccessMixin, DeleteView):
    model = LeaveType
    template_name = 'setup/confirm_delete.html'
    success_url = reverse_lazy('leave_type_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'setup_title': 'Delete Leave Setting',
            'cancel_url': reverse_lazy('leave_type_list'),
        })
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Leave setting deleted successfully.')
        return super().form_valid(form)

class DepartmentListView(LoginRequiredMixin, AdminAccessMixin, ListView):
    model = Department
    template_name = 'setup/department_list.html'
    context_object_name = 'departments'

    def get_queryset(self):
        return Department.objects.select_related('manager__user').order_by('name')

class DepartmentCreateView(LoginRequiredMixin, AdminAccessMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'setup/department_form.html'
    success_url = reverse_lazy('department_list')

    def form_valid(self, form):
        messages.success(self.request, 'Department created successfully.')
        return super().form_valid(form)

class DepartmentUpdateView(LoginRequiredMixin, AdminAccessMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'setup/department_form.html'
    success_url = reverse_lazy('department_list')

    def form_valid(self, form):
        messages.success(self.request, 'Department updated successfully.')
        return super().form_valid(form)

class DepartmentDeleteView(LoginRequiredMixin, AdminAccessMixin, DeleteView):
    model = Department
    template_name = 'setup/confirm_delete.html'
    success_url = reverse_lazy('department_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'setup_title': 'Delete Department',
            'cancel_url': reverse_lazy('department_list'),
        })
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Department deleted successfully.')
        return super().form_valid(form)

class DesignationListView(LoginRequiredMixin, AdminAccessMixin, ListView):
    model = EmpDesignation
    template_name = 'setup/designation_list.html'
    context_object_name = 'designations'

    def get_queryset(self):
        return EmpDesignation.objects.select_related('department', 'created_by').order_by('designation_name')

class DesignationCreateView(LoginRequiredMixin, AdminAccessMixin, CreateView):
    model = EmpDesignation
    form_class = EmpDesignationForm
    template_name = 'setup/designation_form.html'
    success_url = reverse_lazy('designation_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Designation created successfully.')
        return super().form_valid(form)

class DesignationUpdateView(LoginRequiredMixin, AdminAccessMixin, UpdateView):
    model = EmpDesignation
    form_class = EmpDesignationForm
    template_name = 'setup/designation_form.html'
    success_url = reverse_lazy('designation_list')

    def form_valid(self, form):
        messages.success(self.request, 'Designation updated successfully.')
        return super().form_valid(form)

class DesignationDeleteView(LoginRequiredMixin, AdminAccessMixin, DeleteView):
    model = EmpDesignation
    template_name = 'setup/confirm_delete.html'
    success_url = reverse_lazy('designation_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'setup_title': 'Delete Designation',
            'cancel_url': reverse_lazy('designation_list'),
        })
        return context

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                'This designation is assigned to employees or registrations and cannot be deleted.',
            )
            return redirect(self.success_url)
        messages.success(self.request, 'Designation deleted successfully.')
        return response

class EmployeeListView(LoginRequiredMixin, AdminAccessMixin, ListView):
    model = Employee
    template_name = 'employees/employee_list.html'
    context_object_name = 'employees'

    def get_queryset(self):
        today = timezone.localdate()
        today_login = Attendance.objects.filter(
            employee=OuterRef('pk'),
            date=today,
            check_in__isnull=False,
        ).order_by('check_in')

        queryset = Employee.objects.select_related(
            'user',
            'department',
            'designation',
            'supervisor__user',
        ).annotate(
            today_login_time=Subquery(today_login.values('check_in')[:1]),
            used_leave_days=Coalesce(
                Sum(
                    'leave_requests__total_days',
                    filter=Q(
                        leave_requests__status='APPROVED',
                        leave_requests__from_date__year=timezone.now().year,
                    ),
                ),
                0,
            ),
        ).order_by('employee_id')

        search_query = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()

        if search_query:
            queryset = queryset.filter(
                Q(employee_id__icontains=search_query)
                | Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__username__icontains=search_query)
                | Q(user__email__icontains=search_query)
                | Q(department__name__icontains=search_query)
                | Q(designation__designation_name__icontains=search_query)
            )

        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_employees = Employee.objects.all()
        for employee in context['employees']:
            leave_summary = employee.get_leave_summary(timezone.now().year)
            employee.yearly_leave_allowance = leave_summary['allowance']
            employee.used_leave_days = leave_summary['used']
            employee.leave_balance = leave_summary['balance']
            employee.uses_custom_leave = leave_summary['uses_custom_leave']

        context.update({
            'total_employees': all_employees.count(),
            'active_employees': all_employees.filter(is_active=True).count(),
            'inactive_employees': all_employees.filter(is_active=False).count(),
            'department_count': all_employees.exclude(department=None)
                .values('department').distinct().count(),
            'recent_requests': LeaveRequest.objects.select_related(
                'employee__user',
                'employee__department',
                'leave_type',
            ).order_by('-applied_at')[:10],
            'search_query': self.request.GET.get('q', '').strip(),
            'selected_status': self.request.GET.get('status', '').strip(),
        })
        return context

def _is_admin_user(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.is_staff
        or getattr(user, 'role', '') == 'ADMIN'
    )


def _employee_for_admin_edit(pk):
    return get_object_or_404(
        Employee.objects.select_related(
            'user', 'department', 'designation', 'extended_profile',
        ),
        pk=pk,
    )


def _add_employee_list_values(employee):
    summary = employee.get_leave_summary(timezone.now().year)
    employee.yearly_leave_allowance = summary['allowance']
    employee.used_leave_days = summary['used']
    employee.leave_balance = summary['balance']
    employee.uses_custom_leave = summary['uses_custom_leave']
    return employee


@login_required
@user_passes_test(_is_admin_user)
def employee_admin_edit(request, pk):
    """Return a pre-populated employee edit form for the Bootstrap modal."""
    employee = _employee_for_admin_edit(pk)
    form = EmployeeAdminEditForm(employee=employee)
    html = render_to_string(
        'employees/partials/employee_edit_form.html',
        {'form': form, 'employee': employee},
        request=request,
    )
    return JsonResponse({'ok': True, 'html': html})


@require_POST
@login_required
@user_passes_test(_is_admin_user)
def employee_admin_update(request, pk):
    """Validate and save an employee edit, returning modal/row HTML as JSON."""
    employee = _employee_for_admin_edit(pk)
    form = EmployeeAdminEditForm(
        request.POST,
        request.FILES,
        employee=employee,
    )
    if not form.is_valid():
        html = render_to_string(
            'employees/partials/employee_edit_form.html',
            {'form': form, 'employee': employee},
            request=request,
        )
        return JsonResponse({'ok': False, 'html': html}, status=422)

    employee = form.save()
    employee = Employee.objects.select_related(
        'user', 'department', 'designation',
    ).get(pk=employee.pk)
    _add_employee_list_values(employee)
    row_html = render_to_string(
        'employees/partials/employee_row.html',
        {'employee': employee},
        request=request,
    )
    all_employees = Employee.objects.all()
    return JsonResponse({
        'ok': True,
        'message': 'Employee information updated successfully.',
        'row_html': row_html,
        'stats': {
            'total': all_employees.count(),
            'active': all_employees.filter(is_active=True).count(),
            'inactive': all_employees.filter(is_active=False).count(),
        },
    })


@require_POST
@login_required
@user_passes_test(_is_admin_user)
def department_quick_create(request):
    """Create a department from an employee modal without leaving the page."""
    form = QuickDepartmentForm(request.POST)
    if not form.is_valid():
        return JsonResponse({
            'ok': False,
            'errors': {
                name: [str(error) for error in errors]
                for name, errors in form.errors.items()
            },
        }, status=422)

    try:
        department = form.save()
    except IntegrityError:
        return JsonResponse({
            'ok': False,
            'errors': {
                'name': ['A department with this name already exists.'],
            },
        }, status=409)

    return JsonResponse({
        'ok': True,
        'department': {
            'id': department.pk,
            'name': department.name,
        },
        'message': f'{department.name} was added successfully.',
    }, status=201)
