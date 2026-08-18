from django.contrib import admin
from .models import Attendance, AttendanceLog
# Register your models here.
admin.site.register(Attendance)


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ('employee', 'event_type', 'event_time', 'attendance')
    list_filter = ('event_type',)
    search_fields = ('employee__employee_id', 'employee__user__username')
