from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from employees.models import Employee, LeaveRequest

@login_required
def dashboard(request):
    user = request.user
    is_admin = user.is_superuser or user.is_staff or getattr(user, 'role', '') == 'ADMIN'

    if is_admin:
        # Admin/HR Stats
        now = timezone.now()
        current_month_requests = LeaveRequest.objects.filter(
            applied_at__month=now.month,
            applied_at__year=now.year
        )
        recent_requests = (
            LeaveRequest.objects
            .select_related('employee__user', 'employee__department', 'leave_type')
            .order_by('-applied_at')[:10]
        )

        context = {
            'total_employees': Employee.objects.count(),
            'pending_requests_count': LeaveRequest.objects.filter(status='PENDING').count(),
            'approved_this_month': current_month_requests.filter(status='APPROVED').count(),
            'rejected_this_month': current_month_requests.filter(status='REJECTED').count(),
            'recent_requests': recent_requests,
            'today': now,
        }
        return render(request, 'dashboard/admin_dashboard.html', context)
    else:
        # Employee Stats
        try:
            employee = user.employee_profile
            approved_leaves = LeaveRequest.objects.filter(employee=employee, status='APPROVED')
            leave_summary = employee.get_leave_summary(timezone.now().year)
            
            context = {
                'leave_balance': leave_summary['balance'],
                'used_leave': leave_summary['used'],
                'uses_custom_leave': leave_summary['uses_custom_leave'],
                'pending_count': LeaveRequest.objects.filter(employee=employee, status='PENDING').count(),
                'approved_count': approved_leaves.count(),
                'leave_history': LeaveRequest.objects.filter(employee=employee).order_by('-applied_at'),
                'messages_in_content': True,
            }
            return render(request, 'dashboard/employee_dashboard.html', context)
        except Employee.DoesNotExist:
            # Handle users without an employee profile
            return render(request, 'dashboard/no_profile.html')
