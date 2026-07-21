from io import StringIO
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from employees.models import EmpDesignation
from holidays.models import Holiday

from .management.commands.reset_uat_data import Command as ResetUatDataCommand
from .forms import RegistrationForm
from .models import Registration
from .models import User


class RegistrationDesignationTests(TestCase):
    def setUp(self):
        self.active_designation = EmpDesignation.objects.create(
            designation_name='Sales Executive',
        )
        self.inactive_designation = EmpDesignation.objects.create(
            designation_name='Legacy Position',
            status=EmpDesignation.Status.INACTIVE,
        )

    def test_registration_designation_is_protected_from_deletion(self):
        Registration.objects.create(
            first_name='Retail',
            last_name='Applicant',
            username='retail-applicant',
            password='temporary-password',
            phone='+8801700000000',
            designation=self.active_designation,
        )

        with self.assertRaises(ProtectedError):
            self.active_designation.delete()

    def test_registration_form_only_lists_active_designations(self):
        designation_queryset = RegistrationForm().fields[
            'designation'
        ].queryset

        self.assertIn(self.active_designation, designation_queryset)
        self.assertNotIn(self.inactive_designation, designation_queryset)


class GlobalFooterTests(TestCase):
    def assert_global_footer(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="app-footer"', count=1)
        self.assertContains(response, '&copy; 2026 LeaveBox', html=True)
        self.assertContains(response, 'Application Version:')
        self.assertContains(response, 'v1.0.0')
        self.assertContains(response, '/static/css/footer.css')

    def test_authentication_pages_use_shared_footer(self):
        self.assert_global_footer(self.client.get(reverse('accounts:login')))
        self.assert_global_footer(self.client.get(reverse('accounts:register')))

    def test_authenticated_base_layout_uses_shared_footer(self):
        admin_user = User.objects.create_user(
            username='footer-admin',
            password='test-password',
            role='ADMIN',
        )
        self.client.force_login(admin_user)

        self.assert_global_footer(self.client.get(reverse('dashboard')))


class ResetUatDataCommandTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='uat-admin',
            email='admin@example.com',
            password='test-password',
        )
        self.regular_user = User.objects.create_user(
            username='uat-employee',
            password='test-password',
        )
        self.designation = EmpDesignation.objects.create(
            designation_name='UAT Tester',
            created_by=self.admin,
        )
        Registration.objects.create(
            first_name='UAT',
            last_name='Applicant',
            username='uat-applicant',
            password='temporary-password',
            phone='+8801700000000',
            designation=self.designation,
            approved_by=self.admin,
        )
        Holiday.objects.create(name='UAT Holiday', date='2026-01-01')

    def test_reset_deletes_application_data_and_preserves_system_data(self):
        content_type_count = ContentType.objects.count()
        stdout = StringIO()

        call_command('reset_uat_data', no_input=True, stdout=stdout)

        self.assertTrue(User.objects.filter(pk=self.admin.pk, is_superuser=True).exists())
        self.assertFalse(User.objects.filter(pk=self.regular_user.pk).exists())
        self.assertFalse(Registration.objects.exists())
        self.assertFalse(EmpDesignation.objects.exists())
        self.assertFalse(Holiday.objects.exists())
        self.assertEqual(ContentType.objects.count(), content_type_count)
        self.assertIn('UAT data reset completed successfully.', stdout.getvalue())

        # The preserved superuser prevents the user sequence returning to 1, while
        # emptied application tables restart at their backend-supported initial ID.
        holiday = Holiday.objects.create(name='First New Holiday', date='2026-01-02')
        self.assertEqual(holiday.pk, 1)

    def test_confirmation_other_than_exact_reset_cancels(self):
        stdout = StringIO()
        with patch('builtins.input', return_value='reset'):
            call_command('reset_uat_data', stdout=stdout)

        self.assertTrue(Registration.objects.exists())
        self.assertTrue(User.objects.filter(pk=self.regular_user.pk).exists())
        self.assertIn('Reset cancelled', stdout.getvalue())

    def test_media_is_only_removed_when_requested(self):
        with patch.object(ResetUatDataCommand, '_delete_media') as delete_media:
            call_command('reset_uat_data', no_input=True, stdout=StringIO())
            delete_media.assert_not_called()

            call_command(
                'reset_uat_data',
                no_input=True,
                delete_media=True,
                stdout=StringIO(),
            )
            delete_media.assert_called_once_with()
