from django.contrib import admin
from django.urls import path, include
from LAF import views

urlpatterns = [
	path('', views.dashboard, name='dashboard'),
    path('admin/', views.dashboard, name='adm_dashboard'),
    path('employee/', views.dashboard, name='emp_dashboard'),
]