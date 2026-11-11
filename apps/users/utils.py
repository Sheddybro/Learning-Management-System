from typing import Iterable, Optional


def has_role_or_perm(
    user,
    perm: Optional[str] = None,
    role_type: Optional[str] = None,
    role_types: Optional[Iterable[str]] = None,
):
    """Return True if user has `perm` or belongs to `role_type`/`role_types`.

    Prefers permission check first, then falls back to role membership.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if perm and user.has_perm(perm):
        return True

    qs = user.user_roles
    if role_type:
        return qs.filter(role__role_type=role_type).exists()
    if role_types:
        return qs.filter(role__role_type__in=list(role_types)).exists()

    return False
