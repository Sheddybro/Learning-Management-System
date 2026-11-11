from django import template

register = template.Library()


@register.filter
def has_role(user, role_type):
    """
    Check if a user has a specific role.

    Args:
        user: User instance
        role_type: String - 'student' or 'coordinator'

    Returns:
        Boolean indicating if user has the specified role
    """
    if not user or not user.is_authenticated:
        return False

    if role_type == "student":
        # Check if user has an active student role
        # Prefer permission check where available, fallback to role membership
        if user.has_perm("academics.view_enrollment") or user.has_perm(
            "academics.view_student"
        ):
            return True
        return user.user_roles.filter(
            role__role_type="student", status="active"
        ).exists()

    elif role_type == "coordinator":
        # Check if user coordinates any activities
        from apps.activities.models import Activity

        return Activity.objects.filter(coordinator=user).exists()

    return False
