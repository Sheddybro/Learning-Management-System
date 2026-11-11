from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    # Configuration Management URLs
    path("configs/", views.SystemConfigListView.as_view(), name="config_list"),
    path(
        "configs/dashboard/",
        views.SystemConfigDashboardView.as_view(),
        name="config_dashboard",
    ),
    path(
        "configs/create/", views.SystemConfigCreateView.as_view(), name="config_create"
    ),
    path(
        "configs/<uuid:pk>/",
        views.SystemConfigDetailView.as_view(),
        name="config_detail",
    ),
    path(
        "configs/<uuid:pk>/update/",
        views.SystemConfigUpdateView.as_view(),
        name="config_update",
    ),
    path(
        "configs/<uuid:pk>/delete/",
        views.SystemConfigDeleteView.as_view(),
        name="config_delete",
    ),
    path(
        "configs/bulk-update/",
        views.SystemConfigBulkUpdateView.as_view(),
        name="config_bulk_update",
    ),
    path(
        "ui-config-management/",
        views.UIConfigManagementView.as_view(),
        name="ui_config_management",
    ),
    # Institution Management URLs
    path(
        "institution/select/",
        views.InstitutionSwitcherView.as_view(),
        name="institution_select",
    ),
    path("institutions/", views.InstitutionListView.as_view(), name="institution_list"),
    path(
        "institutions/create/",
        views.InstitutionCreateView.as_view(),
        name="institution_create",
    ),
    path(
        "institutions/<uuid:pk>/",
        views.InstitutionDetailView.as_view(),
        name="institution_detail",
    ),
    path(
        "institutions/<uuid:pk>/update/",
        views.InstitutionUpdateView.as_view(),
        name="institution_update",
    ),
    path(
        "institutions/<uuid:pk>/delete/",
        views.InstitutionDeleteView.as_view(),
        name="institution_delete",
    ),
    path(
        "institutions/<uuid:institution_id>/config-overrides/",
        views.InstitutionConfigOverrideView.as_view(),
        name="institution_config_overrides",
    ),
    # Admin Dashboards
    path(
        "dashboard/",
        views.SuperAdminDashboardView.as_view(),
        name="super_admin_dashboard",
    ),
    path(
        "entities/", views.SuperAdminEntityView.as_view(), name="super_admin_entities"
    ),
    path(
        "school-dashboard/",
        views.SchoolAdminDashboardView.as_view(),
        name="school_admin_dashboard",
    ),
    # Principal Views
    path(
        "principal/performance-monitoring/",
        views.PrincipalPerformanceMonitoringView.as_view(),
        name="principal_performance_monitoring",
    ),
    path(
        "principal/teacher-management/",
        views.PrincipalTeacherManagementView.as_view(),
        name="principal_teacher_management",
    ),
    path(
        "principal/student-welfare/",
        views.PrincipalStudentWelfareView.as_view(),
        name="principal_student_welfare",
    ),
    path(
        "principal/curriculum-planning/",
        views.PrincipalCurriculumPlanningView.as_view(),
        name="principal_curriculum_planning",
    ),
    path(
        "principal/communication/",
        views.PrincipalCommunicationView.as_view(),
        name="principal_communication",
    ),
    # Global Search
    path("search/", views.GlobalSearchView.as_view(), name="global_search"),
    # UI Configuration Demo
    path("ui-config-demo/", views.ui_config_demo, name="ui_config_demo"),
    # API endpoints
    path(
        "api/config/<str:config_key>/", views.get_config_value, name="get_config_value"
    ),
    path(
        "api/config/validate/",
        views.validate_config_value,
        name="validate_config_value",
    ),
    path("api/configs/export/", views.export_configs, name="export_configs"),
    path("api/configs/import/", views.import_configs, name="import_configs"),
    # Institution API endpoints
    path(
        "api/institution/<str:institution_code>/config/<str:config_key>/",
        views.get_institution_config_value,
        name="get_institution_config_value",
    ),
    path(
        "api/institutions/statistics/",
        views.institution_statistics_api,
        name="institution_statistics_api",
    ),
]
