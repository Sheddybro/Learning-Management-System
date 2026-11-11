from django.contrib import admin
from django.utils import timezone
from apps.core.admin import InstitutionModelAdmin
from .models import (
    Category,
    Tag,
    HelpCenterArticle,
    Resource,
    FAQ,
    ContactSubmission,
    LegalDocument,
    SupportCase,
    CaseUpdate,
    CaseParticipant,
    CaseAttachment,
)


@admin.register(Category)
class CategoryAdmin(InstitutionModelAdmin):
    list_display = ("name", "slug", "description", "is_active", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(Tag)
class TagAdmin(InstitutionModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(HelpCenterArticle)
class HelpCenterArticleAdmin(InstitutionModelAdmin):
    list_display = (
        "title",
        "category",
        "article_category",
        "is_published",
        "views",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_published", "category", "article_category", "tags")
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ("category",)
    date_hierarchy = "created_at"
    filter_horizontal = ("tags",)


@admin.register(Resource)
class ResourceAdmin(InstitutionModelAdmin):
    list_display = (
        "title",
        "resource_type",
        "is_published",
        "downloads",
        "created_at",
        "updated_at",
    )
    list_filter = ("resource_type", "is_published")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(FAQ)
class FAQAdmin(InstitutionModelAdmin):
    list_display = (
        "question",
        "category",
        "order",
        "is_published",
        "views",
        "created_at",
    )
    list_filter = ("is_published", "category")
    search_fields = ("question", "answer")
    list_editable = ("order", "is_published")
    raw_id_fields = ("category",)


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(InstitutionModelAdmin):
    list_display = ("name", "email", "subject", "created_at", "is_resolved", "priority")
    list_filter = ("is_resolved", "created_at", "priority")
    search_fields = ("name", "email", "subject", "message")
    readonly_fields = ("created_at",)
    actions = ["mark_resolved", "mark_unresolved"]

    def mark_resolved(self, request, queryset):
        queryset.update(is_resolved=True, resolved_at=timezone.now())
        self.message_user(request, "Selected contact submissions marked as resolved.")

    mark_resolved.short_description = "Mark selected submissions as resolved"

    def mark_unresolved(self, request, queryset):
        queryset.update(is_resolved=False, resolved_at=None)
        self.message_user(request, "Selected contact submissions marked as unresolved.")

    mark_unresolved.short_description = "Mark selected submissions as unresolved"


@admin.register(LegalDocument)
class LegalDocumentAdmin(InstitutionModelAdmin):
    list_display = (
        "title",
        "document_type",
        "version",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("document_type", "is_active")
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_active",)


# ===== STUDENT SUPPORT TEAM COLLABORATION ADMIN =====


@admin.register(SupportCase)
class SupportCaseAdmin(InstitutionModelAdmin):
    list_display = (
        "case_number",
        "title",
        "student",
        "case_type",
        "priority",
        "status",
        "reported_by",
        "created_at",
    )
    list_filter = ("case_type", "priority", "status", "is_escalated", "category")
    search_fields = (
        "case_number",
        "title",
        "description",
        "student__user__first_name",
        "student__user__last_name",
    )
    raw_id_fields = ("student", "reported_by", "resolved_by", "escalated_to")
    date_hierarchy = "created_at"
    filter_horizontal = ("tags",)
    readonly_fields = ("case_number", "created_at", "updated_at")

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "case_number",
                    "title",
                    "description",
                    "case_type",
                    "priority",
                    "status",
                )
            },
        ),
        (
            "Related Entities",
            {"fields": ("student", "reported_by", "category", "tags")},
        ),
        (
            "Resolution",
            {
                "fields": ("resolution", "resolved_at", "resolved_by"),
                "classes": ("collapse",),
            },
        ),
        (
            "Escalation",
            {
                "fields": (
                    "is_escalated",
                    "escalated_to",
                    "escalation_reason",
                    "escalated_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Communication",
            {
                "fields": (
                    "requires_parent_notification",
                    "parent_notified",
                    "parent_notification_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "estimated_resolution_time",
                    "actual_resolution_time",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(CaseUpdate)
class CaseUpdateAdmin(InstitutionModelAdmin):
    list_display = ("case", "user", "update_type", "is_private", "created_at")
    list_filter = ("update_type", "is_private", "created_at")
    search_fields = (
        "case__case_number",
        "user__first_name",
        "user__last_name",
        "content",
    )
    raw_id_fields = ("case", "user")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at")


@admin.register(CaseParticipant)
class CaseParticipantAdmin(InstitutionModelAdmin):
    list_display = ("case", "user", "role", "assigned_at", "is_active")
    list_filter = ("role", "is_active", "assigned_at")
    search_fields = ("case__case_number", "user__first_name", "user__last_name")
    raw_id_fields = ("case", "user")
    date_hierarchy = "assigned_at"


@admin.register(CaseAttachment)
class CaseAttachmentAdmin(InstitutionModelAdmin):
    list_display = (
        "case",
        "filename",
        "uploaded_by",
        "file_size",
        "is_private",
        "created_at",
    )
    list_filter = ("is_private", "created_at")
    search_fields = (
        "case__case_number",
        "filename",
        "uploaded_by__first_name",
        "uploaded_by__last_name",
    )
    raw_id_fields = ("case", "uploaded_by")
    date_hierarchy = "created_at"
    readonly_fields = ("file_size", "created_at", "updated_at")
