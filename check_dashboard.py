#!/usr/bin/env python
"""
Diagnostic script to verify dashboard data for Josef
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LeaveManagementSystem.settings')
django.setup()

from employees.models import LeaveType, Employee, LeaveRequest
from accounts.models import User
from django.db.models import Sum

def check_dashboard():
    print("\n" + "="*70)
    print("DASHBOARD ISSUE INVESTIGATION")
    print("="*70 + "\n")
    
    # Check LeaveTypes
    print("STEP 1: LeaveType Data")
    print("-" * 70)
    lt_count = LeaveType.objects.count()
    print(f"Total LeaveTypes: {lt_count}")
    if lt_count > 0:
        total_limit = LeaveType.objects.aggregate(Sum('yearly_limit'))['yearly_limit__sum']
        print(f"Leave types available: {[lt.name for lt in LeaveType.objects.all()]}")
        print(f"Total yearly limit: {total_limit} days")
    else:
        print("ERROR: No LeaveType records found!")
    
    # Check Users
    print("\n\nSTEP 2: User Accounts")
    print("-" * 70)
    users = User.objects.all()
    print(f"Total users: {users.count()}")
    for u in users:
        print(f"  - {u.username} (superuser: {u.is_superuser})")
    
    # Check for Josef
    print("\n\nSTEP 3: Josef Analysis")
    print("-" * 70)
    josef = User.objects.filter(username='josef').first()
    
    if josef:
        print(f"FOUND: Josef exists in database")
        print(f"  - is_superuser: {josef.is_superuser}")
        print(f"  - role: {josef.role}")
        
        try:
            emp = josef.employee_profile
            print(f"  - Employee profile: YES (ID: {emp.employee_id})")
            
            # Calculate stats
            total_limit = LeaveType.objects.aggregate(Sum('yearly_limit'))['yearly_limit__sum'] or 0
            approved = LeaveRequest.objects.filter(employee=emp, status='APPROVED')
            used = approved.aggregate(Sum('total_days'))['total_days__sum'] or 0
            balance = total_limit - used
            pending = LeaveRequest.objects.filter(employee=emp, status='PENDING').count()
            
            print("\n  Dashboard will show:")
            print(f"    - leave_balance: {balance} days")
            print(f"    - used_leave: {used} days")
            print(f"    - pending_count: {pending}")
            print(f"    - approved_count: {approved.count()}")
            
            print("\n  RESULT: ALL CARDS SHOULD DISPLAY!")
            
        except Employee.DoesNotExist:
            print("  ERROR: Josef has NO employee profile!")
            print("  RESULT: He will see no_profile.html instead")
    else:
        print("ERROR: Josef not found in database!")
    
    print("\n" + "="*70 + "\n")

if __name__ == '__main__':
    check_dashboard()
