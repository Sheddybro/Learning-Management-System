# apps/academics/admin.py

import logging

from django.contrib import admin
from apps.core.admin import InstitutionModelAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError

from .models import (
    Department,
    Subject,
    GradeLevel,
    Class,
    Student,
    Teacher,
    Enrollment,
    SubjectAssignment,
    AcademicRecord,
    Timetable,
    AttendanceSchedule,
    ClassMaterial,
    BehaviorRecord,
    Achievement,
    ParentGuardian,
    StudentParentRelationship,
    ClassTransferHistory,
    AcademicWarning,
    Holiday,
    FileAttachment,
    AcademicSession,
)
from apps.academics.forms import AcademicSessionForm
from apps.core.admin import InstitutionModelAdmin
from django.contrib.admin import ModelAdmin

logger = logging.getLogger(__name__)


class TeacherInline(admin.TabularInline):
    """
    Inline admin for Department head of department.
    """

    model = Teacher
    extra = 0
    fields = ("teacher_id", "user", "teacher_type", "specialization")
    readonly_fields = ("teacher_id", "user", "teacher_type", "specialization")
    can_delete = False
    max_num = 0
    verbose_name_plural = _("Department Teachers")

    def has_add_permission(self, request, obj):
        return False


@admin.register(Department)
class DepartmentAdmin(InstitutionModelAdmin):
    """
    Admin interface for Department model.
    """

    list_display = ("name", "code", "head_of_department", "established_date", "status")
    list_filter = ("established_date", "status", "created_at")
    search_fields = ("name", "code", "description")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("head_of_department",)
    raw_id_fields = ("head_of_department",)

    fieldsets = (
        (
            _("Department Information"),
            {
                "fields": (
                    "name",
                    "code",
                    "description",
                    "head_of_department",
                    "established_date",
                )
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [TeacherInline]


@admin.register(Subject)
class SubjectAdmin(InstitutionModelAdmin):
    """
    Admin interface for Subject model.
    """

    list_display = (
        "name",
        "code",
        "subject_type",
        "department",
        "credits",
        "is_active",
    )
    list_filter = ("subject_type", "department", "is_active", "status", "created_at")
    search_fields = ("name", "code", "description")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("prerequisites",)
    autocomplete_fields = ("department",)

    fieldsets = (
        (
            _("Subject Information"),
            {
                "fields": (
                    "name",
                    "code",
                    "subject_type",
                    "department",
                    "credits",
                    "is_active",
                )
            },
        ),
        (_("Description"), {"fields": ("description",), "classes": ("collapse",)}),
        (_("Prerequisites"), {"fields": ("prerequisites",), "classes": ("collapse",)}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["activate_subjects", "deactivate_subjects"]

    def activate_subjects(self, request, queryset):
        """Admin action to activate selected subjects."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} subjects activated.", messages.SUCCESS)

    activate_subjects.short_description = _("Activate selected subjects")

    def deactivate_subjects(self, request, queryset):
        """Admin action to deactivate selected subjects."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} subjects deactivated.", messages.WARNING)

    deactivate_subjects.short_description = _("Deactivate selected subjects")


@admin.register(GradeLevel)
class GradeLevelAdmin(InstitutionModelAdmin):
    """
    Admin interface for GradeLevel model.
    """

    list_display = (
        "name",
        "code",
        "education_stage",
        "grade_type",
        "short_name",
        "is_entry_level",
        "is_final_level",
    )
    list_filter = (
        "education_stage",
        "grade_type",
        "is_entry_level",
        "is_final_level",
        "status",
    )
    search_fields = ("name", "code", "short_name", "description")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("next_level",)

    fieldsets = (
        (
            _("Grade Level Information"),
            {
                "fields": (
                    "name",
                    "code",
                    "education_stage",
                    "grade_type",
                    "short_name",
                    "description",
                )
            },
        ),
        (
            _("Age Information"),
            {
                "fields": ("typical_start_age", "typical_end_age"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Academic Information"),
            {"fields": ("credit_hours", "base_tuition_fee"), "classes": ("collapse",)},
        ),
        (
            _("Progression"),
            {
                "fields": ("is_entry_level", "is_final_level", "next_level"),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


class EnrollmentInline(admin.TabularInline):
    """
    Inline admin for Class enrollments.
    """

    model = Enrollment
    extra = 0
    fields = ("student", "enrollment_status", "roll_number", "enrollment_date")
    readonly_fields = ("enrollment_date",)
    autocomplete_fields = ("student",)
    verbose_name_plural = _("Current Enrollments")
    max_num = 0

    def get_queryset(self, request):
        """Only show active enrollments."""
        return (
            super()
            .get_queryset(request)
            .filter(enrollment_status="active", academic_session__is_current=True)
            .select_related("student__user")
        )


@admin.register(Class)
class ClassAdmin(InstitutionModelAdmin):
    """
    Admin interface for Class model.
    """

    list_display = (
        "name",
        "code",
        "grade_level",
        "class_type",
        "class_teacher",
        "room_number",
        "current_student_count",
        "capacity",
        "is_full",
    )
    list_filter = ("grade_level", "class_type", "academic_session", "status")
    search_fields = ("name", "code", "room_number", "class_teacher__user__email")
    readonly_fields = (
        "created_at",
        "updated_at",
        "current_student_count",
        "available_seats",
    )
    autocomplete_fields = ("grade_level", "class_teacher", "academic_session")
    raw_id_fields = ("class_teacher",)

    fieldsets = (
        (
            _("Class Information"),
            {
                "fields": (
                    "name",
                    "code",
                    "grade_level",
                    "class_type",
                    "capacity",
                    "room_number",
                )
            },
        ),
        (
            _("Staff Assignment"),
            {"fields": ("class_teacher",), "classes": ("collapse",)},
        ),
        (
            _("Academic Session"),
            {"fields": ("academic_session",), "classes": ("collapse",)},
        ),
        (
            _("Statistics"),
            {
                "fields": ("current_student_count", "available_seats"),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [EnrollmentInline]

    def current_student_count(self, obj):
        return obj.current_student_count

    current_student_count.short_description = _("Students")

    def available_seats(self, obj):
        return obj.available_seats

    available_seats.short_description = _("Available Seats")

    def is_full(self, obj):
        return obj.is_full()

    is_full.boolean = True
    is_full.short_description = _("Full")


class EnrollmentInlineForStudent(admin.TabularInline):
    """
    Inline admin for Student enrollments.
    """

    model = Enrollment
    extra = 0
    fields = (
        "class_enrolled",
        "academic_session",
        "enrollment_status",
        "roll_number",
        "enrollment_date",
    )
    readonly_fields = ("enrollment_date",)
    autocomplete_fields = ("class_enrolled", "academic_session")
    verbose_name_plural = _("Enrollment History")


class AcademicRecordInline(admin.TabularInline):
    """
    Inline admin for Student academic records.
    """

    model = AcademicRecord
    extra = 0
    fields = (
        "class_enrolled",
        "academic_session",
        "overall_grade",
        "percentage",
        "rank_in_class",
    )
    readonly_fields = (
        "class_enrolled",
        "academic_session",
        "overall_grade",
        "percentage",
        "rank_in_class",
    )
    autocomplete_fields = ("class_enrolled", "academic_session")
    verbose_name_plural = _("Academic Records")
    max_num = 0

    def has_add_permission(self, request, obj):
        return False


@admin.register(Student)
class StudentAdmin(InstitutionModelAdmin):
    """
    Admin interface for Student model.
    """

    list_display = (
        "student_id",
        "user",
        "admission_number",
        "current_class",
        "gender",
        "student_type",
        "is_boarder",
        "age",
    )
    list_filter = (
        "gender",
        "student_type",
        "is_boarder",
        "has_special_needs",
        "status",
        "admission_date",
    )
    search_fields = (
        "student_id",
        "admission_number",
        "user__email",
        "user__first_name",
        "user__last_name",
    )
    readonly_fields = ("created_at", "updated_at", "age", "current_class")
    raw_id_fields = ("user",)

    fieldsets = (
        (
            _("Student Information"),
            {"fields": ("user", "student_id", "admission_number", "admission_date")},
        ),
        (
            _("Personal Details"),
            {
                "fields": (
                    "date_of_birth",
                    "place_of_birth",
                    "gender",
                    "blood_group",
                    "nationality",
                    "religion",
                )
            },
        ),
        (
            _("Student Type"),
            {
                "fields": (
                    "student_type",
                    "is_boarder",
                    "has_special_needs",
                    "special_needs_description",
                    "previous_school",
                )
            },
        ),
        (
            _("Contact Information"),
            {
                "fields": (
                    "phone",
                    "mobile",
                    "email",
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                    "emergency_contact",
                    "emergency_phone",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Parent Information"),
            {
                "fields": (
                    "father_name",
                    "father_occupation",
                    "father_phone",
                    "father_email",
                    "mother_name",
                    "mother_occupation",
                    "mother_phone",
                    "mother_email",
                    "guardian_name",
                    "guardian_relation",
                    "guardian_occupation",
                    "guardian_phone",
                    "guardian_email",
                ),
                "classes": ("collapse",),
            },
        ),
        (_("Profile Photo"), {"fields": ("photo",), "classes": ("collapse",)}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [EnrollmentInlineForStudent, AcademicRecordInline]

    def age(self, obj):
        return obj.age

    age.short_description = _("Age")

    def current_class(self, obj):
        return obj.current_class

    current_class.short_description = _("Current Class")


class SubjectAssignmentInline(admin.TabularInline):
    """
    Inline admin for Teacher subject assignments.
    """

    model = SubjectAssignment
    extra = 0
    fields = (
        "subject",
        "class_assigned",
        "academic_session",
        "periods_per_week",
        "is_primary_teacher",
    )
    autocomplete_fields = ("subject", "class_assigned", "academic_session")
    verbose_name_plural = _("Subject Assignments")


@admin.register(Teacher)
class TeacherAdmin(InstitutionModelAdmin):
    """
    Admin interface for Teacher model.
    """

    list_display = (
        "teacher_id",
        "user",
        "employee_id",
        "department",
        "teacher_type",
        "qualification",
        "joining_date",
        "is_class_teacher",
    )
    list_filter = (
        "teacher_type",
        "qualification",
        "department",
        "is_class_teacher",
        "status",
        "joining_date",
    )
    search_fields = (
        "teacher_id",
        "employee_id",
        "user__email",
        "user__first_name",
        "user__last_name",
        "specialization",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "subjects_taught_list",
        "current_classes_list",
    )
    raw_id_fields = ("user",)
    autocomplete_fields = ("department",)

    fieldsets = (
        (
            _("Teacher Information"),
            {
                "fields": (
                    "user",
                    "teacher_id",
                    "employee_id",
                    "department",
                    "teacher_type",
                )
            },
        ),
        (
            _("Personal Details"),
            {"fields": ("date_of_birth", "gender", "qualification", "specialization")},
        ),
        (
            _("Employment Details"),
            {"fields": ("joining_date", "experience_years", "is_class_teacher", "bio")},
        ),
        (
            _("Contact Information"),
            {
                "fields": (
                    "phone",
                    "mobile",
                    "email",
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                    "emergency_contact",
                    "emergency_phone",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Current Assignments"),
            {
                "fields": ("subjects_taught_list", "current_classes_list"),
                "classes": ("collapse",),
            },
        ),
        (_("Profile Photo"), {"fields": ("photo",), "classes": ("collapse",)}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [SubjectAssignmentInline]

    def subjects_taught_list(self, obj):
        subjects = obj.subjects_taught
        if subjects:
            return ", ".join([str(subject) for subject in subjects])
        return _("No subjects assigned")

    subjects_taught_list.short_description = _("Subjects Taught")

    def current_classes_list(self, obj):
        classes = obj.current_classes
        if classes:
            return ", ".join([str(cls) for cls in classes])
        return _("No classes assigned")

    current_classes_list.short_description = _("Current Classes")


@admin.register(Enrollment)
class EnrollmentAdmin(InstitutionModelAdmin):
    """
    Admin interface for Enrollment model.
    """

    list_display = (
        "student",
        "class_enrolled",
        "academic_session",
        "enrollment_status",
        "roll_number",
        "enrollment_date",
    )
    list_filter = (
        "enrollment_status",
        "academic_session",
        "class_enrolled__grade_level",
        "created_at",
    )
    search_fields = (
        "student__user__email",
        "student__student_id",
        "class_enrolled__name",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("student", "class_enrolled", "academic_session")
    raw_id_fields = ("student",)

    fieldsets = (
        (
            _("Enrollment Information"),
            {
                "fields": (
                    "student",
                    "class_enrolled",
                    "academic_session",
                    "enrollment_status",
                )
            },
        ),
        (
            _("Enrollment Details"),
            {"fields": ("enrollment_date", "roll_number", "remarks")},
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["transfer_students", "mark_as_withdrawn"]

    def transfer_students(self, request, queryset):
        """Admin action to transfer students to different classes."""
        # This would typically open a custom form for class selection
        self.message_user(
            request, "Transfer functionality would be implemented here.", messages.INFO
        )

    transfer_students.short_description = _("Transfer selected students")

    def mark_as_withdrawn(self, request, queryset):
        """Admin action to mark enrollments as withdrawn."""
        updated = queryset.update(enrollment_status="withdrawn")
        self.message_user(
            request, f"{updated} enrollments marked as withdrawn.", messages.WARNING
        )

    mark_as_withdrawn.short_description = _("Mark selected enrollments as withdrawn")


@admin.register(SubjectAssignment)
class SubjectAssignmentAdmin(InstitutionModelAdmin):
    """
    Admin interface for SubjectAssignment model.
    """

    list_display = (
        "teacher",
        "subject",
        "class_assigned",
        "academic_session",
        "periods_per_week",
        "is_primary_teacher",
    )
    list_filter = (
        "academic_session",
        "is_primary_teacher",
        "subject__department",
        "created_at",
    )
    search_fields = ("teacher__user__email", "subject__name", "class_assigned__name")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("teacher", "subject", "class_assigned", "academic_session")
    raw_id_fields = ("teacher",)

    fieldsets = (
        (
            _("Assignment Information"),
            {"fields": ("teacher", "subject", "class_assigned", "academic_session")},
        ),
        (_("Teaching Details"), {"fields": ("periods_per_week", "is_primary_teacher")}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(AcademicRecord)
class AcademicRecordAdmin(InstitutionModelAdmin):
    """
    Admin interface for AcademicRecord model.
    """

    list_display = (
        "student",
        "class_enrolled",
        "academic_session",
        "overall_grade",
        "percentage",
        "rank_in_class",
        "promoted_to_class",
    )
    list_filter = ("academic_session", "class_enrolled__grade_level", "created_at")
    search_fields = (
        "student__user__email",
        "student__student_id",
        "class_enrolled__name",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = (
        "student",
        "class_enrolled",
        "academic_session",
        "promoted_to_class",
    )
    raw_id_fields = ("student",)

    fieldsets = (
        (
            _("Academic Record"),
            {"fields": ("student", "class_enrolled", "academic_session")},
        ),
        (
            _("Performance"),
            {
                "fields": (
                    "overall_grade",
                    "total_marks",
                    "percentage",
                    "rank_in_class",
                    "total_students_in_class",
                )
            },
        ),
        (
            _("Promotion"),
            {
                "fields": ("promoted_to_class", "promotion_date", "remarks"),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


class TimetableInline(admin.TabularInline):
    """
    Inline admin for Class timetable entries.
    """

    model = Timetable
    extra = 0
    fields = (
        "day_of_week",
        "period_number",
        "period_type",
        "subject",
        "teacher",
        "start_time",
        "end_time",
        "room_number",
    )
    autocomplete_fields = ("subject", "teacher")
    verbose_name_plural = _("Timetable Entries")
    max_num = 40  # Reasonable limit for weekly periods


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    """
    Admin interface for Timetable model.
    """

    list_display = (
        "class_assigned",
        "day_of_week",
        "period_number",
        "period_type",
        "subject",
        "teacher",
        "start_time",
        "end_time",
        "room_number",
    )
    list_filter = (
        "day_of_week",
        "period_type",
        "academic_session",
        "class_assigned__grade_level",
        "created_at",
    )
    search_fields = (
        "class_assigned__name",
        "subject__name",
        "teacher__user__email",
        "room_number",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "duration_minutes",
        "display_room_info",
    )
    autocomplete_fields = ("class_assigned", "subject", "teacher", "academic_session")

    fieldsets = (
        (
            _("Scheduling"),
            {
                "fields": (
                    "class_assigned",
                    "academic_session",
                    "day_of_week",
                    "period_number",
                    "period_type",
                )
            },
        ),
        (_("Time"), {"fields": ("start_time", "end_time", "duration_minutes")}),
        (
            _("Academic Content"),
            {"fields": ("subject", "teacher"), "classes": ("collapse",)},
        ),
        (
            _("Room Allocation"),
            {
                "fields": (
                    "room_number",
                    "room_name",
                    "room_type",
                    "room_capacity",
                    "room_building",
                    "room_floor",
                    "room_facilities",
                    "display_room_info",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Additional Information"),
            {
                "fields": (
                    "title",
                    "description",
                    "color_code",
                    "is_published",
                    "is_shared_event",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    filter_horizontal = ("shared_with_classes",)

    def duration_minutes(self, obj):
        return obj.duration_minutes

    duration_minutes.short_description = _("Duration (minutes)")

    def display_room_info(self, obj):
        return obj.display_room_info

    display_room_info.short_description = _("Room Information")


# Register remaining models with basic admin interfaces
@admin.register(AttendanceSchedule)
class AttendanceScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "class_assigned",
        "academic_session",
        "session_type",
        "session_start_time",
        "session_end_time",
    )
    list_filter = ("session_type", "academic_session")
    autocomplete_fields = ("class_assigned", "academic_session")


@admin.register(ClassMaterial)
class ClassMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "material_type",
        "subject",
        "class_assigned",
        "teacher",
        "is_public",
        "download_count",
    )
    list_filter = ("material_type", "access_level", "is_public", "is_featured")
    search_fields = ("title", "description", "subject__name")
    autocomplete_fields = ("subject", "class_assigned", "teacher", "academic_session")
    readonly_fields = (
        "download_count",
        "view_count",
        "last_downloaded",
        "last_viewed",
        "file_size",
    )


@admin.register(BehaviorRecord)
class BehaviorRecordAdmin(admin.ModelAdmin):
    list_display = (
        "case_number",
        "student",
        "behavior_type",
        "severity",
        "incident_category",
        "reported_by",
        "incident_date",
        "is_resolved",
    )
    list_filter = ("behavior_type", "severity", "incident_category", "is_resolved")
    search_fields = ("case_number", "student__user__email", "title")
    autocomplete_fields = ("student", "reported_by", "escalated_to")
    raw_id_fields = ("student", "reported_by")


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "achievement_type",
        "achievement_level",
        "title",
        "achievement_date",
        "organization",
    )
    list_filter = ("achievement_type", "achievement_level")
    search_fields = ("student__user__email", "title", "organization")
    autocomplete_fields = ("student",)


@admin.register(ParentGuardian)
class ParentGuardianAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "user",
        "gender",
        "occupation",
        "is_primary_contact",
        "emergency_contact_priority",
    )
    list_filter = ("gender", "is_primary_contact")
    search_fields = ("first_name", "last_name", "user__email", "occupation")
    raw_id_fields = ("user",)


@admin.register(StudentParentRelationship)
class StudentParentRelationshipAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "parent",
        "relationship",
        "is_legal_guardian",
        "has_custody",
        "lives_with_student",
    )
    list_filter = (
        "relationship",
        "is_legal_guardian",
        "has_custody",
        "lives_with_student",
    )
    search_fields = ("student__user__email", "parent__first_name", "parent__last_name")
    autocomplete_fields = ("student", "parent")


@admin.register(ClassTransferHistory)
class ClassTransferHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "from_class",
        "to_class",
        "transfer_date",
        "academic_session",
    )
    list_filter = ("academic_session", "transfer_date")
    search_fields = ("student__user__email", "from_class__name", "to_class__name")
    autocomplete_fields = ("student", "from_class", "to_class", "academic_session")
    raw_id_fields = ("student", "initiated_by", "approved_by")


@admin.register(AcademicWarning)
class AcademicWarningAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "warning_type",
        "warning_level",
        "title",
        "issued_date",
        "is_resolved",
    )
    list_filter = ("warning_type", "warning_level", "is_resolved", "parent_notified")
    search_fields = ("student__user__email", "title", "description")
    autocomplete_fields = ("student", "issued_by")
    raw_id_fields = ("student",)


@admin.register(FileAttachment)
class FileAttachmentAdmin(admin.ModelAdmin):
    """
    Admin interface for FileAttachment model.
    """

    list_display = (
        "title",
        "display_file_type",
        "display_file_size",
        "uploaded_by",
        "uploaded_at",
    )
    list_filter = ("status", "uploaded_at")
    search_fields = ("title", "description", "uploaded_by__email")
    readonly_fields = (
        "uploaded_at",
        "updated_at",
        "display_file_type",
        "display_file_size",
    )

    fieldsets = (
        (_("File Information"), {"fields": ("title", "file", "description")}),
        (
            _("Upload Details"),
            {"fields": ("uploaded_by", "uploaded_at"), "classes": ("collapse",)},
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make file-related fields read-only for existing objects."""
        if obj:
            return self.readonly_fields + ("file",)
        return self.readonly_fields

    def display_file_type(self, obj):
        if obj.file:
            return obj.file.name.split(".")[-1].upper()
        return _("N/A")

    display_file_type.short_description = _("File Type")

    def display_file_size(self, obj):
        if obj.file and obj.file.size:
            size_bytes = obj.file.size
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.2f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.2f} MB"
            else:
                return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
        return _("N/A")

    display_file_size.short_description = _("Size")


@admin.register(AcademicSession)
class AcademicSessionAdmin(InstitutionModelAdmin):
    """
    Admin interface for AcademicSession model.
    """

    form = AcademicSessionForm
    list_display = (
        "name",
        "institution",
        "number_of_semesters",
        "term_number",
        "start_date",
        "end_date",
        "is_current",
        "status",
    )
    list_filter = (
        "number_of_semesters",
        "is_current",
        "status",
        "start_date",
        "institution",
    )
    search_fields = ("name", "institution__name")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "start_date"

    fieldsets = (
        (_("Institution"), {"fields": ("institution",)}),
        (
            _("Session Information"),
            {"fields": ("name", "number_of_semesters", "term_number")},
        ),
        (_("Dates"), {"fields": ("start_date", "end_date", "is_current")}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_delete_permission(self, request, obj=None):
        """
        Allow deletion for authorized users with proper institution access.
        """
        if not request.user.is_authenticated:
            return False

        # Superusers can delete anything
        if request.user.is_superuser:
            return True

        # Staff users can delete any session
        if request.user.is_staff:
            return True

        # Check if user has admin or principal role
        has_admin_role = (
            hasattr(request.user, "user_roles")
            and request.user.user_roles.filter(
                role__role_type__in=["admin", "principal"], status="active"
            ).exists()
        )

        if has_admin_role:
            # For admin/principal users, check institution access
            if obj and hasattr(obj, "institution"):
                from apps.core.middleware import get_user_accessible_institutions

                accessible_institutions = get_user_accessible_institutions(request.user)
                return obj.institution in accessible_institutions
            # If no object specified (bulk delete permission), allow it
            return True

        # Regular users - use parent class logic with institution restrictions
        return super().has_delete_permission(request, obj)

    def has_add_permission(self, request):
        """
        Allow adding for staff users, superusers, and admin/principal roles.
        """
        if not request.user.is_authenticated:
            return False

        # Superusers can add anything
        if request.user.is_superuser:
            return True

        # Staff users can add sessions
        if request.user.is_staff:
            return True

        # Check if user has admin or principal role
        if (
            hasattr(request.user, "user_roles")
            and request.user.user_roles.filter(
                role__role_type__in=["admin", "principal"], status="active"
            ).exists()
        ):
            return True

        # Fallback to parent class logic
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """
        Allow editing for staff users and superusers.
        """
        if not request.user.is_authenticated:
            return False

        # Superusers can change anything
        if request.user.is_superuser:
            return True

        # Staff users can change sessions
        if request.user.is_staff:
            return True

        # Check if user has admin or principal role
        if (
            hasattr(request.user, "user_roles")
            and request.user.user_roles.filter(
                role__role_type__in=["admin", "principal"], status="active"
            ).exists()
        ):
            return True

        # Fallback to parent class logic
        return super().has_change_permission(request, obj)

    def get_queryset(self, request):
        """
        Allow school admins to see all sessions or filter appropriately.
        """
        if request.user.is_superuser or request.user.is_staff:
            # Superusers and staff see all sessions
            return super().get_queryset(request)

        # Check if user has admin/principal role
        if (
            hasattr(request.user, "user_roles")
            and request.user.user_roles.filter(
                role__role_type__in=["admin", "principal"], status="active"
            ).exists()
        ):
            # For admin/principal users, show sessions from institutions they can access
            from apps.core.middleware import get_user_accessible_institutions

            accessible_institutions = get_user_accessible_institutions(request.user)
            if accessible_institutions:
                return self.model.objects.filter(
                    institution__in=accessible_institutions
                )
            else:
                # If no accessible institutions, show all (fallback)
                return self.model.objects.all()

        # Regular users get filtered queryset
        return super().get_queryset(request)

    def save_model(self, request, obj, form, change):
        """Enhanced save method with comprehensive error handling."""
        try:
            # Check staff permissions
            if not (request.user.is_staff or request.user.is_superuser):
                logger.error(
                    f"Permission denied: User {request.user} attempted to save AcademicSession"
                )
                raise PermissionDenied(
                    _("You don't have permission to manage academic sessions.")
                )

            # Validate the model instance manually with detailed error reporting
            try:
                obj.full_clean()
            except ValidationError as e:
                logger.error(
                    f"Validation error saving AcademicSession: {e.message_dict}"
                )
                error_messages = []
                for field, messages_list in e.message_dict.items():
                    field_name = self.get_field_display_name(field, obj)
                    for msg in messages_list:
                        error_messages.append(f"{field_name}: {msg}")
                if error_messages:
                    raise ValidationError("; ".join(error_messages))

            # Handle current session logic
            if obj.is_current:
                try:
                    deactivated_count = (
                        AcademicSession.objects.filter(is_current=True)
                        .exclude(pk=obj.pk)
                        .update(is_current=False)
                    )
                    if deactivated_count > 0:
                        logger.info(
                            f"Deactivated {deactivated_count} previous current sessions"
                        )

                    # Check if we're trying to set is_current=True on more than allowed
                    active_sessions = AcademicSession.objects.filter(is_current=True)
                    if active_sessions.count() >= 1 and not change:
                        logger.warning(
                            f"Multiple current sessions detected after save attempt"
                        )
                        # Force only one current session
                        active_sessions.exclude(pk=obj.pk).update(is_current=False)

                except IntegrityError as e:
                    logger.error(
                        f"Database constraint error during session deactivation: {e}"
                    )
                    raise ValidationError(
                        _(
                            "Failed to update current session status due to database constraints."
                        )
                    )

            # Attempt to save
            super().save_model(request, obj, form, change)

            # Log successful save
            action = "updated" if change else "created"
            logger.info(
                f"AcademicSession {action}: '{obj.name}' by user {request.user}"
            )

        except ValidationError as e:
            logger.error(f"Validation error saving AcademicSession: {str(e)}")
            messages.error(request, _("Validation error: ") + str(e))
            # Re-raise to prevent save
            raise e

        except IntegrityError as e:
            logger.error(f"Database integrity error saving AcademicSession: {str(e)}")
            messages.error(
                request,
                _(
                    "Database error: Could not save session due to data integrity constraint."
                ),
            )
            raise ValidationError(
                _("Database constraint violation. Please check the data and try again.")
            )

        except PermissionDenied as e:
            logger.error(f"Permission denied for user {request.user}: {str(e)}")
            messages.error(request, str(e))
            raise e

        except Exception as e:
            logger.error(
                f"Unexpected error saving AcademicSession: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            messages.error(
                request,
                _(
                    "An unexpected error occurred while saving the session. Please try again."
                ),
            )
            raise ValidationError(
                _("Unexpected error occurred. Administrators have been notified.")
            )

    def get_field_display_name(self, field_name, obj):
        """Helper method to get user-friendly field names for error messages."""
        field_display_names = {
            "name": _("Session Name"),
            "number_of_semesters": _("Number of Semesters"),
            "term_number": _("Term Number"),
            "start_date": _("Start Date"),
            "end_date": _("End Date"),
            "is_current": _("Current Session"),
        }
        return field_display_names.get(field_name, field_name)


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    """
    Admin interface for Holiday model.
    """

    list_display = ("name", "date", "academic_session", "is_recurring", "status")
    list_filter = ("is_recurring", "academic_session", "status", "date")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "date"

    fieldsets = (
        (
            _("Holiday Information"),
            {
                "fields": (
                    "name",
                    "date",
                    "academic_session",
                    "is_recurring",
                    "description",
                )
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
