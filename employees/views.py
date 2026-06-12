from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from .models import Employee, LeaveRequest, LeaveType
from .forms import LeaveRequestForm, LeaveApprovalForm, LeaveTypeForm

class AdminAccessMixin(UserPassesTestMixin):
    """Ensures only Admin/HR can access certain views."""
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_staff or getattr(self.request.user, 'role', '') == 'ADMIN'
        )

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
    success_url = reverse_lazy('leave_history')

    def form_valid(self, form):
        try:
            form.instance.employee = self.request.user.employee_profile
            messages.success(self.request, "Leave request submitted successfully.")
            return super().form_valid(form)
        except Employee.DoesNotExist:
            messages.error(self.request, "Employee profile not found. Please contact Admin.")
            return redirect('dashboard')

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

def leave_cancel(request, pk):
    """Allows employees to cancel only PENDING requests."""
    leave = get_object_or_404(LeaveRequest, pk=pk, employee__user=request.user)
    if leave.status == 'PENDING':
        leave.status = 'CANCELLED'
        leave.save()
        messages.success(request, "Leave request cancelled.")
    else:
        messages.error(request, "Only pending requests can be cancelled.")
    return redirect('leave_history')

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
    if request.method == 'POST':
        remarks = request.POST.get('remarks', '')
        leave.status = 'APPROVED'
        leave.remarks = remarks
        leave.approved_by = request.user.employee_profile
        leave.approved_at = timezone.now()
        leave.save()
        messages.success(request, f"Leave request for {leave.employee} approved.")
    return redirect('dashboard')

def leave_reject(request, pk):
    """Admin action to reject a request."""
    if not (request.user.is_staff or getattr(request.user, 'role', '') == 'ADMIN'):
        return redirect('dashboard')
    
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.method == 'POST':
        remarks = request.POST.get('remarks', '')
        leave.status = 'REJECTED'
        leave.remarks = remarks
        leave.approved_by = request.user.employee_profile
        leave.approved_at = timezone.now()
        leave.save()
        messages.warning(request, f"Leave request for {leave.employee} rejected.")
    return redirect('dashboard')

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

class EmployeeListView(LoginRequiredMixin, AdminAccessMixin, ListView):
    model = Employee
    template_name = 'employees/employee_list.html'
    context_object_name = 'employees'
