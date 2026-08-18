from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from employees.models import Employee, LeaveRequest, LeaveType
from holidays.models import Holiday

from .models import Attendance, AttendanceLog
from .reporting import daily_summary


class AttendanceReportingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='report-employee', password='pw')
        self.employee = Employee.objects.create(user=self.user)
        self.day = timezone.localdate() - timedelta(days=2)

    def log(self, attendance, kind, hour, minute=0):
        value = timezone.make_aware(datetime.combine(self.day, time(hour, minute)))
        return AttendanceLog.objects.create(
            attendance=attendance, employee=self.employee,
            event_type=kind, event_time=value,
        )

    def summary(self, attendance=None):
        logs = list(attendance.logs.all()) if attendance else []
        return daily_summary(self.employee, self.day, attendance, logs)

    def test_one_complete_session(self):
        attendance = Attendance.objects.create(employee=self.employee, date=self.day, status='PRESENT')
        self.log(attendance, 'CHECK_IN', 9); self.log(attendance, 'CHECK_OUT', 17)
        result = self.summary(attendance)
        self.assertEqual(result['status'], 'Present')
        self.assertEqual(result['duration'], timedelta(hours=8))

    def test_multiple_sessions_are_added(self):
        attendance = Attendance.objects.create(employee=self.employee, date=self.day, status='PRESENT')
        for kind, hour in [('CHECK_IN', 9), ('CHECK_OUT', 13), ('CHECK_IN', 14), ('CHECK_OUT', 18)]:
            self.log(attendance, kind, hour)
        result = self.summary(attendance)
        self.assertEqual((result['check_in_count'], result['check_out_count']), (2, 2))
        self.assertEqual(result['duration_display'], '8h 00m')

    def test_unmatched_and_duplicate_events_are_incomplete(self):
        attendance = Attendance.objects.create(employee=self.employee, date=self.day, status='PRESENT')
        self.log(attendance, 'CHECK_IN', 9); self.log(attendance, 'CHECK_IN', 10)
        self.assertEqual(self.summary(attendance)['status'], 'Incomplete Attendance')

    def test_no_attendance_is_absent(self):
        self.assertEqual(self.summary()['status'], 'Absent')

    def test_approved_leave_and_holiday(self):
        leave_type = LeaveType.objects.create(name=LeaveType.CASUAL, yearly_limit=10)
        leave = LeaveRequest.objects.create(employee=self.employee, leave_type=leave_type,
            from_date=self.day, to_date=self.day, total_days=1, reason='Test', status='APPROVED')
        holiday = Holiday.objects.create(name='Holiday', date=self.day)
        self.assertEqual(daily_summary(self.employee, self.day, leave=leave)['status'], 'On Leave')
        self.assertEqual(daily_summary(self.employee, self.day, holiday=holiday)['status'], 'Holiday')

    def test_legacy_daily_fields_remain_compatible(self):
        attendance = Attendance.objects.create(employee=self.employee, date=self.day,
            check_in=time(9), check_out=time(17), status='PRESENT')
        self.assertEqual(self.summary(attendance)['duration'], timedelta(hours=8))


class AttendanceReportViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='report-admin', password='pw', role='ADMIN')
        self.admin.user_permissions.add(Permission.objects.get(codename='view_reports'))
        self.employee_user = User.objects.create_user(username='range-employee', password='pw')
        self.employee = Employee.objects.create(user=self.employee_user)
        self.day = timezone.localdate() - timedelta(days=1)

    def test_all_employee_daily_includes_employee_without_attendance(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('all_employees_daily_attendance_report'), {'date': self.day})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.employee.employee_id)
        self.assertContains(response, 'Absent')

    def test_date_range_includes_every_date(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('employee_range_attendance_report'), {
            'employee': self.employee.pk, 'from_date': self.day - timedelta(days=2), 'to_date': self.day,
        })
        self.assertEqual(len(response.context['rows']), 3)

    def test_employee_is_forbidden_from_admin_reports(self):
        self.client.force_login(self.employee_user)
        response = self.client.get(reverse('all_employees_daily_attendance_report'), {'date': self.day})
        self.assertEqual(response.status_code, 403)

    def test_invalid_and_future_ranges_are_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('employee_range_attendance_report'), {
            'employee': self.employee.pk, 'from_date': self.day, 'to_date': self.day - timedelta(days=1),
        })
        self.assertContains(response, 'From date cannot be later')
