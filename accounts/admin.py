from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import AuditLog, User, Registration

# Staff status alone must never grant access to the Django administration site.
admin.site.has_permission = lambda request: (
    request.user.is_active and request.user.is_superuser
)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'role')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'role', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    actions = ['activate_users', 'deactivate_users', 'make_admin', 'make_employee']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'role', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    @admin.action(description="Activate selected users")
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
    
    @admin.action(description="Make selected users Admins")
    def make_admin(self, request, queryset):
        queryset.update(role='ADMIN', is_staff=False)
    
    @admin.action(description="Make selected users Employees")
    def make_employee(self, request, queryset):
        queryset.update(role='EMPLOYEE', is_staff=False)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'module', 'object_repr', 'ip_address')
    list_filter = ('module', 'action', 'created_at')
    search_fields = ('actor__username', 'object_repr', 'details')
    readonly_fields = ('actor', 'action', 'module', 'object_repr', 'details', 'ip_address', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'email',
        'designation',
        'status',
        'created_at',
        'get_actions_display',
    )
    list_filter = ('status', 'designation', 'created_at', 'terms_accepted')
    search_fields = (
        'username',
        'email',
        'first_name',
        'last_name',
        'designation__designation_name',
    )
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'approved_at')
    list_select_related = ('designation', 'department')
    actions = ['approve_registrations', 'reject_registrations']
    
    fieldsets = (
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        ('Professional Info', {'fields': ('designation', 'department')}),
        ('Account Info', {'fields': ('username', 'password', 'confirm_password')}),
        ('Registration Status', {'fields': ('status', 'terms_accepted', 'rejection_reason')}),
        ('Approval Info', {'fields': ('created_at', 'updated_at', 'approved_by', 'approved_at')}),
    )
    
    def get_actions_display(self, obj):
        if obj.status == 'PENDING':
            return '⏳ Pending'
        elif obj.status == 'APPROVED':
            return '✅ Approved'
        else:
            return '❌ Rejected'
    get_actions_display.short_description = 'Status'
    
    @admin.action(description="Approve selected registrations")
    def approve_registrations(self, request, queryset):
        # This is a stub - the actual approval logic should create User accounts
        # This will be fully implemented in Phase 3
        updated = queryset.filter(status='PENDING').update(status='APPROVED', approved_by=request.user)
        self.message_user(request, f"{updated} registrations approved.")
    
    @admin.action(description="Reject selected registrations")
    def reject_registrations(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='REJECTED', approved_by=request.user)
        self.message_user(request, f"{updated} registrations rejected.")
