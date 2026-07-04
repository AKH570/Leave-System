from django.urls import path

from .views import AttendanceHistoryView


urlpatterns = [
    path('history/', AttendanceHistoryView.as_view(), name='attendance_history'),
]
