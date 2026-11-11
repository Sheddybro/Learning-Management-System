# apps/attendance/admin.py

from django.contrib import admin
from apps.core.admin import InstitutionModelAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import (
    AttendanceConfig,
    AttendanceSession,
    DailyAttendance,
    PeriodAttendance,
    LeaveType,
    LeaveApplication,
    AttendanceSummary,
    BulkAttendanceSession,
    AttendanceException,
)

User = get_user_model()


# Export functionality (conceptual - would need proper implementation)
class ExportMixin:
    def export_to_csv(self, request, queryset):
        # This would be implemented with proper CSV export logic
        # For now, it's a placeholder
        self.message_user(request, _("Export feature would be implemented here."))

    export_to_csv.short_description = _("Export selected to CSV")


class AttendanceConfigAdmin(InstitutionModelAdmin):
    list_display = [
        "academic_session",
        "school_start_time",
        "school_end_time",
        "late_threshold_minutes",
        "notify_parents_on_absence",
        "status",
    ]
    list_filter = ["academic_session", "status"]
    search_fields = ["academic_session__name"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (_("Academic Session"), {"fields": ("academic_session",)}),
        (
            _("Timing Configuration"),
            {
                "fields": (
                    "school_start_time",
                    "school_end_time",
                    "late_threshold_minutes",
                    "half_day_threshold_hours",
                )
            },
        ),
        (
            _("Automation Settings"),
            {
                "fields": (
                    "auto_mark_absent_after_days",
                    "notify_after_consecutive_absences",
                )
            },
        ),
        (
            _("Features"),
            {
                "fields": (
                    "enable_biometric",
                    "enable_geo_fencing",
                    "notify_parents_on_absence",
                )
            },
        ),
        (_("Status"), {"fields": ("status",)}),
    )


class AttendanceSessionAdmin(InstitutionModelAdmin):
    list_display = [
        "name",
        "session_type",
        "academic_session",
        "start_time",
        "end_time",
        "is_active",
        "status",
    ]
    list_filter = ["session_type", "academic_session", "is_active", "status"]
    search_fields = ["name", "academic_session__name"]
    list_editable = ["is_active"]
    ordering = ["academic_session", "start_time"]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "session_type", "academic_session")},
        ),
        (_("Timing"), {"fields": ("start_time", "end_time")}),
        (_("Status"), {"fields": ("is_active", "status")}),
    )


class PeriodAttendanceInline(admin.TabularInline):
    model = PeriodAttendance
    extra = 0
    fields = ["subject", "period_number", "is_present", "teacher_remarks"]
    readonly_fields = ["subject", "period_number"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class DailyAttendanceAdmin(InstitutionModelAdmin):
    list_display = [
        "student",
        "date",
        "attendance_session",
        "status",
        "is_late",
        "total_hours",
        "is_present",
        "marked_by",
        "created_at",
    ]
    list_filter = [
        "date",
        "attendance_session",
        "status",
        "is_late",
        "marked_by",
        "created_at",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
        "attendance_session__name",
    ]
    date_hierarchy = "date"
    readonly_fields = [
        "total_hours",
        "is_late",
        "late_minutes",
        "is_present",
        "created_at",
        "updated_at",
    ]
    inlines = [PeriodAttendanceInline]

    fieldsets = (
        (
            _("Student Information"),
            {"fields": ("student", "attendance_session", "date")},
        ),
        (
            _("Attendance Details"),
            {"fields": ("status", "check_in_time", "check_out_time")},
        ),
        (
            _("Calculated Fields"),
            {"fields": ("total_hours", "is_late", "late_minutes", "is_present")},
        ),
        (
            _("Additional Information"),
            {"fields": ("remarks", "marked_by", "ip_address", "device_info")},
        ),
        (_("Status"), {"fields": ("status",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("student__user", "attendance_session", "marked_by")
        )


class PeriodAttendanceAdmin(InstitutionModelAdmin):
    list_display = [
        "daily_attendance",
        "subject",
        "period_number",
        "is_present",
        "period_start_time",
        "period_end_time",
        "marked_by",
        "created_at",
    ]
    list_filter = ["subject", "period_number", "is_present", "created_at"]
    search_fields = [
        "daily_attendance__student__user__first_name",
        "daily_attendance__student__user__last_name",
        "subject__name",
    ]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (_("Attendance Record"), {"fields": ("daily_attendance", "subject")}),
        (
            _("Period Information"),
            {"fields": ("period_number", "period_start_time", "period_end_time")},
        ),
        (
            _("Attendance Status"),
            {"fields": ("is_present", "teacher_remarks", "marked_by")},
        ),
        (_("Status"), {"fields": ("status",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("daily_attendance__student__user", "subject", "marked_by")
        )


class LeaveTypeAdmin(InstitutionModelAdmin):
    list_display = [
        "name",
        "code",
        "max_days_per_year",
        "requires_approval",
        "is_paid",
        "allowed_for_students",
        "allowed_for_teachers",
        "status",
    ]
    list_filter = [
        "requires_approval",
        "is_paid",
        "allowed_for_students",
        "allowed_for_teachers",
        "status",
    ]
    search_fields = ["name", "code"]
    list_editable = [
        "max_days_per_year",
        "requires_approval",
        "is_paid",
        "allowed_for_students",
        "allowed_for_teachers",
    ]

    fieldsets = (
        (_("Basic Information"), {"fields": ("name", "code", "description")}),
        (
            _("Leave Policy"),
            {"fields": ("max_days_per_year", "requires_approval", "is_paid")},
        ),
        (
            _("Eligibility"),
            {"fields": ("allowed_for_students", "allowed_for_teachers")},
        ),
        (_("Display"), {"fields": ("color",)}),
        (_("Status"), {"fields": ("status",)}),
    )


class LeaveApplicationAdmin(InstitutionModelAdmin):
    list_display = [
        "applicant",
        "leave_type",
        "start_date",
        "end_date",
        "total_days",
        "status",
        "is_approved",
        "approved_by",
        "created_at",
    ]
    list_filter = [
        "leave_type",
        "status",
        "start_date",
        "end_date",
        "approved_by",
        "created_at",
    ]
    search_fields = [
        "applicant__first_name",
        "applicant__last_name",
        "applicant__email",
        "leave_type__name",
        "reason",
    ]
    date_hierarchy = "start_date"
    readonly_fields = ["total_days", "created_at", "updated_at"]

    fieldsets = (
        (_("Applicant Information"), {"fields": ("applicant", "leave_type")}),
        (_("Leave Dates"), {"fields": ("start_date", "end_date", "total_days")}),
        (_("Leave Details"), {"fields": ("reason", "supporting_documents")}),
        (
            _("Approval"),
            {"fields": ("status", "approved_by", "approved_at", "rejection_reason")},
        ),
        (_("Status"), {"fields": ("status",)}),
    )

    def is_approved(self, obj):
        return obj.is_approved

    is_approved.boolean = True
    is_approved.short_description = _("Approved")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("applicant", "leave_type", "approved_by")
        )


class AttendanceSummaryAdmin(ExportMixin, admin.ModelAdmin):
    list_display = [
        "student",
        "academic_session",
        "month",
        "year",
        "attendance_percentage",
        "days_present",
        "days_absent",
        "consecutive_absences",
        "status",
    ]
    list_filter = ["academic_session", "month", "year", "status"]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
        "academic_session__name",
    ]
    readonly_fields = ["attendance_percentage", "created_at", "updated_at"]

    fieldsets = (
        (_("Student Information"), {"fields": ("student", "academic_session")}),
        (_("Period"), {"fields": ("month", "year")}),
        (
            _("Attendance Statistics"),
            {
                "fields": (
                    "total_school_days",
                    "days_present",
                    "days_absent",
                    "days_late",
                    "days_half_day",
                    "days_on_leave",
                )
            },
        ),
        (
            _("Calculated Fields"),
            {"fields": ("attendance_percentage", "consecutive_absences")},
        ),
        (_("Status"), {"fields": ("status",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("student__user", "academic_session")
        )


class BulkAttendanceSessionAdmin(InstitutionModelAdmin):
    list_display = [
        "name",
        "class_obj",
        "date",
        "attendance_session",
        "total_students",
        "marked_students",
        "progress_percentage",
        "is_completed",
        "marked_by",
        "created_at",
    ]
    list_filter = [
        "class_obj",
        "attendance_session",
        "date",
        "is_completed",
        "created_at",
    ]
    search_fields = [
        "name",
        "class_obj__name",
        "attendance_session__name",
        "marked_by__first_name",
        "marked_by__last_name",
    ]
    readonly_fields = [
        "total_students",
        "marked_students",
        "progress_percentage",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "date"

    fieldsets = (
        (
            _("Session Information"),
            {"fields": ("name", "class_obj", "date", "attendance_session")},
        ),
        (
            _("Marking Progress"),
            {
                "fields": (
                    "total_students",
                    "marked_students",
                    "progress_percentage",
                    "is_completed",
                    "completed_at",
                )
            },
        ),
        (_("Marked By"), {"fields": ("marked_by",)}),
        (_("Status"), {"fields": ("status",)}),
    )

    def progress_percentage(self, obj):
        return f"{obj.progress_percentage}%"

    progress_percentage.short_description = _("Progress")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("class_obj", "attendance_session", "marked_by")
        )


class AttendanceExceptionAdmin(InstitutionModelAdmin):
    list_display = [
        "daily_attendance",
        "exception_type",
        "original_status",
        "new_status",
        "approved_by",
        "effective_date",
        "status",
    ]
    list_filter = [
        "exception_type",
        "original_status",
        "new_status",
        "approved_by",
        "effective_date",
        "status",
    ]
    search_fields = [
        "daily_attendance__student__user__first_name",
        "daily_attendance__student__user__last_name",
        "reason",
        "approved_by__first_name",
        "approved_by__last_name",
    ]
    readonly_fields = ["effective_date", "created_at", "updated_at"]
    date_hierarchy = "effective_date"

    fieldsets = (
        (_("Attendance Record"), {"fields": ("daily_attendance",)}),
        (
            _("Exception Details"),
            {"fields": ("exception_type", "original_status", "new_status", "reason")},
        ),
        (_("Approval"), {"fields": ("approved_by", "effective_date")}),
        (_("Status"), {"fields": ("status",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("daily_attendance__student__user", "approved_by")
        )


# Custom filters
class LateAttendanceFilter(admin.SimpleListFilter):
    title = _("late attendance")
    parameter_name = "is_late"

    def lookups(self, request, model_admin):
        return (
            ("yes", _("Late")),
            ("no", _("On Time")),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(is_late=True)
        if self.value() == "no":
            return queryset.filter(is_late=False)
        return queryset


class AbsenceDurationFilter(admin.SimpleListFilter):
    title = _("consecutive absences")
    parameter_name = "consecutive_absences"

    def lookups(self, request, model_admin):
        return (
            ("3", _("3+ Consecutive Absences")),
            ("5", _("5+ Consecutive Absences")),
            ("10", _("10+ Consecutive Absences")),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(consecutive_absences__gte=int(self.value()))
        return queryset


# Add custom filters to relevant admins
DailyAttendanceAdmin.list_filter.append(LateAttendanceFilter)
AttendanceSummaryAdmin.list_filter.append(AbsenceDurationFilter)


# Custom admin actions
def mark_selected_present(modeladmin, request, queryset):
    updated = queryset.update(status="present")
    modeladmin.message_user(
        request, _("Successfully marked %d attendance records as present.") % updated
    )


mark_selected_present.short_description = _("Mark selected as present")


def mark_selected_absent(modeladmin, request, queryset):
    updated = queryset.update(status="absent")
    modeladmin.message_user(
        request, _("Successfully marked %d attendance records as absent.") % updated
    )


mark_selected_absent.short_description = _("Mark selected as absent")


def approve_selected_leaves(modeladmin, request, queryset):
    updated = queryset.filter(status="pending").update(
        status="approved", approved_by=request.user, approved_at=timezone.now()
    )
    modeladmin.message_user(
        request, _("Successfully approved %d leave applications.") % updated
    )


approve_selected_leaves.short_description = _("Approve selected leaves")


def reject_selected_leaves(modeladmin, request, queryset):
    updated = queryset.filter(status="pending").update(
        status="rejected", approved_by=request.user, approved_at=timezone.now()
    )
    modeladmin.message_user(
        request, _("Successfully rejected %d leave applications.") % updated
    )


reject_selected_leaves.short_description = _("Reject selected leaves")


def complete_bulk_sessions(modeladmin, request, queryset):
    updated = queryset.filter(is_completed=False).update(
        is_completed=True, completed_at=timezone.now()
    )
    modeladmin.message_user(
        request, _("Successfully marked %d bulk sessions as completed.") % updated
    )


complete_bulk_sessions.short_description = _("Mark bulk sessions as completed")


# NOTE: Custom AttendanceAdminSite removed. Models are registered with the
# default admin site via the admin.register decorators above. Export actions
# are added below to the admin classes.


# Add custom actions to models
DailyAttendanceAdmin.actions = [mark_selected_present, mark_selected_absent]
LeaveApplicationAdmin.actions = [approve_selected_leaves, reject_selected_leaves]
BulkAttendanceSessionAdmin.actions = [complete_bulk_sessions]
