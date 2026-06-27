from django.test import TestCase

from .models import Department


class DepartmentNameNormalizationTests(TestCase):
    def test_department_name_is_saved_in_uppercase(self):
        department = Department.objects.create(
            name='  Human   Resources  ',
            code='HR',
        )

        self.assertEqual(department.name, 'HUMAN RESOURCES')
        department.refresh_from_db()
        self.assertEqual(department.name, 'HUMAN RESOURCES')
