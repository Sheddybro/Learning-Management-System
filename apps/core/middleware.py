import threading
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from .models import Institution


# Thread-local storage for current institution
_local = threading.local()


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware to handle multi-tenancy by identifying the current institution
    from request context (subdomain, session, or user profile).
    """

    def process_request(self, request):
        """
        Set the current institution for this request.
        Priority order:
        1. Subdomain (e.g., school1.domain.com)
        2. Session institution
        3. User's primary institution
        4. Default institution (if configured)
        """
        institution = None

        # Check subdomain
        institution = self._get_institution_from_subdomain(request)

        # If no subdomain match, check session
        if not institution:
            institution = self._get_institution_from_session(request)

        # If still no match, check user profile
        if not institution and request.user.is_authenticated:
            institution = self._get_institution_from_user(request.user)

        # Set the current institution in thread-local storage
        if institution:
            _local.current_institution = institution
            # Also store in request for convenience
            request.institution = institution
            # Store in session for persistence across requests
            request.session["current_institution_id"] = str(institution.id)
            request.session.modified = True
        else:
            # No institution found - store None
            _local.current_institution = None
            request.institution = None
            # Clear session institution if it exists
            if "current_institution_id" in request.session:
                del request.session["current_institution_id"]

        return None

    def process_response(self, request, response):
        """
        Clean up thread-local storage after request processing.
        """
        if hasattr(_local, "current_institution"):
            del _local.current_institution
        return response

    def _get_institution_from_subdomain(self, request):
        """
        Extract institution from subdomain.
        Expected format: institution-code.domain.com
        """
        host = request.get_host().lower()
        domain = getattr(settings, "TENANT_DOMAIN", "localhost")

        # Remove port if present
        if ":" in host:
            host = host.split(":")[0]

        # Check if host ends with our domain
        if host.endswith(domain):
            subdomain = host.replace(f".{domain}", "").replace(domain, "")

            if subdomain and subdomain != "www":
                try:
                    return Institution.objects.get(
                        code__iexact=subdomain, is_active=True
                    )
                except Institution.DoesNotExist:
                    pass

        return None

    def _get_institution_from_session(self, request):
        """
        Get institution from session if stored.
        """
        institution_id = request.session.get("current_institution_id")
        if institution_id:
            try:
                return Institution.objects.get(id=institution_id, is_active=True)
            except Institution.DoesNotExist:
                # Clean up invalid session data
                if "current_institution_id" in request.session:
                    del request.session["current_institution_id"]

        return None

    def _get_institution_from_user(self, user):
        """
        Get institution from user's primary institution via InstitutionUser relationship.
        """
        from .models import InstitutionUser

        # Check if user is superuser (can access all institutions)
        if user.is_superuser:
            # For superuser, return their primary institution or None to allow access to all
            pass

        # Try to find the user's primary institution through InstitutionUser
        try:
            primary_membership = (
                InstitutionUser.objects.filter(
                    user=user, is_primary=True, institution__is_active=True
                )
                .select_related("institution")
                .first()
            )

            if primary_membership:
                return primary_membership.institution
        except:
            pass

        # If no primary found, get the first active institution the user belongs to
        try:
            membership = (
                InstitutionUser.objects.filter(user=user, institution__is_active=True)
                .select_related("institution")
                .first()
            )

            if membership:
                return membership.institution
        except:
            pass

        return None


def get_current_institution():
    """
    Get the current institution from thread-local storage.
    Returns None if no institution is set.
    """
    return getattr(_local, "current_institution", None)


def set_current_institution(institution):
    """
    Manually set the current institution in thread-local storage.
    Use with caution - typically handled by middleware.
    """
    _local.current_institution = institution


def user_can_access_institution(user, institution):
    """
    Check if a user can access a specific institution.
    Returns True if:
    - User is superuser (platform admin)
    - User belongs to the institution via InstitutionUser
    """
    # Superuser can access all institutions
    if user.is_superuser:
        return True

    # Check if user belongs to this institution
    from .models import InstitutionUser

    try:
        return InstitutionUser.objects.filter(
            user=user, institution=institution, institution__is_active=True
        ).exists()
    except:
        return False


def filter_queryset_by_institution(queryset, user, institution_field="institution"):
    """
    Filter a queryset by institution access permissions.
    Superusers can access all institutions.
    Admin/principal users can access their primary institution.
    Regular users can access institutions they belong to.
    """
    # Superusers can access all institutions
    if user.is_superuser:
        return queryset

    # Get accessible institutions for this user
    accessible_institutions = get_user_accessible_institutions(user)

    if accessible_institutions:
        accessible_ids = list(accessible_institutions.values_list("id", flat=True))
        filter_kwargs = {f"{institution_field}__in": accessible_ids}
        return queryset.filter(**filter_kwargs)
    else:
        # No accessible institutions, return empty queryset
        return queryset.none()


def get_user_accessible_institutions(user):
    """
    Get all institutions a user can access.
    Superusers and super_admins get all institutions.
    Admin/principal users get only their primary institution.
    Regular users get institutions they belong to.
    """
    # Django superusers can access all institutions
    if user.is_superuser:
        return Institution.objects.filter(is_active=True)

    # Super admins (custom role) should also access all institutions
    if user.user_roles.filter(
        role__role_type__in=["super_admin"], status="active"
    ).exists():
        return Institution.objects.filter(is_active=True)

    # Check if user has admin, principal, or school_admin role
    if user.user_roles.filter(
        role__role_type__in=["admin", "principal", "school_admin"], status="active"
    ).exists():
        # Admin/principal users only get their primary institution
        from .models import InstitutionUser

        primary_membership = (
            InstitutionUser.objects.filter(
                user=user, is_primary=True, institution__is_active=True
            )
            .select_related("institution")
            .first()
        )
        if primary_membership:
            return Institution.objects.filter(id=primary_membership.institution.id)
        else:
            # Fallback to first institution if no primary set
            first_membership = (
                InstitutionUser.objects.filter(user=user, institution__is_active=True)
                .select_related("institution")
                .first()
            )
            if first_membership:
                return Institution.objects.filter(id=first_membership.institution.id)
        return Institution.objects.none()

    # Regular users get all institutions they belong to
    from .models import InstitutionUser

    accessible_institution_ids = InstitutionUser.objects.filter(
        user=user, institution__is_active=True
    ).values_list("institution_id", flat=True)

    return Institution.objects.filter(id__in=accessible_institution_ids, is_active=True)
