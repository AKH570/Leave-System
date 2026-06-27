from django.contrib import admin

from accounts.models import Registration
from .models import (
    EmpDesignation,
    EmpProfile,
    EmpSalary,
    Employee,
    LeaveRequest,
    LeaveType,
)


@admin.register(EmpDesignation)
class EmpDesignationAdmin(admin.ModelAdmin):
    list_display = (
        'designation_id',
        'designation_name',
        'department',
        'status',
        'created_by',
        'updated_at',
    )
    search_fields = (
        'designation_id',
        'designation_name',
        'description',
        'department__name',
    )
    list_filter = ('status', 'department', 'created_at', 'updated_at')
    ordering = ('designation_name',)
    readonly_fields = ('designation_id', 'created_at', 'updated_at')
    autocomplete_fields = ('created_by',)
    list_select_related = ('department', 'created_by')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'employee_id',
        'get_full_name',
        'department',
        'designation',
        'service_length_display',
        'custom_leave',
        'is_active',
    )
    search_fields = (
        'employee_id',
        'user__first_name',
        'user__last_name',
        'user__username',
        'designation__designation_name',
    )
    list_filter = ('department', 'designation', 'is_active', 'joining_date')
    readonly_fields = ('employee_id', 'joining_date', 'service_length_display')
    list_select_related = ('user', 'department', 'designation')
    autocomplete_fields = ('designation',)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        is_admin = request.user.is_superuser or getattr(
            request.user,
            'role',
            '',
        ) == 'ADMIN'
        if not is_admin:
            readonly_fields.append('custom_leave')
        return readonly_fields

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = 'Name'

    @admin.display(description='Service Length')
    def service_length_display(self, obj):
        return obj.service_length if obj else 'Calculated from joining date'


@admin.register(EmpProfile)
class EmpProfileAdmin(admin.ModelAdmin):
    list_display = (
        'employee',
        'identification_no',
        'gender',
        'emergency_contact_number',
        'updated_at',
    )
    search_fields = (
        'employee__employee_id',
        'employee__user__first_name',
        'employee__user__last_name',
        'identification_no',
        'education',
        'job_description',
        'emergency_contact_number',
    )
    list_filter = ('gender', 'blood_group')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Employee', {'fields': ('employee', 'profile_picture')}),
        ('Identification', {
            'fields': (
                'identification_no', 'gender', 'date_of_birth',
                'blood_group', 'nationality',
            ),
        }),
        ('Employment Profile', {
            'fields': ('education', 'job_description'),
        }),
        ('Addresses', {'fields': ('present_address', 'permanent_address')}),
        ('Emergency Contact', {
            'fields': (
                'emergency_contact_name', 'emergency_contact_relationship',
                'emergency_contact_number',
            ),
        }),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(EmpSalary)
class EmpSalaryAdmin(admin.ModelAdmin):
    list_display = (
        'employee',
        'basic_salary',
        'gross_salary',
        'net_salary',
        'payment_method',
        'salary_effective_from',
        'is_active',
    )
    search_fields = (
        'employee__employee_id',
        'employee__user__first_name',
        'employee__user__last_name',
        'employee__user__username',
        'bank_account_no',
    )
    list_filter = ('payment_method', 'is_active', 'salary_effective_from')
    readonly_fields = (
        'gross_salary',
        'net_salary',
        'updated_by',
        'created_at',
        'updated_at',
    )
    autocomplete_fields = ('employee',)
    list_select_related = ('employee__user',)
    fieldsets = (
        ('Employee and Effective Period', {
            'fields': (
                'employee', 'salary_effective_from', 'salary_end_date',
                'is_active',
            ),
        }),
        ('Earnings', {
            'fields': (
                'basic_salary', 'house_rent', 'medical_allowance',
                'transport_allowance', 'food_allowance',
                'mobile_allowance', 'other_allowance', 'gross_salary',
            ),
        }),
        ('Deductions', {
            'fields': (
                'provident_fund', 'loan_deduction', 'advance_salary',
                'other_deduction', 'net_salary',
            ),
        }),
        ('Increment History', {
            'fields': ('increment_amount', 'increment_date'),
        }),
        ('Payment Details', {
            'fields': (
                'payment_method', 'bank_name', 'bank_account_no',
                'branch_name', 'mobile_banking_name', 'mobile_banking_no',
            ),
        }),
        ('Additional Information', {
            'fields': ('remarks', 'updated_by', 'created_at', 'updated_at'),
        }),
    )

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'yearly_limit')
    search_fields = ('name',)
    list_filter = ('name',)


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
