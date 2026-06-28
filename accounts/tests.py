from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from employees.models import EmpDesignation

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
