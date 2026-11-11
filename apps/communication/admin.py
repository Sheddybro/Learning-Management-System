# apps/communication/admin.py

from django.contrib import admin
from apps.core.admin import InstitutionModelAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    Announcement,
    Message,
    MessageRecipient,
    MessageConfirmation,
    NoticeBoard,
    NoticeBoardItem,
    EmailTemplate,
    SentEmail,
    SMSTemplate,
    SentSMS,
)

User = get_user_model()


# Export functionality
class ExportMixin:
    def export_to_csv(self, request, queryset):
        # Placeholder for CSV export functionality
        self.message_user(request, _("Export feature would be implemented here."))

    export_to_csv.short_description = _("Export selected to CSV")


class NoticeBoardItemInline(admin.TabularInline):
    model = NoticeBoardItem
    extra = 1
    fields = ["announcement", "display_order", "is_active", "display_duration"]
    ordering = ["display_order"]


class NoticeBoardAdmin(InstitutionModelAdmin):
    list_display = [
        "name",
        "board_type",
        "location",
        "is_active",
        "refresh_interval",
        "active_announcements_count",
        "status",
    ]
    list_filter = ["board_type", "is_active", "status"]
    search_fields = ["name", "location", "description"]
    list_editable = ["is_active", "refresh_interval"]
    inlines = [NoticeBoardItemInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "board_type", "description", "location")},
        ),
        (_("Display Settings"), {"fields": ("refresh_interval", "is_active")}),
        (_("Access Control"), {"fields": ("allowed_users",)}),
        (_("Status"), {"fields": ("status",)}),
    )

    def active_announcements_count(self, obj):
        return obj.active_announcements.count()

    active_announcements_count.short_description = _("Active Announcements")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("active_announcements")


class AnnouncementAdmin(InstitutionModelAdmin):
    list_display = [
        "title",
        "announcement_type",
        "priority",
        "target_audience",
        "author",
        "is_published",
        "is_pinned",
        "is_active",
        "published_at",
        "status",
    ]
    list_filter = [
        "announcement_type",
        "priority",
        "target_audience",
        "is_published",
        "is_pinned",
        "author",
        "published_at",
        "status",
    ]
    search_fields = ["title", "content", "author__first_name", "author__last_name"]
    readonly_fields = ["published_at", "created_at", "updated_at", "is_active"]
    date_hierarchy = "published_at"

    fieldsets = (
        (_("Content"), {"fields": ("title", "content", "announcement_type")}),
        (
            _("Targeting"),
            {
                "fields": (
                    "priority",
                    "target_audience",
                    "specific_users",
                    "specific_classes",
                )
            },
        ),
        (
            _("Publication"),
            {
                "fields": (
                    "is_published",
                    "published_at",
                    "schedule_publish",
                    "is_pinned",
                    "pin_until",
                    "expires_at",
                )
            },
        ),
        (_("Media"), {"fields": ("banner_image", "attachments")}),
        (_("Author"), {"fields": ("author",)}),
        (_("Status"), {"fields": ("status", "is_active")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("author")

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)


class MessageRecipientInline(admin.TabularInline):
    model = MessageRecipient
    extra = 1
    fields = ["recipient", "read_at", "deleted_at"]
    readonly_fields = ["read_at"]


class MessageConfirmationInline(admin.TabularInline):
    model = MessageConfirmation
    extra = 0
    fields = ["user", "confirmed_at", "ip_address"]
    readonly_fields = ["confirmed_at"]
    can_delete = False


class MessageAdmin(InstitutionModelAdmin):
    list_display = [
        "subject",
        "sender",
        "message_type",
        "priority",
        "is_important",
        "recipients_count",
        "read_count",
        "confirmed_count",
        "created_at",
    ]
    list_filter = [
        "message_type",
        "priority",
        "is_important",
        "requires_confirmation",
        "created_at",
        "status",
    ]
    search_fields = [
        "subject",
        "content",
        "sender__first_name",
        "sender__last_name",
        "sender__email",
    ]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [MessageRecipientInline, MessageConfirmationInline]

    fieldsets = (
        (_("Basic Information"), {"fields": ("sender", "subject", "content")}),
        (
            _("Message Settings"),
            {"fields": ("message_type", "priority", "is_important")},
        ),
        (_("Threading"), {"fields": ("parent_message",)}),
        (_("Confirmation"), {"fields": ("requires_confirmation",)}),
        (_("Attachments"), {"fields": ("attachments",)}),
        (_("Status"), {"fields": ("status",)}),
    )

    def recipients_count(self, obj):
        return obj.recipients.count()

    recipients_count.short_description = _("Recipients")

    def read_count(self, obj):
        return obj.recipient_status.filter(read_at__isnull=False).count()

    read_count.short_description = _("Read")

    def confirmed_count(self, obj):
        return obj.confirmed_by.count()

    confirmed_count.short_description = _("Confirmed")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("sender")
            .prefetch_related("recipients", "recipient_status", "confirmed_by")
        )

    def save_model(self, request, obj, form, change):
        if not obj.sender_id:
            obj.sender = request.user
        super().save_model(request, obj, form, change)


class MessageRecipientAdmin(InstitutionModelAdmin):
    list_display = [
        "recipient",
        "message",
        "is_read",
        "read_at",
        "is_deleted",
        "deleted_at",
        "created_at",
    ]
    list_filter = ["read_at", "deleted_at", "created_at"]
    search_fields = [
        "recipient__first_name",
        "recipient__last_name",
        "message__subject",
        "recipient__email",
    ]
    readonly_fields = ["read_at", "deleted_at", "created_at", "updated_at"]

    fieldsets = (
        (_("Recipient Information"), {"fields": ("recipient", "message")}),
        (_("Status"), {"fields": ("read_at", "deleted_at", "is_read", "is_deleted")}),
        (_("System"), {"fields": ("status",)}),
    )

    def is_read(self, obj):
        return obj.is_read

    is_read.boolean = True
    is_read.short_description = _("Read")

    def is_deleted(self, obj):
        return obj.is_deleted

    is_deleted.boolean = True
    is_deleted.short_description = _("Deleted")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("recipient", "message", "message__sender")
        )


class MessageConfirmationAdmin(InstitutionModelAdmin):
    list_display = ["user", "message", "confirmed_at", "ip_address"]
    list_filter = ["confirmed_at"]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "message__subject",
        "user__email",
    ]
    readonly_fields = ["confirmed_at", "created_at", "updated_at"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "message", "message__sender")
        )


class NoticeBoardItemAdmin(InstitutionModelAdmin):
    list_display = [
        "notice_board",
        "announcement",
        "display_order",
        "is_active",
        "is_currently_displayed",
        "start_display",
        "end_display",
        "status",
    ]
    list_filter = ["notice_board", "is_active", "status"]
    search_fields = ["notice_board__name", "announcement__title"]
    list_editable = ["display_order", "is_active"]

    fieldsets = (
        (_("Board Assignment"), {"fields": ("notice_board", "announcement")}),
        (_("Display Settings"), {"fields": ("display_order", "display_duration")}),
        (_("Scheduling"), {"fields": ("start_display", "end_display", "is_active")}),
        (_("Status"), {"fields": ("status", "is_currently_displayed")}),
    )

    def is_currently_displayed(self, obj):
        return obj.is_currently_displayed

    is_currently_displayed.boolean = True
    is_currently_displayed.short_description = _("Currently Displayed")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("notice_board", "announcement", "announcement__author")
        )


class EmailTemplateAdmin(InstitutionModelAdmin):
    list_display = [
        "name",
        "template_type",
        "language",
        "subject_preview",
        "is_active",
        "status",
    ]
    list_filter = ["template_type", "language", "is_active", "status"]
    search_fields = ["name", "subject", "body_text"]
    list_editable = ["is_active"]

    fieldsets = (
        (
            _("Template Information"),
            {"fields": ("name", "template_type", "language", "is_active")},
        ),
        (_("Content"), {"fields": ("subject", "body_html", "body_text")}),
        (_("Variables"), {"fields": ("variables",), "classes": ("collapse",)}),
        (_("Status"), {"fields": ("status",)}),
    )

    def subject_preview(self, obj):
        return obj.subject[:50] + "..." if len(obj.subject) > 50 else obj.subject

    subject_preview.short_description = _("Subject Preview")


class SentEmailAdmin(ExportMixin, admin.ModelAdmin):
    list_display = [
        "recipient_email",
        "recipient_user",
        "subject_preview",
        "sent_at",
        "delivered_at",
        "opened_at",
        "click_count",
        "status",
    ]
    list_filter = ["sent_at", "template", "status"]
    search_fields = [
        "recipient_email",
        "recipient_user__first_name",
        "recipient_user__last_name",
        "subject",
    ]
    readonly_fields = [
        "sent_at",
        "delivered_at",
        "opened_at",
        "click_count",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "sent_at"

    fieldsets = (
        (
            _("Recipient Information"),
            {"fields": ("recipient_email", "recipient_user", "template")},
        ),
        (_("Content"), {"fields": ("subject", "body_html", "body_text")}),
        (
            _("Delivery Status"),
            {
                "fields": (
                    "sent_at",
                    "delivered_at",
                    "opened_at",
                    "click_count",
                    "error_message",
                )
            },
        ),
        (
            _("Technical Details"),
            {"fields": ("sender", "message_id"), "classes": ("collapse",)},
        ),
        (_("Status"), {"fields": ("status",)}),
    )

    def subject_preview(self, obj):
        return obj.subject[:50] + "..." if len(obj.subject) > 50 else obj.subject

    subject_preview.short_description = _("Subject")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("recipient_user", "template", "sender")
        )


class SMSTemplateAdmin(InstitutionModelAdmin):
    list_display = ["name", "content_preview", "is_active", "status"]
    list_filter = ["is_active", "status"]
    search_fields = ["name", "content"]
    list_editable = ["is_active"]

    fieldsets = (
        (_("Template Information"), {"fields": ("name", "is_active")}),
        (_("Content"), {"fields": ("content",)}),
        (_("Variables"), {"fields": ("variables",), "classes": ("collapse",)}),
        (_("Status"), {"fields": ("status",)}),
    )

    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

    content_preview.short_description = _("Content Preview")


class SentSMSAdmin(InstitutionModelAdmin):
    list_display = [
        "recipient_phone",
        "recipient_user",
        "content_preview",
        "sent_at",
        "delivered_at",
        "cost",
        "status",
    ]
    list_filter = ["sent_at", "template", "status"]
    search_fields = [
        "recipient_phone",
        "recipient_user__first_name",
        "recipient_user__last_name",
        "content",
    ]
    readonly_fields = ["sent_at", "delivered_at", "cost", "created_at", "updated_at"]
    date_hierarchy = "sent_at"

    fieldsets = (
        (
            _("Recipient Information"),
            {"fields": ("recipient_phone", "recipient_user", "template")},
        ),
        (_("Content"), {"fields": ("content",)}),
        (
            _("Delivery Status"),
            {"fields": ("sent_at", "delivered_at", "cost", "error_message")},
        ),
        (_("Technical Details"), {"fields": ("message_id",), "classes": ("collapse",)}),
        (_("Status"), {"fields": ("status",)}),
    )

    def content_preview(self, obj):
        return obj.content[:30] + "..." if len(obj.content) > 30 else obj.content

    content_preview.short_description = _("Content")

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("recipient_user", "template")
        )


# Custom filters
class ActiveAnnouncementFilter(admin.SimpleListFilter):
    title = _("active status")
    parameter_name = "is_active"

    def lookups(self, request, model_admin):
        return (
            ("active", _("Active")),
            ("expired", _("Expired")),
            ("scheduled", _("Scheduled")),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "active":
            return queryset.filter(is_published=True, expires_at__gt=now)
        elif self.value() == "expired":
            return queryset.filter(expires_at__lte=now)
        elif self.value() == "scheduled":
            return queryset.filter(is_published=False, schedule_publish__gt=now)
        return queryset


class UnreadMessagesFilter(admin.SimpleListFilter):
    title = _("read status")
    parameter_name = "is_read"

    def lookups(self, request, model_admin):
        return (
            ("unread", _("Unread")),
            ("read", _("Read")),
        )

    def queryset(self, request, queryset):
        if self.value() == "unread":
            return queryset.filter(read_at__isnull=True)
        elif self.value() == "read":
            return queryset.filter(read_at__isnull=False)
        return queryset


# Add custom filters
AnnouncementAdmin.list_filter.append(ActiveAnnouncementFilter)
MessageRecipientAdmin.list_filter.append(UnreadMessagesFilter)


# Custom admin actions
def publish_selected_announcements(modeladmin, request, queryset):
    updated = queryset.update(is_published=True, published_at=timezone.now())
    modeladmin.message_user(
        request, _("Successfully published %d announcements.") % updated
    )


publish_selected_announcements.short_description = _("Publish selected announcements")


def unpublish_selected_announcements(modeladmin, request, queryset):
    updated = queryset.update(is_published=False)
    modeladmin.message_user(
        request, _("Successfully unpublished %d announcements.") % updated
    )


unpublish_selected_announcements.short_description = _(
    "Unpublish selected announcements"
)


def pin_selected_announcements(modeladmin, request, queryset):
    updated = queryset.update(is_pinned=True)
    modeladmin.message_user(
        request, _("Successfully pinned %d announcements.") % updated
    )


pin_selected_announcements.short_description = _("Pin selected announcements")


def mark_selected_messages_read(modeladmin, request, queryset):
    updated = queryset.filter(read_at__isnull=True).update(read_at=timezone.now())
    modeladmin.message_user(
        request, _("Successfully marked %d messages as read.") % updated
    )


mark_selected_messages_read.short_description = _("Mark selected as read")


def send_test_email(modeladmin, request, queryset):
    for template in queryset:
        try:
            # Send test email to the current user
            subject, body_html, body_text = template.render_template(
                {
                    "user": request.user,
                    "date": timezone.now().strftime("%Y-%m-%d"),
                    "test": "This is a test email",
                }
            )

            send_mail(
                subject=subject,
                message=body_text,
                html_message=body_html,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=False,
            )

            modeladmin.message_user(
                request,
                _("Test email sent successfully for template: %s") % template.name,
                level="SUCCESS",
            )
        except Exception as e:
            modeladmin.message_user(
                request,
                _("Failed to send test email for template %s: %s")
                % (template.name, str(e)),
                level="ERROR",
            )


send_test_email.short_description = _("Send test email for selected templates")


# Add custom actions to models
AnnouncementAdmin.actions = [
    publish_selected_announcements,
    unpublish_selected_announcements,
    pin_selected_announcements,
]
MessageRecipientAdmin.actions = [mark_selected_messages_read]
EmailTemplateAdmin.actions = [send_test_email]


# NOTE: Custom CommunicationAdminSite removed. Models are registered with the
# default admin site via the @admin.register decorators above.

# Register models with admin site
admin.site.register(NoticeBoard, NoticeBoardAdmin)
admin.site.register(Announcement, AnnouncementAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(MessageRecipient, MessageRecipientAdmin)
admin.site.register(MessageConfirmation, MessageConfirmationAdmin)
admin.site.register(NoticeBoardItem, NoticeBoardItemAdmin)
admin.site.register(EmailTemplate, EmailTemplateAdmin)
admin.site.register(SentEmail, SentEmailAdmin)
admin.site.register(SMSTemplate, SMSTemplateAdmin)
admin.site.register(SentSMS, SentSMSAdmin)


# Add export to relevant admins
AnnouncementAdmin.actions = list(AnnouncementAdmin.actions) + ["export_to_csv"]
SentEmailAdmin.actions = list(SentEmailAdmin.actions) + ["export_to_csv"]
SentSMSAdmin.actions = list(SentSMSAdmin.actions) + ["export_to_csv"]
