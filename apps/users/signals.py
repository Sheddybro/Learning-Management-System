from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserRole, Role
from apps.audit.models import AuditLog

User = get_user_model()


@receiver(post_save, sender=UserRole)
def audit_user_role_changes(sender, instance, created, **kwargs):
    """Audit log for user role assignments and changes."""
    action = "create" if created else "update"
    user = instance.user
    role = instance.role

    # Get the user performing the action (if available from request context)
    # This is a simplified version - in production, you'd want to track the admin user
    performing_user = getattr(instance, "_audit_user", None)

    # Handle case where academic session may have issues
    academic_session_id = None
    try:
        academic_session_id = (
            str(instance.academic_session.id) if instance.academic_session else None
        )
    except:
        # Session may have issues, use cached/original value if available
        academic_session_id = getattr(instance, "_original_academic_session_id", None)

    details = {
        "user_id": str(user.id),
        "user_email": user.email,
        "user_display_name": user.display_name,
        "role_id": str(role.id),
        "role_name": role.name,
        "role_type": role.role_type,
        "is_primary": instance.is_primary,
        "academic_session": academic_session_id,
    }

    if not created:
        # For updates, include what changed
        if (
            hasattr(instance, "_original_is_primary")
            and instance._original_is_primary != instance.is_primary
        ):
            details["primary_role_changed"] = {
                "from": instance._original_is_primary,
                "to": instance.is_primary,
            }

    AuditLog.objects.create(
        user=performing_user,
        action=action,
        model_name="UserRole",
        object_id=str(instance.id),
        details=details,
        ip_address=getattr(instance, "_audit_ip", None),
        user_agent=getattr(instance, "_audit_user_agent", None),
        institution=instance.institution,
    )


@receiver(post_delete, sender=UserRole)
def audit_user_role_deletion(sender, instance, **kwargs):
    """Audit log for user role removals."""
    user = instance.user
    role = instance.role

    # Get the user performing the action
    performing_user = getattr(instance, "_audit_user", None)

    # Handle case where academic session may have been deleted
    academic_session_id = None
    try:
        academic_session_id = (
            str(instance.academic_session.id) if instance.academic_session else None
        )
    except:
        # Session may have been deleted, use cached/original value if available
        academic_session_id = getattr(instance, "_original_academic_session_id", None)

    details = {
        "user_id": str(user.id),
        "user_email": user.email,
        "user_display_name": user.display_name,
        "role_id": str(role.id),
        "role_name": role.name,
        "role_type": role.role_type,
        "was_primary": instance.is_primary,
        "academic_session": academic_session_id,
    }

    AuditLog.objects.create(
        user=performing_user,
        action="delete",
        model_name="UserRole",
        object_id=str(instance.id),
        details=details,
        ip_address=getattr(instance, "_audit_ip", None),
        user_agent=getattr(instance, "_audit_user_agent", None),
        institution=instance.institution,
    )


@receiver(post_save, sender=Role)
def audit_role_changes(sender, instance, created, **kwargs):
    """Audit log for role definition changes."""
    action = "create" if created else "update"

    performing_user = getattr(instance, "_audit_user", None)

    details = {
        "role_id": str(instance.id),
        "role_name": instance.name,
        "role_type": instance.role_type,
        "hierarchy_level": instance.hierarchy_level,
        "is_system_role": instance.is_system_role,
        "status": instance.status,
    }

    if not created:
        # Track specific changes for updates
        changes = {}
        if (
            hasattr(instance, "_original_name")
            and instance._original_name != instance.name
        ):
            changes["name"] = {"from": instance._original_name, "to": instance.name}
        if (
            hasattr(instance, "_original_role_type")
            and instance._original_role_type != instance.role_type
        ):
            changes["role_type"] = {
                "from": instance._original_role_type,
                "to": instance.role_type,
            }
        if (
            hasattr(instance, "_original_hierarchy_level")
            and instance._original_hierarchy_level != instance.hierarchy_level
        ):
            changes["hierarchy_level"] = {
                "from": instance._original_hierarchy_level,
                "to": instance.hierarchy_level,
            }
        if (
            hasattr(instance, "_original_status")
            and instance._original_status != instance.status
        ):
            changes["status"] = {
                "from": instance._original_status,
                "to": instance.status,
            }

        if changes:
            details["changes"] = changes

    AuditLog.objects.create(
        user=performing_user,
        action=action,
        model_name="Role",
        object_id=str(instance.id),
        details=details,
        ip_address=getattr(instance, "_audit_ip", None),
        user_agent=getattr(instance, "_audit_user_agent", None),
        institution=instance.institution,
    )


@receiver(post_delete, sender=Role)
def audit_role_deletion(sender, instance, **kwargs):
    """Audit log for role deletions."""
    performing_user = getattr(instance, "_audit_user", None)

    details = {
        "role_id": str(instance.id),
        "role_name": instance.name,
        "role_type": instance.role_type,
        "hierarchy_level": instance.hierarchy_level,
        "is_system_role": instance.is_system_role,
        "was_active": instance.status == "active",
    }

    AuditLog.objects.create(
        user=performing_user,
        action="delete",
        model_name="Role",
        object_id=str(instance.id),
        details=details,
        ip_address=getattr(instance, "_audit_ip", None),
        user_agent=getattr(instance, "_audit_user_agent", None),
        institution=instance.institution,
    )
