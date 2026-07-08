import csv
import io
from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from attendances.models import Attendance
from departments.models import Department
from employees.models import Employee, LeaveRequest, LeaveType


class ReportViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.admin = user_model.objects.create_user(
            username='hr', password='test-pass', role='ADMIN',
        )
        cls.employee_user = user_model.objects.create_user(
            username='alice', first_name='Alice', last_name='Example',
            password='test-pass', role='EMPLOYEE',
        )
        cls.department = Department.objects.create(name='Engineering', code='ENG')
        cls.employee = Employee.objects.create(
            user=cls.employee_user, department=cls.department,
            joining_date=date(2025, 1, 1),
        )
        cls.leave_type = LeaveType.objects.create(name=LeaveType.CASUAL, yearly_limit=12)
        cls.leave = LeaveRequest.objects.create(
            employee=cls.employee, leave_type=cls.leave_type,
            from_date=date(2026, 7, 5), to_date=date(2026, 7, 7),
            total_days=3, reason='Family event', status='APPROVED',
        )
        cls.attendance = Attendance.objects.create(
            employee=cls.employee, date=date(2026, 7, 8),
            check_in=time(9), check_out=time(17), status='PRESENT',
            remarks='Regular day',
        )

    def test_reports_require_admin_access(self):
        self.client.force_login(self.employee_user)
        self.assertEqual(self.client.get(reverse('leave_report')).status_code, 403)
        self.assertEqual(self.client.get(reverse('attendance_report')).status_code, 403)

    def test_leave_report_filters_and_summarises(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('leave_report'), {
            'from_date': '2026-07-06', 'to_date': '2026-07-06',
            'department': self.department.pk, 'status': 'APPROVED',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_requests'], 1)
        self.assertEqual(response.context['total_days'], 3)
        self.assertContains(response, 'Alice Example')

    def test_attendance_report_filters(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('attendance_report'), {
            'from_date': '2026-07-08', 'to_date': '2026-07-08',
            'status': 'PRESENT',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_records'], 1)
        self.assertEqual(response.context['present_count'], 1)

    def test_leave_csv_export_respects_filters(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('leave_report'), {
            'status': 'APPROVED', 'export': 'csv',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0][0], 'Employee ID')
        self.assertEqual(rows[1][1], 'Alice Example')

    def test_attendance_csv_export(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('attendance_report'), {'export': 'csv'})
        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(rows[0][0], 'Date')
        self.assertEqual(rows[1][6], '8h 00m')
