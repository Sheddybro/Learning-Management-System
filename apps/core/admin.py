# apps/core/admin.py

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import PermissionDenied
from .models import Institution, SystemConfig, SequenceGenerator
from .middleware import (
    get_current_institution,
    filter_queryset_by_institution,
    get_user_accessible_institutions,
)


class InstitutionModelAdmin(admin.ModelAdmin):
    """
    Base admin class that filters querysets by institution access permissions.
    All institution-specific models should inherit from this instead of admin.ModelAdmin.
    """

    def get_queryset(self, request):
        """
        Filter queryset to only show records from institutions the user can access.
        """
        queryset = super().get_queryset(request)

        # Check if this model has an institution field
        if hasattr(self.model, "institution"):
            return filter_queryset_by_institution(queryset, request.user)
        else:
            # For models without institution field, return as-is
            return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Limit institution choices in foreign key fields based on user permissions.
        """
        if db_field.name == "institution":
            # If user is superuser, show all institutions
            if request.user.is_superuser:
                return super().formfield_for_foreignkey(db_field, request, **kwargs)

            # Otherwise, limit to user's accessible institutions
            accessible_institutions = get_user_accessible_institutions(request.user)
            kwargs["queryset"] = accessible_institutions

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        Set institution for new objects if not already set.
        Falls back to user's primary institution for admin users if no current institution.
        """
        # Check if this model has an institution field
        if hasattr(obj, "institution") and hasattr(obj, "institution_id"):
            # For new objects (not change), set institution if not set
            if not change and not obj.institution_id:
                institution = get_current_institution()

                # If no current institution, try to get user's primary institution for admin users
                if not institution:
                    user = request.user
                    if (
                        user.is_superuser
                        or user.has_perm("core.change_institution")
                        or user.user_roles.filter(
                            role__role_type__in=[
                                "admin",
                                "principal",
                                "super_admin",
                                "school_admin",
                            ],
                            status="active",
                        ).exists()
                    ):
                        # Try to get primary institution from InstitutionUser
                        from .models import InstitutionUser

                        try:
                            primary_membership = (
                                InstitutionUser.objects.filter(
                                    user=user,
                                    is_primary=True,
                                    institution__is_active=True,
                                )
                                .select_related("institution")
                                .first()
                            )

                            if primary_membership:
                                institution = primary_membership.institution
                            else:
                                # Fallback to any institution the user belongs to
                                membership = (
                                    InstitutionUser.objects.filter(
                                        user=user, institution__is_active=True
                                    )
                                    .select_related("institution")
                                    .first()
                                )
                                if membership:
                                    institution = membership.institution
                        except:
                            pass  # Fall through to error

                if institution:
                    obj.institution = institution
                elif not request.user.is_superuser:
                    # Non-superuser must have an institution
                    raise PermissionDenied(
                        "Unable to determine institution for this record. Please contact an administrator."
                    )

        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):
        """Check view permission with institution access."""
        if not super().has_view_permission(request, obj):
            return False

        # Additional check for institution access
        if obj and hasattr(obj, "institution"):
            return self._user_can_access_institution(request.user, obj.institution)

        return True

    def has_change_permission(self, request, obj=None):
        """Check change permission with institution access."""
        if not super().has_change_permission(request, obj):
            return False

        # Additional check for institution access
        if obj and hasattr(obj, "institution"):
            return self._user_can_access_institution(request.user, obj.institution)

        return True

    def has_delete_permission(self, request, obj=None):
        """Check delete permission with institution access."""
        if not super().has_delete_permission(request, obj):
            return False

        # Additional check for institution access
        if obj and hasattr(obj, "institution"):
            return self._user_can_access_institution(request.user, obj.institution)

        return True

    def _user_can_access_institution(self, user, institution):
        """
        Check if user can access a specific institution.
        """
        # Superusers can access all institutions
        if user.is_superuser:
            return True

        # Check if user belongs to this institution
        return institution in get_user_accessible_institutions(user)


class InstitutionAdmin(admin.ModelAdmin):
    """
    Admin interface for Institution model.
    """

    list_display = (
        "name",
        "code",
        "institution_type",
        "ownership_type",
        "is_active",
        "status",
    )
    list_filter = (
        "institution_type",
        "ownership_type",
        "is_active",
        "status",
        "created_at",
    )
    search_fields = ("name", "code", "short_name")
    readonly_fields = ("created_at", "updated_at", "api_key")
    ordering = ("name",)

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "code", "short_name", "description")},
        ),
        (
            _("Institution Details"),
            {"fields": ("institution_type", "ownership_type", "established_date")},
        ),
        (
            _("Capacity & Settings"),
            {"fields": ("max_students", "max_staff", "timezone", "is_active")},
        ),
        (
            _("Contact Information"),
            {
                "fields": (
                    "phone",
                    "mobile",
                    "email",
                    "website",
                    "emergency_contact",
                    "emergency_phone",
                )
            },
        ),
        (
            _("Address"),
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Information"),
            {"fields": ("api_key", "database_schema"), "classes": ("collapse",)},
        ),
        (
            _("Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Auto-generate API key for new institutions."""
        if not change:
            # This will be handled by the model's save method
            pass
        super().save_model(request, obj, form, change)

    def has_view_permission(self, request, obj=None):
        """Deny access to school_admin users."""
        if self._user_has_school_admin_role(request.user):
            return False
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        """Deny access to school_admin users."""
        if self._user_has_school_admin_role(request.user):
            return False
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """Deny access to school_admin users."""
        if self._user_has_school_admin_role(request.user):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Deny access to school_admin users."""
        if self._user_has_school_admin_role(request.user):
            return False
        return super().has_delete_permission(request, obj)

    def _user_has_school_admin_role(self, user):
        """Check if user has school_admin role."""
        if not user.is_authenticated:
            return False
        return (
            user.has_perm("core.change_institution")
            or user.user_roles.filter(
                role__role_type="school_admin", status="active"
            ).exists()
        )


@admin.register(SystemConfig)
class SystemConfigAdmin(InstitutionModelAdmin):
    """
    Admin interface for SystemConfig model.
    """

    list_display = ("key", "config_type", "is_public", "is_encrypted", "status")
    list_filter = ("config_type", "is_public", "is_encrypted", "status", "created_at")
    search_fields = ("key", "description")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            _("Configuration Details"),
            {"fields": ("key", "value", "config_type", "description")},
        ),
        (
            _("Security & Visibility"),
            {"fields": ("is_public", "is_encrypted"), "classes": ("collapse",)},
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
        """Make key read-only for existing objects."""
        if obj:
            return self.readonly_fields + ("key", "config_type")
        return self.readonly_fields

    def has_view_permission(self, request, obj=None):
        """Deny access to school_admin users."""
        if self._user_has_school_admin_role(request.user):
            return False
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        """Deny access to school_admin users."""
        if self._user_has_school_admin_role(request.user):
            return False
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """Deny access to school_admin users."""
        if self._user_has_school_admin_role(request.user):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Deny access to school_admin users."""
        if self._user_has_school_admin_role(request.user):
            return False
        return super().has_delete_permission(request, obj)

    def _user_has_school_admin_role(self, user):
        """Check if user has school_admin role."""
        if not user.is_authenticated:
            return False
        return (
            user.has_perm("core.change_institution")
            or user.user_roles.filter(
                role__role_type="school_admin", status="active"
            ).exists()
        )


@admin.register(SequenceGenerator)
class SequenceGeneratorAdmin(InstitutionModelAdmin):
    """
    Admin interface for SequenceGenerator model.
    """

    list_display = (
        "sequence_type",
        "prefix",
        "suffix",
        "last_number",
        "padding",
        "reset_frequency",
        "status",
    )
    list_filter = ("reset_frequency", "status")
    search_fields = ("sequence_type",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (_("Institution"), {"fields": ("institution",)}),
        (
            _("Sequence Configuration"),
            {
                "fields": (
                    "sequence_type",
                    "prefix",
                    "suffix",
                    "padding",
                    "reset_frequency",
                )
            },
        ),
        (_("Current State"), {"fields": ("last_number",), "classes": ("collapse",)}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make sequence_type read-only for existing objects."""
        if obj:
            return self.readonly_fields + ("sequence_type",)
        return self.readonly_fields


# Register Permission model if not already registered
if not admin.site.is_registered(Permission):

    @admin.register(Permission)
    class PermissionAdmin(admin.ModelAdmin):
        """
        Admin interface for Django Permission model.
        """

        list_display = ("name", "content_type", "codename")
        list_filter = ("content_type",)
        search_fields = ("name", "codename")

        def has_add_permission(self, request):
            """Prevent manual creation of permissions."""
            return False

        def has_change_permission(self, request, obj=None):
            """Prevent modification of permissions."""
            return False

        def has_delete_permission(self, request, obj=None):
            """Prevent deletion of permissions."""
            return False


class CoreAdminSite(admin.AdminSite):
    """
    Custom admin site for Core app.
    """

    site_header = _("Core Administration")
    site_title = _("Core Admin")
    index_title = _("Core Management")


# Register Institution with main admin site
admin.site.register(Institution, InstitutionAdmin)

# Create instance of custom admin site
core_admin_site = CoreAdminSite(name="core_admin")

# Register models with custom admin site
core_admin_site.register(Institution, InstitutionAdmin)
core_admin_site.register(SystemConfig, SystemConfigAdmin)
core_admin_site.register(SequenceGenerator, SequenceGeneratorAdmin)
core_admin_site.register(Permission, PermissionAdmin)
