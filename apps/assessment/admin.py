# apps/assessment/admin.py

from django.contrib import admin
from apps.core.admin import InstitutionModelAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import (
    ExamType,
    GradingSystem,
    Grade,
    Exam,
    ExamAttendance,
    Mark,
    Assignment,
    Result,
    ResultSubject,
    ReportCard,
    AssessmentRule,
)

User = get_user_model()


class ExamTypeAdmin(InstitutionModelAdmin):
    list_display = ["name", "code", "weightage", "is_final", "order", "status"]
    list_filter = ["is_final", "status", "created_at"]
    search_fields = ["name", "code"]
    ordering = ["order", "name"]
    list_editable = ["order", "status"]


class GradeInline(admin.TabularInline):
    model = Grade
    extra = 1
    fields = ["grade", "description", "min_mark", "max_mark", "grade_point", "remark"]


class GradingSystemAdmin(InstitutionModelAdmin):
    list_display = ["name", "code", "is_active", "grade_count", "status"]
    list_filter = ["is_active", "status"]
    search_fields = ["name", "code"]
    inlines = [GradeInline]

    def grade_count(self, obj):
        return obj.grades.count()

    grade_count.short_description = _("Number of Grades")


class GradeAdmin(InstitutionModelAdmin):
    list_display = [
        "grade",
        "grading_system",
        "min_mark",
        "max_mark",
        "grade_point",
        "status",
    ]
    list_filter = ["grading_system", "status"]
    search_fields = ["grade", "description"]
    ordering = ["grading_system", "min_mark"]


class ExamAttendanceInline(admin.TabularInline):
    model = ExamAttendance
    extra = 0
    fields = ["student", "is_present", "late_minutes", "remarks"]
    readonly_fields = ["student"]
    can_delete = False


class ExamAdmin(InstitutionModelAdmin):
    list_display = [
        "name",
        "code",
        "exam_type",
        "academic_class",
        "subject",
        "exam_date",
        "total_marks",
        "is_published",
        "status",
    ]
    list_filter = [
        "exam_type",
        "academic_class",
        "subject",
        "exam_date",
        "is_published",
        "status",
    ]
    search_fields = ["name", "code", "academic_class__name", "subject__name"]
    date_hierarchy = "exam_date"
    readonly_fields = ["duration"]
    inlines = [ExamAttendanceInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "code", "exam_type", "academic_class", "subject")},
        ),
        (
            _("Schedule & Venue"),
            {"fields": ("exam_date", "start_time", "end_time", "venue", "duration")},
        ),
        (
            _("Marks & Instructions"),
            {"fields": ("total_marks", "passing_marks", "instructions")},
        ),
        (_("Publication"), {"fields": ("is_published", "published_at")}),
        (_("Status"), {"fields": ("status",)}),
    )


class ExamAttendanceAdmin(InstitutionModelAdmin):
    list_display = ["exam", "student", "is_present", "late_minutes", "created_at"]
    list_filter = ["is_present", "exam__exam_date", "created_at"]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "exam__name",
    ]
    readonly_fields = ["created_at", "updated_at"]


class MarkAdmin(InstitutionModelAdmin):
    list_display = [
        "student",
        "exam",
        "marks_obtained",
        "max_marks",
        "percentage",
        "is_absent",
        "is_pass",
        "entered_by",
        "entered_at",
    ]
    list_filter = [
        "exam__exam_type",
        "exam__academic_class",
        "exam__subject",
        "is_absent",
        "entered_at",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "exam__name",
        "exam__subject__name",
    ]
    readonly_fields = ["max_marks", "percentage", "entered_at"]

    def is_pass(self, obj):
        return obj.is_pass

    is_pass.boolean = True
    is_pass.short_description = _("Passed")


class AssignmentSubmissionInline(admin.TabularInline):
    model = Assignment
    extra = 0
    fields = ["student", "submission_status", "submission_date", "marks_obtained"]
    readonly_fields = ["student", "submission_date"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class AssignmentAdmin(InstitutionModelAdmin):
    list_display = [
        "title",
        "assignment_type",
        "subject",
        "get_class",
        "teacher",
        "due_date",
        "total_marks",
        "is_published",
        "submission_count",
        "graded_count",
        "status",
    ]
    list_filter = [
        "assignment_type",
        "subject",
        "academic_class",
        "teacher",
        "is_published",
        "submission_status",
        "status",
        "due_date",
    ]
    search_fields = [
        "title",
        "subject__name",
        "teacher__user__first_name",
        "teacher__user__last_name",
        "description",
    ]
    date_hierarchy = "due_date"
    readonly_fields = [
        "submission_count",
        "graded_count",
        "is_overdue",
        "days_until_due",
        "submission_rate",
    ]

    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "title",
                    "assignment_type",
                    "subject",
                    "academic_class",
                    "class_assigned",
                    "teacher",
                    "academic_session",
                )
            },
        ),
        (
            _("Content & Instructions"),
            {
                "fields": (
                    "description",
                    "instructions",
                    "attachment",
                    "grading_criteria",
                )
            },
        ),
        (_("Timing"), {"fields": ("publish_date", "due_date", "assigned_date")}),
        (
            _("Grading"),
            {
                "fields": (
                    "total_marks",
                    "passing_marks",
                    "weightage",
                    "allow_late_submissions",
                    "late_submission_penalty",
                )
            },
        ),
        (
            _("Submission Settings"),
            {"fields": ("max_submission_attempts", "max_file_size")},
        ),
        (_("Publication"), {"fields": ("is_published", "display_order", "tags")}),
        (
            _("Statistics"),
            {
                "fields": (
                    "submission_count",
                    "graded_count",
                    "is_overdue",
                    "days_until_due",
                    "submission_rate",
                ),
                "classes": ("collapse",),
            },
        ),
        (_("Status"), {"fields": ("status",)}),
    )

    def get_class(self, obj):
        return obj.get_class()

    get_class.short_description = _("Class")

    def submission_count(self, obj):
        return obj.submission_count

    submission_count.short_description = _("Submissions")

    def graded_count(self, obj):
        return obj.graded_count

    graded_count.short_description = _("Graded")

    def is_overdue(self, obj):
        return obj.is_overdue

    is_overdue.boolean = True
    is_overdue.short_description = _("Overdue")

    def get_queryset(self, request):
        # Only show assignment templates (not individual submissions) in list view
        return super().get_queryset(request).filter(student__isnull=True)


class AssignmentSubmissionAdmin(InstitutionModelAdmin):
    list_display = [
        "student",
        "title",
        "subject",
        "submission_status",
        "submission_date",
        "marks_obtained",
        "is_late_submission",
        "graded_by",
        "graded_date",
    ]
    list_filter = [
        "submission_status",
        "is_late_submission",
        "subject",
        "graded_date",
        "submission_date",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "title",
        "subject__name",
    ]
    readonly_fields = [
        "submission_date",
        "is_late_submission",
        "late_minutes",
        "percentage",
        "is_passing",
        "can_resubmit",
    ]

    fieldsets = (
        (
            _("Submission Details"),
            {
                "fields": (
                    "student",
                    "title",
                    "subject",
                    "submission_status",
                    "submission_attempt",
                    "original_submission",
                )
            },
        ),
        (
            _("Submission Content"),
            {
                "fields": (
                    "submission_text",
                    "submission_attachment",
                    "submission_file_name",
                    "submission_file_size",
                )
            },
        ),
        (
            _("Timing"),
            {"fields": ("submission_date", "is_late_submission", "late_minutes")},
        ),
        (
            _("Grading"),
            {
                "fields": (
                    "marks_obtained",
                    "penalty_applied",
                    "final_marks",
                    "percentage",
                    "is_passing",
                    "rubric_scores",
                )
            },
        ),
        (
            _("Feedback"),
            {
                "fields": (
                    "feedback",
                    "student_feedback",
                    "graded_by",
                    "graded_date",
                    "is_feedback_read",
                )
            },
        ),
        (_("Resubmission"), {"fields": ("can_resubmit",), "classes": ("collapse",)}),
        (_("Status"), {"fields": ("status",)}),
    )

    def get_queryset(self, request):
        # Only show student submissions
        return super().get_queryset(request).filter(student__isnull=False)


class ResultSubjectInline(admin.TabularInline):
    model = ResultSubject
    extra = 0
    fields = ["subject", "marks_obtained", "max_marks", "percentage", "grade"]
    readonly_fields = ["percentage"]


class ResultAdmin(InstitutionModelAdmin):
    list_display = [
        "student",
        "academic_class",
        "exam_type",
        "total_marks",
        "marks_obtained",
        "percentage",
        "grade",
        "rank",
        "is_promoted",
        "status",
    ]
    list_filter = ["academic_class", "exam_type", "grade", "is_promoted", "status"]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "academic_class__name",
        "exam_type__name",
    ]
    readonly_fields = ["percentage", "attendance_percentage"]
    inlines = [ResultSubjectInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("student__user", "academic_class", "exam_type", "grade")
        )


class ResultSubjectAdmin(InstitutionModelAdmin):
    list_display = [
        "result",
        "subject",
        "marks_obtained",
        "max_marks",
        "percentage",
        "grade",
        "status",
    ]
    list_filter = ["subject", "grade", "status"]
    search_fields = [
        "result__student__user__first_name",
        "result__student__user__last_name",
        "subject__name",
    ]
    readonly_fields = ["percentage"]


class ReportCardAdmin(InstitutionModelAdmin):
    list_display = [
        "student",
        "academic_class",
        "exam_type",
        "generated_at",
        "is_approved",
        "approved_by",
        "parent_signature",
        "status",
    ]
    list_filter = [
        "academic_class",
        "exam_type",
        "is_approved",
        "parent_signature",
        "generated_at",
        "status",
    ]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "academic_class__name",
        "exam_type__name",
    ]
    readonly_fields = ["generated_at"]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("student", "academic_class", "exam_type", "result")},
        ),
        (
            _("Approval"),
            {
                "fields": (
                    "is_approved",
                    "approved_by",
                    "approved_at",
                    "parent_signature",
                )
            },
        ),
        (_("Generation"), {"fields": ("generated_by", "generated_at", "comments")}),
        (_("Status"), {"fields": ("status",)}),
    )


class AssessmentRuleAdmin(InstitutionModelAdmin):
    list_display = ["name", "key", "applies_to", "status"]
    list_filter = ["applies_to", "status"]
    search_fields = ["name", "key", "description"]
    readonly_fields = ["key"]


# Custom admin site configuration
class AssessmentAdminSite(admin.AdminSite):
    site_header = _("Assessment Management System")
    site_title = _("Assessment Admin")
    index_title = _("Assessment Administration")


# Create instance of custom admin site
assessment_admin_site = AssessmentAdminSite(name="assessment_admin")

# Register models with custom admin site
assessment_admin_site.register(ExamType, ExamTypeAdmin)
assessment_admin_site.register(GradingSystem, GradingSystemAdmin)
assessment_admin_site.register(Grade, GradeAdmin)
assessment_admin_site.register(Exam, ExamAdmin)
assessment_admin_site.register(ExamAttendance, ExamAttendanceAdmin)
assessment_admin_site.register(Mark, MarkAdmin)
assessment_admin_site.register(Assignment, AssignmentAdmin)
# Register AssignmentSubmissionAdmin separately for submissions
assessment_admin_site.register(Result, ResultAdmin)
assessment_admin_site.register(ResultSubject, ResultSubjectAdmin)
assessment_admin_site.register(ReportCard, ReportCardAdmin)
assessment_admin_site.register(AssessmentRule, AssessmentRuleAdmin)


# Custom admin action examples
def publish_selected_assignments(modeladmin, request, queryset):
    queryset.update(is_published=True)


publish_selected_assignments.short_description = _("Publish selected assignments")


def unpublish_selected_assignments(modeladmin, request, queryset):
    queryset.update(is_published=False)


unpublish_selected_assignments.short_description = _("Unpublish selected assignments")


def approve_selected_report_cards(modeladmin, request, queryset):
    from django.utils import timezone

    queryset.update(
        is_approved=True, approved_by=request.user, approved_at=timezone.now()
    )


approve_selected_report_cards.short_description = _("Approve selected report cards")

# Add custom actions to models
AssignmentAdmin.actions = [publish_selected_assignments, unpublish_selected_assignments]
ReportCardAdmin.actions = [approve_selected_report_cards]
