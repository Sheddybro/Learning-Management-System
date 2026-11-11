from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from apps.core.admin import InstitutionModelAdmin
from .models import (
    ActivityCategory,
    Activity,
    ActivityEnrollment,
    ActivityStaffAssignment,
    SportsTeam,
    Club,
    Competition,
    Equipment,
    ActivityBudget,
    ActivityAttendance,
    ActivityAchievement,
)


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(InstitutionModelAdmin):
    list_display = ["name", "category_type", "is_active", "color_code"]
    list_filter = ["category_type", "is_active"]
    search_fields = ["name", "description"]
    ordering = ["name"]


class ActivityEnrollmentInline(admin.TabularInline):
    model = ActivityEnrollment
    extra = 0
    readonly_fields = ["enrollment_date", "status"]
    can_delete = True


class ActivityStaffAssignmentInline(admin.TabularInline):
    model = ActivityStaffAssignment
    extra = 0
    readonly_fields = ["assigned_date"]
    can_delete = True


@admin.register(Activity)
class ActivityAdmin(InstitutionModelAdmin):
    list_display = [
        "title",
        "category",
        "activity_type",
        "status",
        "start_date",
        "coordinator",
        "current_participants",
    ]
    list_filter = [
        "category",
        "activity_type",
        "frequency",
        "status",
        "academic_session",
    ]
    search_fields = ["title", "description", "venue"]
    ordering = ["-start_date", "title"]
    readonly_fields = ["current_participants", "available_spots", "is_full"]
    inlines = [ActivityEnrollmentInline, ActivityStaffAssignmentInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("title", "description", "category", "status")},
        ),
        (
            _("Activity Details"),
            {
                "fields": (
                    "activity_type",
                    "frequency",
                    "max_participants",
                    "min_participants",
                )
            },
        ),
        (
            _("Scheduling"),
            {
                "fields": (
                    "start_date",
                    "end_date",
                    "start_time",
                    "end_time",
                    "days_of_week",
                )
            },
        ),
        (
            _("Location & Resources"),
            {"fields": ("venue", "room_number", "equipment_needed")},
        ),
        (_("Financial"), {"fields": ("fee_amount", "currency")}),
        (_("Management"), {"fields": ("academic_session", "coordinator")}),
        (
            _("Additional Information"),
            {
                "fields": (
                    "prerequisites",
                    "objectives",
                    "contact_info",
                    "registration_deadline",
                ),
                "classes": ("collapse",),
            },
        ),
        (_("Media"), {"fields": ("image", "brochure"), "classes": ("collapse",)}),
    )


@admin.register(ActivityEnrollment)
class ActivityEnrollmentAdmin(InstitutionModelAdmin):
    list_display = [
        "student",
        "activity",
        "status",
        "enrollment_date",
        "payment_status",
        "attendance_count",
    ]
    list_filter = ["status", "payment_status", "enrollment_date", "activity__category"]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "student__student_id",
        "activity__title",
    ]
    ordering = ["-enrollment_date"]
    readonly_fields = ["enrollment_date", "attendance_percentage"]

    fieldsets = (
        (
            _("Enrollment Details"),
            {"fields": ("student", "activity", "status", "enrollment_date")},
        ),
        (
            _("Additional Information"),
            {
                "fields": (
                    "special_requirements",
                    "emergency_contact",
                    "medical_conditions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Payment"),
            {
                "fields": ("payment_status", "payment_date", "transaction_id"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Tracking"),
            {
                "fields": (
                    "attendance_count",
                    "last_attendance",
                    "performance_notes",
                    "grade",
                    "certificate_issued",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(ActivityStaffAssignment)
class ActivityStaffAssignmentAdmin(InstitutionModelAdmin):
    list_display = ["staff_member", "activity", "role", "is_primary", "assigned_date"]
    list_filter = ["role", "is_primary", "assigned_date", "activity__category"]
    search_fields = [
        "staff_member__first_name",
        "staff_member__last_name",
        "staff_member__email",
        "activity__title",
    ]
    ordering = ["activity", "role"]


@admin.register(SportsTeam)
class SportsTeamAdmin(InstitutionModelAdmin):
    list_display = [
        "team_name",
        "activity",
        "team_level",
        "captain",
        "current_players",
        "wins",
        "losses",
        "draws",
    ]
    list_filter = ["team_level"]
    search_fields = ["team_name", "activity__title"]
    ordering = ["team_name"]
    readonly_fields = ["current_players", "matches_played"]


@admin.register(Club)
class ClubAdmin(InstitutionModelAdmin):
    list_display = [
        "activity",
        "club_type",
        "president",
        "vice_president",
        "budget_allocated",
    ]
    list_filter = ["club_type"]
    search_fields = [
        "activity__title",
        "president__user__first_name",
        "president__user__last_name",
    ]


@admin.register(Competition)
class CompetitionAdmin(InstitutionModelAdmin):
    list_display = [
        "title",
        "activity",
        "competition_type",
        "level",
        "start_date",
        "is_active",
    ]
    list_filter = ["competition_type", "level", "is_active", "start_date"]
    search_fields = ["title", "description", "activity__title"]
    ordering = ["-start_date", "title"]


@admin.register(Equipment)
class EquipmentAdmin(InstitutionModelAdmin):
    list_display = [
        "name",
        "equipment_type",
        "quantity_available",
        "quantity_total",
        "condition",
        "assigned_to_activity",
    ]
    list_filter = ["equipment_type", "condition", "assigned_to_activity__category"]
    search_fields = ["name", "description", "storage_location"]
    ordering = ["equipment_type", "name"]
    readonly_fields = ["utilization_rate"]


@admin.register(ActivityBudget)
class ActivityBudgetAdmin(InstitutionModelAdmin):
    list_display = [
        "activity",
        "budget_type",
        "category",
        "amount",
        "currency",
        "approved_by",
        "actual_date",
    ]
    list_filter = [
        "budget_type",
        "category",
        "approved_by",
        "planned_date",
        "actual_date",
    ]
    search_fields = ["activity__title", "description"]
    ordering = ["activity", "-planned_date"]


@admin.register(ActivityAttendance)
class ActivityAttendanceAdmin(InstitutionModelAdmin):
    list_display = [
        "enrollment",
        "session_date",
        "is_present",
        "arrival_time",
        "departure_time",
        "participation_rating",
    ]
    list_filter = ["is_present", "session_date", "participation_rating"]
    search_fields = [
        "enrollment__student__user__first_name",
        "enrollment__student__user__last_name",
        "enrollment__activity__title",
    ]
    ordering = ["-session_date"]
    date_hierarchy = "session_date"


@admin.register(ActivityAchievement)
class ActivityAchievementAdmin(InstitutionModelAdmin):
    list_display = [
        "enrollment",
        "achievement_type",
        "title",
        "achievement_date",
        "awarded_by",
        "certificate_issued",
    ]
    list_filter = ["achievement_type", "achievement_date", "certificate_issued"]
    search_fields = [
        "enrollment__student__user__first_name",
        "enrollment__student__user__last_name",
        "title",
        "description",
    ]
    ordering = ["-achievement_date"]
    date_hierarchy = "achievement_date"
