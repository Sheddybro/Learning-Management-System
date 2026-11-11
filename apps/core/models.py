# apps/core/models.py
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class AddressModel(models.Model):
    """
    Abstract model for storing address information.
    """

    address_line_1 = models.CharField(_("address line 1"), max_length=255, blank=True)
    address_line_2 = models.CharField(_("address line 2"), max_length=255, blank=True)
    city = models.CharField(_("city"), max_length=100, blank=True)
    state = models.CharField(_("state/province"), max_length=100, blank=True)
    postal_code = models.CharField(_("postal code"), max_length=20, blank=True)
    country = models.CharField(_("country"), max_length=100, blank=True)

    class Meta:
        abstract = True

    @property
    def full_address(self):
        """Return formatted full address."""
        parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.state,
            self.postal_code,
            self.country,
        ]
        return ", ".join(filter(None, parts))


class ContactModel(models.Model):
    """
    Abstract model for storing contact information.
    """

    phone = models.CharField(_("phone number"), max_length=20, blank=True)
    mobile = models.CharField(_("mobile number"), max_length=20, blank=True)
    email = models.EmailField(_("email address"), blank=True)
    emergency_contact = models.CharField(
        _("emergency contact"), max_length=100, blank=True
    )
    emergency_phone = models.CharField(_("emergency phone"), max_length=20, blank=True)

    class Meta:
        abstract = True


class Institution(AddressModel, ContactModel):
    """
    Model for managing multiple school institutions under one platform.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        PENDING = "pending", _("Pending")
        SUSPENDED = "suspended", _("Suspended")
        ARCHIVED = "archived", _("Archived")

    # UUID Primary Key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Timestamp fields
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True, db_index=True)

    # Status fields
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    """
    Model for managing multiple school institutions under one platform.
    """

    class InstitutionType(models.TextChoices):
        PRESCHOOL = "preschool", _("Preschool")
        ELEMENTARY = "elementary", _("Elementary School")
        MIDDLE_SCHOOL = "middle_school", _("Middle School")
        HIGH_SCHOOL = "high_school", _("High School")
        COLLEGE = "college", _("College/University")
        VOCATIONAL = "vocational", _("Vocational/Technical")
        SPECIAL_EDUCATION = "special_education", _("Special Education")
        INTERNATIONAL = "international", _("International School")

    class OwnershipType(models.TextChoices):
        PUBLIC = "public", _("Public/Government")
        PRIVATE = "private", _("Private")
        CHARTER = "charter", _("Charter")
        RELIGIOUS = "religious", _("Religious")
        INTERNATIONAL = "international", _("International")

    # Basic Information
    name = models.CharField(_("institution name"), max_length=200, unique=True)
    code = models.CharField(
        _("institution code"), max_length=20, unique=True, db_index=True
    )
    short_name = models.CharField(_("short name"), max_length=50, blank=True)
    description = models.TextField(_("description"), blank=True)

    # Institution Details
    institution_type = models.CharField(
        _("institution type"),
        max_length=20,
        choices=InstitutionType.choices,
        default=InstitutionType.HIGH_SCHOOL,
    )
    ownership_type = models.CharField(
        _("ownership type"),
        max_length=20,
        choices=OwnershipType.choices,
        default=OwnershipType.PRIVATE,
    )

    # Contact & Location (inherited from AddressModel and ContactModel)
    website = models.URLField(_("website"), blank=True)
    established_date = models.DateField(_("established date"), null=True, blank=True)

    # Capacity & Settings
    max_students = models.PositiveIntegerField(_("maximum students"), default=1000)
    max_staff = models.PositiveIntegerField(_("maximum staff"), default=100)
    timezone = models.CharField(_("timezone"), max_length=50, default="UTC")

    # Configuration
    is_active = models.BooleanField(_("is active"), default=True)
    allows_online_enrollment = models.BooleanField(
        _("allows online enrollment"), default=True
    )
    requires_parent_approval = models.BooleanField(
        _("requires parent approval"), default=True
    )

    # System Settings
    database_schema = models.CharField(
        _("database schema"),
        max_length=50,
        blank=True,
        help_text=_("For multi-tenant database separation"),
    )
    api_key = models.CharField(_("API key"), max_length=100, blank=True, unique=True)

    # Relationships
    users = models.ManyToManyField(
        "users.User",
        through="InstitutionUser",
        related_name="institutions",
        verbose_name=_("users"),
        blank=True,
        help_text=_("Users associated with this institution"),
    )

    # Metadata
    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_institutions",
        verbose_name=_("created by"),
    )

    class Meta:
        verbose_name = _("Institution")
        verbose_name_plural = _("Institutions")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code", "status"]),
            models.Index(fields=["institution_type", "ownership_type"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = self.generate_api_key()
        super().save(*args, **kwargs)

    def generate_api_key(self):
        """Generate a unique API key for the institution."""
        import secrets
        import string

        while True:
            api_key = "".join(
                secrets.choice(string.ascii_letters + string.digits) for _ in range(32)
            )
            if not Institution.objects.filter(api_key=api_key).exists():
                return api_key

    @property
    def current_student_count(self):
        """Get current number of active students."""
        return self.users.filter(
            user_roles__role__role_type="student",
            user_roles__status="active",
            is_active=True,
        ).count()

    @property
    def current_staff_count(self):
        """Get current number of active staff."""
        return self.users.filter(
            user_roles__role__role_type__in=[
                "teacher",
                "admin",
                "principal",
                "support",
                "school_admin",
                "counselor",
                "accountant",
                "librarian",
                "department_head",
                "transport_manager",
                "hostel_warden",
                "driver",
                "activities_coordinator",
            ],
            user_roles__status="active",
            is_active=True,
        ).count()

    @property
    def utilization_rate(self):
        """Calculate institution utilization rate."""
        if self.max_students == 0:
            return 0
        return (self.current_student_count / self.max_students) * 100


class GlobalBaseModel(models.Model):
    """
    Base model for truly global/system-wide data that doesn't belong to any institution.
    Provides core functionality without institution association:
    - UUID primary key
    - Created/updated timestamps
    - Status tracking with change timestamp
    - Soft delete functionality
    - NO institution association (truly global data)
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        PENDING = "pending", _("Pending")
        SUSPENDED = "suspended", _("Suspended")
        ARCHIVED = "archived", _("Archived")

    # UUID Primary Key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Timestamp fields
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True, db_index=True)

    # Status fields
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    status_changed_at = models.DateTimeField(_("status changed at"), auto_now_add=True)

    # Soft delete fields
    is_deleted = models.BooleanField(_("is deleted"), default=False, db_index=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Update status_changed_at when status changes.
        """
        if (
            self.pk and not self._state.adding
        ):  # Check if object exists and is not being added
            try:
                original = self.__class__.objects.get(pk=self.pk)
                if original.status != self.status:
                    self.status_changed_at = timezone.now()
            except self.__class__.DoesNotExist:
                # Object doesn't exist yet (shouldn't happen in normal flow)
                pass

        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """
        Soft delete by setting is_deleted flag and deleted_at timestamp.
        """
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def hard_delete(self, using=None, keep_parents=False):
        """
        Perform actual database deletion.
        """
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """
        Restore a soft-deleted instance.
        """
        self.is_deleted = False
        self.deleted_at = None
        self.save()

    def __str__(self):
        return f"{self.__class__.__name__} {self.id}"


class CoreBaseModel(models.Model):
    """
    Comprehensive base model combining all core functionalities:
    - UUID primary key
    - Created/updated timestamps
    - Status tracking with change timestamp
    - Soft delete functionality
    - Institution association (multi-tenancy support)
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        INACTIVE = "inactive", _("Inactive")
        PENDING = "pending", _("Pending")
        SUSPENDED = "suspended", _("Suspended")
        ARCHIVED = "archived", _("Archived")

    # UUID Primary Key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Timestamp fields
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True, db_index=True)

    # Status fields
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    status_changed_at = models.DateTimeField(_("status changed at"), auto_now_add=True)

    # Soft delete fields
    is_deleted = models.BooleanField(_("is deleted"), default=False, db_index=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    # Multi-tenancy support
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="%(class)s_records",
        verbose_name=_("institution"),
        help_text=_("Institution this record belongs to"),
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Update status_changed_at when status changes.
        Institution must be explicitly set during creation - no automatic defaults.
        """
        if (
            self.pk and not self._state.adding
        ):  # Check if object exists and is not being added
            try:
                original = self.__class__.objects.get(pk=self.pk)
                if original.status != self.status:
                    self.status_changed_at = timezone.now()
            except self.__class__.DoesNotExist:
                # Object doesn't exist yet (shouldn't happen in normal flow)
                pass

        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """
        Soft delete by setting is_deleted flag and deleted_at timestamp.
        """
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()

    def hard_delete(self, using=None, keep_parents=False):
        """
        Perform actual database deletion.
        """
        super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        """
        Restore a soft-deleted instance.
        """
        self.is_deleted = False
        self.deleted_at = None
        self.save()

    def __str__(self):
        return f"{self.__class__.__name__} {self.id}"


class InstitutionUser(CoreBaseModel):
    """
    Through model for user-institution many-to-many relationship.
    Provides additional fields for user-institution associations.
    """

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="institution_memberships",
        verbose_name=_("user"),
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="user_memberships",
        verbose_name=_("institution"),
    )
    date_joined = models.DateField(_("date joined"), auto_now_add=True)
    employee_id = models.CharField(
        _("employee/student ID"),
        max_length=20,
        blank=True,
        help_text=_("Unique identifier within this institution"),
    )
    is_primary = models.BooleanField(
        _("is primary institution"),
        default=False,
        help_text=_("Primary institution for this user"),
    )

    class Meta:
        verbose_name = _("Institution User")
        verbose_name_plural = _("Institution Users")
        unique_together = ["user", "institution"]
        ordering = ["-is_primary", "date_joined"]
        indexes = [
            models.Index(fields=["user", "is_primary"]),
            models.Index(fields=["institution", "user"]),
        ]

    def __str__(self):
        return f"{self.user} at {self.institution}"

    def save(self, *args, **kwargs):
        """Ensure only one primary institution per user."""
        if self.is_primary:
            InstitutionUser.objects.filter(user=self.user, is_primary=True).exclude(
                pk=self.pk
            ).update(is_primary=False)
        super().save(*args, **kwargs)


class InstitutionConfig(CoreBaseModel):
    """
    Model for institution-specific configuration overrides.
    """

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="configurations",
        verbose_name=_("institution"),
    )
    system_config = models.ForeignKey(
        "SystemConfig",
        on_delete=models.CASCADE,
        related_name="institution_overrides",
        verbose_name=_("system configuration"),
    )
    override_value = models.JSONField(_("override value"))
    is_active = models.BooleanField(_("is active"), default=True)

    class Meta:
        verbose_name = _("Institution Configuration")
        verbose_name_plural = _("Institution Configurations")
        unique_together = ["institution", "system_config"]
        ordering = ["institution", "system_config__config_type", "system_config__key"]

    def __str__(self):
        return f"{self.institution.code}: {self.system_config.key}"

    @property
    def effective_value(self):
        """Get the effective configuration value (override or global)."""
        return self.override_value if self.is_active else self.system_config.value


class SystemConfig(GlobalBaseModel):
    """
    Model for storing system-wide configuration settings.
    """

    class ConfigType(models.TextChoices):
        GENERAL = "general", _("General")
        ACADEMIC = "academic", _("Academic")
        FINANCE = "finance", _("Finance")
        COMMUNICATION = "communication", _("Communication")
        SECURITY = "security", _("Security")
        UI = "ui", _("User Interface")

    key = models.CharField(_("config key"), max_length=100, unique=True, db_index=True)
    value = models.JSONField(_("config value"), default=dict)
    config_type = models.CharField(
        _("config type"),
        max_length=20,
        choices=ConfigType.choices,
        default=ConfigType.GENERAL,
    )
    description = models.TextField(_("description"), blank=True)
    is_public = models.BooleanField(_("is public"), default=False)
    is_encrypted = models.BooleanField(_("is encrypted"), default=False)
    allows_institution_override = models.BooleanField(
        _("allows institution override"), default=True
    )

    class Meta:
        verbose_name = _("System Configuration")
        verbose_name_plural = _("System Configurations")
        ordering = ["config_type", "key"]

    def __str__(self):
        return f"{self.key} ({self.config_type})"

    def get_value_for_institution(self, institution):
        """
        Get the effective configuration value for a specific institution.
        Returns institution override if exists and active, otherwise global value.
        """
        if not self.allows_institution_override:
            return self.value

        try:
            institution_config = InstitutionConfig.objects.get(
                institution=institution, system_config=self, is_active=True
            )
            return institution_config.effective_value
        except InstitutionConfig.DoesNotExist:
            return self.value


class SequenceGenerator(CoreBaseModel):
    """
    Model for generating sequential numbers for various purposes.
    """

    class SequenceType(models.TextChoices):
        STUDENT_ID = "student_id", _("Student ID")
        EMPLOYEE_ID = "employee_id", _("Employee ID")
        INVOICE = "invoice", _("Invoice Number")
        RECEIPT = "receipt", _("Receipt Number")
        LIBRARY_BOOK = "library_book", _("Library Book ID")
        TRANSPORT_BUS = "transport_bus", _("Transport Bus ID")
        STAFF_APPLICATION = "staff_application", _("Staff Application Number")

    sequence_type = models.CharField(
        _("sequence type"), max_length=50, choices=SequenceType.choices
    )
    prefix = models.CharField(_("prefix"), max_length=10, blank=True)
    suffix = models.CharField(_("suffix"), max_length=10, blank=True)
    last_number = models.PositiveIntegerField(_("last number"), default=0)
    padding = models.PositiveIntegerField(
        _("number padding"),
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    reset_frequency = models.CharField(
        _("reset frequency"),
        max_length=20,
        choices=[
            ("never", _("Never")),
            ("yearly", _("Yearly")),
            ("monthly", _("Monthly")),
            ("daily", _("Daily")),
        ],
        default="never",
    )

    class Meta:
        verbose_name = _("Sequence Generator")
        verbose_name_plural = _("Sequence Generators")
        unique_together = [["sequence_type", "institution"]]

    def __str__(self):
        return f"{self.sequence_type} - Last: {self.last_number}"

    def get_next_number(self):
        """Generate and return the next sequential number."""
        self.last_number += 1
        self.save()

        number_str = str(self.last_number).zfill(self.padding)
        return f"{self.prefix}{number_str}{self.suffix}"
