from django.urls import path

from .views import (AllEmployeesDailyReportView, AttendanceHistoryView,
                    EmployeeDailyReportView, EmployeeRangeReportView)


urlpatterns = [
    path('history/', AttendanceHistoryView.as_view(), name='attendance_history'),
    path('reports/employee-daily/', EmployeeDailyReportView.as_view(), name='employee_daily_attendance_report'),
    path('reports/all-employees-daily/', AllEmployeesDailyReportView.as_view(), name='all_employees_daily_attendance_report'),
    path('reports/employee-range/', EmployeeRangeReportView.as_view(), name='employee_range_attendance_report'),
]
