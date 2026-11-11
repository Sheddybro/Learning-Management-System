# apps/communication/models.py

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import (
    MinLengthValidator,
    MaxLengthValidator,
    MinValueValidator,
    MaxValueValidator,
)

from apps.core.models import CoreBaseModel


class Announcement(CoreBaseModel):
    """
    Model for school-wide announcements and notices.
    """

    class AnnouncementType(models.TextChoices):
        GENERAL = "general", _("General Announcement")
        ACADEMIC = "academic", _("Academic Announcement")
        EXAM = "exam", _("Exam Related")
        FEE = "fee", _("Fee Related")
        HOLIDAY = "holiday", _("Holiday Announcement")
        EVENT = "event", _("Event Announcement")
        URGENT = "urgent", _("Urgent Notice")
        MAINTENANCE = "maintenance", _("System Maintenance")

    class PriorityLevel(models.TextChoices):
        LOW = "low", _("Low")
        NORMAL = "normal", _("Normal")
        HIGH = "high", _("High")
        URGENT = "urgent", _("Urgent")

    class TargetAudience(models.TextChoices):
        ALL = "all", _("All Users")
        STUDENTS = "students", _("Students Only")
        PARENTS = "parents", _("Parents Only")
        TEACHERS = "teachers", _("Teachers Only")
        STAFF = "staff", _("Staff Only")
        ADMIN = "admin", _("Administrators Only")
        SPECIFIC = "specific", _("Specific Users")

    title = models.CharField(
        _("title"),
        max_length=200,
        validators=[MinLengthValidator(5), MaxLengthValidator(200)],
    )
    content = models.TextField(_("content"), validators=[MinLengthValidator(10)])
    announcement_type = models.CharField(
        _("announcement type"),
        max_length=20,
        choices=AnnouncementType.choices,
        default=AnnouncementType.GENERAL,
    )
    priority = models.CharField(
        _("priority level"),
        max_length=10,
        choices=PriorityLevel.choices,
        default=PriorityLevel.NORMAL,
    )
    target_audience = models.CharField(
        _("target audience"),
        max_length=20,
        choices=TargetAudience.choices,
        default=TargetAudience.ALL,
    )
    author = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="authored_announcements",
        verbose_name=_("author"),
    )
    is_published = models.BooleanField(_("is published"), default=False)
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)
    schedule_publish = models.DateTimeField(
        _("schedule publish"), null=True, blank=True
    )
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    is_pinned = models.BooleanField(_("is pinned"), default=False)
    pin_until = models.DateTimeField(_("pin until"), null=True, blank=True)

    # Specific targeting
    specific_users = models.ManyToManyField(
        "users.User",
        blank=True,
        related_name="targeted_announcements",
        verbose_name=_("specific users"),
    )
    specific_classes = models.ManyToManyField(
        "academics.Class",
        blank=True,
        related_name="announcements",
        verbose_name=_("specific classes"),
    )

    # Media and attachments
    banner_image = models.ImageField(
        _("banner image"), upload_to="announcements/banners/", null=True, blank=True
    )
    attachments = models.FileField(  # Use simple file field instead
        _("attachments"),
        upload_to="communication/attachments/%Y/%m/%d/",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Announcement")
        verbose_name_plural = _("Announcements")
        ordering = ["-is_pinned", "-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["announcement_type", "is_published"]),
            models.Index(fields=["target_audience", "status"]),
            models.Index(fields=["schedule_publish", "is_published"]),
            models.Index(fields=["expires_at", "status"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.get_announcement_type_display()}"

    def save(self, *args, **kwargs):
        """
        Automatically set published_at when is_published becomes True.
        Handle scheduled publishing.
        """
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()

        # Auto-publish if schedule time has passed
        if (
            self.schedule_publish
            and self.schedule_publish <= timezone.now()
            and not self.is_published
        ):
            self.is_published = True
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

    @property
    def is_active(self):
        """Check if announcement is currently active."""
        if not self.is_published:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True

    @property
    def is_scheduled(self):
        """Check if announcement is scheduled for future publishing."""
        return self.schedule_publish and self.schedule_publish > timezone.now()

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("communication:announcement_detail", kwargs={"pk": self.pk})


class NoticeBoard(CoreBaseModel):
    """
    Model for digital notice board displays.
    """

    class BoardType(models.TextChoices):
        MAIN = "main", _("Main Notice Board")
        STAFF = "staff", _("Staff Notice Board")
        STUDENT = "student", _("Student Notice Board")
        PARENT = "parent", _("Parent Notice Board")
        EVENT = "event", _("Event Notice Board")

    name = models.CharField(_("board name"), max_length=100)
    board_type = models.CharField(
        _("board type"),
        max_length=20,
        choices=BoardType.choices,
        default=BoardType.MAIN,
    )
    description = models.TextField(_("description"), blank=True)
    location = models.CharField(_("location"), max_length=200, blank=True)
    is_active = models.BooleanField(_("is active"), default=True)
    refresh_interval = models.PositiveIntegerField(
        _("refresh interval in seconds"),
        default=30,
        help_text=_("How often the notice board refreshes in seconds"),
    )
    announcements = models.ManyToManyField(
        Announcement,
        through="NoticeBoardItem",
        related_name="notice_boards",
        verbose_name=_("announcements"),
    )
    allowed_users = models.ManyToManyField(
        "users.User",
        blank=True,
        related_name="accessible_notice_boards",
        verbose_name=_("allowed users"),
    )

    class Meta:
        verbose_name = _("Notice Board")
        verbose_name_plural = _("Notice Boards")
        ordering = ["board_type", "name"]
        indexes = [
            models.Index(fields=["board_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_board_type_display()})"

    @property
    def active_announcements(self):
        """Get active announcements for this notice board."""
        return self.announcements.filter(
            noticeboarditem__notice_board=self,
            noticeboarditem__is_active=True,
            is_published=True,
        ).order_by("-noticeboarditem__display_order", "-published_at")


class NoticeBoardItem(CoreBaseModel):
    """
    Through model for notice board announcements with display settings.
    """

    notice_board = models.ForeignKey(
        NoticeBoard, on_delete=models.CASCADE, verbose_name=_("notice board")
    )
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, verbose_name=_("announcement")
    )
    display_order = models.PositiveIntegerField(_("display order"), default=0)
    is_active = models.BooleanField(_("is active"), default=True)
    start_display = models.DateTimeField(_("start display"), null=True, blank=True)
    end_display = models.DateTimeField(_("end display"), null=True, blank=True)
    display_duration = models.PositiveIntegerField(
        _("display duration in seconds"),
        default=10,
        help_text=_("How long this announcement displays on the board"),
    )

    class Meta:
        verbose_name = _("Notice Board Item")
        verbose_name_plural = _("Notice Board Items")
        ordering = ["display_order", "-created_at"]
        unique_together = ["notice_board", "announcement"]

    def __str__(self):
        return f"{self.notice_board} - {self.announcement}"

    @property
    def is_currently_displayed(self):
        """Check if item should be displayed now."""
        if not self.is_active:
            return False
        now = timezone.now()
        if self.start_display and self.start_display > now:
            return False
        if self.end_display and self.end_display <= now:
            return False
        return True


class EmailTemplate(CoreBaseModel):
    """
    Model for managing email templates.
    """

    class TemplateType(models.TextChoices):
        SYSTEM = "system", _("System Email")
        NOTIFICATION = "notification", _("Notification Email")
        MARKETING = "marketing", _("Marketing Email")
        ALERT = "alert", _("Alert Email")

    name = models.CharField(_("template name"), max_length=100)
    template_type = models.CharField(
        _("template type"),
        max_length=20,
        choices=TemplateType.choices,
        default=TemplateType.SYSTEM,
    )
    subject = models.CharField(_("email subject"), max_length=200)
    body_html = models.TextField(
        _("HTML body"), help_text=_("HTML content for the email")
    )
    body_text = models.TextField(
        _("text body"), help_text=_("Plain text version of the email")
    )
    language = models.CharField(_("language"), max_length=10, default="en")
    is_active = models.BooleanField(_("is active"), default=True)
    variables = models.JSONField(
        _("template variables"),
        default=dict,
        help_text=_("Available variables for this template in JSON format"),
    )

    class Meta:
        verbose_name = _("Email Template")
        verbose_name_plural = _("Email Templates")
        ordering = ["name", "language"]
        unique_together = ["name", "language"]

    def __str__(self):
        return f"{self.name} ({self.language})"

    def render_template(self, context):
        """
        Render template with given context.
        This would typically use a template engine in practice.
        """
        # Simplified rendering - in practice, use Django templates or Jinja2
        subject = self.subject
        body_html = self.body_html
        body_text = self.body_text

        for key, value in context.items():
            placeholder = f"{{{{ {key} }}}}"
            subject = subject.replace(placeholder, str(value))
            body_html = body_html.replace(placeholder, str(value))
            body_text = body_text.replace(placeholder, str(value))

        return subject, body_html, body_text


class SentEmail(CoreBaseModel):
    """
    Model for tracking sent emails.
    """

    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_emails",
        verbose_name=_("template"),
    )
    sender = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_emails",
        verbose_name=_("sender"),
    )
    recipient_email = models.EmailField(_("recipient email"))
    recipient_user = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_emails",
        verbose_name=_("recipient user"),
    )
    subject = models.CharField(_("subject"), max_length=200)
    body_html = models.TextField(_("HTML body"))
    body_text = models.TextField(_("text body"))
    sent_at = models.DateTimeField(_("sent at"), auto_now_add=True)
    delivered_at = models.DateTimeField(_("delivered at"), null=True, blank=True)
    opened_at = models.DateTimeField(_("opened at"), null=True, blank=True)
    click_count = models.PositiveIntegerField(_("click count"), default=0)
    error_message = models.TextField(_("error message"), blank=True)
    message_id = models.CharField(_("message ID"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Sent Email")
        verbose_name_plural = _("Sent Emails")
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["recipient_email", "sent_at"]),
            models.Index(fields=["sent_at", "status"]),
            models.Index(fields=["template", "sent_at"]),
        ]

    def __str__(self):
        return f"{self.subject} to {self.recipient_email}"


class SMSTemplate(CoreBaseModel):
    """
    Model for managing SMS templates.
    """

    name = models.CharField(_("template name"), max_length=100)
    content = models.TextField(
        _("content"),
        max_length=160,  # Standard SMS character limit
        validators=[MaxLengthValidator(160)],
    )
    is_active = models.BooleanField(_("is active"), default=True)
    variables = models.JSONField(
        _("template variables"),
        default=dict,
        help_text=_("Available variables for this template"),
    )

    class Meta:
        verbose_name = _("SMS Template")
        verbose_name_plural = _("SMS Templates")
        ordering = ["name"]

    def __str__(self):
        return self.name


class SentSMS(CoreBaseModel):
    """
    Model for tracking sent SMS messages.
    """

    template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_sms",
        verbose_name=_("template"),
    )
    recipient_phone = models.CharField(_("recipient phone"), max_length=20)
    recipient_user = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_sms",
        verbose_name=_("recipient user"),
    )
    content = models.CharField(_("content"), max_length=160)
    sent_at = models.DateTimeField(_("sent at"), auto_now_add=True)
    delivered_at = models.DateTimeField(_("delivered at"), null=True, blank=True)
    cost = models.DecimalField(
        _("cost"), max_digits=6, decimal_places=4, null=True, blank=True
    )
    error_message = models.TextField(_("error message"), blank=True)
    message_id = models.CharField(_("message ID"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("Sent SMS")
        verbose_name_plural = _("Sent SMS")
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["recipient_phone", "sent_at"]),
            models.Index(fields=["sent_at", "status"]),
        ]

    def __str__(self):
        return f"SMS to {self.recipient_phone}"


class EmergencyAlert(CoreBaseModel):
    """
    Model for emergency alerts and critical notifications.
    """

    class AlertType(models.TextChoices):
        FIRE = "fire", _("Fire Emergency")
        MEDICAL = "medical", _("Medical Emergency")
        SECURITY = "security", _("Security Threat")
        WEATHER = "weather", _("Severe Weather")
        INFRASTRUCTURE = "infrastructure", _("Infrastructure Failure")
        HEALTH = "health", _("Health Crisis")
        OTHER = "other", _("Other Emergency")

    class AlertLevel(models.TextChoices):
        LOW = "low", _("Low - Informational")
        MEDIUM = "medium", _("Medium - Action Required")
        HIGH = "high", _("High - Immediate Action")
        CRITICAL = "critical", _("Critical - Evacuation Required")

    class AlertStatus(models.TextChoices):
        ACTIVE = "active", _("Active")
        RESOLVED = "resolved", _("Resolved")
        CANCELLED = "cancelled", _("Cancelled")

    title = models.CharField(_("alert title"), max_length=200)
    description = models.TextField(_("alert description"))
    alert_type = models.CharField(
        _("alert type"),
        max_length=20,
        choices=AlertType.choices,
        default=AlertType.OTHER,
    )
    alert_level = models.CharField(
        _("alert level"),
        max_length=20,
        choices=AlertLevel.choices,
        default=AlertLevel.MEDIUM,
    )
    status = models.CharField(
        _("alert status"),
        max_length=20,
        choices=AlertStatus.choices,
        default=AlertStatus.ACTIVE,
    )

    # Location and scope
    location = models.CharField(_("location"), max_length=200, blank=True)
    affected_areas = models.TextField(_("affected areas"), blank=True)
    evacuation_required = models.BooleanField(_("evacuation required"), default=False)
    evacuation_location = models.CharField(
        _("evacuation location"), max_length=200, blank=True
    )

    # Timing
    alert_time = models.DateTimeField(_("alert time"), auto_now_add=True)
    resolved_time = models.DateTimeField(_("resolved time"), null=True, blank=True)
    estimated_resolution = models.DateTimeField(
        _("estimated resolution"), null=True, blank=True
    )

    # Response information
    response_actions = models.TextField(_("response actions"), blank=True)
    contact_person = models.CharField(_("contact person"), max_length=100, blank=True)
    contact_phone = models.CharField(_("contact phone"), max_length=20, blank=True)
    contact_email = models.EmailField(_("contact email"), blank=True)

    # Initiator
    initiated_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="initiated_emergency_alerts",
        verbose_name=_("initiated by"),
    )

    # Media and evidence
    alert_image = models.ImageField(
        _("alert image"), upload_to="emergency_alerts/images/", null=True, blank=True
    )
    attachments = models.FileField(
        _("attachments"),
        upload_to="emergency_alerts/attachments/",
        null=True,
        blank=True,
    )

    # Communication tracking
    notification_sent = models.BooleanField(_("notification sent"), default=False)
    notification_count = models.PositiveIntegerField(_("notification count"), default=0)
    acknowledgment_required = models.BooleanField(
        _("acknowledgment required"), default=True
    )

    class Meta:
        verbose_name = _("Emergency Alert")
        verbose_name_plural = _("Emergency Alerts")
        ordering = ["-alert_time"]
        indexes = [
            models.Index(fields=["alert_type", "status"]),
            models.Index(fields=["alert_level", "status"]),
            models.Index(fields=["status", "alert_time"]),
        ]

    def __str__(self):
        return f"{self.get_alert_level_display()} - {self.title}"

    def save(self, *args, **kwargs):
        """Auto-set resolved time when status changes to resolved."""
        if self.status == self.AlertStatus.RESOLVED and not self.resolved_time:
            self.resolved_time = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        """Check if alert is currently active."""
        return self.status == self.AlertStatus.ACTIVE

    @property
    def duration(self):
        """Get alert duration."""
        end_time = self.resolved_time or timezone.now()
        return end_time - self.alert_time

    def get_recipients(self):
        """Get all users who should receive this alert."""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        recipients = set()

        # Get all active users based on alert level
        if self.alert_level in [self.AlertLevel.CRITICAL, self.AlertLevel.HIGH]:
            # Critical and high alerts go to everyone
            recipients.update(
                User.objects.filter(is_active=True).values_list("id", flat=True)
            )
        elif self.alert_level == self.AlertLevel.MEDIUM:
            # Medium alerts go to staff and parents
            recipients.update(
                User.objects.filter(is_active=True)
                .exclude(user_roles__role__role_type="student")
                .values_list("id", flat=True)
            )
        else:
            # Low alerts go to staff only
            recipients.update(
                User.objects.filter(
                    is_active=True,
                    user_roles__role__role_type__in=[
                        "admin",
                        "teacher",
                        "support",
                        "principal",
                        "super_admin",
                    ],
                ).values_list("id", flat=True)
            )

        return list(recipients)


class AlertRecipient(CoreBaseModel):
    """
    Through model for tracking alert recipients and their acknowledgment status.
    """

    alert = models.ForeignKey(
        EmergencyAlert,
        on_delete=models.CASCADE,
        related_name="recipients",
        verbose_name=_("emergency alert"),
    )
    recipient = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="emergency_alerts",
        verbose_name=_("recipient"),
    )
    notified_at = models.DateTimeField(_("notified at"), null=True, blank=True)
    acknowledged_at = models.DateTimeField(_("acknowledged at"), null=True, blank=True)
    acknowledgment_method = models.CharField(
        _("acknowledgment method"),
        max_length=20,
        choices=[
            ("web", _("Web Interface")),
            ("email", _("Email")),
            ("sms", _("SMS")),
            ("app", _("Mobile App")),
        ],
        blank=True,
    )
    response_notes = models.TextField(_("response notes"), blank=True)

    class Meta:
        verbose_name = _("Alert Recipient")
        verbose_name_plural = _("Alert Recipients")
        unique_together = ["alert", "recipient"]
        indexes = [
            models.Index(fields=["alert", "acknowledged_at"]),
            models.Index(fields=["recipient", "notified_at"]),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.alert.title}"

    @property
    def is_acknowledged(self):
        """Check if recipient has acknowledged the alert."""
        return self.acknowledged_at is not None

    @property
    def acknowledgment_time(self):
        """Get time taken to acknowledge."""
        if self.acknowledged_at and self.notified_at:
            return self.acknowledged_at - self.notified_at
        return None


class EmergencyProtocol(CoreBaseModel):
    """
    Model for predefined emergency response protocols.
    """

    class ProtocolType(models.TextChoices):
        FIRE = "fire", _("Fire Emergency Protocol")
        MEDICAL = "medical", _("Medical Emergency Protocol")
        SECURITY = "security", _("Security Threat Protocol")
        WEATHER = "weather", _("Severe Weather Protocol")
        INFRASTRUCTURE = "infrastructure", _("Infrastructure Failure Protocol")
        HEALTH = "health", _("Health Crisis Protocol")
        EVACUATION = "evacuation", _("Evacuation Protocol")

    name = models.CharField(_("protocol name"), max_length=200)
    protocol_type = models.CharField(
        _("protocol type"), max_length=20, choices=ProtocolType.choices
    )
    description = models.TextField(_("description"))
    steps = models.JSONField(_("response steps"), default=list)
    contact_roles = models.JSONField(_("contact roles"), default=dict)
    resources_required = models.JSONField(_("resources required"), default=dict)
    is_active = models.BooleanField(_("is active"), default=True)

    # Templates
    alert_template = models.TextField(_("alert message template"), blank=True)
    email_template = models.TextField(_("email template"), blank=True)
    sms_template = models.TextField(_("SMS template"), blank=True)

    class Meta:
        verbose_name = _("Emergency Protocol")
        verbose_name_plural = _("Emergency Protocols")
        ordering = ["protocol_type", "name"]
        indexes = [
            models.Index(fields=["protocol_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.get_protocol_type_display()} - {self.name}"


# ===== NOTIFICATION MODELS =====


class RealTimeNotification(CoreBaseModel):
    """
    Model for real-time notifications sent via WebSocket.
    """

    NOTIFICATION_TYPES = [
        ("message", "New Message"),
        ("assignment", "Assignment Due"),
        ("grade", "Grade Posted"),
        ("announcement", "Announcement"),
        ("event", "School Event"),
        ("alert", "System Alert"),
        ("reminder", "Reminder"),
        ("achievement", "Achievement Unlocked"),
        ("warning", "Academic Warning"),
        ("meeting", "Meeting Scheduled"),
    ]

    recipient = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="realtime_notifications",
        verbose_name="recipient",
    )
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPES, verbose_name="notification type"
    )
    title = models.CharField(max_length=200, verbose_name="title")
    message = models.TextField(verbose_name="message")
    is_read = models.BooleanField(default=False, verbose_name="is read")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="read at")

    # Related object (generic foreign key)
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="realtime_notifications",
    )

    # Delivery tracking
    email_sent = models.BooleanField(default=False, verbose_name="email sent")
    push_sent = models.BooleanField(
        default=False, verbose_name="push notification sent"
    )
    sms_sent = models.BooleanField(default=False, verbose_name="SMS sent")

    # Priority and urgency
    priority = models.CharField(
        max_length=10,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        default="medium",
        verbose_name="priority",
    )

    # Scheduling
    scheduled_for = models.DateTimeField(
        null=True, blank=True, verbose_name="scheduled for"
    )
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="expires at")

    # Actions
    action_url = models.URLField(null=True, blank=True, verbose_name="action URL")
    action_text = models.CharField(
        max_length=50, null=True, blank=True, verbose_name="action text"
    )

    class Meta:
        verbose_name = "Real-time Notification"
        verbose_name_plural = "Real-time Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "created_at"]),
            models.Index(fields=["notification_type", "created_at"]),
            models.Index(fields=["priority", "created_at"]),
            models.Index(fields=["scheduled_for"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.title} -> {self.recipient}"

    @property
    def is_expired(self):
        """Check if notification has expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def is_scheduled(self):
        """Check if notification is scheduled for future delivery."""
        if self.scheduled_for:
            return self.scheduled_for > timezone.now()
        return False

    def mark_as_read(self):
        """Mark notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    @classmethod
    def create_notification(
        cls,
        recipient,
        notification_type,
        title,
        message,
        content_object=None,
        priority="medium",
        action_url=None,
        action_text=None,
        scheduled_for=None,
        expires_at=None,
    ):
        """
        Class method to create a notification.
        """
        # Resolve institution for CoreBaseModel requirement. Prefer user's
        # primary institution, fallback to any institution, then first Institution.
        from django.apps import apps

        Institution = apps.get_model("core", "Institution")
        inst = None
        try:
            primary = getattr(recipient, "institution_memberships", None)
            if primary and primary.filter(is_primary=True).exists():
                inst = primary.filter(is_primary=True).first().institution
            elif (
                getattr(recipient, "institutions", None)
                and recipient.institutions.exists()
            ):
                inst = recipient.institutions.first()
        except Exception:
            inst = None

        if not inst:
            inst = Institution.objects.first()

        notification = cls.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            action_url=action_url,
            action_text=action_text,
            scheduled_for=scheduled_for,
            expires_at=expires_at,
            institution=inst,
        )

        if content_object:
            notification.content_type = models.ContentType.objects.get_for_model(
                content_object
            )
            notification.object_id = content_object.pk
            notification.save()

        return notification

    @classmethod
    def get_unread_count(cls, user):
        """Get count of unread notifications for a user."""
        return (
            cls.objects.filter(recipient=user, is_read=False)
            .exclude(
                models.Q(expires_at__isnull=False)
                & models.Q(expires_at__lt=models.functions.Now())
            )
            .count()
        )

    @classmethod
    def mark_all_read(cls, user):
        """Mark all notifications as read for a user."""
        return cls.objects.filter(recipient=user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )


class NotificationPreference(CoreBaseModel):
    """
    Model for user notification preferences.
    """

    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        verbose_name="user",
    )

    # Real-time notification preferences
    enable_realtime = models.BooleanField(
        default=True, verbose_name="enable real-time notifications"
    )

    # Notification type preferences
    message_notifications = models.BooleanField(
        default=True, verbose_name="message notifications"
    )
    assignment_notifications = models.BooleanField(
        default=True, verbose_name="assignment notifications"
    )
    grade_notifications = models.BooleanField(
        default=True, verbose_name="grade notifications"
    )
    announcement_notifications = models.BooleanField(
        default=True, verbose_name="announcement notifications"
    )
    event_notifications = models.BooleanField(
        default=True, verbose_name="event notifications"
    )
    alert_notifications = models.BooleanField(
        default=True, verbose_name="alert notifications"
    )

    # Delivery method preferences
    email_notifications = models.BooleanField(
        default=True, verbose_name="email notifications"
    )
    push_notifications = models.BooleanField(
        default=True, verbose_name="push notifications"
    )
    sms_notifications = models.BooleanField(
        default=False, verbose_name="SMS notifications"
    )

    # Quiet hours
    quiet_hours_enabled = models.BooleanField(
        default=False, verbose_name="quiet hours enabled"
    )
    quiet_hours_start = models.TimeField(
        null=True, blank=True, verbose_name="quiet hours start"
    )
    quiet_hours_end = models.TimeField(
        null=True, blank=True, verbose_name="quiet hours end"
    )

    # Sound preferences
    sound_enabled = models.BooleanField(default=True, verbose_name="sound enabled")
    sound_volume = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="sound volume",
    )

    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        return f"Preferences for {self.user}"

    def should_send_notification(self, notification_type):
        """
        Check if notification should be sent based on user preferences.
        """
        if not self.enable_realtime:
            return False

        # Check notification type preference
        type_field_map = {
            "message": "message_notifications",
            "assignment": "assignment_notifications",
            "grade": "grade_notifications",
            "announcement": "announcement_notifications",
            "event": "event_notifications",
            "alert": "alert_notifications",
        }

        type_field = type_field_map.get(notification_type)
        if type_field and not getattr(self, type_field, True):
            return False

        # Check quiet hours
        if self.quiet_hours_enabled and self.quiet_hours_start and self.quiet_hours_end:
            now = timezone.now().time()
            if self.quiet_hours_start <= self.quiet_hours_end:
                # Same day range
                if self.quiet_hours_start <= now <= self.quiet_hours_end:
                    return False
            else:
                # Overnight range
                if now >= self.quiet_hours_start or now <= self.quiet_hours_end:
                    return False

        return True


class NotificationTemplate(CoreBaseModel):
    """
    Model for notification templates.
    """

    TEMPLATE_TYPES = [
        ("email", "Email Template"),
        ("push", "Push Notification Template"),
        ("sms", "SMS Template"),
        ("in_app", "In-App Template"),
    ]

    name = models.CharField(max_length=100, unique=True, verbose_name="name")
    template_type = models.CharField(
        max_length=20, choices=TEMPLATE_TYPES, verbose_name="template type"
    )
    subject = models.CharField(
        max_length=200, blank=True, verbose_name="subject (for email)"
    )
    body = models.TextField(verbose_name="body template")
    is_active = models.BooleanField(default=True, verbose_name="is active")

    # Template variables (JSON field for dynamic content)
    variables = models.JSONField(
        default=dict,
        blank=True,
        help_text="Available variables for template substitution",
        verbose_name="template variables",
    )

    class Meta:
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

    def render_template(self, context):
        """
        Render template with given context.
        """
        from django.template import Template, Context

        try:
            template = Template(self.body)
            rendered_body = template.render(Context(context))

            if self.template_type == "email" and self.subject:
                subject_template = Template(self.subject)
                rendered_subject = subject_template.render(Context(context))
                return rendered_subject, rendered_body
            else:
                return rendered_body

        except Exception as e:
            # Fallback to basic string formatting
            return self.body.format(**context)


# ===== CHAT MODELS =====


class ChatRoom(CoreBaseModel):
    """
    Model for managing chat rooms and conversations.
    """

    ROOM_TYPES = [
        ("direct", "Direct Message"),
        ("group", "Group Chat"),
        ("class", "Class Discussion"),
        ("announcement", "Announcement Channel"),
    ]

    name = models.CharField(max_length=100)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # For class-specific rooms
    academic_class = models.ForeignKey(
        "academics.Class",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="academic class",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="subject",
    )

    # Members
    members = models.ManyToManyField("users.User", related_name="chat_rooms")
    admins = models.ManyToManyField(
        "users.User", related_name="admin_chat_rooms", blank=True
    )

    class Meta:
        verbose_name = "Chat Room"
        verbose_name_plural = "Chat Rooms"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"

    @property
    def member_count(self):
        """Get total number of members."""
        return self.members.count()

    @property
    def last_message(self):
        """Get the most recent message in this room."""
        return self.messages.order_by("-created_at").first()


class ChatMessage(CoreBaseModel):
    """
    Model for individual chat messages.
    """

    room = models.ForeignKey(
        ChatRoom, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="chat_messages"
    )
    content = models.TextField()
    message_type = models.CharField(
        max_length=20,
        choices=[
            ("text", "Text"),
            ("file", "File"),
            ("image", "Image"),
            ("system", "System Message"),
        ],
        default="text",
    )

    # File attachments
    attachment = models.FileField(
        upload_to="chat_attachments/%Y/%m/%d/", null=True, blank=True
    )

    # Message metadata
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    reply_to = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replies"
    )

    # Read status
    read_by = models.ManyToManyField(
        "users.User", related_name="read_messages", blank=True
    )

    class Meta:
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["room", "created_at"]),
            models.Index(fields=["sender", "created_at"]),
        ]

    def __str__(self):
        return f"{self.sender.get_full_name()}: {self.content[:50]}..."

    @property
    def is_read_by_user(self, user):
        """Check if message is read by a specific user."""
        return self.read_by.filter(id=user.id).exists()

    def mark_as_read(self, user):
        """Mark message as read by a user."""
        if not self.is_read_by_user(user):
            self.read_by.add(user)


class ChatParticipant(CoreBaseModel):
    """
    Model for tracking user participation in chat rooms.
    """

    room = models.ForeignKey(
        ChatRoom, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="chat_participation"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    is_muted = models.BooleanField(default=False)
    role = models.CharField(
        max_length=20,
        choices=[
            ("member", "Member"),
            ("admin", "Admin"),
            ("moderator", "Moderator"),
        ],
        default="member",
    )

    class Meta:
        verbose_name = "Chat Participant"
        verbose_name_plural = "Chat Participants"
        unique_together = ["room", "user"]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user.get_full_name()} in {self.room.name}"


class TypingIndicator(CoreBaseModel):
    """
    Model for tracking typing indicators in chat rooms.
    """

    room = models.ForeignKey(
        ChatRoom, on_delete=models.CASCADE, related_name="typing_indicators"
    )
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="typing_in"
    )
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Typing Indicator"
        verbose_name_plural = "Typing Indicators"
        ordering = ["-timestamp"]
        unique_together = ["room", "user"]

    def __str__(self):
        return f"{self.user.get_full_name()} typing in {self.room.name}"

    @property
    def is_expired(self):
        """Check if typing indicator has expired (older than 5 seconds)."""
        return (timezone.now() - self.timestamp).seconds > 5


# ===== MESSAGE MODELS =====


class Message(CoreBaseModel):
    """
    Model for general messaging system (separate from chat).
    """

    class MessageType(models.TextChoices):
        DIRECT = "direct", _("Direct Message")
        GROUP = "group", _("Group Message")
        SYSTEM = "system", _("System Message")

    class Priority(models.TextChoices):
        LOW = "low", _("Low")
        NORMAL = "normal", _("Normal")
        HIGH = "high", _("High")

    subject = models.CharField(
        _("subject"),
        max_length=200,
        validators=[MinLengthValidator(3), MaxLengthValidator(200)],
    )
    content = models.TextField(_("content"), validators=[MinLengthValidator(1)])
    sender = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="sent_messages",
        verbose_name=_("sender"),
    )
    message_type = models.CharField(
        _("message type"),
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.DIRECT,
    )
    priority = models.CharField(
        _("priority"), max_length=10, choices=Priority.choices, default=Priority.NORMAL
    )
    is_important = models.BooleanField(_("is important"), default=False)
    requires_confirmation = models.BooleanField(
        _("requires confirmation"), default=False
    )

    # Threading support
    parent_message = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
        verbose_name=_("parent message"),
    )

    # Recipients (many-to-many through MessageRecipient)
    recipients = models.ManyToManyField(
        "users.User",
        related_name="received_messages",
        through="MessageRecipient",
        verbose_name=_("recipients"),
    )

    # Confirmed by (many-to-many through MessageConfirmation)
    confirmed_by = models.ManyToManyField(
        "users.User",
        related_name="confirmed_messages",
        through="MessageConfirmation",
        verbose_name=_("confirmed by"),
    )

    # Attachments
    attachments = models.ManyToManyField(
        "academics.FileAttachment",
        blank=True,
        related_name="messages",
        verbose_name=_("attachments"),
    )

    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sender", "created_at"]),
            models.Index(fields=["message_type", "status"]),
            models.Index(fields=["is_important", "created_at"]),
        ]

    def __str__(self):
        return f"{self.subject} - {self.sender.get_full_name()}"

    @property
    def recipients_count(self):
        """Get total number of recipients."""
        return self.recipients.count()

    @property
    def read_count(self):
        """Get number of recipients who have read the message."""
        return self.recipient_status.filter(read_at__isnull=False).count()

    @property
    def confirmed_count(self):
        """Get number of recipients who have confirmed the message."""
        return self.confirmed_by.count()


class MessageRecipient(CoreBaseModel):
    """
    Through model for message recipients with read status.
    """

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="recipient_status",
        verbose_name=_("message"),
    )
    recipient = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="message_status",
        verbose_name=_("recipient"),
    )
    read_at = models.DateTimeField(_("read at"), null=True, blank=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        verbose_name = _("Message Recipient")
        verbose_name_plural = _("Message Recipients")
        unique_together = ["message", "recipient"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["message", "recipient"]),
        ]

    def __str__(self):
        return f"{self.recipient.get_full_name()} - {self.message.subject}"

    @property
    def is_read(self):
        """Check if message has been read."""
        return self.read_at is not None

    @property
    def is_deleted(self):
        """Check if message has been deleted by recipient."""
        return self.deleted_at is not None


class MessageConfirmation(CoreBaseModel):
    """
    Model for tracking message confirmations.
    """

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, verbose_name=_("message")
    )
    user = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, verbose_name=_("user")
    )
    confirmed_at = models.DateTimeField(_("confirmed at"), auto_now_add=True)
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)

    class Meta:
        verbose_name = _("Message Confirmation")
        verbose_name_plural = _("Message Confirmations")
        unique_together = ["message", "user"]

    def __str__(self):
        return f"{self.user.get_full_name()} confirmed {self.message.subject}"


# Signal handlers for emergency alerts
# Note: Signal handlers moved to separate file to avoid circular imports during model loading
