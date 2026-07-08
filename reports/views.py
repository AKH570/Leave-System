import csv
from datetime import datetime

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.views.generic import TemplateView

from attendances.models import Attendance
from departments.models import Department
from employees.models import Employee, LeaveRequest, LeaveType


class AdminReportMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True
    paginate_by = 20

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or user.is_staff
            or getattr(user, 'role', '') == 'ADMIN'
        )

    @staticmethod
    def parse_date(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def safe_csv_value(value):
        text = str(value or '')
        return "'" + text if text.startswith(('=', '+', '-', '@')) else text

    def csv_response(self, filename, headers, rows):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(headers)
        writer.writerows(rows)
        return response

    def filter_context(self):
        query = self.request.GET.copy()
        query.pop('page', None)
        query.pop('export', None)
        return {
            'filter_query': query.urlencode(),
            'from_date': self.request.GET.get('from_date', ''),
            'to_date': self.request.GET.get('to_date', ''),
            'selected_employee': self.request.GET.get('employee', ''),
            'selected_department': self.request.GET.get('department', ''),
        }

    def paginate(self, queryset):
        return Paginator(queryset, self.paginate_by).get_page(self.request.GET.get('page'))


class LeaveReportView(AdminReportMixin, TemplateView):
    template_name = 'leaves/leave_report.html'

    def get_queryset(self):
        queryset = LeaveRequest.objects.select_related(
            'employee__user', 'employee__department', 'leave_type', 'approved_by__user',
        )
        params = self.request.GET
        from_date = self.parse_date(params.get('from_date'))
        to_date = self.parse_date(params.get('to_date'))
        if from_date:
            queryset = queryset.filter(to_date__gte=from_date)
        if to_date:
            queryset = queryset.filter(from_date__lte=to_date)
        if params.get('employee', '').isdigit():
            queryset = queryset.filter(employee_id=params['employee'])
        if params.get('department', '').isdigit():
            queryset = queryset.filter(employee__department_id=params['department'])
        if params.get('leave_type', '').isdigit():
            queryset = queryset.filter(leave_type_id=params['leave_type'])
        if params.get('status') in dict(LeaveRequest.STATUS_CHOICES):
            queryset = queryset.filter(status=params['status'])
        return queryset.order_by('-from_date', '-applied_at')

    def export_csv(self, records):
        rows = ([
            record.employee.employee_id,
            self.safe_csv_value(record.employee.user.get_full_name() or record.employee.user.username),
            self.safe_csv_value(record.employee.department or ''), record.leave_type.name,
            record.from_date.isoformat(), record.to_date.isoformat(), record.total_days,
            record.get_status_display(), record.applied_at.date().isoformat(),
            self.safe_csv_value(record.reason), self.safe_csv_value(record.remarks),
        ] for record in records.iterator())
        return self.csv_response(
            'leave-report.csv',
            ['Employee ID', 'Employee', 'Department', 'Leave Type', 'From', 'To',
             'Days', 'Status', 'Applied On', 'Reason', 'Remarks'], rows,
        )

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if request.GET.get('export') == 'csv':
            return self.export_csv(self.object_list)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        totals = self.object_list.aggregate(total_requests=Count('pk'), total_days=Sum('total_days'))
        context.update(self.filter_context())
        context.update({
            'page_obj': self.paginate(self.object_list),
            'total_requests': totals['total_requests'], 'total_days': totals['total_days'] or 0,
            'approved_count': self.object_list.filter(status='APPROVED').count(),
            'pending_count': self.object_list.filter(status='PENDING').count(),
            'employees': Employee.objects.select_related('user').order_by('employee_id'),
            'departments': Department.objects.order_by('name'),
            'leave_types': LeaveType.objects.order_by('name'),
            'status_choices': LeaveRequest.STATUS_CHOICES,
            'selected_leave_type': self.request.GET.get('leave_type', ''),
            'selected_status': self.request.GET.get('status', ''),
        })
        return context


class AttendanceReportView(AdminReportMixin, TemplateView):
    template_name = 'attendance/attendance_report.html'

    def get_queryset(self):
        queryset = Attendance.objects.select_related('employee__user', 'employee__department')
        params = self.request.GET
        from_date = self.parse_date(params.get('from_date'))
        to_date = self.parse_date(params.get('to_date'))
        if from_date:
            queryset = queryset.filter(date__gte=from_date)
        if to_date:
            queryset = queryset.filter(date__lte=to_date)
        if params.get('employee', '').isdigit():
            queryset = queryset.filter(employee_id=params['employee'])
        if params.get('department', '').isdigit():
            queryset = queryset.filter(employee__department_id=params['department'])
        if params.get('status') in dict(Attendance.STATUS_CHOICES):
            queryset = queryset.filter(status=params['status'])
        return queryset.order_by('-date', 'employee__employee_id')

    def export_csv(self, records):
        rows = ([
            record.date.isoformat(), record.employee.employee_id,
            self.safe_csv_value(record.employee.user.get_full_name() or record.employee.user.username),
            self.safe_csv_value(record.employee.department or ''),
            record.check_in.strftime('%I:%M %p') if record.check_in else '',
            record.check_out.strftime('%I:%M %p') if record.check_out else '',
            record.working_hours_display, record.get_status_display(),
            self.safe_csv_value(record.remarks),
        ] for record in records.iterator())
        return self.csv_response(
            'attendance-report.csv',
            ['Date', 'Employee ID', 'Employee', 'Department', 'Check In', 'Check Out',
             'Working Hours', 'Status', 'Remarks'], rows,
        )

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if request.GET.get('export') == 'csv':
            return self.export_csv(self.object_list)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counts = {item['status']: item['total'] for item in self.object_list.values('status').annotate(total=Count('pk'))}
        context.update(self.filter_context())
        context.update({
            'page_obj': self.paginate(self.object_list), 'total_records': self.object_list.count(),
            'present_count': counts.get('PRESENT', 0), 'absent_count': counts.get('ABSENT', 0),
            'late_count': counts.get('LATE', 0),
            'employees': Employee.objects.select_related('user').order_by('employee_id'),
            'departments': Department.objects.order_by('name'),
            'status_choices': Attendance.STATUS_CHOICES,
            'selected_status': self.request.GET.get('status', ''),
        })
        return context
