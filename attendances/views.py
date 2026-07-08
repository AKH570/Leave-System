import csv
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

from employees.models import Employee

from .models import Attendance


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
