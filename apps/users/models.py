import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
import secrets
import string
import logging
from apps.core.models import CoreBaseModel, AddressModel, ContactModel, Institution

logger = logging.getLogger(__name__)


class UserManager(BaseUserManager):
    """
    Custom user manager for email-based authentication.
    """

    def get_admin_users(self):
        """Simple method to get all admin users for your custom admin panel"""
        return self.filter(is_staff=True)

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and return a regular user with an email and password.
        """
        if not email:
            raise ValueError(_("The Email field must be set"))

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and return a superuser with admin permissions.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        user = self.create_user(email, password, **extra_fields)

        # Automatically assign SUPER_ADMIN role to ensure superuser gets all custom permissions
        try:
            from apps.core.models import Institution
            from django.conf import settings

            # Only attach a SUPER_ADMIN role if a DEFAULT institution exists.
            default_institution = Institution.objects.filter(
                code="DEFAULT", is_active=True
            ).first()
            if default_institution:
                super_admin_role, created = Role.objects.get_or_create(
                    role_type=Role.RoleType.SUPER_ADMIN,
                    institution=default_institution,
                    defaults={
                        "name": "Super Administrator",
                        "description": "Full system access and control",
                        "hierarchy_level": 100,
                        "is_system_role": True,
                        "status": "active",
                    },
                )

                # Check if user already has SUPER_ADMIN role
                if not user.user_roles.filter(role=super_admin_role).exists():
                    UserRole.objects.create(
                        user=user,
                        role=super_admin_role,
                        institution=default_institution,
                        is_primary=True,
                    )
            else:
                # No default institution found; do not create one implicitly here.
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    "No DEFAULT institution found while creating superuser; skipping role assignment."
                )
        except Exception as e:
            # Log error but don't fail superuser creation
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Failed to assign SUPER_ADMIN role to superuser {user.email}: {e}"
            )

        return user


class User(AbstractUser):
    """
    Custom User model with email as primary identifier.
    """

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )
    # Remove username field, use email instead
    username = None
    email = models.EmailField(
        _("email address"),
        unique=True,
        db_index=True,
        help_text=_("Primary email address for communication"),
    )

    # Additional fields
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message=_(
            "Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        ),
    )
    mobile = models.CharField(
        _("mobile number"),
        validators=[phone_regex],
        max_length=17,
        blank=True,
        help_text=_("Primary mobile number for SMS notifications"),
    )

    # Verification fields
    is_verified = models.BooleanField(
        _("verified"),
        default=False,
        help_text=_("Designates whether the user has verified their email address"),
    )
    email_verified_at = models.DateTimeField(
        _("email verified at"), null=True, blank=True
    )
    verification_token = models.CharField(
        _("verification token"), max_length=100, blank=True
    )

    # Security fields
    last_login_ip = models.GenericIPAddressField(
        _("last login IP"), null=True, blank=True
    )
    current_login_ip = models.GenericIPAddressField(
        _("current login IP"), null=True, blank=True
    )
    login_count = models.PositiveIntegerField(_("login count"), default=0)

    # Preferences
    language = models.CharField(
        _("language"),
        max_length=10,
        default="en",
        choices=[
            ("en", _("English")),
            ("es", _("Spanish")),
            ("fr", _("French")),
            ("ar", _("Arabic")),
        ],
        help_text=_("Preferred language for the interface"),
    )
    timezone = models.CharField(
        _("timezone"),
        max_length=50,
        default="UTC",
        help_text=_("User's preferred timezone"),
    )

    # Override AbstractUser fields to make optional
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["is_active", "is_verified"]),
            models.Index(fields=["last_login"]),
        ]

    def __str__(self):
        return self.email

    def get_initials(self):
        """Return initials for the user (e.g. 'JD' for John Doe)."""
        parts = []

        if self.first_name:
            parts.append(self.first_name.strip())
        if self.last_name:
            parts.append(self.last_name.strip())
        if parts:
            initials = "".join([p[0].upper() for p in parts if p])
            return initials[:2]
        # fallback to email username part
        if self.email:
            name_part = self.email.split("@", 1)[0]
            return name_part[:2].upper()
        return ""

    @property
    def full_name(self):
        """Return the full name of the user."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self):
        """Return display name (full name)."""
        return self.full_name

    @property
    def current_institution(self):
        """
        Get the user's current institution.

        Priority:
        1. Thread-local/current request institution (set by TenantMiddleware)
        2. User's primary membership institution
        """
        # Prefer the institution set by the TenantMiddleware (thread-local)
        try:
            from apps.core.middleware import get_current_institution

            current_inst = get_current_institution()
            if current_inst:
                return current_inst
        except Exception:
            # Ignore and fallback to membership-based lookup
            pass

        try:
            primary_membership = (
                self.institution_memberships.filter(is_primary=True)
                .select_related("institution")
                .first()
            )
            return primary_membership.institution if primary_membership else None
        except Exception:
            return None

    def verify_email(self):
        """Mark user's email as verified."""
        self.is_verified = True
        self.email_verified_at = timezone.now()
        self.verification_token = ""
        self.save()

    def increment_login_count(self):
        """Increment login count and update IP addresses."""
        self.login_count += 1
        self.last_login_ip = self.current_login_ip
        self.current_login_ip = None  # Will be set during login
        self.save()

    def is_admin_user(self):
        """Simple check if user can access admin panel"""
        return self.is_staff or self.is_superuser

    def make_random_password(self, length=12):
        """
        Generate a random password for the user.
        """
        characters = string.ascii_letters + string.digits + string.punctuation
        password = "".join(secrets.choice(characters) for i in range(length))
        self.set_password(password)
        self.save()
        return password


class Role(CoreBaseModel):
    """
    Model for defining user roles and permissions.
    """

    class RoleType(models.TextChoices):
        SUPER_ADMIN = "super_admin", _("Super Administrator")
        SCHOOL_ADMIN = "school_admin", _("School Administrator")
        ADMIN = "admin", _("Administrator")
        PRINCIPAL = "principal", _("Principal")
        DEPARTMENT_HEAD = "department_head", _("Department Head")
        COUNSELOR = "counselor", _("School Counselor")
        TEACHER = "teacher", _("Teacher")
        STUDENT = "student", _("Student")
        PARENT = "parent", _("Parent")
        ACCOUNTANT = "accountant", _("Accountant")
        LIBRARIAN = "librarian", _("Librarian")
        ACTIVITIES_COORDINATOR = "activities_coordinator", _("Activities Coordinator")
        DRIVER = "driver", _("Driver")
        SUPPORT = "support", _("Support Staff")
        TRANSPORT_MANAGER = "transport_manager", _("Transport Manager")
        HOSTEL_WARDEN = "hostel_warden", _("Hostel Warden")

    STAFF_ROLES = [
        RoleType.SUPER_ADMIN,
        RoleType.SCHOOL_ADMIN,
        RoleType.ADMIN,
        RoleType.PRINCIPAL,
        RoleType.DEPARTMENT_HEAD,
        RoleType.COUNSELOR,
        RoleType.TEACHER,
        RoleType.ACCOUNTANT,
        RoleType.LIBRARIAN,
        RoleType.ACTIVITIES_COORDINATOR,
        RoleType.DRIVER,
        RoleType.SUPPORT,
        RoleType.TRANSPORT_MANAGER,
        RoleType.HOSTEL_WARDEN,
    ]

    name = models.CharField(_("role name"), max_length=50)
    role_type = models.CharField(
        _("role type"), max_length=25, choices=RoleType.choices
    )
    description = models.TextField(_("description"), blank=True)
    permissions = models.ManyToManyField(
        "auth.Permission",
        verbose_name=_("permissions"),
        blank=True,
        related_name="roles",
    )
    is_system_role = models.BooleanField(_("is system role"), default=False)
    hierarchy_level = models.PositiveIntegerField(
        _("hierarchy level"),
        default=0,
        help_text=_("Higher number indicates higher authority (0 = lowest)"),
    )

    class Meta:
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        ordering = ["-hierarchy_level", "name"]
        unique_together = ["role_type", "institution"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Ensure system roles cannot be modified."""
        # Track original values for audit logging
        if self.pk:
            try:
                original = Role.objects.get(pk=self.pk)
                self._original_name = original.name
                self._original_role_type = original.role_type
                self._original_hierarchy_level = original.hierarchy_level
                self._original_status = original.status

                # Check system role constraints only if this is an update (not creation)
                if self.is_system_role:
                    if (
                        original.name != self.name
                        or original.role_type != self.role_type
                    ):
                        raise ValueError(_("System roles cannot be modified."))
            except Role.DoesNotExist:
                # Object doesn't exist yet (during creation)
                pass

        super().save(*args, **kwargs)


class UserProfile(CoreBaseModel, AddressModel, ContactModel):
    """
    Extended profile information for users.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile", verbose_name=_("user")
    )

    # Personal Information
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)
    GENDER_CHOICES = [
        ("male", _("Male")),
        ("female", _("Female")),
        ("other", _("Other")),
        ("prefer_not_to_say", _("Prefer not to say")),
    ]
    gender = models.CharField(
        _("gender"), max_length=20, choices=GENDER_CHOICES, blank=True
    )
    nationality = models.CharField(_("nationality"), max_length=100, blank=True)
    identification_number = models.CharField(
        _("identification number"),
        max_length=50,
        blank=True,
        help_text=_("National ID, Passport number, etc."),
    )

    # Profile Image
    profile_picture = models.ImageField(
        _("profile picture"),
        upload_to="profiles/%Y/%m/%d/",
        null=True,
        blank=True,
        help_text=_("Profile picture (recommended size: 200x200 pixels)"),
    )

    # Employee ID (for staff members)
    employee_id = models.CharField(
        _("employee ID"),
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        help_text=_("Unique identifier for staff members"),
    )

    # Biography
    bio = models.TextField(_("biography"), blank=True)

    # Social Media
    website = models.URLField(_("website"), blank=True)
    facebook = models.URLField(_("facebook"), blank=True)
    twitter = models.URLField(_("twitter"), blank=True)
    linkedin = models.URLField(_("linkedin"), blank=True)

    # Settings
    email_notifications = models.BooleanField(_("email notifications"), default=True)
    sms_notifications = models.BooleanField(_("SMS notifications"), default=False)
    push_notifications = models.BooleanField(_("push notifications"), default=True)

    # Theme Preferences
    THEME_CHOICES = [
        ("light", _("Light")),
        ("dark", _("Dark")),
        ("auto", _("Auto (System)")),
    ]
    theme = models.CharField(
        _("theme preference"),
        max_length=20,
        choices=THEME_CHOICES,
        default="light",
        help_text=_(
            "Choose your preferred theme or set to auto to follow system preference"
        ),
    )

    # Metadata
    last_profile_update = models.DateTimeField(_("last profile update"), auto_now=True)

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["identification_number"]),
        ]

    def __str__(self):
        return f"Profile of {self.user}"

    @property
    def age(self):
        """Calculate age from date of birth."""
        if self.date_of_birth:
            today = timezone.now().date()
            return (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
        return None


class UserRole(CoreBaseModel):
    """
    Model for assigning roles to users with context (e.g., which school/class).
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_roles",
        verbose_name=_("user"),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_roles",
        verbose_name=_("role"),
    )
    is_primary = models.BooleanField(
        _("is primary role"),
        default=True,
        help_text=_("Designates the primary role for this user"),
    )

    # Context fields (optional, for role-specific context)
    academic_session = models.ForeignKey(
        "academics.AcademicSession",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("academic session"),
    )
    # Additional context fields can be added based on role type
    context_id = models.CharField(
        _("context ID"),
        max_length=100,
        blank=True,
        help_text=_("Role context identifier (e.g., class_id for teachers)"),
    )

    class Meta:
        verbose_name = _("User Role")
        verbose_name_plural = _("User Roles")
        unique_together = ["user", "role", "institution", "context_id"]
        ordering = ["-is_primary", "-created_at"]
        indexes = [
            models.Index(fields=["user", "is_primary"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.role}"

    def clean(self):
        """Validate UserRole data integrity."""
        # Ensure the referenced user still exists
        if not User.objects.filter(id=self.user_id).exists():
            raise ValidationError(_("The referenced user does not exist."))

        # Ensure the referenced role still exists
        if not Role.objects.filter(id=self.role_id).exists():
            raise ValidationError(_("The referenced role does not exist."))

    def save(self, *args, **kwargs):
        """Ensure only one primary role per user per academic session."""
        # Track original values for audit logging
        if self.pk:
            try:
                original = UserRole.objects.get(pk=self.pk)
                self._original_is_primary = original.is_primary
            except UserRole.DoesNotExist:
                pass

        if self.is_primary:
            # Set all other roles for this user in the same context as non-primary
            UserRole.objects.filter(
                user=self.user, academic_session=self.academic_session, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class UserRoleActivity(CoreBaseModel):
    """
    Model for tracking user role assignment and removal activities.
    """

    class ActionType(models.TextChoices):
        ASSIGNED = "assigned", _("Role Assigned")
        REMOVED = "removed", _("Role Removed")
        SET_PRIMARY = "set_primary", _("Set as Primary")
        SET_SECONDARY = "set_secondary", _("Set as Secondary")

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="role_activities",
        verbose_name=_("affected user"),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="role_activities",
        verbose_name=_("affected role"),
    )
    action_type = models.CharField(
        _("action type"), max_length=15, choices=ActionType.choices
    )
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performed_role_activities",
        verbose_name=_("performed by"),
    )
    academic_session = models.ForeignKey(
        "academics.AcademicSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("academic session"),
    )
    details = models.TextField(
        _("details"), blank=True, help_text=_("Additional context about the change")
    )

    class Meta:
        verbose_name = _("User Role Activity")
        verbose_name_plural = _("User Role Activities")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["role", "created_at"]),
            models.Index(fields=["performed_by", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action_type}: {self.user} - {self.role} (by {self.performed_by})"

    @property
    def action_description(self):
        """Return a human-readable description of the action."""
        if self.action_type == self.ActionType.ASSIGNED:
            return _("was assigned the role")
        elif self.action_type == self.ActionType.REMOVED:
            return _("was removed from the role")
        elif self.action_type == self.ActionType.SET_PRIMARY:
            return _("had their role set as primary")
        elif self.action_type == self.ActionType.SET_SECONDARY:
            return _("had their role set as secondary")
        return self.action_type

    @classmethod
    def log_activity(
        cls,
        user,
        role,
        action_type,
        performed_by=None,
        academic_session=None,
        details="",
    ):
        """
        Class method to log a user role activity.
        """
        return cls.objects.create(
            user=user,
            role=role,
            action_type=action_type,
            performed_by=performed_by,
            academic_session=academic_session,
            details=details,
        )


class LoginHistory(CoreBaseModel):
    """
    Model for tracking user login history.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="login_history",
        verbose_name=_("user"),
        null=True,
        blank=True,
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="login_history_records",
        verbose_name=_("institution"),
        help_text=_("Institution this record belongs to"),
        null=True,
        blank=True,
    )
    ip_address = models.GenericIPAddressField(_("IP address"))
    user_agent = models.TextField(_("user agent"), blank=True)
    location = models.CharField(_("location"), max_length=255, blank=True)
    login_method = models.CharField(
        _("login method"),
        max_length=20,
        choices=[
            ("password", _("Password")),
            ("sso", _("Single Sign-On")),
            ("token", _("Token")),
        ],
        default="password",
    )
    was_successful = models.BooleanField(_("was successful"), default=True)
    failure_reason = models.CharField(_("failure reason"), max_length=100, blank=True)
    session_key = models.CharField(_("session key"), max_length=100, blank=True)

    class Meta:
        verbose_name = _("Login History")
        verbose_name_plural = _("Login History")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
        ]

    def __str__(self):
        status = "Success" if self.was_successful else "Failed"
        return f"{self.user} - {self.created_at} - {status}"


class PasswordHistory(CoreBaseModel):
    """
    Model for storing password history to enforce password policies.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="password_history",
        verbose_name=_("user"),
    )
    password_hash = models.CharField(_("password hash"), max_length=255)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="changed_passwords",
        verbose_name=_("changed by"),
    )
    change_reason = models.CharField(
        _("change reason"),
        max_length=20,
        choices=[
            ("initial", _("Initial Setup")),
            ("regular", _("Regular Change")),
            ("compromise", _("Suspected Compromise")),
            ("reset", _("Password Reset")),
        ],
        default="regular",
    )

    class Meta:
        verbose_name = _("Password History")
        verbose_name_plural = _("Password History")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.created_at}"


class UserSession(CoreBaseModel):
    """
    Model for tracking active user sessions.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sessions", verbose_name=_("user")
    )
    session_key = models.CharField(_("session key"), max_length=100, unique=True)
    ip_address = models.GenericIPAddressField(_("IP address"))
    user_agent = models.TextField(_("user agent"), blank=True)
    last_activity = models.DateTimeField(_("last activity"), auto_now=True)
    expires_at = models.DateTimeField(_("expires at"))

    class Meta:
        verbose_name = _("User Session")
        verbose_name_plural = _("User Sessions")
        ordering = ["-last_activity"]
        indexes = [
            models.Index(fields=["user", "expires_at"]),
            models.Index(fields=["session_key"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.session_key}"

    @property
    def is_expired(self):
        """Check if session has expired."""
        return timezone.now() > self.expires_at


class ParentStudentRelationship(CoreBaseModel):
    """
    Model for managing parent-student relationships.
    """

    class RelationshipType(models.TextChoices):
        FATHER = "father", _("Father")
        MOTHER = "mother", _("Mother")
        GUARDIAN = "guardian", _("Guardian")
        SIBLING = "sibling", _("Sibling")
        OTHER = "other", _("Other")

    parent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="children_relationships",
        verbose_name=_("parent"),
        limit_choices_to={"user_roles__role__role_type": Role.RoleType.PARENT},
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="parent_relationships",
        verbose_name=_("student"),
        limit_choices_to={"user_roles__role__role_type": Role.RoleType.STUDENT},
    )
    relationship_type = models.CharField(
        _("relationship type"), max_length=20, choices=RelationshipType.choices
    )
    is_primary_contact = models.BooleanField(
        _("is primary contact"),
        default=False,
        help_text=_("Designates the primary contact for the student"),
    )
    can_pickup = models.BooleanField(
        _("can pickup student"),
        default=True,
        help_text=_("Can this person pickup the student from school?"),
    )
    emergency_contact_order = models.PositiveIntegerField(
        _("emergency contact order"),
        default=0,
        help_text=_("Order in which to contact in emergencies (0 = first)"),
    )

    class Meta:
        verbose_name = _("Parent-Student Relationship")
        verbose_name_plural = _("Parent-Student Relationships")
        unique_together = ["parent", "student", "relationship_type"]
        ordering = ["emergency_contact_order", "relationship_type"]
        indexes = [
            models.Index(fields=["parent", "is_primary_contact"]),
            models.Index(fields=["student", "relationship_type"]),
        ]

    def __str__(self):
        return f"{self.parent} - {self.relationship_type} - {self.student}"

    def save(self, *args, **kwargs):
        """Ensure only one primary contact per student."""
        if self.is_primary_contact:
            ParentStudentRelationship.objects.filter(
                student=self.student, is_primary_contact=True
            ).exclude(pk=self.pk).update(is_primary_contact=False)
        super().save(*args, **kwargs)


# Institution Transfer Models


class InstitutionTransferRequest(CoreBaseModel):
    """
    Model for tracking institution transfer requests by existing users.
    """

    class TransferType(models.TextChoices):
        STUDENT_TRANSFER = "student_transfer", _("Student Transfer")
        STAFF_TRANSFER = "staff_transfer", _("Staff Transfer")

    class RequestStatus(models.TextChoices):
        PENDING = "pending", _("Pending Review")
        UNDER_REVIEW = "under_review", _("Under Review")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        COMPLETED = "completed", _("Transfer Completed")
        CANCELLED = "cancelled", _("Cancelled")

    # Transfer Details
    transfer_type = models.CharField(
        _("transfer type"), max_length=20, choices=TransferType.choices
    )
    requesting_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="institution_transfer_requests",
        verbose_name=_("requesting user"),
    )

    # Institution Details
    current_institution = models.ForeignKey(
        "core.Institution",
        on_delete=models.CASCADE,
        related_name="outgoing_transfers",
        verbose_name=_("current institution"),
    )
    requested_institution = models.ForeignKey(
        "core.Institution",
        on_delete=models.CASCADE,
        related_name="incoming_transfer_requests",
        verbose_name=_("requested institution"),
    )

    # Request Details
    request_reason = models.TextField(
        _("reason for transfer"),
        help_text=_("Please explain why you want to transfer institutions"),
    )
    additional_notes = models.TextField(
        _("additional notes"),
        blank=True,
        help_text=_("Any additional information relevant to your transfer request"),
    )

    # Status and Workflow
    request_status = models.CharField(
        _("request status"),
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
    )
    priority_level = models.CharField(
        _("priority level"),
        max_length=10,
        choices=[
            ("low", _("Low")),
            ("medium", _("Medium")),
            ("high", _("High")),
            ("urgent", _("Urgent")),
        ],
        default="medium",
    )

    # Approval Workflow
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_transfer_requests",
        verbose_name=_("reviewed by"),
    )
    reviewed_at = models.DateTimeField(_("reviewed at"), null=True, blank=True)
    review_notes = models.TextField(_("review notes"), blank=True)
    approval_date = models.DateTimeField(_("approval date"), null=True, blank=True)

    # Transfer Completion
    transfer_completed_at = models.DateTimeField(
        _("transfer completed at"), null=True, blank=True
    )
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_transfers",
        verbose_name=_("transfer completed by"),
    )

    # Academic/Professional Context (for transfers)
    academic_session = models.ForeignKey(
        "academics.AcademicSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("academic session"),
    )
    current_role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_transfer_requests",
        verbose_name=_("current role/position"),
        help_text=_("Current role at the institution"),
    )

    # System fields
    request_number = models.CharField(
        _("request number"), max_length=20, unique=True, blank=True
    )

    class Meta:
        verbose_name = _("Institution Transfer Request")
        verbose_name_plural = _("Institution Transfer Requests")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["requesting_user", "request_status"]),
            models.Index(fields=["current_institution", "requested_institution"]),
            models.Index(fields=["transfer_type", "request_status"]),
            models.Index(fields=["request_number"]),
        ]

    def __str__(self):
        return f"{self.requesting_user.get_full_name()} - {self.current_institution.code} to {self.requested_institution.code}"

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self.generate_request_number()
        super().save(*args, **kwargs)

    def generate_request_number(self):
        """Generate unique request number."""
        prefix_map = {
            self.TransferType.STUDENT_TRANSFER: "STU",
            self.TransferType.STAFF_TRANSFER: "STF",
        }
        prefix = prefix_map.get(self.transfer_type, "TRF")
        year = timezone.now().strftime("%Y")

        # Find the last request number for this year
        last_request = (
            InstitutionTransferRequest.objects.filter(
                request_number__startswith=f"{prefix}{year}"
            )
            .order_by("request_number")
            .last()
        )

        if last_request:
            try:
                last_num = int(last_request.request_number[-4:])
                new_num = last_num + 1
            except (ValueError, IndexError):
                new_num = 1
        else:
            new_num = 1

        return f"{prefix}{year}{new_num:04d}"

    @property
    def can_be_approved_by(self, user):
        """Check if a user can approve this transfer request."""
        if not user.is_authenticated:
            return False

        # Superusers can approve anything
        if user.is_superuser:
            return True

        # Check user's roles and institution permissions
        user_institutions = user.institutions.filter(is_active=True)

        # Can approve if user has admin role at either current or requested institution
        has_admin_rights_current = user_institutions.filter(
            id=self.current_institution.id
        ).exists() and (
            user.user_roles.filter(
                role__role_type__in=[
                    "admin",
                    "principal",
                    "school_admin",
                    "super_admin",
                ],
                status="active",
            ).exists()
            or user.has_perm("core.change_institution")
        )

        has_admin_rights_requested = user_institutions.filter(
            id=self.requested_institution.id
        ).exists() and (
            user.user_roles.filter(
                role__role_type__in=[
                    "admin",
                    "principal",
                    "school_admin",
                    "super_admin",
                ],
                status="active",
            ).exists()
            or user.has_perm("core.change_institution")
        )

        return has_admin_rights_current or has_admin_rights_requested

    def approve(self, approved_by, review_notes=""):
        """Approve the transfer request."""
        from django.utils import timezone

        if self.request_status in [
            self.RequestStatus.APPROVED,
            self.RequestStatus.COMPLETED,
        ]:
            raise ValueError("Transfer request is already approved or completed.")

        self.request_status = self.RequestStatus.APPROVED
        self.reviewed_by = approved_by
        self.reviewed_at = timezone.now()
        self.approval_date = timezone.now()
        self.review_notes = review_notes
        self.save()

        # TODO: Trigger transfer completion process

    def reject(self, rejected_by, review_notes=""):
        """Reject the transfer request."""
        from django.utils import timezone

        if self.request_status in [
            self.RequestStatus.REJECTED,
            self.RequestStatus.COMPLETED,
        ]:
            raise ValueError("Transfer request is already rejected or completed.")

        self.request_status = self.RequestStatus.REJECTED
        self.reviewed_by = rejected_by
        self.reviewed_at = timezone.now()
        self.review_notes = review_notes
        self.save()

    def complete_transfer(self, completed_by):
        """Mark the transfer as completed."""
        from django.utils import timezone

        if self.request_status != self.RequestStatus.APPROVED:
            raise ValueError("Cannot complete transfer that hasn't been approved.")

        self.request_status = self.RequestStatus.COMPLETED
        self.transfer_completed_at = timezone.now()
        self.completed_by = completed_by
        self.save()

    @property
    def status_badge_class(self):
        """Return Bootstrap badge class for status."""
        status_classes = {
            self.RequestStatus.PENDING: "secondary",
            self.RequestStatus.UNDER_REVIEW: "warning",
            self.RequestStatus.APPROVED: "success",
            self.RequestStatus.REJECTED: "danger",
            self.RequestStatus.COMPLETED: "success",
            self.RequestStatus.CANCELLED: "secondary",
        }
        return status_classes.get(self.request_status, "secondary")

    @property
    def transfer_summary(self):
        """Return a summary of the transfer request."""
        return {
            "request_number": self.request_number,
            "user": self.requesting_user.get_full_name(),
            "from_institution": str(self.current_institution),
            "to_institution": str(self.requested_institution),
            "status": self.get_request_status_display(),
            "requested_at": self.created_at,
            "transfer_type": self.get_transfer_type_display(),
        }


# Application Models


class ApplicationStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    UNDER_REVIEW = "under_review", _("Under Review")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")
    INTERVIEW_SCHEDULED = "interview_scheduled", _("Interview Scheduled")


class StudentApplication(CoreBaseModel, AddressModel):
    """
    Model for student applications from public/guest users.
    """

    # Personal Information
    first_name = models.CharField(_("first name"), max_length=50)
    last_name = models.CharField(_("last name"), max_length=50)
    email = models.EmailField(_("email address"))
    phone = models.CharField(_("phone number"), max_length=20, blank=True)
    date_of_birth = models.DateField(_("date of birth"))
    gender = models.CharField(
        _("gender"),
        max_length=20,
        choices=[
            ("male", _("Male")),
            ("female", _("Female")),
            ("other", _("Other")),
        ],
    )
    nationality = models.CharField(_("nationality"), max_length=50)

    # Academic Information
    grade_applying_for = models.CharField(_("grade applying for"), max_length=100)
    previous_school = models.CharField(_("previous school"), max_length=100, blank=True)
    previous_grade = models.CharField(_("previous grade"), max_length=20, blank=True)
    academic_achievements = models.TextField(_("academic achievements"), blank=True)
    medical_conditions = models.TextField(_("medical conditions"), blank=True)
    special_needs = models.TextField(_("special educational needs"), blank=True)
    extracurricular_interests = models.TextField(
        _("extracurricular interests"), blank=True
    )

    # Department for tertiary education applications
    department = models.ForeignKey(
        "academics.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_applications",
        verbose_name=_("department"),
        help_text=_("Department for tertiary education applications"),
    )

    # Parent/Guardian Information
    parent_first_name = models.CharField(_("parent first name"), max_length=50)
    parent_last_name = models.CharField(_("parent last name"), max_length=50)
    parent_email = models.EmailField(_("parent email"))
    parent_phone = models.CharField(_("parent phone"), max_length=20)
    parent_relationship = models.CharField(
        _("parent relationship"),
        max_length=20,
        choices=[
            ("father", _("Father")),
            ("mother", _("Mother")),
            ("guardian", _("Guardian")),
            ("other", _("Other")),
        ],
    )

    # Application Details
    application_status = models.CharField(
        _("application status"),
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
    )
    academic_session = models.ForeignKey(
        "academics.AcademicSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("academic session"),
    )
    application_date = models.DateTimeField(_("application date"), auto_now_add=True)

    # Review Information
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_student_applications",
        verbose_name=_("reviewed by"),
    )
    reviewed_at = models.DateTimeField(_("reviewed at"), null=True, blank=True)
    review_notes = models.TextField(_("review notes"), blank=True)

    # System fields
    application_number = models.CharField(
        _("application number"), max_length=20, unique=True, blank=True
    )
    user_account = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_application",
        verbose_name=_("user account"),
    )

    # Institution field - where the student is applying to study
    institution = models.ForeignKey(
        "core.Institution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_applications",
        verbose_name=_("institution"),
        help_text=_("The institution the student is applying to study at"),
    )

    class Meta:
        verbose_name = _("Student Application")
        verbose_name_plural = _("Student Applications")
        ordering = ["-application_date"]
        indexes = [
            models.Index(fields=["application_status", "application_date"]),
            models.Index(fields=["email"]),
            models.Index(fields=["application_number"]),
            models.Index(fields=["institution"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - Application {self.application_number}"

    def save(self, *args, **kwargs):
        if not self.application_number:
            self.application_number = self.generate_application_number()
        super().save(*args, **kwargs)

    def generate_application_number(self):
        """Generate unique application number using SequenceGenerator."""
        from apps.core.models import SequenceGenerator

        sequence, created = SequenceGenerator.objects.get_or_create(
            sequence_type="student_application",
            defaults={"prefix": "STU", "padding": 4, "reset_frequency": "yearly"},
        )
        return sequence.get_next_number()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.now().date()
            return (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
        return None

    @property
    def parent_full_name(self):
        """Return the full name of the parent/guardian."""
        return f"{self.parent_first_name} {self.parent_last_name}".strip()


class StaffApplication(CoreBaseModel, AddressModel):
    """
    Model for staff applications from public/guest users.
    """

    class PositionType(models.TextChoices):
        TEACHING = "teaching", _("Teaching Staff")
        ADMINISTRATIVE = "administrative", _("Administrative Staff")
        SUPPORT = "support", _("Support Staff")
        TECHNICAL = "technical", _("Technical Staff")

    # Personal Information
    first_name = models.CharField(_("first name"), max_length=50)
    last_name = models.CharField(_("last name"), max_length=50)
    email = models.EmailField(_("email address"))
    phone = models.CharField(_("phone number"), max_length=20, blank=True)
    date_of_birth = models.DateField(_("date of birth"))
    gender = models.CharField(
        _("gender"),
        max_length=20,
        choices=[
            ("male", _("Male")),
            ("female", _("Female")),
            ("other", _("Other")),
        ],
    )
    nationality = models.CharField(_("nationality"), max_length=50)

    # Professional Information
    position_applied_for = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        verbose_name=_("position applied for"),
        help_text=_("The position/role the applicant is applying for"),
    )
    position_type = models.CharField(
        _("position type"),
        max_length=20,
        choices=PositionType.choices,
        default=PositionType.TEACHING,
    )
    expected_salary = models.DecimalField(
        _("expected salary"), max_digits=10, decimal_places=2, null=True, blank=True
    )

    # Educational Background
    highest_qualification = models.CharField(_("highest qualification"), max_length=100)
    institution = models.CharField(
        _("institution"),
        max_length=200,
        help_text=_("Institution where qualification was obtained"),
    )
    year_graduated = models.PositiveIntegerField(_("year graduated"))

    # Professional Experience
    years_of_experience = models.PositiveIntegerField(
        _("years of experience"), default=0
    )
    previous_employer = models.CharField(
        _("previous employer"), max_length=200, blank=True
    )
    previous_position = models.CharField(
        _("previous position"), max_length=200, blank=True
    )

    # Documents
    cv = models.FileField(
        _("curriculum vitae"),
        upload_to="staff_applications/cvs/%Y/%m/%d/",
        help_text=_("Upload your CV (PDF, DOC, DOCX)"),
    )
    cover_letter = models.FileField(
        _("cover letter"),
        upload_to="staff_applications/cover_letters/%Y/%m/%d/",
        blank=True,
        help_text=_("Upload your cover letter (optional)"),
    )
    certificates = models.FileField(
        _("certificates"),
        upload_to="staff_applications/certificates/%Y/%m/%d/",
        blank=True,
        help_text=_("Upload relevant certificates (optional)"),
    )

    # References
    reference1_name = models.CharField(_("reference 1 name"), max_length=100)
    reference1_position = models.CharField(_("reference 1 position"), max_length=100)
    reference1_contact = models.CharField(_("reference 1 contact"), max_length=100)

    reference2_name = models.CharField(
        _("reference 2 name"), max_length=100, blank=True
    )
    reference2_position = models.CharField(
        _("reference 2 position"), max_length=100, blank=True
    )
    reference2_contact = models.CharField(
        _("reference 2 contact"), max_length=100, blank=True
    )

    # Application Details
    application_status = models.CharField(
        _("application status"),
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
    )
    academic_session = models.ForeignKey(
        "academics.AcademicSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("academic session"),
    )
    application_date = models.DateTimeField(_("application date"), auto_now_add=True)
    interview_date = models.DateTimeField(_("interview date"), null=True, blank=True)

    # Review Information
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_staff_applications",
        verbose_name=_("reviewed by"),
    )
    reviewed_at = models.DateTimeField(_("reviewed at"), null=True, blank=True)
    review_notes = models.TextField(_("review notes"), blank=True)

    # System fields
    application_number = models.CharField(
        _("application number"), max_length=20, unique=True, blank=True
    )
    user_account = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_application",
        verbose_name=_("user account"),
    )

    # Institution field - where the staff member is applying to work
    institution = models.ForeignKey(
        "core.Institution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_applications",
        verbose_name=_("institution"),
        help_text=_("The institution the applicant is applying to work at"),
    )

    class Meta:
        verbose_name = _("Staff Application")
        verbose_name_plural = _("Staff Applications")
        ordering = ["-application_date"]
        indexes = [
            models.Index(fields=["application_status", "application_date"]),
            models.Index(fields=["email"]),
            models.Index(fields=["application_number"]),
            models.Index(fields=["position_applied_for"]),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.position_applied_for}"

    def save(self, *args, **kwargs):
        if not self.application_number:
            self.application_number = self.generate_application_number()
        super().save(*args, **kwargs)

    def generate_application_number(self):
        """Generate unique application number using SequenceGenerator."""
        from apps.core.models import SequenceGenerator

        sequence, created = SequenceGenerator.objects.get_or_create(
            sequence_type=SequenceGenerator.SequenceType.STAFF_APPLICATION,
            defaults={"prefix": "STA", "padding": 4, "reset_frequency": "yearly"},
        )
        return sequence.get_next_number()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        if self.date_of_birth:
            today = timezone.now().date()
            return (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
        return None

    def clean(self):
        """Validate file types and sizes."""
        from django.core.exceptions import ValidationError

        # CV validation
        if self.cv:
            valid_extensions = [".pdf", ".doc", ".docx"]
            ext = str(self.cv.name).lower().split(".")[-1]
            if f".{ext}" not in valid_extensions:
                raise ValidationError(
                    {"cv": _("Only PDF, DOC, and DOCX files are allowed for CV.")}
                )

            if self.cv.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError({"cv": _("CV file size must not exceed 5MB.")})


# Permission synchronization utilities
def sync_user_permissions(user):
    """
    Synchronize user's Django permissions based on their active roles.
    This ensures that PermissionRequiredMixin checks work correctly.
    """
    from django.contrib.auth.models import Permission

    # Get all permissions from user's active roles
    role_permissions = Permission.objects.filter(
        roles__user_roles__user=user, roles__user_roles__status="active"
    ).distinct()

    # Update user's permissions
    user.user_permissions.set(role_permissions)
    user.save()

    return role_permissions.count()


def sync_all_user_permissions():
    """
    Synchronize permissions for all users based on their roles.
    Useful for initial setup or bulk updates.
    """
    users_updated = 0
    for user in User.objects.all():
        permissions_count = sync_user_permissions(user)
        if permissions_count > 0:
            users_updated += 1

    return users_updated


# Utility functions for ID generation
def generate_employee_id(institution):
    """
    Generate unique employee ID using SequenceGenerator per institution.
    Format: {INSTITUTION_CODE}-EMP-{SEQUENTIAL_NUMBER}
    """
    from apps.core.models import SequenceGenerator

    sequence, created = SequenceGenerator.objects.get_or_create(
        sequence_type=SequenceGenerator.SequenceType.EMPLOYEE_ID,
        institution=institution,
        defaults={"prefix": f"{institution.code}-EMP-", "padding": 3},
    )
    return sequence.get_next_number()


# Utility functions for guardian notifications
def get_student_guardians(student_user):
    """
    Get all guardians (parents) for a student user.
    Returns a QuerySet of User objects who are guardians of the student.
    """
    return User.objects.filter(
        children_relationships__student=student_user,
        children_relationships__status="active",
    ).distinct()


def notify_guardians_profile_update(student_user, guardians, changed_fields):
    """
    Send notifications to guardians when a student updates their profile.
    """
    from apps.communication.views import create_notification
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    from django.utils.html import strip_tags

    student_name = student_user.get_full_name() or student_user.email
    changed_fields_str = ", ".join(
        [field.replace("_", " ").title() for field in changed_fields]
    )

    # Create in-app notifications for each guardian
    for guardian in guardians:
        try:
            create_notification(
                user=guardian,
                title=f"Profile Update: {student_name}",
                message=f"{student_name} has updated their profile. Changed fields: {changed_fields_str}",
                notification_type="info",
                priority="medium",
                action_url=f"/users/profile/{student_user.id}/",
                related_model="users.UserProfile",
                related_object_id=str(student_user.profile.id),
            )
        except Exception as e:
            # Log error but don't fail the entire process
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to create notification for guardian {guardian.id}: {e}"
            )

    # Send email notifications
    subject = f"Profile Update Notification - {student_name}"

    for guardian in guardians:
        try:
            if guardian.profile.email_notifications:
                context = {
                    "guardian": guardian,
                    "student": student_user,
                    "student_name": student_name,
                    "changed_fields": changed_fields,
                    "changed_fields_str": changed_fields_str,
                    "school_name": getattr(settings, "SCHOOL_NAME", "Our School"),
                    "profile_url": (
                        f"{settings.SITE_URL}/users/profile/{student_user.id}/"
                        if hasattr(settings, "SITE_URL")
                        else "#"
                    ),
                }

                # Try to use email template if it exists
                try:
                    from apps.communication.models import EmailTemplate

                    template = EmailTemplate.objects.filter(
                        name="guardian_profile_update", is_active=True
                    ).first()

                    if template:
                        subject, html_message, text_message = template.render_template(
                            context
                        )
                    else:
                        # Fallback to basic template
                        html_message = render_to_string(
                            "users/emails/guardian_profile_update.html", context
                        )
                        text_message = strip_tags(html_message)
                except:
                    # Fallback if template system fails
                    html_message = f"""
                    <h2>Profile Update Notification</h2>
                    <p>Dear {guardian.get_full_name() or guardian.email},</p>
                    <p>Your child {student_name} has updated their profile information.</p>
                    <p><strong>Changed fields:</strong> {changed_fields_str}</p>
                    <p>Please review the changes and contact the school if you have any concerns.</p>
                    <p>Best regards,<br>{getattr(settings, 'SCHOOL_NAME', 'School Administration')}</p>
                    """
                    text_message = strip_tags(html_message)

                send_mail(
                    subject,
                    text_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [guardian.email],
                    html_message=html_message,
                    fail_silently=True,
                )
        except Exception as e:
            # Log error but don't fail the entire process
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send email to guardian {guardian.id}: {e}")


# Signal handlers for user management
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create user profile when a new user is created.
    """
    if created:
        from apps.core.models import Institution, InstitutionUser

        # Prefer user's primary institution (if any), then default by code, then any active, then create DEFAULT
        institution = None
        try:
            primary_membership = (
                InstitutionUser.objects.filter(
                    user=instance, is_primary=True, institution__is_active=True
                )
                .select_related("institution")
                .first()
            )
            if primary_membership:
                institution = primary_membership.institution
        except Exception:
            institution = None

        if not institution:
            institution = Institution.objects.filter(
                code="DEFAULT", is_active=True
            ).first()

        if not institution:
            institution = Institution.objects.filter(is_active=True).first()

        if not institution:
            # Do not implicitly create institutions here. Operator should run
            # the bootstrap commands (create.py / setup_multitenancy) to
            # provision DEFAULT. If implicit creation is enabled in settings,
            # create a minimal default; otherwise log and skip profile creation.
            from django.conf import settings
            import logging

            logger = logging.getLogger(__name__)
            if getattr(settings, "ALLOW_IMPLICIT_INSTITUTION_CREATION", False):
                institution = Institution.objects.create(
                    name="Default Institution",
                    code="DEFAULT",
                    short_name="Default",
                    institution_type="high_school",
                    ownership_type="private",
                    is_active=True,
                )
                logger.warning(
                    "Implicitly created DEFAULT institution while creating user profile."
                )
            else:
                logger.error(
                    "No Institution found for new user. Run setup_multitenancy/create.py to bootstrap institutions. Skipping profile creation."
                )
                return

        UserProfile.objects.create(user=instance, institution=institution)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Automatically save user profile when user is saved.
    """
    if hasattr(instance, "profile"):
        instance.profile.save()


@receiver(post_save, sender=UserRole)
def auto_map_user_to_institution(sender, instance, created, **kwargs):
    """
    Automatically map users to institutions when roles are assigned.
    Respects existing institution mappings from applications and prevents conflicts.
    """
    from apps.core.models import Institution, InstitutionUser

    # Only process if this is a staff role that requires institution mapping
    staff_role_types = [
        "super_admin",
        "school_admin",
        "admin",
        "principal",
        "department_head",
        "counselor",
        "teacher",
        "accountant",
        "librarian",
        "activities_coordinator",
        "driver",
        "support",
        "transport_manager",
        "hostel_warden",
    ]

    if instance.role.role_type in staff_role_types:
        # Check if user is already mapped to an institution
        existing_mapping = InstitutionUser.objects.filter(
            user=instance.user, is_primary=True
        ).first()

        if not existing_mapping:
            # First, try to get institution from user's approved application
            preferred_institution = None

            # Check staff application first (most reliable source)
            staff_application = (
                StaffApplication.objects.filter(
                    user_account=instance.user, application_status="approved"
                )
                .order_by("-reviewed_at")
                .first()
            )

            if staff_application and staff_application.institution:
                preferred_institution = staff_application.institution

            # If no preferred institution from applications, check existing mappings
            if not preferred_institution:
                any_existing_mapping = InstitutionUser.objects.filter(
                    user=instance.user
                ).first()
                if any_existing_mapping:
                    preferred_institution = any_existing_mapping.institution

            # If still no institution, use a default active institution
            if not preferred_institution:
                preferred_institution = Institution.objects.filter(
                    is_active=True
                ).first()

            if preferred_institution:
                # Create institution-user mapping with proper error handling
                try:
                    institution_user, inst_created = (
                        InstitutionUser.objects.get_or_create(
                            user=instance.user,
                            institution=preferred_institution,
                            defaults={
                                "is_primary": True,
                                "employee_id": generate_employee_id(
                                    preferred_institution
                                ),
                            },
                        )
                    )

                    if inst_created:
                        # Update user profile with employee ID
                        if hasattr(instance.user, "profile") and instance.user.profile:
                            instance.user.profile.employee_id = (
                                institution_user.employee_id
                            )
                            instance.user.profile.save()

                        logger.info(
                            f"Auto-mapped user {instance.user.email} to institution {preferred_institution.name}"
                        )
                    else:
                        logger.info(
                            f"User {instance.user.email} already mapped to {preferred_institution.name}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to auto-map user {instance.user.email} to institution: {e}"
                    )


@receiver(post_save, sender=UserRole)
def sync_permissions_on_role_save(sender, instance, **kwargs):
    """
    Sync user permissions when a role is assigned or updated.
    """
    try:
        sync_user_permissions(instance.user)
    except Exception as e:
        logger.error(f"Failed to sync permissions for user {instance.user.email}: {e}")


@receiver(post_delete, sender=UserRole)
def sync_permissions_on_role_delete(sender, instance, **kwargs):
    """
    Sync user permissions when a role is removed.
    """
    try:
        sync_user_permissions(instance.user)
    except Exception as e:
        logger.error(f"Failed to sync permissions for user {instance.user.email}: {e}")


@receiver(post_save, sender=UserProfile)
def notify_guardians_on_profile_update(sender, instance, created, **kwargs):
    """
    Notify guardians when a student updates their profile.
    """
    if created:
        # Don't notify on profile creation
        return

    # Check if the user is a student
    if not instance.user.user_roles.filter(
        role__role_type=Role.RoleType.STUDENT
    ).exists():
        return

    # Get the previous profile state from the database
    try:
        previous_profile = UserProfile.objects.get(pk=instance.pk)
    except UserProfile.DoesNotExist:
        return

    # Check if any meaningful fields changed
    meaningful_fields = [
        "date_of_birth",
        "gender",
        "nationality",
        "identification_number",
        "bio",
        "website",
        "facebook",
        "twitter",
        "linkedin",
    ]

    changed_fields = []
    for field in meaningful_fields:
        old_value = getattr(previous_profile, field)
        new_value = getattr(instance, field)
        if old_value != new_value:
            changed_fields.append(field)

    # Also check address fields if they exist
    address_fields = [
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "country",
    ]
    for field in address_fields:
        if hasattr(instance, field):
            old_value = getattr(previous_profile, field)
            new_value = getattr(instance, field)
            if old_value != new_value:
                changed_fields.append(field)

    # If profile picture changed
    if previous_profile.profile_picture != instance.profile_picture:
        changed_fields.append("profile_picture")

    # Only notify if there were actual changes
    if not changed_fields:
        return

    # Get guardians and send notifications
    guardians = get_student_guardians(instance.user)
    if guardians:
        notify_guardians_profile_update(instance.user, guardians, changed_fields)
