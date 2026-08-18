import csv
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.utils import timezone

from employees.models import Employee
from employees.models import LeaveRequest
from holidays.models import Holiday

from .models import Attendance
from .reporting import daily_summary, date_span, format_duration


class AttendanceReportMixin(LoginRequiredMixin, PermissionRequiredMixin):
    permission_required = 'accounts.view_reports'
    raise_exception = True

    def render_to_response(self, context, **response_kwargs):
        if isinstance(context, HttpResponse):
            return context
        return super().render_to_response(context, **response_kwargs)

    @staticmethod
    def parse_date(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def employees(self):
        return Employee.objects.filter(is_active=True).select_related(
            'user', 'department', 'designation'
        ).order_by('employee_id')

    def report_data(self, employees, start, end):
        employee_list = list(employees)
        ids = [employee.pk for employee in employee_list]
        attendances = Attendance.objects.filter(
            employee_id__in=ids, date__range=(start, end)
        ).select_related('employee').prefetch_related('logs')
        attendance_map = {(item.employee_id, item.date): item for item in attendances}
        leaves = LeaveRequest.objects.filter(
            employee_id__in=ids, status='APPROVED',
            from_date__lte=end, to_date__gte=start,
        ).select_related('leave_type')
        holidays = Holiday.objects.filter(date__range=(start, end))
        holiday_map = {item.date: item for item in holidays}
        leave_map = {}
        for leave in leaves:
            for day in date_span(max(start, leave.from_date), min(end, leave.to_date)):
                leave_map[(leave.employee_id, day)] = leave
        result = []
        for employee in employee_list:
            for day in date_span(start, end):
                attendance = attendance_map.get((employee.pk, day))
                result.append(daily_summary(
                    employee, day, attendance,
                    list(attendance.logs.all()) if attendance else (),
                    leave_map.get((employee.pk, day)), holiday_map.get(day),
                ))
        return result

    def csv_response(self, filename, title, rows):
        if not self.request.user.has_perm('accounts.export_reports'):
            raise PermissionDenied
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(['LeaveBox', title])
        writer.writerow(['Generated', timezone.localtime().strftime('%Y-%m-%d %I:%M %p')])
        writer.writerows(rows)
        return response


class EmployeeDailyReportView(AttendanceReportMixin, TemplateView):
    template_name = 'attendances/employee_daily_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee_id = self.request.GET.get('employee', '')
        selected_date = self.parse_date(self.request.GET.get('date'))
        report = None
        error = ''
        if employee_id.isdigit() and selected_date:
            if selected_date > timezone.localdate():
                error = 'Future dates are not allowed.'
            else:
                employee = self.employees().filter(pk=employee_id).first()
                if employee:
                    report = self.report_data([employee], selected_date, selected_date)[0]
        if self.request.GET.get('export') == 'csv' and report:
            event_rows = [['Time', 'Activity']] + [
                [at.strftime('%Y-%m-%d %I:%M %p'), kind.replace('_', '-').title()]
                for kind, at in report['events']
            ]
            return self.csv_response('employee-daily-attendance.csv', 'Employee Daily Attendance', event_rows)
        context.update({'employees': self.employees(), 'report': report, 'error': error,
                        'selected_employee': employee_id, 'selected_date': self.request.GET.get('date', '')})
        return context


class AllEmployeesDailyReportView(AttendanceReportMixin, TemplateView):
    template_name = 'attendances/all_employees_daily_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_date = self.parse_date(self.request.GET.get('date'))
        rows, error = [], ''
        if selected_date:
            if selected_date > timezone.localdate():
                error = 'Future dates are not allowed.'
            else:
                rows = self.report_data(self.employees(), selected_date, selected_date)
        if self.request.GET.get('export') == 'csv' and rows:
            export_rows = [['SL', 'Employee ID', 'Employee', 'Department', 'Designation', 'Date', 'First Check-In', 'Last Check-Out', 'Check-Ins', 'Check-Outs', 'Working Hours', 'Status']]
            export_rows += [[i, row['employee'].employee_id, row['employee'].user.get_full_name() or row['employee'].user.username,
                str(row['employee'].department or ''), str(row['employee'].designation or ''), row['date'].isoformat(),
                row['first_check_in'].strftime('%I:%M %p') if row['first_check_in'] else '',
                row['last_check_out'].strftime('%I:%M %p') if row['last_check_out'] else '', row['check_in_count'], row['check_out_count'], row['duration_display'], row['status']]
                for i, row in enumerate(rows, 1)]
            return self.csv_response('all-employees-daily-attendance.csv', 'All Employees Daily Attendance', export_rows)
        context.update({'rows': rows, 'error': error, 'selected_date': self.request.GET.get('date', '')})
        return context


class EmployeeRangeReportView(AttendanceReportMixin, TemplateView):
    template_name = 'attendances/employee_range_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee_id = self.request.GET.get('employee', '')
        start = self.parse_date(self.request.GET.get('from_date'))
        end = self.parse_date(self.request.GET.get('to_date'))
        rows, employee, error = [], None, ''
        if employee_id.isdigit() and start and end:
            if start > end:
                error = 'From date cannot be later than to date.'
            elif end > timezone.localdate():
                error = 'Future dates are not allowed.'
            else:
                employee = self.employees().filter(pk=employee_id).first()
                if employee:
                    rows = self.report_data([employee], start, end)
        present = [row for row in rows if row['status'] in ('Present', 'Late')]
        total_duration = sum((row['duration'] for row in rows), timedelta())
        summary = {
            'total_days': len(rows), 'present_days': len(present),
            'absent_days': sum(row['status'] == 'Absent' for row in rows),
            'leave_days': sum(row['status'] == 'On Leave' for row in rows),
            'holidays': sum(row['status'] == 'Holiday' for row in rows),
            'late_days': sum(row['status'] == 'Late' for row in rows),
            'total_check_ins': sum(row['check_in_count'] for row in rows),
            'total_check_outs': sum(row['check_out_count'] for row in rows),
            'total_working_hours': format_duration(total_duration),
            'average_working_hours': format_duration(total_duration / len(present)) if present else '0h 00m',
        }
        if self.request.GET.get('export') == 'csv' and rows:
            export_rows = [['Date', 'Day', 'First Check-In', 'Last Check-Out', 'Check-Ins', 'Check-Outs', 'Working Hours', 'Status', 'Leave/Holiday']]
            export_rows += [[row['date'].isoformat(), row['date'].strftime('%A'),
                row['first_check_in'].strftime('%I:%M %p') if row['first_check_in'] else '',
                row['last_check_out'].strftime('%I:%M %p') if row['last_check_out'] else '', row['check_in_count'], row['check_out_count'], row['duration_display'], row['status'], row['info']] for row in rows]
            return self.csv_response('employee-attendance-range.csv', 'Employee Date Range Attendance', export_rows)
        context.update({'employees': self.employees(), 'employee': employee, 'rows': rows, 'summary': summary,
                        'error': error, 'selected_employee': employee_id,
                        'from_date': self.request.GET.get('from_date', ''), 'to_date': self.request.GET.get('to_date', '')})
        return context


class AttendanceHistoryView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'attendances/attendance_history.html'
    raise_exception = True

    def test_func(self):
        user = self.request.user
        return (
            user.is_authenticated
            and not user.is_superuser
            and not user.is_staff
            and getattr(user, 'role', '') == 'EMPLOYEE'
        )

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if (
                request.user.is_superuser
                or request.user.is_staff
                or getattr(request.user, 'role', '') != 'EMPLOYEE'
            ):
                raise PermissionDenied
            try:
                self.employee = Employee.objects.get(user=request.user)
            except Employee.DoesNotExist:
                messages.error(
                    request,
                    'Employee profile not found. Please contact Admin.',
                )
                return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    @staticmethod
    def _parse_date(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    def get_queryset(self):
        # Ownership is derived exclusively from the authenticated user. There is
        # deliberately no employee identifier accepted from the request.
        queryset = Attendance.objects.filter(employee=self.employee)
        params = self.request.GET

        from_date = self._parse_date(params.get('from_date'))
        to_date = self._parse_date(params.get('to_date'))
        search_date = self._parse_date(params.get('q'))
        month = params.get('month', '').strip()
        year = params.get('year', '').strip()

        if from_date:
            queryset = queryset.filter(date__gte=from_date)
        if to_date:
            queryset = queryset.filter(date__lte=to_date)
        if search_date:
            queryset = queryset.filter(date=search_date)
        if month.isdigit() and 1 <= int(month) <= 12:
            queryset = queryset.filter(date__month=int(month))
        if year.isdigit() and 1900 <= int(year) <= 9999:
            queryset = queryset.filter(date__year=int(year))

        return queryset.order_by('-date')

    @staticmethod
    def _safe_csv_value(value):
        text = str(value or '')
        if text.startswith(('=', '+', '-', '@')):
            return "'" + text
        return text

    def _csv_response(self, records):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            'attachment; filename="my-attendance-history.csv"'
        )
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Check-in Time', 'Check-out Time',
            'Total Working Hours', 'Attendance Status', 'Remarks',
        ])
        for record in records.iterator():
            writer.writerow([
                record.date.isoformat(),
                record.check_in.strftime('%I:%M %p') if record.check_in else '',
                record.check_out.strftime('%I:%M %p') if record.check_out else '',
                record.working_hours_display,
                record.get_status_display(),
                self._safe_csv_value(record.remarks),
            ])
        return response

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        if request.GET.get('export') == 'csv':
            return self._csv_response(self.object_list)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filtered_records = self.object_list
        paginator = Paginator(filtered_records, 15)
        page_obj = paginator.get_page(self.request.GET.get('page'))

        status_totals = filtered_records.aggregate(
            total_present=Count('pk', filter=Q(status='PRESENT')),
            total_absent=Count('pk', filter=Q(status='ABSENT')),
            total_late=Count('pk', filter=Q(status='LATE')),
        )
        total_seconds = 0
        for record_date, check_in, check_out in filtered_records.values_list(
            'date', 'check_in', 'check_out',
        ).iterator():
            if not check_in or not check_out:
                continue
            start = datetime.combine(record_date, check_in)
            end = datetime.combine(record_date, check_out)
            if end < start:
                end += timedelta(days=1)
            total_seconds += (end - start).total_seconds()
        total_minutes = int(total_seconds // 60)
        hours, minutes = divmod(total_minutes, 60)

        query_params = self.request.GET.copy()
        query_params.pop('page', None)
        query_params.pop('export', None)
        context.update({
            'employee': self.employee,
            'page_obj': page_obj,
            'attendances': page_obj.object_list,
            **status_totals,
            'total_working_hours': f'{hours}h {minutes:02d}m',
            'filter_query': query_params.urlencode(),
            'selected_month': self.request.GET.get('month', ''),
            'selected_year': self.request.GET.get('year', ''),
            'from_date': self.request.GET.get('from_date', ''),
            'to_date': self.request.GET.get('to_date', ''),
            'search_date': self.request.GET.get('q', ''),
            'year_options': range(datetime.now().year, 1999, -1),
        })
        return context
