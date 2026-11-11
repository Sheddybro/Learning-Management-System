# apps/analytics/urls.py

from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from . import views

app_name = 'analytics'

urlpatterns = [
    # Dashboard URLs
    path('', login_required(views.analytics_dashboard), name='dashboard'),
    
    # Report URLs
    path('reports/', login_required(views.report_list), name='report_list'),
    path('reports/<uuid:report_id>/', login_required(views.report_detail), name='report_detail'),
    path('reports/<uuid:report_id>/download/', login_required(views.download_report), name='download_report'),
    path('reports/generate/<uuid:report_type_id>/', login_required(views.generate_report), name='generate_report'),
    
    # KPI URLs
    path('kpis/', login_required(views.kpi_list), name='kpi_list'),
    path('kpis/<uuid:kpi_id>/', login_required(views.kpi_detail), name='kpi_detail'),
    path('kpis/<uuid:kpi_id>/trend-data/', login_required(views.kpi_trend_data), name='kpi_trend_data'),
    
    # Data Export URLs
    path('exports/', login_required(views.export_list), name='export_list'),
    path('exports/request/', login_required(views.request_data_export), name='request_export'),
    path('exports/<uuid:export_id>/download/', login_required(views.download_export), name='download_export'),
    
    # Trend Analysis URLs
    path('trends/', login_required(views.trend_analysis_list), name='trend_list'),
    path('trends/<uuid:analysis_id>/', login_required(views.trend_analysis_detail), name='trend_detail'),
    
    # Dashboard Management URLs (Class-Based Views)
    path('dashboards/create/', login_required(views.DashboardCreateView.as_view()), name='dashboard_create'),
    path('dashboards/<uuid:pk>/edit/', login_required(views.DashboardUpdateView.as_view()), name='dashboard_edit'),
    path('dashboards/<uuid:pk>/delete/', login_required(views.DashboardDeleteView.as_view()), name='dashboard_delete'),
    
    # Settings URLs
    path('settings/', login_required(views.analytics_settings), name='settings'),
    path('cache/clear/', login_required(views.clear_analytics_cache), name='clear_cache'),
    
    # API URLs
    path('api/kpis/<str:kpi_code>/measurements/', login_required(views.api_kpi_measurements), name='api_kpi_measurements'),
    path('api/report-types/', login_required(views.api_report_types), name='api_report_types'),
    path('api/overview/', login_required(views.analytics_overview_api), name='api_overview'),

    # System Metrics Collection
    path('collect-metrics/', login_required(views.collect_system_metrics), name='collect_system_metrics'),
]

# Additional URL patterns for REST API (if using Django REST Framework)
# from rest_framework import routers
# from . import api_views

# router = routers.DefaultRouter()
# router.register(r'reports', api_views.ReportViewSet)
# router.register(r'kpis', api_views.KPIViewSet)
# router.register(r'dashboards', api_views.DashboardViewSet)

# urlpatterns += [
#     path('api/', include(router.urls)),
# ]
