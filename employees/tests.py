from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .forms import EmployeeProfileForm
from .models import EmpDesignation, EmpProfile, Employee


User = get_user_model()


class EmployeeIdTests(TestCase):
    def create_employee(self, username, employee_id=''):
        user = User.objects.create_user(
            username=username,
            password='test-password',
        )
        return Employee.objects.create(
            user=user,
            employee_id=employee_id,
        )

    def test_first_employee_id_is_generated(self):
        employee = self.create_employee('first-employee')

        self.assertEqual(employee.employee_id, 'EMP0001')

    def test_employee_ids_increment_from_latest_employee(self):
        self.create_employee('first-employee')
        second_employee = self.create_employee('second-employee')

        self.assertEqual(second_employee.employee_id, 'EMP0002')

    def test_manual_employee_id_is_ignored_during_creation(self):
        employee = self.create_employee('manual-id-employee', 'MANUAL-ID')

        self.assertEqual(employee.employee_id, 'EMP0001')

    def test_employee_id_is_not_modified_during_updates(self):
        employee = self.create_employee('immutable-id-employee')
        employee.employee_id = 'EMP9999'
        employee.is_active = False
        employee.save()
        employee.refresh_from_db()

        self.assertEqual(employee.employee_id, 'EMP0001')
        self.assertFalse(employee.is_active)

    def test_employee_id_is_not_in_employee_edit_form(self):
        self.assertNotIn('employee_id', EmployeeProfileForm().fields)


class EmpDesignationTests(TestCase):
    def test_designation_generates_retail_code_and_defaults_to_active(self):
        designation = EmpDesignation.objects.create(
            designation_name='Store Manager',
        )

        self.assertTrue(designation.designation_id.startswith('DSG'))
        self.assertEqual(len(designation.designation_id), 12)
        self.assertEqual(designation.status, EmpDesignation.Status.ACTIVE)
        self.assertEqual(str(designation), 'Store Manager')

    def test_designation_names_are_case_insensitively_unique(self):
        EmpDesignation.objects.create(designation_name='Cashier')
        duplicate = EmpDesignation(designation_name=' cashier ')

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_designation_name_is_trimmed_when_saved(self):
        designation = EmpDesignation.objects.create(
            designation_name='  Inventory Officer  ',
        )

        self.assertEqual(designation.designation_name, 'Inventory Officer')

    def test_assigned_designation_is_protected_from_deletion(self):
        user = User.objects.create_user(
            username='cashier-user',
            password='test-password',
        )
        designation = EmpDesignation.objects.create(
            designation_name='Cashier',
        )
        Employee.objects.create(
            user=user,
            designation=designation,
        )

        with self.assertRaises(ProtectedError):
            designation.delete()


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
        self.designation = EmpDesignation.objects.create(
            designation_name='Developer',
        )
        self.employee = Employee.objects.create(
            user=self.user,
            designation=self.designation,
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
        self.assertEqual(self.employee.designation, self.designation)

    def test_invalid_emergency_contact_is_rejected(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('employee_profile_edit'), {
            'emergency_contact_number': 'invalid',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid emergency contact number')
