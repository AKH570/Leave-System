from django.urls import path

from .views import AttendanceReportView, LeaveReportView


urlpatterns = [
    path('', LeaveReportView.as_view(), name='leave_report'),
    path('attendance/', AttendanceReportView.as_view(), name='attendance_report'),
]
