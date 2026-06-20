#!/usr/bin/env python
"""
Script to populate LeaveType records in the database
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LeaveManagementSystem.settings')
django.setup()

from employees.models import LeaveType

# Create standard leave types
leave_types = [
    {'name': LeaveType.CASUAL, 'yearly_limit': 12},
    {'name': LeaveType.SICK, 'yearly_limit': 10},
    {'name': LeaveType.EARNED, 'yearly_limit': 20},
    {'name': LeaveType.OTHER, 'yearly_limit': 5},
]

print("=" * 60)
print("POPULATING LEAVE TYPES")
print("=" * 60)

for leave in leave_types:
    obj, created = LeaveType.objects.get_or_create(
        name=leave['name'],
        defaults={'yearly_limit': leave['yearly_limit']}
    )
    if created:
        print(f"✓ Created: {obj.name} ({obj.yearly_limit} days)")
    else:
        print(f"✓ Exists: {obj.name} ({obj.yearly_limit} days)")

total = LeaveType.objects.count()
print(f"\nTotal LeaveTypes in database: {total}")
print("=" * 60)
