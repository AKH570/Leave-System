from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from employees.models import Employee

from .models import Attendance


User = get_user_model()


class EmployeeLoginAttendanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='attendance-employee',
            password='test-password',
        )
        self.employee = Employee.objects.create(user=self.user)

    def test_successful_login_records_todays_first_login_time(self):
        self.client.post(reverse('accounts:login'), {
            'username': self.user.username,
            'password': 'test-password',
        })

        attendance = Attendance.objects.get(
            employee=self.employee,
            date=timezone.localdate(),
        )
        self.assertEqual(attendance.status, 'PRESENT')
        self.assertIsNotNone(attendance.check_in)

        first_login_time = attendance.check_in
        self.client.logout()
        self.client.post(reverse('accounts:login'), {
            'username': self.user.username,
            'password': 'test-password',
        })
        attendance.refresh_from_db()
        self.assertEqual(attendance.check_in, first_login_time)

    def test_employee_list_shows_only_todays_login_to_admin(self):
        Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate() - timedelta(days=1),
            check_in=time(8, 30),
            status='PRESENT',
        )
        admin = User.objects.create_user(
            username='attendance-admin',
            password='test-password',
            role='ADMIN',
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('employee_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Attendance Status')
        self.assertContains(response, 'Absent')
        self.assertContains(response, 'Not logged in')

    def test_non_admin_cannot_view_employee_attendance_list(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('employee_list'))

        self.assertEqual(response.status_code, 403)


class AttendanceHistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='history-employee',
            password='test-password',
            role='EMPLOYEE',
        )
        self.employee = Employee.objects.create(user=self.user)
        self.other_user = User.objects.create_user(
            username='other-employee',
            password='test-password',
            role='EMPLOYEE',
        )
        self.other_employee = Employee.objects.create(user=self.other_user)
        self.client.force_login(self.user)

    def test_history_only_contains_logged_in_employees_records(self):
        own, _ = Attendance.objects.update_or_create(
            employee=self.employee,
            date=timezone.localdate(),
            defaults={
                'check_in': time(9),
                'check_out': time(17, 30),
                'status': 'PRESENT',
                'remarks': 'Own record',
            },
        )
        Attendance.objects.update_or_create(
            employee=self.other_employee,
            date=timezone.localdate(),
            defaults={'status': 'ABSENT', 'remarks': 'Private record'},
        )

        response = self.client.get(reverse('attendance_history'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Own record')
        self.assertContains(response, '8h 30m')
        self.assertNotContains(response, 'Private record')
        self.assertEqual(list(response.context['attendances']), [own])

    def test_history_filters_by_date_and_exports_csv(self):
        today = timezone.localdate()
        Attendance.objects.update_or_create(
            employee=self.employee,
            date=today,
            defaults={'status': 'PRESENT'},
        )
        Attendance.objects.create(
            employee=self.employee,
            date=today - timedelta(days=1),
            status='LATE',
        )

        response = self.client.get(
            reverse('attendance_history'),
            {'q': today.isoformat()},
        )
        self.assertEqual(len(response.context['attendances']), 1)
        self.assertEqual(response.context['total_present'], 1)

        export = self.client.get(
            reverse('attendance_history'),
            {'q': today.isoformat(), 'export': 'csv'},
        )
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn(today.isoformat(), export.content.decode('utf-8-sig'))

    def test_admin_cannot_access_employee_attendance_history(self):
        admin = User.objects.create_user(
            username='history-admin',
            password='test-password',
            role='ADMIN',
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('attendance_history'))

        self.assertEqual(response.status_code, 403)
