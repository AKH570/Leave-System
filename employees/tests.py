from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from departments.models import Department

from .forms import EmployeeAdminEditForm, EmployeeProfileForm, LeaveRequestForm, LeaveTypeForm
from .models import (
    EmpDesignation,
    EmpProfile,
    EmpSalary,
    Employee,
    LeaveRequest,
    LeaveType,
)


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


class EmployeeAdminAjaxEditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='employee-admin',
            password='test-password',
            role='ADMIN',
        )
        self.user = User.objects.create_user(
            username='employee-to-edit',
            password='test-password',
            first_name='Original',
            last_name='Name',
            email='original@example.com',
            phone='+8801700000000',
        )
        self.department = Department.objects.create(
            name='ACCOUNTS',
            code='AJAX-ACC',
        )
        self.designation = EmpDesignation.objects.create(
            designation_name='Ajax Tester',
            department=self.department,
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department=self.department,
            designation=self.designation,
            custom_leave=12,
        )
        EmpProfile.objects.create(
            employee=self.employee,
            present_address='Old address',
        )
        self.client.force_login(self.admin)

    def valid_data(self):
        return {
            'employee_id': self.employee.employee_id,
            'employee_name': 'Updated Employee',
            'username': 'updated-employee',
            'email': 'updated@example.com',
            'mobile_number': '+8801800000000',
            'department': self.department.pk,
            'designation': self.designation.pk,
            'role': 'ADMIN',
            'employment_status': 'inactive',
            'joining_date': '2025-01-15',
            'leave_balance': '20',
            'present_address': 'New present address',
            'permanent_address': 'New permanent address',
            'remarks': 'Updated through the modal',
        }

    def test_edit_endpoint_returns_prepopulated_modal_form_json(self):
        response = self.client.get(
            reverse('employee_admin_edit', args=[self.employee.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertIn(self.employee.employee_id, response.json()['html'])
        self.assertIn('Original Name', response.json()['html'])
        self.assertNotIn('name="remarks"', response.json()['html'])
        self.assertIn('Add New Department', response.json()['html'])

    def test_admin_form_contains_only_administrative_fields(self):
        form = EmployeeAdminEditForm(employee=self.employee)

        self.assertEqual(set(form.fields), {
            'department',
            'designation',
            'role',
            'employment_status',
            'joining_date',
            'leave_balance',
        })

    def test_invalid_update_returns_field_errors_without_saving(self):
        data = self.valid_data()
        data['joining_date'] = ''

        response = self.client.post(
            reverse('employee_admin_update', args=[self.employee.pk]),
            data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.json()['ok'])
        self.assertIn('is-invalid', response.json()['html'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'original@example.com')

    def test_valid_update_saves_related_records_and_returns_row(self):
        response = self.client.post(
            reverse('employee_admin_update', args=[self.employee.pk]),
            self.valid_data(),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertIn('Original Name', payload['row_html'])

        self.user.refresh_from_db()
        self.employee.refresh_from_db()
        profile = EmpProfile.objects.get(employee=self.employee)
        self.assertEqual(self.user.first_name, 'Original')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(self.user.username, 'employee-to-edit')
        self.assertEqual(self.user.email, 'original@example.com')
        self.assertEqual(self.user.role, 'ADMIN')
        self.assertFalse(self.employee.is_active)
        self.assertEqual(self.employee.custom_leave, 20)
        self.assertEqual(str(self.employee.joining_date), '2025-01-15')
        self.assertEqual(profile.present_address, 'Old address')
        self.assertEqual(profile.job_description, '')

    def test_non_admin_cannot_access_edit_endpoint(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('employee_admin_edit', args=[self.employee.pk]))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_quick_create_department(self):
        response = self.client.post(
            reverse('department_quick_create'),
            {'name': 'Human Resources'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 201)
        department = Department.objects.get(name='HUMAN RESOURCES')
        self.assertEqual(response.json()['department']['id'], department.pk)
        self.assertEqual(response.json()['department']['name'], 'HUMAN RESOURCES')
        self.assertEqual(department.code, 'HUMAN-RESOURCES')

    def test_quick_create_rejects_duplicate_department_case_insensitively(self):
        response = self.client.post(
            reverse('department_quick_create'),
            {'name': 'accounts'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn('already exists', response.json()['errors']['name'][0])

    def test_non_admin_cannot_quick_create_department(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('department_quick_create'),
            {'name': 'Unauthorized Department'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Department.objects.filter(name='Unauthorized Department').exists())


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
            'education': 'BSc in Computer Science',
            'emergency_contact_name': 'Emergency Person',
            'emergency_contact_relationship': 'Sibling',
            'emergency_contact_number': '+8801800000000',
            'job_description': 'Develops and maintains business applications.',
            'email': 'attempted-change@example.com',
            'designation': 'Attempted Change',
        })

        self.assertRedirects(response, reverse('employee_profile'))
        profile = EmpProfile.objects.get(employee=self.employee)
        self.assertEqual(profile.nationality, 'Bangladeshi')
        self.assertEqual(profile.identification_no, 'NID-1234567890')
        self.assertEqual(profile.emergency_contact_number, '+8801800000000')
        self.assertEqual(profile.education, 'BSc in Computer Science')
        self.assertEqual(
            profile.job_description,
            'Develops and maintains business applications.',
        )

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

    def test_admin_employee_detail_displays_extended_profile_fields(self):
        admin_user = User.objects.create_user(
            username='profile-admin',
            password='test-password',
            role='ADMIN',
        )
        EmpProfile.objects.create(
            employee=self.employee,
            identification_no='NID-987654321',
            present_address='Dhaka',
            permanent_address='Chattogram',
            education='BSc in Computer Science',
            job_description='Builds internal systems.',
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('employee_detail', args=[self.employee.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NID-987654321')
        self.assertContains(response, self.employee.service_length)
        self.assertContains(response, 'BSc in Computer Science')
        self.assertContains(response, 'Builds internal systems.')
        self.assertContains(response, 'No salary information available.')

    def test_employee_detail_displays_latest_active_salary(self):
        admin_user = User.objects.create_user(
            username='salary-detail-admin',
            password='test-password',
            role='ADMIN',
        )
        EmpSalary.objects.create(
            employee=self.employee,
            basic_salary=Decimal('1000.00'),
            salary_effective_from=date(2025, 1, 1),
        )
        latest_active = EmpSalary.objects.create(
            employee=self.employee,
            basic_salary=Decimal('2000.00'),
            increment_amount=Decimal('250.00'),
            increment_date=date(2026, 1, 15),
            salary_effective_from=date(2026, 1, 1),
        )
        EmpSalary.objects.create(
            employee=self.employee,
            basic_salary=Decimal('9999.00'),
            salary_effective_from=date(2027, 1, 1),
            is_active=False,
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse('employee_detail', args=[self.employee.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['latest_salary'], latest_active)
        self.assertContains(response, '2000.00')
        self.assertContains(response, '250.00')
        self.assertContains(response, '15 January 2026')
        self.assertNotContains(response, '9999.00')

    def test_service_length_is_calculated_from_joining_date(self):
        self.employee.joining_date = date(2024, 2, 29)

        with patch('employees.models.timezone.localdate', return_value=date(2026, 2, 28)):
            self.assertEqual(self.employee.service_length, '2 years')

    def test_education_is_required_on_profile_form(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('employee_profile_edit'), {
            'education': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required.')


class EmpSalaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='salary-user',
            first_name='John',
            last_name='Smith',
            password='test-password',
        )
        self.employee = Employee.objects.create(user=self.user)

    def create_salary(self, **overrides):
        values = {
            'employee': self.employee,
            'basic_salary': Decimal('50000.00'),
            'house_rent': Decimal('20000.00'),
            'medical_allowance': Decimal('5000.00'),
            'transport_allowance': Decimal('3000.00'),
            'food_allowance': Decimal('2000.00'),
            'mobile_allowance': Decimal('1000.00'),
            'other_allowance': Decimal('500.00'),
            'provident_fund': Decimal('5000.00'),
            'loan_deduction': Decimal('1000.00'),
            'advance_salary': Decimal('500.00'),
            'other_deduction': Decimal('250.00'),
            'bank_name': 'Example Bank',
            'bank_account_no': '1234567890',
            'branch_name': 'Dhaka',
            'salary_effective_from': date(2026, 1, 1),
        }
        values.update(overrides)
        return EmpSalary.objects.create(**values)

    def test_salary_totals_are_calculated_automatically(self):
        salary = self.create_salary(
            gross_salary=Decimal('1.00'),
            net_salary=Decimal('1.00'),
        )

        self.assertEqual(salary.gross_salary, Decimal('81500.00'))
        self.assertEqual(salary.net_salary, Decimal('74750.00'))

    def test_partial_update_also_persists_recalculated_totals(self):
        salary = self.create_salary()
        salary.basic_salary = Decimal('60000.00')

        salary.save(update_fields=['basic_salary'])
        salary.refresh_from_db()

        self.assertEqual(salary.gross_salary, Decimal('91500.00'))
        self.assertEqual(salary.net_salary, Decimal('84750.00'))

    def test_salary_validation_rejects_negative_amount_and_invalid_dates(self):
        salary = EmpSalary(
            employee=self.employee,
            basic_salary=Decimal('-1.00'),
            bank_name='Example Bank',
            bank_account_no='1234567890',
            branch_name='Dhaka',
            salary_effective_from=date(2026, 2, 1),
            salary_end_date=date(2026, 1, 31),
        )

        with self.assertRaises(ValidationError) as error:
            salary.full_clean()

        self.assertIn('basic_salary', error.exception.message_dict)
        self.assertIn('salary_end_date', error.exception.message_dict)

    def test_bank_details_are_optional(self):
        salary = EmpSalary(
            employee=self.employee,
            salary_effective_from=date(2026, 1, 1),
        )

        salary.full_clean()
        salary.save()

        self.assertEqual(salary.bank_name, '')
        self.assertEqual(salary.bank_account_no, '')
        self.assertEqual(salary.branch_name, '')
        self.assertEqual(salary.increment_amount, Decimal('0.00'))
        self.assertIsNone(salary.increment_date)
        self.assertIsNone(salary.updated_by)

    def test_increment_fields_store_audit_data_without_changing_totals(self):
        salary = self.create_salary(
            increment_amount=Decimal('5000.00'),
            increment_date=date(2026, 1, 1),
            updated_by=self.user,
        )

        self.assertEqual(salary.increment_amount, Decimal('5000.00'))
        self.assertEqual(salary.increment_date, date(2026, 1, 1))
        self.assertEqual(salary.updated_by, self.user)
        self.assertEqual(salary.gross_salary, Decimal('81500.00'))
        self.assertEqual(salary.net_salary, Decimal('74750.00'))

    def test_salary_history_ordering_indexes_and_string(self):
        older_salary = self.create_salary(
            salary_effective_from=date(2025, 1, 1),
        )
        newer_salary = self.create_salary(
            salary_effective_from=date(2026, 1, 1),
        )

        self.assertEqual(EmpSalary.objects.first(), newer_salary)
        self.assertEqual(str(older_salary), f'{self.employee.employee_id} - John Smith')
        self.assertEqual(
            {index.name for index in EmpSalary._meta.indexes},
            {
                'emp_sal_employee_idx',
                'emp_sal_effective_idx',
                'emp_sal_active_idx',
            },
        )
