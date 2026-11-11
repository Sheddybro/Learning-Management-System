from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinLengthValidator, MaxLengthValidator

from apps.core.models import CoreBaseModel, GlobalBaseModel


class Category(GlobalBaseModel):
    """
    Categories for organizing help center content and support cases.
    """

    name = models.CharField(_("name"), max_length=100, unique=True)
    slug = models.SlugField(_("slug"), max_length=100, unique=True)
    description = models.TextField(_("description"), blank=True)
    color_code = models.CharField(_("color code"), max_length=7, default="#3498db")
    is_active = models.BooleanField(_("is active"), default=True)

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tag(CoreBaseModel):
    """
    Tags for categorizing content and cases.
    """

    name = models.CharField(_("name"), max_length=50, unique=True)
    slug = models.SlugField(_("slug"), max_length=50, unique=True)
    color_code = models.CharField(_("color code"), max_length=7, default="#95a5a6")
    is_active = models.BooleanField(_("is active"), default=True)

    class Meta:
        verbose_name = _("Tag")
        verbose_name_plural = _("Tags")
        ordering = ["name"]

    def __str__(self):
        return self.name


class HelpCenterArticle(CoreBaseModel):
    """
    Knowledge base articles for self-service support.
    """

    class ArticleCategory(models.TextChoices):
        HELP_CENTER = "help_center", _("Help Center")
        KNOWLEDGE_BASE = "knowledge_base", _("Knowledge Base")
        FAQ = "faq", _("FAQ")

    title = models.CharField(_("title"), max_length=200)
    slug = models.SlugField(_("slug"), max_length=200, unique=True)
    content = models.TextField(_("content"))
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
        verbose_name=_("category"),
    )
    tags = models.ManyToManyField(
        Tag, blank=True, related_name="articles", verbose_name=_("tags")
    )
    article_category = models.CharField(
        _("article category"),
        max_length=20,
        choices=ArticleCategory.choices,
        default=ArticleCategory.HELP_CENTER,
    )
    is_published = models.BooleanField(_("is published"), default=True)
    views = models.PositiveIntegerField(_("views"), default=0)
    helpful_votes = models.PositiveIntegerField(_("helpful votes"), default=0)
    total_votes = models.PositiveIntegerField(_("total votes"), default=0)

    class Meta:
        verbose_name = _("Help Center Article")
        verbose_name_plural = _("Help Center Articles")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["article_category", "is_published"]),
            models.Index(fields=["category", "is_published"]),
        ]

    def __str__(self):
        return self.title

    @property
    def helpful_percentage(self):
        """Calculate helpful percentage."""
        if self.total_votes == 0:
            return 0
        return int((self.helpful_votes / self.total_votes) * 100)


class Resource(CoreBaseModel):
    """
    Support resources and documentation.
    """

    class ResourceType(models.TextChoices):
        USER_GUIDE = "user_guide", _("User Guide")
        VIDEO_TUTORIAL = "video_tutorial", _("Video Tutorial")
        DOCUMENT = "document", _("Document")
        LINK = "link", _("External Link")

    title = models.CharField(_("title"), max_length=200)
    slug = models.SlugField(_("slug"), max_length=200, unique=True)
    description = models.TextField(_("description"), blank=True)
    resource_type = models.CharField(
        _("resource type"),
        max_length=20,
        choices=ResourceType.choices,
        default=ResourceType.DOCUMENT,
    )
    file = models.FileField(
        _("file"), upload_to="support/resources/", blank=True, null=True
    )
    external_url = models.URLField(_("external URL"), blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resources",
        verbose_name=_("category"),
    )
    tags = models.ManyToManyField(
        Tag, blank=True, related_name="resources", verbose_name=_("tags")
    )
    is_published = models.BooleanField(_("is published"), default=True)
    downloads = models.PositiveIntegerField(_("downloads"), default=0)

    class Meta:
        verbose_name = _("Resource")
        verbose_name_plural = _("Resources")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resource_type", "is_published"]),
            models.Index(fields=["category", "is_published"]),
        ]

    def __str__(self):
        return self.title


class FAQ(GlobalBaseModel):
    """
    Frequently asked questions.
    """

    question = models.CharField(
        _("question"),
        max_length=500,
        validators=[MinLengthValidator(10), MaxLengthValidator(500)],
    )
    answer = models.TextField(_("answer"), validators=[MinLengthValidator(10)])
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faqs",
        verbose_name=_("category"),
    )
    tags = models.ManyToManyField(
        Tag, blank=True, related_name="faqs", verbose_name=_("tags")
    )
    order = models.PositiveIntegerField(_("display order"), default=0)
    is_published = models.BooleanField(_("is published"), default=True)
    views = models.PositiveIntegerField(_("views"), default=0)

    class Meta:
        verbose_name = _("FAQ")
        verbose_name_plural = _("FAQs")
        ordering = ["order", "-created_at"]
        indexes = [
            models.Index(fields=["category", "is_published"]),
            models.Index(fields=["order", "is_published"]),
        ]

    def __str__(self):
        return self.question


class ContactSubmission(CoreBaseModel):
    """
    Contact form submissions from users.
    """

    name = models.CharField(
        _("name"),
        max_length=100,
        validators=[MinLengthValidator(2), MaxLengthValidator(100)],
    )
    email = models.EmailField(_("email"))
    subject = models.CharField(
        _("subject"), max_length=200, blank=True, validators=[MaxLengthValidator(200)]
    )
    message = models.TextField(_("message"), validators=[MinLengthValidator(10)])
    phone = models.CharField(_("phone"), max_length=20, blank=True)
    is_resolved = models.BooleanField(_("is resolved"), default=False)
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    resolved_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_contacts",
        verbose_name=_("resolved by"),
    )
    resolution_notes = models.TextField(_("resolution notes"), blank=True)
    priority = models.CharField(
        _("priority"),
        max_length=10,
        choices=[
            ("low", _("Low")),
            ("normal", _("Normal")),
            ("high", _("High")),
            ("urgent", _("Urgent")),
        ],
        default="normal",
    )

    class Meta:
        verbose_name = _("Contact Submission")
        verbose_name_plural = _("Contact Submissions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_resolved", "created_at"]),
            models.Index(fields=["priority", "is_resolved"]),
        ]

    def __str__(self):
        return f"Contact from {self.name} - {self.subject or 'No Subject'}"

    def save(self, *args, **kwargs):
        if self.is_resolved and not self.resolved_at:
            self.resolved_at = timezone.now()
        elif not self.is_resolved:
            self.resolved_at = None
            self.resolved_by = None
        super().save(*args, **kwargs)


class LegalDocument(GlobalBaseModel):
    """
    Legal documents and policies.
    """

    class DocumentType(models.TextChoices):
        PRIVACY_POLICY = "privacy_policy", _("Privacy Policy")
        TERMS_OF_SERVICE = "terms_of_service", _("Terms of Service")
        DATA_PROTECTION = "data_protection", _("Data Protection Policy")
        COOKIE_POLICY = "cookie_policy", _("Cookie Policy")
        ACCESSIBILITY_STATEMENT = "accessibility_statement", _(
            "Accessibility Statement"
        )
        OTHER = "other", _("Other")

    title = models.CharField(_("title"), max_length=200)
    slug = models.SlugField(_("slug"), max_length=200, unique=True)
    content = models.TextField(_("content"))
    document_type = models.CharField(
        _("document type"), max_length=30, choices=DocumentType.choices, unique=True
    )
    version = models.CharField(_("version"), max_length=20, blank=True)
    is_active = models.BooleanField(_("is active"), default=True)
    requires_acknowledgment = models.BooleanField(
        _("requires acknowledgment"), default=False
    )

    class Meta:
        verbose_name = _("Legal Document")
        verbose_name_plural = _("Legal Documents")
        ordering = ["title"]
        indexes = [
            models.Index(fields=["document_type", "is_active"]),
        ]

    def __str__(self):
        return self.title


# ===== STUDENT SUPPORT TEAM COLLABORATION MODELS =====


class SupportCase(CoreBaseModel):
    """
    Collaborative case management for student support issues.
    """

    class CasePriority(models.TextChoices):
        LOW = "low", _("Low")
        NORMAL = "normal", _("Normal")
        HIGH = "high", _("High")
        URGENT = "urgent", _("Urgent")
        CRITICAL = "critical", _("Critical")

    class CaseStatus(models.TextChoices):
        OPEN = "open", _("Open")
        IN_PROGRESS = "in_progress", _("In Progress")
        PENDING = "pending", _("Pending")
        RESOLVED = "resolved", _("Resolved")
        CLOSED = "closed", _("Closed")
        ESCALATED = "escalated", _("Escalated")

    class CaseType(models.TextChoices):
        ACADEMIC = "academic", _("Academic Support")
        BEHAVIORAL = "behavioral", _("Behavioral Support")
        MEDICAL = "medical", _("Medical Support")
        FINANCIAL = "financial", _("Financial Aid")
        TECHNICAL = "technical", _("Technical Support")
        COUNSELING = "counseling", _("Counseling")
        PARENTAL = "parental", _("Parental Concern")
        ADMINISTRATIVE = "administrative", _("Administrative")
        OTHER = "other", _("Other")

    # Basic Case Information
    title = models.CharField(
        _("case title"),
        max_length=200,
        validators=[MinLengthValidator(5), MaxLengthValidator(200)],
    )
    description = models.TextField(
        _("case description"), validators=[MinLengthValidator(10)]
    )
    case_type = models.CharField(
        _("case type"), max_length=20, choices=CaseType.choices, default=CaseType.OTHER
    )
    priority = models.CharField(
        _("priority"),
        max_length=10,
        choices=CasePriority.choices,
        default=CasePriority.NORMAL,
    )
    status = models.CharField(
        _("status"), max_length=15, choices=CaseStatus.choices, default=CaseStatus.OPEN
    )

    # Related Entities
    student = models.ForeignKey(
        "academics.Student",
        on_delete=models.CASCADE,
        related_name="support_cases",
        verbose_name=_("student"),
    )
    reported_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="reported_cases",
        verbose_name=_("reported by"),
    )
    assigned_to = models.ManyToManyField(
        "users.User",
        through="CaseParticipant",
        related_name="assigned_cases",
        verbose_name=_("assigned to"),
        blank=True,
    )

    # Case Management
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_cases",
        verbose_name=_("category"),
    )
    tags = models.ManyToManyField(
        Tag, blank=True, related_name="support_cases", verbose_name=_("tags")
    )

    # Resolution
    resolution = models.TextField(_("resolution"), blank=True)
    resolved_at = models.DateTimeField(_("resolved at"), null=True, blank=True)
    resolved_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_cases",
        verbose_name=_("resolved by"),
    )

    # Escalation
    is_escalated = models.BooleanField(_("is escalated"), default=False)
    escalated_to = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalated_cases",
        verbose_name=_("escalated to"),
    )
    escalation_reason = models.TextField(_("escalation reason"), blank=True)
    escalated_at = models.DateTimeField(_("escalated at"), null=True, blank=True)

    # Communication
    requires_parent_notification = models.BooleanField(
        _("requires parent notification"), default=False
    )
    parent_notified = models.BooleanField(_("parent notified"), default=False)
    parent_notification_date = models.DateTimeField(
        _("parent notification date"), null=True, blank=True
    )

    # Metadata
    case_number = models.CharField(
        _("case number"),
        max_length=20,
        unique=True,
        blank=True,
        help_text=_("Auto-generated case number"),
    )
    estimated_resolution_time = models.PositiveIntegerField(
        _("estimated resolution time (hours)"), null=True, blank=True
    )
    actual_resolution_time = models.PositiveIntegerField(
        _("actual resolution time (hours)"), null=True, blank=True
    )

    class Meta:
        verbose_name = _("Support Case")
        verbose_name_plural = _("Support Cases")
        ordering = ["-created_at", "priority"]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["case_type", "priority"]),
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["reported_by", "created_at"]),
            models.Index(fields=["case_number"]),
        ]

    def __str__(self):
        return f"{self.case_number}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = self.generate_case_number()

        # Auto-set resolved timestamp
        if (
            self.status in [self.CaseStatus.RESOLVED, self.CaseStatus.CLOSED]
            and not self.resolved_at
        ):
            self.resolved_at = timezone.now()
        elif self.status not in [self.CaseStatus.RESOLVED, self.CaseStatus.CLOSED]:
            self.resolved_at = None

        # Auto-set escalation timestamp
        if self.is_escalated and not self.escalated_at:
            self.escalated_at = timezone.now()
        elif not self.is_escalated:
            self.escalated_at = None

        super().save(*args, **kwargs)

    def generate_case_number(self):
        """Generate unique case number in format: CASE{year}{sequential_number}."""
        year = timezone.now().strftime("%Y")
        last_case = (
            SupportCase.objects.filter(case_number__startswith=f"CASE{year}")
            .order_by("-case_number")
            .first()
        )

        if last_case:
            try:
                last_num = int(last_case.case_number[-4:])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1

        return f"CASE{year}{new_num:04d}"

    @property
    def is_overdue(self):
        """Check if case is overdue based on estimated resolution time."""
        if not self.estimated_resolution_time:
            return False

        hours_elapsed = (timezone.now() - self.created_at).total_seconds() / 3600
        return hours_elapsed > self.estimated_resolution_time

    @property
    def days_open(self):
        """Calculate days since case was opened."""
        delta = timezone.now() - self.created_at
        return delta.days

    @property
    def participant_count(self):
        """Get count of assigned participants."""
        return self.assigned_to.count()

    @property
    def update_count(self):
        """Get count of case updates."""
        return self.updates.count()

    def add_participant(self, user, role="member"):
        """Add a participant to the case."""
        CaseParticipant.objects.get_or_create(
            case=self, user=user, defaults={"role": role}
        )

    def remove_participant(self, user):
        """Remove a participant from the case."""
        CaseParticipant.objects.filter(case=self, user=user).delete()

    def create_update(self, user, update_type, content, is_private=False):
        """Create a new case update."""
        return CaseUpdate.objects.create(
            case=self,
            user=user,
            update_type=update_type,
            content=content,
            is_private=is_private,
        )


class CaseParticipant(CoreBaseModel):
    """
    Through model for case participants with roles.
    """

    class ParticipantRole(models.TextChoices):
        LEAD = "lead", _("Case Lead")
        MEMBER = "member", _("Team Member")
        REVIEWER = "reviewer", _("Reviewer")
        OBSERVER = "observer", _("Observer")

    case = models.ForeignKey(
        SupportCase,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name=_("case"),
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="case_participations",
        verbose_name=_("user"),
    )
    role = models.CharField(
        _("role"),
        max_length=15,
        choices=ParticipantRole.choices,
        default=ParticipantRole.MEMBER,
    )
    assigned_at = models.DateTimeField(_("assigned at"), auto_now_add=True)
    is_active = models.BooleanField(_("is active"), default=True)

    class Meta:
        verbose_name = _("Case Participant")
        verbose_name_plural = _("Case Participants")
        unique_together = ["case", "user"]
        ordering = ["-assigned_at"]
        indexes = [
            models.Index(fields=["case", "role"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_role_display()} on {self.case.title}"


class CaseUpdate(CoreBaseModel):
    """
    Updates and notes on support cases for collaboration.
    """

    class UpdateType(models.TextChoices):
        COMMENT = "comment", _("Comment")
        STATUS_CHANGE = "status_change", _("Status Change")
        ASSIGNMENT = "assignment", _("Assignment")
        ESCALATION = "escalation", _("Escalation")
        RESOLUTION = "resolution", _("Resolution")
        FILE_UPLOAD = "file_upload", _("File Upload")
        MEETING = "meeting", _("Meeting Note")
        FOLLOW_UP = "follow_up", _("Follow-up")

    case = models.ForeignKey(
        SupportCase,
        on_delete=models.CASCADE,
        related_name="updates",
        verbose_name=_("case"),
    )
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="case_updates",
        verbose_name=_("user"),
    )
    update_type = models.CharField(
        _("update type"),
        max_length=15,
        choices=UpdateType.choices,
        default=UpdateType.COMMENT,
    )
    content = models.TextField(_("content"), validators=[MinLengthValidator(1)])
    is_private = models.BooleanField(
        _("is private"),
        default=False,
        help_text=_("Private updates are only visible to case participants"),
    )
    attachment = models.FileField(
        _("attachment"), upload_to="support/case_updates/", null=True, blank=True
    )

    class Meta:
        verbose_name = _("Case Update")
        verbose_name_plural = _("Case Updates")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["case", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["update_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()}: {self.get_update_type_display()} on {self.case.title}"


class CaseAttachment(CoreBaseModel):
    """
    File attachments for support cases.
    """

    case = models.ForeignKey(
        SupportCase,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name=_("case"),
    )
    uploaded_by = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="case_attachments",
        verbose_name=_("uploaded by"),
    )
    file = models.FileField(_("file"), upload_to="support/case_attachments/")
    filename = models.CharField(_("filename"), max_length=255)
    file_size = models.PositiveIntegerField(
        _("file size"), help_text=_("Size in bytes")
    )
    description = models.TextField(_("description"), blank=True)
    is_private = models.BooleanField(_("is private"), default=False)

    class Meta:
        verbose_name = _("Case Attachment")
        verbose_name_plural = _("Case Attachments")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["case", "created_at"]),
            models.Index(fields=["uploaded_by", "created_at"]),
        ]

    def __str__(self):
        return f"{self.filename} - {self.case.title}"

    def save(self, *args, **kwargs):
        if self.file and not self.filename:
            self.filename = self.file.name
            self.file_size = self.file.size
        super().save(*args, **kwargs)
