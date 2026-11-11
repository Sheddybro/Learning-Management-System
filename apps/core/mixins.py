from django.contrib.auth.mixins import (
    AccessMixin,
    UserPassesTestMixin,
    LoginRequiredMixin,
)
from django.http import Http404
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db import models
from .middleware import (
    get_current_institution,
    user_can_access_institution,
    filter_queryset_by_institution,
    get_user_accessible_institutions,
)


class InstitutionAccessMixin(AccessMixin):
    """
    Mixin to ensure user has access to the current institution.
    Should be used with views that operate within institution context.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Allow admin and principal users to bypass institution selection
        user = request.user
        if (
            user.user_roles.filter(
                role__role_type__in=[
                    "admin",
                    "principal",
                    "super_admin",
                    "school_admin",
                ],
                status="active",
            ).exists()
            or user.is_superuser
        ):
            return super().dispatch(request, *args, **kwargs)

        institution = get_current_institution()

        if not institution:
            # No institution context - redirect to institution selection
            messages.warning(request, _("Please select an institution to continue."))
            return redirect("core:institution_select")

        # Check if user can access this institution
        if not user_can_access_institution(request.user, institution):
            messages.error(
                request, _("You don't have permission to access this institution.")
            )
            return redirect("users:dashboard")

        return super().dispatch(request, *args, **kwargs)


class InstitutionPermissionMixin(InstitutionAccessMixin):
    """
    Mixin that filters querysets by institution and ensures user permissions.
    Use for views that list or manipulate institution-specific data.
    """

    def get_queryset(self):
        """
        Filter queryset to only show records from institutions the user can access.
        """
        queryset = super().get_queryset()
        return filter_queryset_by_institution(queryset, self.request.user)

    def form_valid(self, form):
        """
        Ensure the form instance is saved with the current institution.
        Assumes the model has an 'institution' field.
        Falls back to user's primary institution for admin users if no current institution.
        """
        institution = get_current_institution()

        # If no current institution, try to get user's primary institution for admin users
        if not institution:
            user = self.request.user
            if (
                user.is_superuser
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
                            user=user, is_primary=True, institution__is_active=True
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

        if not institution:
            user = self.request.user
            if user.user_roles.filter(
                role__role_type__in=[
                    "admin",
                    "principal",
                    "super_admin",
                    "school_admin",
                ],
                status="active",
            ).exists():
                # Admin user doesn't have institution assignment - this needs to be set up
                from django.core.exceptions import ValidationError

                raise ValidationError(
                    _(
                        "Your account is not properly configured with an institution assignment. "
                        "Please contact a system administrator to set up your institution access."
                    )
                )
            else:
                # Regular user without institution
                from django.core.exceptions import ValidationError

                raise ValidationError(
                    _(
                        "Unable to determine institution for this record. Please contact an administrator."
                    )
                )

        form.instance.institution = institution
        return super().form_valid(form)


class InstitutionAdminMixin(InstitutionAccessMixin):
    """
    Mixin for views that require institution admin privileges.
    """

    def dispatch(self, request, *args, **kwargs):
        # First check institution access
        result = super().dispatch(request, *args, **kwargs)
        if not isinstance(result, type(None)):
            return result  # Permission denied or redirect

        # Check if user has admin role in current institution
        institution = get_current_institution()
        user_roles = request.user.user_roles.filter(
            role__hierarchy_level__gte=70,  # Principal level and above
            academic_session__is_current=True,
        )

        if not user_roles.exists():
            messages.error(
                request, _("You need institution admin privileges to access this page.")
            )
            return redirect("users:dashboard")

        return super().dispatch(request, *args, **kwargs)


class SuperAdminMixin(AccessMixin):
    """
    Mixin for views that require super admin (platform-level) privileges.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if not request.user.is_superuser:
            messages.error(
                request,
                _("You need super administrator privileges to access this page."),
            )
            return redirect("users:dashboard")

        return super().dispatch(request, *args, **kwargs)


class InstitutionFormMixin:
    """
    Mixin for forms that need institution field handling.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = kwargs.pop("user", None)

        # If user is not super admin, limit institution choices
        if self.user and not self.user.is_superuser:
            from .models import InstitutionUser

            accessible_institutions = InstitutionUser.objects.filter(
                user=self.user, institution__is_active=True
            ).values_list("institution", flat=True)

            if "institution" in self.fields:
                self.fields["institution"].queryset = self.fields[
                    "institution"
                ].queryset.filter(id__in=accessible_institutions)

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Set institution for new instances if not set
        if not getattr(instance, "institution", None):
            if self.user and self.user.is_superuser:
                # Super admin can have instances without institution (for global config)
                pass
            else:
                # Set to current institution for regular users
                current_institution = get_current_institution()
                if current_institution:
                    instance.institution = current_institution

        if commit:
            instance.save()
        return instance


class MultiInstitutionMixin:
    """
    Mixin for views that need to handle multiple institutions (e.g., super admin dashboard).
    Adds context data for institution switching.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        # Add accessible institutions
        context["accessible_institutions"] = get_user_accessible_institutions(user)
        context["current_institution"] = get_current_institution()

        # Add institution switcher flag
        context["can_switch_institutions"] = (
            user.is_superuser or context["accessible_institutions"].count() > 1
        )

        return context


def institution_required(view_func):
    """
    Decorator to ensure user has access to current institution.
    Usage: @institution_required
    def my_view(request):
        pass
    """

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())

        institution = get_current_institution()
        if not institution:
            messages.warning(request, _("Please select an institution to continue."))
            return redirect("core:institution_select")

        if not user_can_access_institution(request.user, institution):
            messages.error(
                request, _("You don't have permission to access this institution.")
            )
            return redirect("users:dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


def institution_admin_required(view_func):
    """
    Decorator to ensure user has institution admin privileges.
    """

    def wrapper(request, *args, **kwargs):
        # First check institution access
        result = institution_required(lambda r: None)(request, *args, **kwargs)
        if result:
            return result

        # Check admin role
        institution = get_current_institution()
        user_roles = request.user.user_roles.filter(
            role__hierarchy_level__gte=70, academic_session__is_current=True
        )

        if not user_roles.exists():
            messages.error(
                request, _("You need institution admin privileges to access this page.")
            )
            return redirect("users:dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


def super_admin_required(view_func):
    """
    Decorator to ensure user has super admin privileges.
    """

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())

        if not request.user.is_superuser:
            messages.error(
                request,
                _("You need super administrator privileges to access this page."),
            )
            return redirect("users:dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


# =============================================================================
# ROLE-BASED PERMISSION MIXINS
# =============================================================================
# These mixins are consolidated from various apps to eliminate duplication
# and ensure consistent permission checking across the entire system.


class StudentRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is a student.
    Consolidated from: academics, assessment, attendance, health
    """

    def test_func(self):
        return hasattr(self.request.user, "student_profile")


class TeacherRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is a teacher, staff, or admin.
    Consolidated from: academics, assessment, attendance
    """

    def test_func(self):
        user = self.request.user

        # Allow Django superusers
        if user.is_superuser:
            return True

        if hasattr(user, "teacher_profile") or user.is_staff:
            return True

        # Check if user has admin, principal, or super_admin role
        user_roles = user.user_roles.all()
        admin_roles = ["admin", "principal", "super_admin", "school_admin"]
        return any(role.role.role_type in admin_roles for role in user_roles)


class ParentRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is a parent.
    Consolidated from: users
    """

    def test_func(self):
        user_roles = self.request.user.user_roles.all()
        return any(role.role.role_type == "parent" for role in user_roles)


class StaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is staff.
    Consolidated from: academics
    """

    def test_func(self):
        return self.request.user.is_staff


class AdminRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user has admin, principal, or super_admin role, or is a Django superuser.
    Consolidated from: academics
    """

    def test_func(self):
        user = self.request.user

        # Allow Django superusers
        if user.is_superuser:
            return True

        # Check if user has admin, principal, super_admin, or school_admin role
        user_roles = user.user_roles.all()
        admin_roles = ["admin", "principal", "super_admin", "school_admin"]
        return any(role.role.role_type in admin_roles for role in user_roles)


class AdminOrTeacherRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user has admin, principal, super_admin, school_admin role, or is a teacher.
    Consolidated from: assessment
    """

    def test_func(self):
        user = self.request.user

        # Allow Django superusers
        if user.is_superuser:
            return True

        # Check if user has admin, principal, super_admin, school_admin role or is a teacher
        user_roles = user.user_roles.all()
        allowed_roles = ["admin", "principal", "super_admin", "school_admin", "teacher"]
        return any(role.role.role_type in allowed_roles for role in user_roles)


class SupportStaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is support staff.
    Consolidated from: support
    """

    def test_func(self):
        user = self.request.user
        if user.is_staff:
            return True

        # Check if user has support staff role
        user_roles = user.user_roles.all()
        support_roles = ["support", "admin", "principal", "super_admin"]
        return any(role.role.role_type in support_roles for role in user_roles)


class TransportManagerRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is a transport manager, staff, or admin.
    Consolidated from: transport
    """

    def test_func(self):
        user = self.request.user

        # Allow Django superusers and staff
        if user.is_superuser or user.is_staff:
            return True

        # Check if user has transport manager or admin role
        user_roles = user.user_roles.all()
        transport_roles = ["transport_manager", "admin", "principal", "super_admin"]
        return any(role.role.role_type in transport_roles for role in user_roles)


class LibrarianRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is a librarian, staff, or admin.
    Consolidated from: library
    """

    def test_func(self):
        user = self.request.user

        # Allow Django superusers and staff
        if user.is_superuser or user.is_staff:
            return True

        # Check if user has librarian or admin role
        user_roles = user.user_roles.all()
        library_roles = ["librarian", "admin", "principal", "super_admin"]
        return any(role.role.role_type in library_roles for role in user_roles)


class HostelWardenRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is a hostel warden, staff, or admin.
    Consolidated from: hostels
    """

    def test_func(self):
        user = self.request.user

        # Allow Django superusers and staff
        if user.is_superuser or user.is_staff:
            return True

        # Check if user has hostel warden or admin role
        user_roles = user.user_roles.all()
        hostel_roles = ["hostel_warden", "admin", "principal", "super_admin"]
        return any(role.role.role_type in hostel_roles for role in user_roles)


class FinanceAccessMixin(LoginRequiredMixin):
    """
    Mixin for finance app access control.
    Consolidated from: finance
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Allow Django superusers
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        # Check if user has finance-related role
        user_roles = request.user.user_roles.all()
        finance_roles = ["accountant", "admin", "principal", "super_admin"]

        if not any(role.role.role_type in finance_roles for role in user_roles):
            messages.error(
                request, _("You don't have permission to access finance resources.")
            )
            return redirect("users:dashboard")

        return super().dispatch(request, *args, **kwargs)


class AccountantRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is an accountant, staff, or admin.
    Consolidated from: finance
    """

    def test_func(self):
        user = self.request.user

        # Allow Django superusers and staff
        if user.is_superuser or user.is_staff:
            return True

        # Check if user has accountant or admin role
        user_roles = user.user_roles.all()
        finance_roles = ["accountant", "admin", "principal", "super_admin"]
        return any(role.role.role_type in finance_roles for role in user_roles)


class CommunicationStaffRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is staff or admin for communication management.
    Consolidated from: communication
    """

    def test_func(self):
        user = self.request.user

        # Allow Django superusers and staff
        if user.is_superuser or user.is_staff:
            return True

        # Check if user has communication staff or admin role
        user_roles = user.user_roles.all()
        comm_roles = ["communication_staff", "admin", "principal", "super_admin"]
        return any(role.role.role_type in comm_roles for role in user_roles)


class CounselorRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is a counselor.
    Consolidated from: academics
    """

    def test_func(self):
        user = self.request.user
        if hasattr(user, "teacher_profile"):
            return user.teacher_profile.is_counselor
        return False


class CommitteeRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is a committee member.
    Consolidated from: academics
    """

    def test_func(self):
        user = self.request.user
        # Check if user is a committee member
        return AcademicPlanningCommittee.objects.filter(
            models.Q(chairperson=user.teacher_profile)
            | models.Q(members=user.teacher_profile),
            is_active=True,
        ).exists()


class AcademicsAccessMixin(LoginRequiredMixin):
    """
    Mixin to ensure user has access to academic resources.
    Allows teachers, students, parents, and staff/admin users.
    Consolidated from: academics
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        user = request.user

        # Allow Django superusers and staff
        if user.is_superuser or user.is_staff:
            return super().dispatch(request, *args, **kwargs)

        # Check if user has academic-related roles
        user_roles = user.user_roles.all()
        academic_roles = [
            "teacher",
            "student",
            "parent",
            "admin",
            "principal",
            "super_admin",
            "department_head",
            "counselor",
            "librarian",
        ]

        has_academic_role = any(
            role.role.role_type in academic_roles for role in user_roles
        )

        # Also check for teacher/student/parent profiles
        has_academic_profile = (
            hasattr(user, "teacher_profile")
            or hasattr(user, "student_profile")
            or user_roles.filter(role__role_type="parent").exists()
        )

        if not (has_academic_role or has_academic_profile):
            messages.error(
                request, _("You don't have permission to access academic resources.")
            )
            return redirect("users:dashboard")

        return super().dispatch(request, *args, **kwargs)


class DepartmentHeadRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure user is a department head.
    Consolidated from: academics
    """

    def test_func(self):
        user = self.request.user
        if hasattr(user, "teacher_profile"):
            return user.teacher_profile.is_department_head
        return False
