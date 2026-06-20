from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import EmployeeProfileForm, LeaveRequestForm, LeaveTypeForm
from .models import EmpDesignation, EmpProfile, Employee, LeaveRequest, LeaveType


User = get_user_model()


class CustomLeaveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='custom-leave-employee',
            password='test-password',
        )
        self.employee = Employee.objects.create(
            user=self.user,
            custom_leave=5,
        )
        self.leave_type = LeaveType.objects.create(
            name=LeaveType.CASUAL,
            yearly_limit=1,
        )
        today = timezone.localdate()
        self.form_data = {
            'leave_type': self.leave_type.pk,
            'from_date': today,
            'to_date': today + timedelta(days=2),
            'reason': 'Custom allocation test',
        }

    def test_custom_leave_cannot_be_negative(self):
        self.employee.custom_leave = -1

        with self.assertRaises(ValidationError):
            self.employee.full_clean()

    def test_custom_balance_ignores_leave_type_limit(self):
        form = LeaveRequestForm(self.form_data, employee=self.employee)

        self.assertTrue(form.is_valid(), form.errors)

    def test_request_over_custom_balance_is_rejected(self):
        self.form_data['to_date'] += timedelta(days=3)
        form = LeaveRequestForm(self.form_data, employee=self.employee)

        self.assertFalse(form.is_valid())
        self.assertIn('Insufficient custom leave balance', str(form.errors))

    def test_approval_deducts_custom_balance(self):
        form = LeaveRequestForm(self.form_data, employee=self.employee)
        self.assertTrue(form.is_valid(), form.errors)
        leave = form.save()

        leave.approve(remarks='Approved')

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.custom_leave, 2)
        self.assertEqual(leave.status, 'APPROVED')

    def test_approval_does_not_overdraw_changed_custom_balance(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            from_date=self.form_data['from_date'],
            to_date=self.form_data['to_date'],
            total_days=3,
            reason='Balance changed while pending',
        )
        self.employee.custom_leave = 2
        self.employee.save(update_fields=['custom_leave'])

        with self.assertRaisesMessage(ValidationError, '2 days remaining'):
            leave.approve()

        leave.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(leave.status, 'PENDING')
        self.assertEqual(self.employee.custom_leave, 2)

    def test_normal_employee_keeps_leave_type_validation(self):
        self.employee.custom_leave = None
        self.employee.save(update_fields=['custom_leave'])
        form = LeaveRequestForm(self.form_data, employee=self.employee)

        self.assertFalse(form.is_valid())
        self.assertIn('Insufficient balance', str(form.errors))


class LeaveTypeTests(TestCase):
    def test_name_defaults_to_casual_leave(self):
        leave_type = LeaveType.objects.create(yearly_limit=12)

        self.assertEqual(leave_type.name, LeaveType.CASUAL)
        self.assertEqual(str(leave_type), 'Casual Leave')

    def test_form_renders_name_as_select_with_supported_choices(self):
        form = LeaveTypeForm()

        self.assertEqual(form.fields['name'].initial, LeaveType.CASUAL)
        self.assertEqual(
            list(form.fields['name'].choices),
            LeaveType.LEAVE_TYPE_CHOICES,
        )
        self.assertEqual(form.fields['name'].widget.__class__.__name__, 'Select')
        self.assertNotIn('description', form.fields)

    def test_admin_leave_type_pages_render(self):
        user = User.objects.create_user(
            username='leave-type-admin',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(user)

        list_response = self.client.get(reverse('leave_type_list'))
        create_response = self.client.get(reverse('leave_type_add'))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(create_response.status_code, 200)
        self.assertContains(create_response, '<select', html=False)
        self.assertContains(create_response, 'Casual Leave')
        self.assertNotContains(create_response, 'Description')

        leave_type = LeaveType.objects.create(
            name=LeaveType.SICK,
            yearly_limit=10,
        )
        edit_response = self.client.get(reverse('leave_type_edit', args=[leave_type.pk]))

        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(edit_response, 'Edit Leave Type')
        self.assertContains(edit_response, 'Update leave category and yearly limit')
        self.assertContains(edit_response, 'Save Changes')


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
