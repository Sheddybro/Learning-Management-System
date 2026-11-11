from django.shortcuts import get_object_or_404
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from .middleware import (
    get_current_institution,
    user_can_access_institution,
    get_user_accessible_institutions,
)


def get_institution_object_or_404(
    model,
    user=None,
    require_institution=True,
    institution_field="institution",
    current_institution=None,
    **lookup,
):
    """
    Fetch object with institution scoping.

    Parameters:
    - model: Django model class
    - user: User object (optional, use if available)
    - require_institution: Whether to require institution filtering
    - institution_field: Field name for institution filter (default: 'institution')
    - current_institution: Institution to filter by (overrides auto-detection)
    - **lookup: Field lookups for get_object_or_404

    Behavior:
    - Superusers can access objects from any institution
    - Non-superusers must have institutions configured
    - Raises Http404 if object not found in allowed institutions
    """
    # For superusers, no institution filtering needed
    if user and user.is_superuser:
        return get_object_or_404(model, **lookup)

    # Determine institution to filter by
    if not current_institution:
        current_institution = get_current_institution()

    if require_institution and not current_institution:
        # No institution context available
        if user:
            raise ImproperlyConfigured(
                f"No current institution for non-superuser {user.email}"
            )
        else:
            raise ImproperlyConfigured("No current institution available")

    # Add institution filter to lookups
    lookup_with_inst = dict(lookup)
    if current_institution:
        lookup_with_inst[institution_field] = current_institution

    return get_object_or_404(model, **lookup_with_inst)


def get_multi_institution_object_or_404(
    model, user, institution_field="institution", **lookup
):
    """
    Fetch object from any of the user's accessible institutions.

    Parameters:
    - model: Django model class
    - user: User object (required)
    - institution_field: Field name for institution filter
    - **lookup: Field lookups for get_object_or_404

    Returns: First matching object from user's accessible institutions
    Raises: Http404 if no object found in accessible institutions
    """
    if user.is_superuser:
        return get_object_or_404(model, **lookup)

    # Get all institutions user can access
    accessible_institutions = get_user_accessible_institutions(user)

    if not accessible_institutions.exists():
        raise Http404("User has no accessible institutions")

    # Add institution filter
    lookup_with_inst = dict(lookup)
    lookup_with_inst[f"{institution_field}__in"] = accessible_institutions

    return get_object_or_404(model, **lookup_with_inst)


def ensure_institution_access(obj, user, institution_field="institution"):
    """
    Verify user can access an institution-scoped object.

    Parameters:
    - obj: Object with institution FK
    - user: User object
    - institution_field: Name of institution field on obj

    Returns: True if access allowed
    Raises: Http404 if access denied
    """
    if user.is_superuser:
        return True

    institution = getattr(obj, institution_field, None)
    if not institution:
        raise Http404("Object has no institution assigned")

    if not user_can_access_institution(user, institution):
        raise Http404("Access to this object is not permitted")

    return True
