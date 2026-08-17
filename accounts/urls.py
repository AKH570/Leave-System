from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('session/refresh/', views.session_refresh, name='session_refresh'),
    path('register/', views.registration_view, name='register'),
    path('access/users/', views.access_users, name='access_users'),
    path('access/users/add/', views.access_user_create, name='access_user_add'),
    path('access/users/<int:pk>/', views.access_user_edit, name='access_user_edit'),
    path('access/roles/', views.access_roles, name='access_roles'),
    path('access/roles/add/', views.access_role_edit, name='access_role_add'),
    path('access/roles/<int:pk>/', views.access_role_edit, name='access_role_edit'),
    path('access/permissions/', views.access_permissions, name='access_permissions'),
    path('access/audit/', views.access_audit, name='access_audit'),
]
