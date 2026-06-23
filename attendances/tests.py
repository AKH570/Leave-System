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
