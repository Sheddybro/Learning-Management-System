from django.urls import path
from . import views

app_name = "activities"

urlpatterns = [
    # Activity management
    path("", views.ActivityListView.as_view(), name="activity_list"),
    path("create/", views.ActivityCreateView.as_view(), name="activity_create"),
    path("<uuid:pk>/", views.ActivityDetailView.as_view(), name="activity_detail"),
    path(
        "<uuid:pk>/update/", views.ActivityUpdateView.as_view(), name="activity_update"
    ),
    path(
        "<uuid:pk>/delete/", views.ActivityDeleteView.as_view(), name="activity_delete"
    ),
    # Student enrollment
    path("<uuid:pk>/enroll/", views.activity_enroll, name="activity_enroll"),
    path("<uuid:pk>/unenroll/", views.activity_unenroll, name="activity_unenroll"),
    path("my-activities/", views.MyActivitiesView.as_view(), name="my_activities"),
    # Enrollment management (coordinators)
    path(
        "enrollments/",
        views.ActivityEnrollmentListView.as_view(),
        name="enrollment_list",
    ),
    path(
        "enrollments/<uuid:pk>/status/",
        views.update_enrollment_status,
        name="update_enrollment_status",
    ),
    # Attendance
    path(
        "<uuid:pk>/attendance/",
        views.ActivityAttendanceView.as_view(),
        name="activity_attendance",
    ),
    # Equipment management
    path("equipment/", views.EquipmentListView.as_view(), name="equipment_list"),
    path(
        "equipment/create/",
        views.EquipmentCreateView.as_view(),
        name="equipment_create",
    ),
    path(
        "equipment/<uuid:pk>/update/",
        views.EquipmentUpdateView.as_view(),
        name="equipment_update",
    ),
    # Budget management
    path("budgets/", views.ActivityBudgetListView.as_view(), name="budget_list"),
    # Competitions
    path("competitions/", views.CompetitionListView.as_view(), name="competition_list"),
    path(
        "competitions/create/",
        views.CompetitionCreateView.as_view(),
        name="competition_create",
    ),
    path(
        "competitions/<uuid:pk>/",
        views.CompetitionDetailView.as_view(),
        name="competition_detail",
    ),
    # AJAX endpoints
    path(
        "ajax/<uuid:activity_id>/enrollments/",
        views.get_activity_enrollments,
        name="ajax_enrollments",
    ),
    path("ajax/<uuid:activity_id>/stats/", views.get_activity_stats, name="ajax_stats"),
]
