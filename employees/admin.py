from django.contrib import admin
from .models import EmpProfile, Employee, LeaveType, LeaveRequest
from accounts.models import Registration

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'get_full_name', 'department', 'designation', 'is_active')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name', 'user__username')
    list_filter = ('department', 'is_active', 'joining_date')
    readonly_fields = ('joining_date',)

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Name'

@admin.register(EmpProfile)
class EmpProfileAdmin(admin.ModelAdmin):
    list_display = ('employee', 'identification_no', 'gender', 'emergency_contact_number', 'updated_at')
    search_fields = (
        'employee__employee_id',
        'employee__user__first_name',
        'employee__user__last_name',
        'identification_no',
        'emergency_contact_number',
    )
    list_filter = ('gender', 'blood_group')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'yearly_limit', 'description')
    search_fields = ('name',)

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'from_date', 'to_date', 'total_days', 'status', 'applied_at')
    list_filter = ('status', 'leave_type', 'applied_at', 'from_date')
    search_fields = ('employee__user__username', 'employee__user__first_name', 'reason')
    readonly_fields = ('applied_at', 'total_days', 'approved_at')
    fieldsets = (
        ('Request Info', {'fields': ('employee', 'leave_type', 'reason')}),
        ('Dates', {'fields': ('from_date', 'to_date', 'total_days')}),
        ('Status & Approval', {'fields': ('status', 'applied_at', 'approved_by', 'approved_at', 'remarks')}),
    )
