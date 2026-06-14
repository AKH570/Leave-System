from django.urls import path
from . import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='emp_dashboard'),
    path('leave/apply/', views.LeaveApplyView.as_view(), name='leave_apply'),
    path('leave/history/', views.LeaveHistoryView.as_view(), name='leave_history'),
    path('leave/detail/<int:pk>/', views.LeaveDetailView.as_view(), name='leave_detail'),
    path('profile/', views.EmployeeProfileView.as_view(), name='employee_profile'),
    path('profile/edit/', views.EmployeeProfileUpdateView.as_view(), name='employee_profile_edit'),
    path('leave/cancel/<int:pk>/', views.leave_cancel, name='leave_cancel'),
    path('leave/approve/<int:pk>/', views.leave_approve, name='leave_approve'),
    path('leave/reject/<int:pk>/', views.leave_reject, name='leave_reject'),
    path('leave-types/', views.LeaveTypeListView.as_view(), name='leave_type_list'),
    path('leave-types/add/', views.LeaveTypeCreateView.as_view(), name='leave_type_add'),
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/<int:pk>/', views.EmployeeDetailView.as_view(), name='employee_detail'),
]
