from django.contrib import admin
from .models import Department

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'manager', 'created_at')
    search_fields = ('name', 'code')
    list_filter = ('created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
