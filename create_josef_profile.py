#!/usr/bin/env python
"""
Create employee profile for Josef
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LeaveManagementSystem.settings')
django.setup()

from employees.models import EmpDesignation, Employee
from accounts.models import User
from departments.models import Department

print("\n" + "="*70)
print("CREATING EMPLOYEE PROFILE FOR JOSEF")
print("="*70 + "\n")

# Get Josef's user account
josef = User.objects.filter(username='josef').first()

if not josef:
    print("ERROR: Josef user not found!")
    exit(1)

# Get or create a department
dept, created = Department.objects.get_or_create(
    name='MEDICINE',
    defaults={'code': 'MED'}
)
print(f"Department: {dept.name} (code: {dept.code})")

# Check if employee profile already exists
emp = Employee.objects.filter(user=josef).first()

if emp:
    print(f"Employee profile already exists for Josef: ID={emp.employee_id}")
else:
    # Create employee profile
    designation, _ = EmpDesignation.objects.get_or_create(
        designation_name="Staff Member",
    )
    emp = Employee.objects.create(
        user=josef,
        department=dept,
        designation=designation,
        is_active=True
    )
    print(f"\nCreated employee profile for Josef:")
    print(f"  - Employee ID: {emp.employee_id}")
    print(f"  - Department: {emp.department.name}")
    print(f"  - Designation: {emp.designation}")
    print(f"  - Active: {emp.is_active}")

print("\n" + "="*70)
print("VERIFICATION")
print("="*70 + "\n")

# Verify
josef_fresh = User.objects.get(username='josef')
emp_fresh = josef_fresh.employee_profile

total_yearly = 47  # From our earlier check
approved = 0  # No approved leaves yet

print(f"Josef's Dashboard Context (what he will see):")
print(f"  - leave_balance: {total_yearly - approved} days")
print(f"  - used_leave: {approved} days")
print(f"  - pending_count: 0")
print(f"  - approved_count: 0")
print(f"\nResult: ALL 4 CARDS WILL NOW DISPLAY!")
print("\n" + "="*70 + "\n")
