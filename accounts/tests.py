from django.db.models.deletion import ProtectedError
from django.test import TestCase

from employees.models import EmpDesignation

from .forms import RegistrationForm
from .models import Registration


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
