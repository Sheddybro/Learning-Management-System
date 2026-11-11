# apps/audit/urls.py
from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    # Audit Log URLs
    path('', views.AuditLogListView.as_view(), name='auditlog_list'),
    path('dashboard/', views.AuditLogDashboardView.as_view(), name='auditlog_dashboard'),
    path('<uuid:pk>/', views.AuditLogDetailView.as_view(), name='auditlog_detail'),
    path('export/', views.AuditLogExportView.as_view(), name='auditlog_export'),
    path('statistics/', views.AuditLogStatisticsView.as_view(), name='auditlog_statistics'),
]