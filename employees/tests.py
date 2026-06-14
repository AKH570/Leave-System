from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import EmpProfile, Employee


User = get_user_model()


class EmployeeProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='profile-user',
            password='test-password',
            first_name='Profile',
            last_name='User',
            email='profile@example.com',
            phone='+8801700000000',
            role='EMPLOYEE',
        )
        self.employee = Employee.objects.create(
            employee_id='EMP-PROFILE-1',
            user=self.user,
            designation='Developer',
        )

    def test_profile_pages_require_login(self):
        response = self.client.get(reverse('employee_profile'))
        self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse('employee_profile_edit'))
        self.assertEqual(response.status_code, 302)

    def test_my_profile_creates_missing_extended_profile(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('employee_profile'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(EmpProfile.objects.filter(employee=self.employee).exists())
        self.assertContains(response, self.employee.employee_id)
        self.assertContains(response, self.user.email)

    def test_employee_can_update_only_additional_profile_fields(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('employee_profile_edit'), {
            'gender': 'MALE',
            'blood_group': 'A+',
            'identification_no': 'NID-1234567890',
            'nationality': 'Bangladeshi',
            'present_address': 'Present address',
            'permanent_address': 'Permanent address',
            'emergency_contact_name': 'Emergency Person',
            'emergency_contact_relationship': 'Sibling',
            'emergency_contact_number': '+8801800000000',
            'bio': 'Profile bio',
            'email': 'attempted-change@example.com',
            'designation': 'Attempted Change',
        })

        self.assertRedirects(response, reverse('employee_profile'))
        profile = EmpProfile.objects.get(employee=self.employee)
        self.assertEqual(profile.nationality, 'Bangladeshi')
        self.assertEqual(profile.identification_no, 'NID-1234567890')
        self.assertEqual(profile.emergency_contact_number, '+8801800000000')

        self.user.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(self.user.email, 'profile@example.com')
        self.assertEqual(self.employee.designation, 'Developer')

    def test_invalid_emergency_contact_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('employee_profile_edit'), {
            'emergency_contact_number': 'invalid',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid emergency contact number')
