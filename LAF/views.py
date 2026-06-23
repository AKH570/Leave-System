from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from employees.models import Employee, LeaveRequest
from attendances.models import Attendance

@login_required
def dashboard(request):
    user = request.user
    is_admin = user.is_superuser or user.is_staff or getattr(user, 'role', '') == 'ADMIN'

    if is_admin:
        # Admin/HR Stats
        now = timezone.now()
        today = timezone.localdate()
        current_month_requests = LeaveRequest.objects.filter(
            applied_at__month=now.month,
            applied_at__year=now.year
        )
        today_attendance = Attendance.objects.filter(
            employee=OuterRef('pk'),
            date=today,
        )
        employee_attendance = (
            Employee.objects
            .select_related('user', 'department', 'designation')
            .annotate(
                today_check_in=Subquery(today_attendance.values('check_in')[:1]),
                today_check_out=Subquery(today_attendance.values('check_out')[:1]),
            )
            .order_by('employee_id')
        )

        context = {
            'total_employees': Employee.objects.count(),
            'pending_requests_count': LeaveRequest.objects.filter(status='PENDING').count(),
            'approved_this_month': current_month_requests.filter(status='APPROVED').count(),
            'rejected_this_month': current_month_requests.filter(status='REJECTED').count(),
            'employee_attendance': employee_attendance,
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
