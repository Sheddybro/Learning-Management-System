# apps/users/views.py

import logging
import secrets
import string
import datetime
from datetime import date, time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView
from django.db import transaction
from django.db.models import Q, Sum
from django.core.mail import send_mail, get_connection, EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import smtplib
import ssl
from django.http import JsonResponse, HttpResponse
import csv
import openpyxl
from io import BytesIO


from apps.audit.models import AuditLog
from apps.core.middleware import get_current_institution
from apps.academics.models import (
    AcademicSession,
    AcademicRecord,
    BehaviorRecord,
    Class,
    ClassMaterial,
    Enrollment,
    Student,
    Subject,
    SubjectAssignment,
    Teacher,
    Timetable,
)
from apps.users.utils import has_role_or_perm

from .models import (
    User,
    UserProfile,
    Role,
    UserRole,
    LoginHistory,
    PasswordHistory,
    UserSession,
    ParentStudentRelationship,
    StudentApplication,
    StaffApplication,
    ApplicationStatus,
    UserRoleActivity,
    InstitutionTransferRequest,
    get_student_guardians,
    notify_guardians_profile_update,
)
from .forms import (
    UserCreationForm,
    UserUpdateForm,
    UserProfileForm,
    RoleForm,
    UserRoleAssignmentForm,
    CustomPasswordChangeForm,
    ParentStudentRelationshipForm,
    StudentApplicationForm,
    StaffApplicationForm,
    LoginHistorySearchForm,
    UserBulkActionForm,
    UserImportForm,
)

logger = logging.getLogger(__name__)

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def can_assign_roles(user):
    """
    Check if user can assign roles to other users.
    Only superusers and school admins (admin/school_admin roles) can assign roles.
    """
    if user.is_superuser:
        return True

    # First allow users with explicit role-management permissions
    if user.has_perm("users.add_role") or user.has_perm("users.change_role"):
        return True

    # Check if user has admin, principal, or school_admin role
    return user.user_roles.filter(
        role__role_type__in=["admin", "school_admin"], status="active"
    ).exists()


def login_history(request):
    """
    View login history with search and filtering capabilities.
    """
    from django.core.paginator import Paginator

    # Get login history queryset filtered by institution
    current_user_institution = request.user.current_institution
    if current_user_institution:
        login_entries = (
            LoginHistory.objects.filter(
                user__institution_memberships__institution=current_user_institution,
                user__institution_memberships__is_primary=True,
            )
            .select_related("user")
            .order_by("-created_at")
            .distinct()
        )
    else:
        # Fallback for users without primary institution (like during setup)
        login_entries = LoginHistory.objects.none()

    # Filter by user if specified (for user detail page link)
    user_id = request.GET.get("user")
    if user_id:
        try:
            user = User.objects.get(id=user_id)
            # Check if user belongs to same institution
            if user.current_institution == current_user_institution:
                login_entries = login_entries.filter(user=user)
            else:
                messages.error(
                    request, _("Access denied: User not in your institution.")
                )
                return redirect("users:user_list")
        except User.DoesNotExist:
            messages.error(request, _("User not found."))
            return redirect("users:user_list")

    # Apply form filters
    form = LoginHistorySearchForm(request.GET, user=request.user)
    if form.is_valid():
        # User filter - ensure user belongs to same institution
        if form.cleaned_data["user"]:
            if (
                form.cleaned_data["user"].current_institution
                == request.user.current_institution
            ):
                login_entries = login_entries.filter(user=form.cleaned_data["user"])
            else:
                # Don't show login history for users from other institutions
                pass

        # Success filter
        if form.cleaned_data["was_successful"] != "":
            if form.cleaned_data["was_successful"] == "true":
                login_entries = login_entries.filter(was_successful=True)
            elif form.cleaned_data["was_successful"] == "false":
                login_entries = login_entries.filter(was_successful=False)

        # Date range filter
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")
        date_range = form.cleaned_data.get("date_range")

        if date_range == "custom" and start_date and end_date:
            login_entries = login_entries.filter(
                created_at__date__range=[start_date, end_date]
            )
        elif date_range == "today":
            today = timezone.now().date()
            login_entries = login_entries.filter(created_at__date=today)
        elif date_range == "week":
            week_ago = timezone.now() - timezone.timedelta(days=7)
            login_entries = login_entries.filter(created_at__gte=week_ago)
        elif date_range == "month":
            month_ago = timezone.now() - timezone.timedelta(days=30)
            login_entries = login_entries.filter(created_at__gte=month_ago)

    # Pagination
    paginator = Paginator(login_entries, 25)  # 25 items per page
    page = request.GET.get("page")
    login_entries_page = paginator.get_page(page)

    context = {
        "title": _("Login History"),
        "login_entries": login_entries_page,
        "form": form,
        "active_tab": "login_history",
    }

    return render(request, "users/admin/login_history.html", context)


def create_user_from_student_application(application, reviewed_by):
    """Create user account from approved student application."""
    try:
        with transaction.atomic():
            from apps.core.models import Institution, InstitutionUser

            # Generate temporary password
            characters = string.ascii_letters + string.digits + string.punctuation
            temporary_password = "".join(secrets.choice(characters) for i in range(12))

            # Check if user already exists
            user, created = User.objects.get_or_create(
                email=application.email,
                defaults={
                    "first_name": application.first_name,
                    "last_name": application.last_name,
                    "mobile": application.phone,
                    "is_active": True,
                    "is_verified": True,  # Will need to verify email
                },
            )

            if created:
                user.set_password(temporary_password)
            else:
                # If user exists, update their details and set a new temporary password
                user.first_name = application.first_name
                user.last_name = application.last_name
                user.mobile = application.phone
                user.is_active = True
                user.is_verified = True
                user.set_password(
                    temporary_password
                )  # Reset password for existing user
            user.save()

            # Update profile
            profile = user.profile
            profile.date_of_birth = application.date_of_birth
            profile.gender = application.gender
            profile.nationality = application.nationality
            profile.address_line_1 = application.address_line_1
            profile.address_line_2 = application.address_line_2
            profile.city = application.city
            profile.state = application.state
            profile.postal_code = application.postal_code
            profile.country = application.country
            profile.save()

            # Create Student profile
            from apps.academics.models import Student

            student, student_created = Student.objects.get_or_create(
                user=user,
                defaults={
                    "admission_number": application.application_number,  # Use application number as admission number
                    "admission_date": timezone.now().date(),
                    "date_of_birth": application.date_of_birth,
                    "place_of_birth": "",  # Could be added to application form later
                    "gender": application.gender,
                    "nationality": application.nationality,
                    "previous_school": application.previous_school or "",
                    "status": "active",
                },
            )

            if not student_created:
                # Update existing student profile
                student.admission_number = application.application_number
                student.admission_date = timezone.now().date()
                student.date_of_birth = application.date_of_birth
                student.gender = application.gender
                student.nationality = application.nationality
                student.previous_school = application.previous_school or ""
                student.status = "active"
                student.save()

            # Create enrollment if this is for tertiary education and department is specified
            from apps.academics.models import GradeLevel

            grade_obj = GradeLevel.objects.filter(
                name=application.grade_applying_for
            ).first()

            if (
                grade_obj
                and grade_obj.education_stage
                in ["undergraduate", "graduate", "postgraduate", "diploma"]
                and application.department
            ):
                # This is a tertiary application with department specified
                current_session = AcademicSession.objects.filter(
                    is_current=True
                ).first()

                if current_session:
                    # Find or create appropriate class for the department and grade level
                    # For now, we'll create a basic enrollment - this would need refinement based on specific requirements
                    from apps.academics.models import Class, Enrollment

                    # Try to find existing class for this department and grade level
                    class_obj = Class.objects.filter(
                        grade_level=grade_obj,
                        academic_session=current_session,
                        # Additional filtering might be needed based on department
                    ).first()

                    if class_obj:
                        # Check if student is already enrolled
                        existing_enrollment = Enrollment.objects.filter(
                            student=student,
                            academic_session=current_session,
                            enrollment_status="active",
                        ).first()

                        if not existing_enrollment:
                            # Create enrollment with department
                            last_roll = (
                                Enrollment.objects.filter(
                                    class_enrolled=class_obj,
                                    academic_session=current_session,
                                )
                                .order_by("-roll_number")
                                .first()
                            )

                            roll_number = last_roll.roll_number + 1 if last_roll else 1

                            Enrollment.objects.create(
                                student=student,
                                class_enrolled=class_obj,
                                academic_session=current_session,
                                department=application.department,
                                enrollment_date=timezone.now().date(),
                                roll_number=roll_number,
                                enrollment_status="active",
                                notes=f"Enrolled from application {application.application_number}",
                            )

            student_role = Role.objects.filter(role_type="student").first()
            if not student_role:
                student_role = Role.objects.create(
                    name="Student",
                    role_type="student",
                    description="Student role",
                    hierarchy_level=10,
                    is_system_role=True,
                    status="active",
                )

            UserRole.objects.create(
                user=user,
                role=student_role,
                is_primary=True,
                context_id=f"grade_{application.grade_applying_for}",
            )

            # Map user to the institution they applied to
            if application.institution:
                institution_user, inst_created = InstitutionUser.objects.get_or_create(
                    user=user,
                    institution=application.institution,
                    defaults={
                        "is_primary": True,
                        "employee_id": f"STU_{application.institution.code}_{application.application_number}",
                    },
                )
                if not inst_created:
                    # Update existing mapping to be primary
                    institution_user.is_primary = True
                    institution_user.save()
                logger.info(
                    f"Mapped student {user.email} to institution {application.institution.name}"
                )

            # Create parent relationship if parent email is different
            if (
                application.parent_email
                and application.parent_email != application.email
            ):
                parent_user, created = User.objects.get_or_create(
                    email=application.parent_email,
                    defaults={
                        "first_name": application.parent_first_name or "Parent",
                        "last_name": application.parent_last_name or "User",
                        "mobile": application.parent_phone,
                        "is_active": True,
                    },
                )

                if created:
                    # Set temporary password for parent
                    parent_user.make_random_password(length=12)

                    # Get or create parent role - FIXED VERSION
                    parent_role = Role.objects.filter(role_type="parent").first()
                    if not parent_role:
                        parent_role = Role.objects.create(
                            name="Parent",
                            role_type="parent",
                            description="Parent role",
                            hierarchy_level=20,
                            is_system_role=True,
                            status="active",
                        )

                    UserRole.objects.create(
                        user=parent_user, role=parent_role, is_primary=True
                    )
                    # Create profile for parent if it doesn't exist
                    if not hasattr(parent_user, "profile"):
                        UserProfile.objects.create(user=parent_user)

                # Map parent to the same institution as the student
                if application.institution:
                    InstitutionUser.objects.get_or_create(
                        user=parent_user,
                        institution=application.institution,
                        defaults={
                            "is_primary": True,
                            "employee_id": f"PAR_{application.institution.code}_{parent_user.id}",
                        },
                    )

                # Create parent-student relationship
                ParentStudentRelationship.objects.create(
                    parent=parent_user,
                    student=user,
                    relationship_type=application.parent_relationship,
                    is_primary_contact=True,
                )

            return user, temporary_password

    except Exception as e:
        logger.error(f"Error creating user from student application: {e}")
        raise


def create_user_from_staff_application(application, reviewed_by):
    """Create user account from approved staff application."""
    try:
        with transaction.atomic():
            from apps.core.models import Institution, InstitutionUser, SequenceGenerator

            # Generate temporary password
            characters = string.ascii_letters + string.digits + string.punctuation
            temporary_password = "".join(secrets.choice(characters) for i in range(12))

            # Check if user already exists
            user, created = User.objects.get_or_create(
                email=application.email,
                defaults={
                    "first_name": application.first_name,
                    "last_name": application.last_name,
                    "mobile": application.phone,
                    "is_active": True,
                    "is_verified": True,
                },
            )

            if created:
                user.set_password(temporary_password)
            else:
                # If user exists, update their details and set a new temporary password
                user.first_name = application.first_name
                user.last_name = application.last_name
                user.mobile = application.phone
                user.is_active = True
                user.is_verified = True
                user.set_password(
                    temporary_password
                )  # Reset password for existing user
            user.save()

            # Update profile
            profile = user.profile
            profile.date_of_birth = application.date_of_birth
            profile.gender = application.gender
            profile.nationality = application.nationality
            profile.address_line_1 = application.address_line_1
            profile.address_line_2 = application.address_line_2
            profile.city = application.city
            profile.state = application.state
            profile.postal_code = application.postal_code
            profile.country = application.country
            profile.bio = (
                f"Applied for {application.position_applied_for.name} position"
            )
            profile.save()

            # Generate employee ID using SequenceGenerator with institution-specific prefix
            # Create a professional prefix reflecting the school name
            institution_code = application.institution.code.upper()
            prefix = f"{institution_code}-EMP"

            sequence, created = SequenceGenerator.objects.get_or_create(
                sequence_type="employee_id",
                institution=application.institution,
                defaults={"prefix": prefix, "last_number": 0, "padding": 6},
            )

            # Update prefix for existing sequences if institution code changed
            if not created and sequence.prefix != prefix:
                sequence.prefix = prefix
                sequence.save()

            employee_id = sequence.get_next_number()

            # Create staff profile based on position type
            position_role_type = application.position_applied_for.role_type

            if position_role_type == "teacher":
                # Create Teacher profile
                from apps.academics.models import Teacher

                teacher, teacher_created = Teacher.objects.get_or_create(
                    user=user,
                    defaults={
                        "teacher_id": f"T{sequence.last_number:06d}",  # Use sequence number directly
                        "employee_id": employee_id,
                        "date_of_birth": application.date_of_birth,
                        "gender": application.gender,
                        "qualification": application.highest_qualification,
                        "specialization": application.previous_position or "",
                        "joining_date": timezone.now().date(),
                        "experience_years": application.years_of_experience,
                        "bio": f"Hired as {application.position_applied_for.name}",
                        "status": "active",
                    },
                )
                if not teacher_created:
                    # Update existing teacher profile
                    teacher.employee_id = employee_id
                    teacher.qualification = application.highest_qualification
                    teacher.specialization = (
                        application.previous_position or teacher.specialization
                    )
                    teacher.experience_years = application.years_of_experience
                    teacher.save()

            elif position_role_type == "driver":
                # Create Driver profile
                from apps.transport.models import Driver

                driver, driver_created = Driver.objects.get_or_create(
                    user=user,
                    defaults={
                        "employee_id": employee_id,
                        "license_number": "",  # Will need to be updated later
                        "license_type": "lmv",
                        "license_expiry": timezone.now().date()
                        + timezone.timedelta(days=365),  # Default 1 year
                        "date_of_birth": application.date_of_birth,
                        "date_of_joining": timezone.now().date(),
                        "status": "active",
                    },
                )
                if not driver_created:
                    driver.employee_id = employee_id
                    driver.save()

            elif position_role_type in ["support", "librarian", "accountant"]:
                # For support staff, create Attendant profile (can be used for various support roles)
                from apps.transport.models import Attendant

                attendant, attendant_created = Attendant.objects.get_or_create(
                    user=user,
                    defaults={
                        "employee_id": employee_id,
                        "date_of_birth": application.date_of_birth,
                        "date_of_joining": timezone.now().date(),
                        "responsibilities": f"{application.position_applied_for.name} responsibilities",
                        "status": "active",
                    },
                )
                if not attendant_created:
                    attendant.employee_id = employee_id
                    attendant.responsibilities = (
                        f"{application.position_applied_for.name} responsibilities"
                    )
                    attendant.save()

            elif position_role_type == "activities_coordinator":
                # Activities coordinator doesn't need a specific profile
                # They coordinate activities through the Activity model's coordinator field
                pass

            elif position_role_type == "transport_manager":
                # Transport manager doesn't need a specific profile
                # They manage transport operations through Driver and Attendant profiles
                pass

            elif position_role_type == "hostel_warden":
                # Hostel warden doesn't need a specific profile
                # They manage hostels through the Hostel model's warden field
                pass

            elif position_role_type in [
                "super_admin",
                "school_admin",
                "admin",
                "principal",
                "department_head",
                "counselor",
            ]:
                # Administrative roles without specific profiles
                # These roles get permissions through the Role model
                pass

            else:
                # Unknown role type - log warning but continue
                logger.warning(
                    f"Unknown role type: {position_role_type} for user {user.email}"
                )

            # Assign staff role if not already assigned
            existing_role = UserRole.objects.filter(
                user=user, role=application.position_applied_for
            ).first()

            if not existing_role:
                UserRole.objects.create(
                    user=user, role=application.position_applied_for, is_primary=True
                )

            # Set staff permissions based on role
            if position_role_type in [
                "super_admin",
                "school_admin",
                "admin",
                "principal",
                "department_head",
                "counselor",
                "teacher",
                "activities_coordinator",
                "librarian",
                "accountant",
                "support",
                "transport_manager",
                "hostel_warden",
            ]:
                user.is_staff = True
                user.save()

            # Map user to the institution they applied to
            if application.institution:
                institution_user, inst_created = InstitutionUser.objects.get_or_create(
                    user=user,
                    institution=application.institution,
                    defaults={
                        "is_primary": True,
                        "employee_id": employee_id,
                    },
                )
                if not inst_created:
                    # Update existing mapping to be primary
                    institution_user.is_primary = True
                    institution_user.save()
                logger.info(
                    f"Mapped staff {user.email} to institution {application.institution.name}"
                )

            return user, temporary_password

    except Exception as e:
        logger.error(f"Error creating user from staff application: {e}")
        raise


def send_email_with_retry(
    subject, message, from_email, recipient_list, html_message=None, max_retries=3
):
    """
    Send email with retry logic and better error handling for Gmail.
    """
    connection = None
    last_error = None

    for attempt in range(max_retries):
        try:
            # Create email message
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=from_email,
                to=recipient_list,
            )

            if html_message:
                email.content_subtype = "html"
                email.body = html_message

            # Get connection with proper Gmail settings
            connection = get_connection()

            # Send the email
            email.send()

            logger.info(
                f"Email sent successfully to {recipient_list} on attempt {attempt + 1}"
            )
            return True

        except smtplib.SMTPAuthenticationError as e:
            last_error = f"Authentication failed: {e}"
            logger.error(f"SMTP Authentication Error (attempt {attempt + 1}): {e}")
            # Don't retry auth errors
            break
        except smtplib.SMTPConnectError as e:
            last_error = f"Connection failed: {e}"
            logger.error(f"SMTP Connection Error (attempt {attempt + 1}): {e}")
        except smtplib.SMTPException as e:
            last_error = f"SMTP error: {e}"
            logger.error(f"SMTP Error (attempt {attempt + 1}): {e}")
        except Exception as e:
            last_error = f"Unexpected error: {e}"
            logger.error(f"Unexpected email error (attempt {attempt + 1}): {e}")

        # Wait before retry (exponential backoff)
        if attempt < max_retries - 1:
            import time

            time.sleep(2**attempt)

    logger.error(
        f"Failed to send email after {max_retries} attempts. Last error: {last_error}"
    )
    return False


def send_approval_email(request, application, user, temporary_password):
    """Send approval email with login credentials to student."""
    # Get institution details from the application
    institution = (
        application.institution
        if hasattr(application, "institution") and application.institution
        else None
    )

    # Use institution name if available, otherwise fallback to settings
    school_name = (
        institution.name
        if institution
        else getattr(settings, "SCHOOL_NAME", "Nexus-Academy")
    )
    from_email = (
        institution.email
        if institution and institution.email
        else settings.DEFAULT_FROM_EMAIL
    )
    contact_email = (
        institution.email
        if institution and institution.email
        else settings.DEFAULT_FROM_EMAIL
    )

    subject = _("Application Approved - Welcome to {}").format(school_name)

    # Get student information if this is a student application
    student_id = None
    admission_number = None
    if hasattr(user, "student_profile"):
        student_id = user.student_profile.student_id
        admission_number = user.student_profile.admission_number

    # Check if this was a staff application that went through interview process
    had_interview = False
    interview_date = None
    if hasattr(application, "interview_date") and application.interview_date:
        had_interview = True
        interview_date = application.interview_date

    context = {
        "application": application,
        "user": user,
        "temporary_password": temporary_password,
        "login_url": request.build_absolute_uri(reverse("users:login")),
        "school_name": school_name,
        "contact_email": contact_email,
        "student_id": student_id,
        "admission_number": admission_number,
        "had_interview": had_interview,
        "interview_date": interview_date,
    }

    html_message = render_to_string("users/emails/application_approved.html", context)
    text_message = strip_tags(html_message)

    success = send_email_with_retry(
        subject=subject,
        message=text_message,
        from_email=from_email,
        recipient_list=[user.email],
        html_message=html_message,
    )

    if success:
        logger.info(f"Student approval email sent to {user.email}")
    else:
        logger.error(f"Failed to send student approval email to {user.email}")

    return success


def send_parent_approval_email(request, application, student_user, parent_user):
    """Send approval notification email to parent."""
    subject = _("Student Application Approved - {}").format(
        getattr(settings, "SCHOOL_NAME", "Nexus-Academy")
    )

    # Get student information
    student_id = None
    admission_number = None
    if hasattr(student_user, "student_profile"):
        student_id = student_user.student_profile.student_id
        admission_number = student_user.student_profile.admission_number

    # Check if this was an application that went through interview process
    had_interview = False
    interview_date = None
    if hasattr(application, "interview_date") and application.interview_date:
        had_interview = True
        interview_date = application.interview_date

    context = {
        "application": application,
        "student": student_user,
        "parent": parent_user,
        "school_name": getattr(settings, "SCHOOL_NAME", "Nexus-Academy"),
        "contact_email": settings.DEFAULT_FROM_EMAIL,
        "student_id": student_id,
        "admission_number": admission_number,
        "grade_applying_for": getattr(application, "grade_applying_for", None),
        "had_interview": had_interview,
        "interview_date": interview_date,
    }

    html_message = render_to_string(
        "users/emails/parent_application_approved.html", context
    )
    text_message = strip_tags(html_message)

    success = send_email_with_retry(
        subject=subject,
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[parent_user.email],
        html_message=html_message,
    )

    if success:
        logger.info(f"Parent approval email sent to {parent_user.email}")
    else:
        logger.error(f"Failed to send parent approval email to {parent_user.email}")

    return success


def send_rejection_email(application, review_notes):
    """Send rejection email to applicant."""
    subject = _("Application Update - {}").format(application.application_number)

    context = {
        "application": application,
        "review_notes": review_notes,
        "contact_email": settings.DEFAULT_FROM_EMAIL,
    }

    html_message = render_to_string("users/emails/application_rejected.html", context)
    text_message = strip_tags(html_message)

    success = send_email_with_retry(
        subject=subject,
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[application.email],
        html_message=html_message,
    )

    if success:
        logger.info(f"Rejection email sent to {application.email}")
    else:
        logger.error(f"Failed to send rejection email to {application.email}")


def send_interview_email(
    application, interview_date, review_notes, approving_staff=None
):
    """Send interview scheduling email to applicant."""
    subject = _("Interview Scheduled - {}").format(application.application_number)

    # Get staff information
    staff_name = None
    staff_role = None
    staff_email = None
    staff_phone = None

    if approving_staff:
        staff_name = (
            approving_staff.get_full_name()
            if approving_staff.get_full_name()
            else approving_staff.email
        )
        # Get primary role
        primary_role = approving_staff.user_roles.filter(is_primary=True).first()
        if primary_role:
            staff_role = primary_role.role.name
            staff_email = approving_staff.email
            staff_phone = approving_staff.mobile if approving_staff.mobile else None

    context = {
        "application": application,
        "interview_date": interview_date,
        "review_notes": review_notes,
        "contact_email": settings.DEFAULT_FROM_EMAIL,
        "school_name": getattr(settings, "SCHOOL_NAME", "Nexus-Academy"),
        "staff_name": staff_name,
        "staff_role": staff_role,
        "staff_email": staff_email,
        "staff_phone": staff_phone,
    }

    html_message = render_to_string("users/emails/interview_scheduled.html", context)
    text_message = strip_tags(html_message)

    success = send_email_with_retry(
        subject=subject,
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[application.email],
        html_message=html_message,
    )

    if success:
        logger.info(f"Interview scheduling email sent to {application.email}")
    else:
        logger.error(
            f"Failed to send interview scheduling email to {application.email}"
        )
    return success


def get_user_redirect_url(user):
    """
    Determine redirect URL based on user's primary role.
    Django superusers are automatically treated as super admins.
    """
    try:
        # Django superusers should always go to super admin dashboard
        if user.is_superuser:
            return reverse("core:super_admin_dashboard")

        primary_role = user.user_roles.filter(is_primary=True).first()

        if not primary_role:
            # If no primary role, check any role
            any_role = user.user_roles.first()
            if any_role:
                return get_role_redirect_url(any_role.role.role_type)
            return reverse("users:dashboard")

        return get_role_redirect_url(primary_role.role.role_type)

    except Exception as e:
        logger.error(f"Error determining redirect URL for user {user.id}: {e}")
        return reverse("users:dashboard")


def get_role_redirect_url(role_type):
    """
    Map role types to their respective dashboard URLs.
    """
    role_redirects = {
        "super_admin": reverse("core:super_admin_dashboard"),
        "school_admin": reverse("core:school_admin_dashboard"),
        "admin": reverse("core:school_admin_dashboard"),
        "principal": reverse("core:school_admin_dashboard"),
        "teacher": reverse("users:teacher_dashboard"),
        "student": reverse("users:dashboard"),
        "parent": reverse("users:parent_dashboard"),
        "accountant": reverse("finance:dashboard"),
        "librarian": reverse("library:dashboard"),
        "driver": reverse("transport:dashboard"),
        "support": reverse("support:dashboard"),
        "counselor": reverse(
            "users:dashboard"
        ),  # Generic dashboard for academic oversight
        "department_head": reverse(
            "users:dashboard"
        ),  # Generic dashboard for academic oversight
        "activities_coordinator": reverse(
            "activities:activity_list"
        ),  # Activities list as dashboard
        "hostel_warden": reverse("hostels:dashboard"),
    }
    return role_redirects.get(role_type, reverse("users:dashboard"))


# =============================================================================
# APPLICATION DETAIL VIEWS
# =============================================================================


@login_required
@user_passes_test(lambda u: u.is_superuser or u.has_perm("users.view_staffapplication"))
def staff_application_detail(request, application_id):
    """
    View detailed information about a specific staff application.
    """
    application = get_object_or_404(StaffApplication, id=application_id)

    context = {
        "title": _("Staff Application Details"),
        "application": application,
        "active_tab": "applications",
    }
    return render(
        request, "users/admin/applications/staff_application_detail.html", context
    )


@login_required
@user_passes_test(
    lambda u: u.is_superuser or u.has_perm("users.view_studentapplication")
)
def student_application_detail(request, application_id):
    """
    View detailed information about a specific student application.
    """
    application = get_object_or_404(StudentApplication, id=application_id)

    context = {
        "title": _("Student Application Details"),
        "application": application,
        "active_tab": "applications",
    }
    return render(
        request, "users/admin/applications/student_application_detail.html", context
    )


# =============================================================================
# GUEST/PUBLIC VIEWS
# =============================================================================


def guest_home(request):
    """
    Main landing page for non-authenticated users.
    """
    context = {
        "title": _("Welcome to Nexus Intelligence School Management System"),
        "show_application_links": True,
    }
    return render(request, "users/guest/guest_home.html", context)


def application_portal(request):
    """
    Portal where non-members can apply as students or staff.
    """
    context = {
        "title": _("Application Portal"),
        "academic_sessions": AcademicSession.objects.filter(
            status="active", is_current=True
        ),
    }
    return render(request, "users/applications/application_portal.html", context)


def application_submitted(request):
    """
    Confirmation page after application submission.
    """
    context = {
        "title": _("Application Submitted"),
        "message": _(
            "Thank you for your application! We have received your submission and will review it shortly."
        ),
        "show_application_links": False,
    }
    return render(request, "users/applications/application_submitted.html", context)


class StudentApplicationView(FormView):
    """
    View for student applications.
    """

    template_name = "users/applications/student_application.html"
    form_class = StudentApplicationForm
    success_url = reverse_lazy("users:application_submitted")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = _("Student Application")
        return context

    def form_valid(self, form):
        try:
            # Save the application
            application = form.save(commit=False)

            # Set additional fields
            application.application_status = ApplicationStatus.PENDING

            # Handle academic_session - it's now optional in the form
            academic_session = form.cleaned_data.get("academic_session")
            if academic_session:
                application.academic_session = academic_session
            else:
                # Set to current session if not provided
                current_session = AcademicSession.objects.filter(
                    is_current=True
                ).first()
                if current_session:
                    application.academic_session = current_session

            # Save the application
            application.save()

            # Log the application submission
            AuditLog.objects.create(
                user=None,  # No user since it's a public application
                action=AuditLog.ActionType.CREATE,
                model_name="users.StudentApplication",
                object_id=str(application.id),
                ip_address=get_client_ip(self.request),
                details={
                    "action": "Student application submitted",
                    "application_number": application.application_number,
                    "grade": application.grade_applying_for,
                    "academic_session": (
                        str(application.academic_session)
                        if application.academic_session
                        else "Not specified"
                    ),
                },
            )

            # Send confirmation email to applicant
            self.send_application_confirmation_email(application)

            # Send notification email to admin
            self.send_admin_notification_email(application)

            messages.success(
                self.request,
                _(
                    "Student application submitted successfully! You will receive a confirmation email shortly."
                ),
            )

        except Exception as e:
            logger.error(f"Error submitting student application: {e}")
            logger.error(f"Form errors: {form.errors}")
            logger.error(f"Form data: {form.cleaned_data}")
            messages.error(
                self.request,
                _(
                    "There was an error submitting your application. Please check the form and try again."
                ),
            )
            return self.form_invalid(form)

        return super().form_valid(form)

    def send_application_confirmation_email(self, application):
        """Send confirmation email to student applicant."""
        subject = _("Application Received - {}").format(
            getattr(settings, "SCHOOL_NAME", "Nexus-Academy")
        )

        context = {
            "application": application,
            "school_name": getattr(settings, "SCHOOL_NAME", "Nexus-Academy"),
            "contact_email": settings.DEFAULT_FROM_EMAIL,
        }

        message = render_to_string(
            "users/emails/student_application_confirmation.html", context
        )

        try:
            send_mail(
                subject,
                strip_tags(message),
                settings.DEFAULT_FROM_EMAIL,
                [application.email],
                html_message=message,
                fail_silently=False,
            )
            logger.info(
                f"Student application confirmation email sent to {application.email}"
            )
        except Exception as e:
            logger.error(f"Error sending student application confirmation email: {e}")
            raise

    def send_admin_notification_email(self, application):
        """Send notification email to admin about new student application."""
        subject = _("New Student Application Received - {}").format(
            application.application_number
        )

        context = {
            "application": application,
            "admin_url": self.request.build_absolute_uri(
                reverse("users:pending_applications")
            ),
            "school_name": getattr(settings, "SCHOOL_NAME", "Nexus-Academy"),
        }

        message = render_to_string(
            "users/emails/admin_student_application_notification.html", context
        )

        # Get emails of actual admin users (superusers and admin/principal roles)
        admin_users = User.objects.filter(
            Q(is_superuser=True)
            | Q(
                user_roles__role__role_type__in=[
                    "super_admin",
                    "admin",
                    "school_admin",
                    "principal",
                ],
                user_roles__status="active",
            )
        ).distinct()
        admin_emails = list(admin_users.values_list("email", flat=True))

        # Fallback to ADMINS setting or DEFAULT_FROM_EMAIL if no admin users found
        if not admin_emails:
            admin_emails = (
                [email for name, email in settings.ADMINS]
                if hasattr(settings, "ADMINS")
                else [settings.DEFAULT_FROM_EMAIL]
            )

        try:
            send_mail(
                subject,
                strip_tags(message),
                settings.DEFAULT_FROM_EMAIL,
                admin_emails,
                html_message=message,
                fail_silently=False,
            )
            logger.info(
                f"Admin notification email sent to {len(admin_emails)} admins for application {application.application_number}"
            )
        except Exception as e:
            logger.error(
                f"Error sending admin notification email for application {application.application_number}: {e}"
            )
            raise


class StaffApplicationView(FormView):
    """
    View for staff applications.
    """

    template_name = "users/applications/staff_application.html"
    form_class = StaffApplicationForm
    success_url = reverse_lazy("users:application_submitted")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = _("Staff Application")
        context["staff_types"] = Role.objects.exclude(
            role_type__in=["student", "parent"]
        ).filter(status="active")
        return context

    def send_application_confirmation_email(self, application):
        """Send confirmation email to staff applicant."""
        subject = _("Staff Application Received - {}").format(
            getattr(settings, "SCHOOL_NAME", "Our School")
        )

        context = {
            "application": application,
            "school_name": getattr(settings, "SCHOOL_NAME", "Nexus-Academy"),
            "contact_email": settings.DEFAULT_FROM_EMAIL,
        }

        try:
            message = render_to_string(
                "users/emails/staff_application_confirmation.html", context
            )

            send_mail(
                subject,
                strip_tags(message),
                settings.DEFAULT_FROM_EMAIL,
                [application.email],
                html_message=message,
                fail_silently=True,  # Changed to fail_silently=True to prevent application failure
            )
            logger.info(
                f"Staff application confirmation email sent to {application.email}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Error sending staff application confirmation email to {application.email}: {e}"
            )
            return False

    def send_admin_notification_email(self, application):
        """Send notification email to admin about new staff application."""
        subject = _("New Staff Application Received - {}").format(
            application.application_number
        )

        context = {
            "application": application,
            "admin_url": self.request.build_absolute_uri(
                reverse("users:pending_applications")
            ),
            "school_name": getattr(settings, "SCHOOL_NAME", "Our School"),
        }

        try:
            message = render_to_string(
                "users/emails/admin_staff_application_notification.html", context
            )

            # Get emails of actual admin users (superusers and admin/principal roles)
            admin_users = User.objects.filter(
                Q(is_superuser=True)
                | Q(
                    user_roles__role__role_type__in=[
                        "super_admin",
                        "school_admin",
                        "admin",
                        "principal",
                    ],
                    user_roles__status="active",
                )
            ).distinct()
            admin_emails = list(admin_users.values_list("email", flat=True))

            # Fallback to ADMINS setting or DEFAULT_FROM_EMAIL if no admin users found
            if not admin_emails:
                admin_emails = (
                    [email for name, email in settings.ADMINS]
                    if hasattr(settings, "ADMINS")
                    else [settings.DEFAULT_FROM_EMAIL]
                )

            send_mail(
                subject,
                strip_tags(message),
                settings.DEFAULT_FROM_EMAIL,
                admin_emails,
                html_message=message,
                fail_silently=True,  # Changed to fail_silently=True to prevent application failure
            )
            logger.info(
                f"Admin notification email sent to {len(admin_emails)} admins for staff application {application.application_number}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Error sending admin notification email for staff application {application.application_number}: {e}"
            )
            return False

    def form_valid(self, form):
        try:
            logger.info(
                f"Starting staff application submission for email: {form.cleaned_data.get('email')}"
            )

            # Save the application
            application = form.save(commit=False)

            # Set additional fields
            application.application_status = ApplicationStatus.PENDING

            # Save the application
            application.save()

            logger.info(
                f"Staff application saved successfully with ID: {application.id}, number: {application.application_number}"
            )

            # Log the application submission
            AuditLog.objects.create(
                user=None,  # No user since it's a public application
                action=AuditLog.ActionType.CREATE,
                model_name="users.StaffApplication",
                object_id=str(application.id),
                ip_address=get_client_ip(self.request),
                details={
                    "action": "Staff application submitted",
                    "application_number": application.application_number,
                    "position": (
                        application.position_applied_for.name
                        if application.position_applied_for
                        else "Not specified"
                    ),
                },
            )

            # Send confirmation email to applicant
            email_sent_to_applicant = self.send_application_confirmation_email(
                application
            )
            if email_sent_to_applicant:
                logger.info(
                    f"Confirmation email sent successfully to {application.email}"
                )
            else:
                logger.warning(
                    f"Failed to send confirmation email to {application.email}"
                )

            # Send notification email to admin
            email_sent_to_admin = self.send_admin_notification_email(application)
            if email_sent_to_admin:
                logger.info(
                    f"Admin notification email sent successfully for application {application.application_number}"
                )
            else:
                logger.warning(
                    f"Failed to send admin notification email for application {application.application_number}"
                )

            # Success message based on email status
            if email_sent_to_applicant and email_sent_to_admin:
                messages.success(
                    self.request,
                    _(
                        "Staff application submitted successfully! You will receive a confirmation email shortly."
                    ),
                )
            elif email_sent_to_applicant:
                messages.success(
                    self.request,
                    _(
                        "Staff application submitted successfully! You will receive a confirmation email shortly. (Note: Admin notification may be delayed)"
                    ),
                )
            elif email_sent_to_admin:
                messages.warning(
                    self.request,
                    _(
                        "Staff application submitted successfully, but there was an issue sending the confirmation email. Please check your email later or contact support."
                    ),
                )
            else:
                messages.warning(
                    self.request,
                    _(
                        "Staff application submitted successfully, but there were issues sending emails. Please contact support if you do not receive confirmation."
                    ),
                )

        except Exception as e:
            logger.error(f"Error submitting staff application: {e}")
            logger.error(f"Form errors: {form.errors}")
            logger.error(f"Form data: {form.cleaned_data}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")

            # Provide more specific error messages
            error_message = str(e).lower()
            if (
                "unique constraint failed" in error_message
                or "duplicate key value" in error_message
            ):
                messages.error(
                    self.request,
                    _(
                        "An application with this email address has already been submitted."
                    ),
                )
            elif "file" in error_message and (
                "size" in error_message or "type" in error_message
            ):
                messages.error(
                    self.request,
                    _(
                        "There was an issue with one of your uploaded files. Please check the file type and size."
                    ),
                )
            elif "sequence" in error_message:
                messages.error(
                    self.request,
                    _(
                        "There was a system error generating your application number. Please try again."
                    ),
                )
            elif "validation" in error_message:
                messages.error(
                    self.request,
                    _(
                        "Please check your form data and try again. Some fields may be invalid."
                    ),
                )
            else:
                messages.error(
                    self.request,
                    _(
                        "There was an error submitting your application. Please try again or contact support if the problem persists."
                    ),
                )

            return self.form_invalid(form)

        return super().form_valid(form)


def send_password_change_email(user, request):
    """
    Send email confirmation when user changes password.
    """
    subject = _("Password Changed - {}").format(
        getattr(settings, "SCHOOL_NAME", "Nexus-Academy")
    )

    context = {
        "user": user,
        "school_name": getattr(settings, "SCHOOL_NAME", "Nexus-Academy"),
        "contact_email": settings.DEFAULT_FROM_EMAIL,
        "login_url": request.build_absolute_uri(reverse("users:login")),
        "change_date": timezone.now(),
    }

    html_message = render_to_string("users/emails/password_changed.html", context)
    text_message = strip_tags(html_message)

    success = send_email_with_retry(
        subject=subject,
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
    )

    if success:
        logger.info(f"Password change email sent to {user.email}")
    else:
        logger.error(f"Failed to send password change email to {user.email}")

    return success


# =============================================================================
# AUTHENTICATION VIEWS
# =============================================================================


def custom_password_retrieval(request):
    """
    Custom password retrieval view that sends user's password via email.
    Also sends notification to admin.
    """
    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        if not email:
            messages.error(request, _("Please enter your email address."))
            return redirect("users:password_reset")

        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, _("No account found with this email address."))
            return redirect("users:password_reset")

        # Generate a temporary password if needed
        temporary_password = None
        is_temporary = False

        # For security, we'll generate a new temporary password for retrieval
        import secrets
        import string

        characters = string.ascii_letters + string.digits + string.punctuation
        temporary_password = "".join(secrets.choice(characters) for i in range(12))
        is_temporary = True

        # Update user's password with the temporary one
        user.set_password(temporary_password)
        user.save()

        # Send password via email to user
        success = send_password_retrieval_email(user, temporary_password, request)

        if success:
            # Send notification to admins
            send_admin_password_retrieval_notification(user, request)

            # Log the password retrieval event
            AuditLog.objects.create(
                user=user,
                action=AuditLog.ActionType.UPDATE,
                model_name="users.User",
                object_id=str(user.id),
                ip_address=get_client_ip(request),
                details={"action": "Password retrieved via email"},
            )

            messages.success(
                request,
                _(
                    "Your password has been sent to your email address. Please check your inbox and update your password immediately for security reasons."
                ),
            )
            return redirect("users:password_reset_done")
        else:
            # If email fails, revert password change for security
            user.set_password(user.password)
            user.save()
            messages.error(
                request,
                _(
                    "There was an error sending your password. Please try again later or contact support."
                ),
            )
            return redirect("users:password_reset")

    # GET request - show form
    context = {
        "title": _("Retrieve Password"),
    }
    return render(request, "users/password_retrieval.html", context)


def send_password_retrieval_email(user, password, request):
    """
    Send email with user's password and update request.
    """
    subject = _("Your Password - {}").format(
        getattr(settings, "SCHOOL_NAME", "Our School")
    )

    context = {
        "user": user,
        "password": password,
        "school_name": getattr(settings, "SCHOOL_NAME", "Our School"),
        "contact_email": settings.DEFAULT_FROM_EMAIL,
        "login_url": request.build_absolute_uri(reverse("users:login")),
        "profile_url": request.build_absolute_uri(reverse("users:password_change")),
        "retrieval_time": timezone.now(),
    }

    html_message = render_to_string(
        "users/emails/password_retrieval_email.html", context
    )
    text_message = strip_tags(html_message)

    success = send_email_with_retry(
        subject=subject,
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
    )

    if success:
        logger.info(f"Password retrieval email sent to {user.email}")
    else:
        logger.error(f"Failed to send password retrieval email to {user.email}")

    return success


def send_admin_password_retrieval_notification(user, request):
    """
    Send notification email to admins about password retrieval request.
    """
    subject = _("Password Retrieval Request - {}").format(
        getattr(settings, "SCHOOL_NAME", "Our School")
    )

    # Get emails of actual admin users (superusers and admin/principal roles)
    admin_users = User.objects.filter(
        Q(is_superuser=True)
        | Q(
            user_roles__role__role_type__in=["super_admin", "admin", "principal"],
            user_roles__status="active",
        )
    ).distinct()
    admin_emails = list(admin_users.values_list("email", flat=True))

    # Fallback to ADMINS setting or DEFAULT_FROM_EMAIL if no admin users found
    if not admin_emails:
        admin_emails = (
            [email for name, email in settings.ADMINS]
            if hasattr(settings, "ADMINS")
            else [settings.DEFAULT_FROM_EMAIL]
        )

    if not admin_emails:
        logger.warning("No admin emails found for password retrieval notification")
        return False

    context = {
        "user": user,
        "school_name": getattr(settings, "SCHOOL_NAME", "Our School"),
        "retrieval_time": timezone.now(),
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "admin_panel_url": request.build_absolute_uri(reverse("admin:index")),
        "user_detail_url": request.build_absolute_uri(
            reverse("users:user_detail", kwargs={"user_id": user.id})
        ),
    }

    html_message = render_to_string(
        "users/emails/admin_password_retrieval_notification.html", context
    )
    text_message = strip_tags(html_message)

    success = send_email_with_retry(
        subject=subject,
        message=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=admin_emails,
        html_message=html_message,
    )

    if success:
        logger.info(
            f"Admin password retrieval notification sent to {len(admin_emails)} admins for user {user.email}"
        )
    else:
        logger.error(
            f"Failed to send admin notification for password retrieval by user {user.email}"
        )

    return success


def custom_login(request):
    """
    Custom login view with enhanced logging and security.
    """
    # Redirect if already authenticated
    if request.user.is_authenticated:
        return redirect(get_user_redirect_url(request.user))

    change_password_mode = False

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        print(f"Login attempt - Email: {email}")  # Debug line
        remember_me = request.POST.get("remember_me")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")
        change_password = request.POST.get("change_password")

        # Check if this is a change password request
        if change_password and new_password and confirm_password:
            # Change password mode
            change_password_mode = True
            user = authenticate(request, email=email, password=password)

            if user is not None:
                # Check if user is active
                if not user.is_active:
                    messages.error(
                        request,
                        _("Your account is inactive. Please contact administrator."),
                    )
                    return render(
                        request,
                        "users/auth/login.html",
                        {"change_password_mode": change_password_mode},
                    )

                if new_password != confirm_password:
                    messages.error(request, _("New passwords do not match."))
                    return render(
                        request,
                        "users/auth/login.html",
                        {"change_password_mode": change_password_mode},
                    )

                # Validate new password strength
                if len(new_password) < 8:
                    messages.error(
                        request, _("Password must be at least 8 characters long.")
                    )
                    return render(
                        request,
                        "users/auth/login.html",
                        {"change_password_mode": change_password_mode},
                    )

                # Change password
                user.set_password(new_password)
                user.save()

                # Send password change confirmation email
                send_password_change_email(user, request)

                # Log password change
                AuditLog.objects.create(
                    user=user,
                    action=AuditLog.ActionType.UPDATE,
                    model_name="users.User",
                    object_id=str(user.id),
                    ip_address=get_client_ip(request),
                    details={"action": "Password changed via login page"},
                )

                messages.success(
                    request,
                    _(
                        "Password changed successfully! Please log in with your new password."
                    ),
                )
                return redirect("users:login")
            else:
                messages.error(request, _("Invalid email or current password."))
                return render(
                    request,
                    "users/auth/login.html",
                    {"change_password_mode": change_password_mode},
                )
        else:
            # Normal login attempt
            # Authenticate user
            user = authenticate(request, email=email, password=password)
            print(f"Authentication result: {user}")  # Debug line

            # Log login attempt
            login_history = LoginHistory(
                user=user if user else None,
                institution=(
                    user.current_institution if user else get_current_institution()
                ),
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                was_successful=user is not None,
                failure_reason="" if user else "Invalid credentials",
            )

            if user is not None:
                # Check if user is active
                if not user.is_active:
                    login_history.failure_reason = "Account inactive"
                    login_history.save()
                    messages.error(
                        request,
                        _("Your account is inactive. Please contact administrator."),
                    )
                    return render(request, "users/auth/login.html")

                # Check if user is verified (if required)
                if not user.is_verified:
                    login_history.failure_reason = "Email not verified"
                    login_history.save()
                    messages.warning(
                        request, _("Please verify your email before logging in.")
                    )
                    return render(request, "users/auth/login.html")

                # Login successful
                login(request, user)
                login_history.was_successful = True
                login_history.failure_reason = ""
                login_history.save()

                # Update user login stats
                user.increment_login_count()
                user.current_login_ip = get_client_ip(request)
                user.save()

                # Set session expiry based on remember me
                if not remember_me:
                    request.session.set_expiry(0)  # Browser session
                else:
                    request.session.set_expiry(1209600)  # 2 weeks

                # Log audit event
                AuditLog.objects.create(
                    user=user,
                    action=AuditLog.ActionType.LOGIN,
                    model_name="users.User",
                    object_id=str(user.id),
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )

                messages.success(request, _("Login successful!"))
                logger.debug(
                    f"User {user.email} authenticated. Is authenticated: {request.user.is_authenticated}. Redirecting to: {get_user_redirect_url(user)}"
                )
                return redirect(get_user_redirect_url(user))

            else:
                # Login failed
                login_history.save()
                messages.error(request, _("Invalid email or password."))

    context = {
        "title": _("Login"),
        "show_application_links": True,
        "change_password_mode": change_password_mode,
    }
    return render(request, "users/auth/login.html", context)


def custom_logout(request):
    """
    Custom logout view with logging.
    """
    if request.user.is_authenticated:
        # Log audit event
        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.ActionType.LOGOUT,
            model_name="users.User",
            object_id=str(request.user.id),
            ip_address=get_client_ip(request),
        )

    logout(request)
    messages.info(request, _("You have been logged out successfully."))
    return redirect("users:guest_home")


# =============================================================================
# DASHBOARD & PROFILE VIEWS
# =============================================================================


@login_required
def user_dashboard(request):
    """
    Main user dashboard - redirects to role-specific dashboard or shows basic dashboard.
    """
    logger.debug(
        f"Accessing user_dashboard. Is authenticated: {request.user.is_authenticated}. User: {request.user.email}"
    )
    try:
        redirect_url = get_user_redirect_url(request.user)
        logger.debug(
            f"user_dashboard determined redirect URL: {redirect_url} for user {request.user.email}"
        )

        # Prevent redirect loop if get_user_redirect_url points back to user_dashboard itself
        if redirect_url == reverse("users:dashboard"):
            logger.debug(
                "Redirect URL is 'users:dashboard', rendering generic dashboard directly."
            )
            primary_role = request.user.user_roles.filter(is_primary=True).first()
            context = {
                "title": _("Dashboard"),
                "user": request.user,
                "primary_role": primary_role,
            }

            # Add role-based context variables for sidebar navigation
            primary_role = request.user.user_roles.filter(is_primary=True).first()
            user_roles = request.user.user_roles.all()

            # Role flags for sidebar
            is_student = hasattr(request.user, "student_profile")
            is_teacher = (
                request.user.has_perm("academics.view_class")
                or request.user.user_roles.filter(role__role_type="teacher").exists()
            )
            is_parent = request.user.has_perm(
                "academics.view_student"
            ) or has_role_or_perm(
                request.user, perm="academics.view_student", role_type="parent"
            )
            can_manage_academics = (
                request.user.has_perm("academics.change_class")
                or request.user.user_roles.filter(
                    role__role_type__in=[
                        "admin",
                        "principal",
                        "school_admin",
                        "teacher",
                    ]
                ).exists()
            )
            can_manage_users = (
                request.user.is_superuser
                or request.user.has_perm("users.change_user")
                or request.user.user_roles.filter(
                    role__role_type__in=["admin", "principal", "school_admin"]
                ).exists()
            )
            can_manage_library = (
                request.user.has_perm("library.change_book")
                or request.user.user_roles.filter(
                    role__role_type__in=[
                        "admin",
                        "principal",
                        "librarian",
                        "school_admin",
                    ]
                ).exists()
            )
            can_manage_transport = (
                request.user.has_perm("transport.change_route")
                or request.user.user_roles.filter(
                    role__role_type__in=["admin", "principal", "driver", "school_admin"]
                ).exists()
            )
            can_manage_hostels = (
                request.user.has_perm("hostels.change_hostel")
                or request.user.user_roles.filter(
                    role__role_type__in=["admin", "principal", "warden", "school_admin"]
                ).exists()
            )

            # Get unread notification count
            from apps.communication.models import RealTimeNotification

            unread_notification_count = RealTimeNotification.objects.filter(
                recipient=request.user, is_read=False
            ).count()

            # Add student-specific context if user is a student
            if is_student:
                student = request.user.student_profile
                current_session = AcademicSession.objects.filter(
                    is_current=True
                ).first()

                # Get current enrollment
                current_enrollment = None
                if current_session:
                    current_enrollment = (
                        student.enrollments.filter(
                            academic_session=current_session, enrollment_status="active"
                        )
                        .select_related("class_enrolled")
                        .first()
                    )

                # Add calculated class statistics if enrollment exists
                if current_enrollment:
                    current_class = current_enrollment.class_enrolled
                    # Calculate student count for the class
                    student_count = current_class.enrollments.filter(
                        academic_session=current_session, enrollment_status="active"
                    ).count()
                    # Calculate subject count for the class
                    subject_count = (
                        current_class.subject_assignments.filter(
                            academic_session=current_session
                        )
                        .values("subject")
                        .distinct()
                        .count()
                    )

                    # Add these to the class object for template access
                    current_class.student_count = student_count
                    current_class.subject_count = subject_count

                # Get today's attendance
                from django.utils import timezone

                today = timezone.now().date()
                today_attendance = None
                if current_session and current_enrollment:
                    from apps.attendance.models import DailyAttendance

                    today_attendance = DailyAttendance.objects.filter(
                        student=student,
                        date=today,
                        attendance_session__academic_session=current_session,
                    ).first()

                # Get today's timetable
                today_timetable = []
                if current_enrollment and current_session:
                    from apps.academics.models import Timetable

                    today_weekday = timezone.now().strftime("%A").lower()
                    today_timetable = (
                        Timetable.objects.filter(
                            class_assigned=current_enrollment.class_enrolled,
                            academic_session=current_session,
                            day_of_week=today_weekday,
                        )
                        .select_related("subject", "teacher")
                        .order_by("start_time")
                    )

                # Get recent announcements
                recent_announcements = []
                try:
                    from apps.communication.models import Announcement

                    recent_announcements = Announcement.objects.filter(
                        is_published=True, published_at__isnull=False
                    ).order_by("-published_at")[:5]
                except:
                    pass

                # Get upcoming assignments
                upcoming_assignments = []
                if current_session:
                    try:
                        from apps.assessment.models import Assignment
                        from django.db.models import Q

                        upcoming_assignments = (
                            Assignment.objects.filter(
                                (
                                    Q(academic_class=current_enrollment.class_enrolled)
                                    if current_enrollment
                                    else Q()
                                ),
                                academic_session=current_session,
                                due_date__gte=today,
                                is_active=True,
                            )
                            .select_related("subject", "teacher")
                            .order_by("due_date")[:5]
                        )
                    except:
                        pass

                # Get performance stats
                performance_stats = {}
                if current_session:
                    try:
                        from apps.assessment.models import Mark

                        marks = Mark.objects.filter(
                            student=student, exam__academic_session=current_session
                        )
                        if marks.exists():
                            total_marks = marks.count()
                            average_percentage = (
                                marks.aggregate(avg=models.Avg("percentage"))["avg"]
                                or 0
                            )
                            passed_exams = marks.filter(percentage__gte=40).count()

                            performance_stats = {
                                "total_exams": total_marks,
                                "average_percentage": round(average_percentage, 1),
                                "passed_exams": passed_exams,
                                "pass_rate": (
                                    round((passed_exams / total_marks * 100), 1)
                                    if total_marks > 0
                                    else 0
                                ),
                            }
                    except:
                        pass

                # Get recent grades
                recent_grades = []
                if current_session:
                    try:
                        from apps.assessment.models import Mark

                        recent_grades = (
                            Mark.objects.filter(
                                student=student, exam__academic_session=current_session
                            )
                            .select_related("exam", "exam__subject")
                            .order_by("-exam__exam_date")[:6]
                        )
                    except:
                        pass

                # Get library status
                library_status = None
                try:
                    from apps.library.models import BookBorrow

                    current_borrows = BookBorrow.objects.filter(
                        student=student, return_date__isnull=True, due_date__gte=today
                    ).select_related("book")
                    max_borrows = 5  # You can make this configurable
                    can_borrow_more = len(current_borrows) < max_borrows

                    library_status = {
                        "current_borrows": list(current_borrows),
                        "can_borrow_more": can_borrow_more,
                        "max_borrows": max_borrows,
                    }
                except ImportError:
                    # Library app might not be available
                    pass

                # Add all the context variables needed by the comprehensive dashboard
                context.update(
                    {
                        "student": student,
                        "current_session": current_session,
                        "current_enrollment": current_enrollment,
                        "today_timetable": today_timetable,
                        "recent_announcements": recent_announcements,
                        "upcoming_assignments": upcoming_assignments,
                        "today_attendance": today_attendance,
                        "performance_stats": performance_stats,
                        "recent_grades": recent_grades,
                        "library_status": library_status,
                        "today": today,
                    }
                )

            return render(request, "users/dashboard/dashboard.html", context)
        else:
            logger.debug(f"Redirecting to: {redirect_url}")
            return redirect(redirect_url)
    except Exception as e:
        logger.error(f"Error in user_dashboard for user {request.user.email}: {e}")
        # Fallback basic dashboard
        primary_role = request.user.user_roles.filter(is_primary=True).first()
        is_admin_staff = request.user.is_staff or (
            primary_role
            and primary_role.role.role_type
            in ["admin", "principal", "super_admin", "school_admin"]
        )
        context = {
            "title": _("Dashboard"),
            "user": request.user,
            "primary_role": primary_role,
            "is_admin_staff": is_admin_staff,
        }
        return render(request, "users/dashboard/dashboard.html", context)


@login_required
def profile_view(request):
    """
    Comprehensive user profile view showing all collected information across the system.
    """
    user = request.user
    profile = user.profile

    # Get user's application data if it exists
    try:
        student_application = user.student_application
    except User.student_application.RelatedObjectDoesNotExist:
        student_application = None

    try:
        staff_application = user.staff_application
    except User.staff_application.RelatedObjectDoesNotExist:
        staff_application = None

    # Initialize all data collections
    academic_data = {}
    assessment_data = {}
    attendance_data = {}
    activity_data = {}
    relationships_data = {}

    # ===== STUDENT-SPECIFIC DATA =====
    if hasattr(user, "student_profile") and user.student_profile:
        student = user.student_profile

        # Academic Information
        academic_data = {
            "student_profile": student,
            "current_enrollment": student.enrollments.filter(
                status="active", academic_session__is_current=True
            )
            .select_related("class_enrolled", "academic_session")
            .first(),
            "academic_records": student.academic_records.select_related(
                "class_enrolled", "academic_session"
            ).order_by("-academic_session__start_date")[
                :10
            ],  # Last 10 records
            "behavior_records": student.behavior_records.select_related(
                "reported_by"
            ).order_by("-incident_date")[
                :5
            ],  # Recent behavior records
            "achievements": student.achievements.order_by("-achievement_date")[
                :10
            ],  # Recent achievements
            "timetable_entries": [],  # Will be populated below
        }

        # Current timetable
        current_session = academic_data.get("current_enrollment")
        if current_session:
            from apps.academics.models import Timetable

            academic_data["timetable_entries"] = (
                Timetable.objects.filter(
                    class_assigned=current_session.class_enrolled,
                    academic_session=current_session.academic_session,
                    is_published=True,
                )
                .select_related("subject", "teacher")
                .order_by("day_of_week", "start_time")[:20]
            )

        # Assessment Data (Marks, Results)
        from apps.assessment.models import Mark, Result, Assignment

        assessment_data = {
            "exam_marks": Mark.objects.filter(student=student)
            .select_related("exam", "exam__subject", "exam__exam_type")
            .order_by("-exam__exam_date")[:20],  # Recent marks
            "results": Result.objects.filter(student=student)
            .select_related("academic_class", "exam_type", "grade")
            .order_by("-exam_type__order")[:10],  # Results by exam type
            "assignment_submissions": Assignment.objects.filter(
                student=student, student__isnull=False
            )
            .select_related("subject", "graded_by")
            .order_by("-submission_date")[:15],  # Recent assignments
        }

        # Attendance Data
        from apps.attendance.models import (
            DailyAttendance,
            AttendanceSummary,
            LeaveApplication,
        )

        attendance_data = {
            "daily_attendance": DailyAttendance.objects.filter(
                student=student
            ).order_by("-date")[
                :30
            ],  # Last 30 days
            "attendance_summaries": AttendanceSummary.objects.filter(
                student=student
            ).order_by("-year", "-month")[
                :12
            ],  # Last 12 months
            "leave_applications": LeaveApplication.objects.filter(
                applicant=user
            ).order_by("-created_at")[
                :5
            ],  # Recent leave applications
        }

    # ===== TEACHER-SPECIFIC DATA =====
    elif hasattr(user, "teacher_profile") and user.teacher_profile:
        teacher = user.teacher_profile

        # Academic Information for Teachers
        academic_data = {
            "teacher_profile": teacher,
            "subjects_taught": teacher.subjects_taught,
            "current_classes": teacher.current_classes,
            "counseling_sessions": [],  # Will populate below
            "career_guidance": [],  # Will populate below
        }

        # Counseling and Career Guidance
        from apps.academics.models import CounselingSession, CareerGuidance

        academic_data["counseling_sessions"] = (
            CounselingSession.objects.filter(counselor=teacher)
            .select_related("student")
            .order_by("-scheduled_date")[:10]
        )

        academic_data["career_guidance"] = (
            CareerGuidance.objects.filter(counselor=teacher)
            .select_related("student")
            .order_by("-session_date")[:10]
        )

    # ===== PARENT-SPECIFIC DATA =====
    if user.has_perm("academics.view_student") or has_role_or_perm(
        user, perm="academics.view_student", role_type="parent"
    ):
        from apps.users.models import ParentStudentRelationship

        relationships_data = {
            "children": ParentStudentRelationship.objects.filter(
                parent=user, status="active"
            ).select_related("student__user"),
        }

    # ===== SYSTEM ACTIVITY DATA (All Users) =====
    activity_data = {
        "login_history": LoginHistory.objects.filter(user=user).order_by("-created_at")[
            :10
        ],
        "password_history": user.password_history.order_by("-created_at")[:5],
        "transfer_requests": InstitutionTransferRequest.objects.filter(
            requesting_user=user
        ).order_by("-created_at")[:5],
        "role_activities": user.role_activities.all().order_by("-created_at")[:10],
    }

    # ===== ADDITIONAL APP DATA =====
    try:
        # Finance data
        from apps.finance.models import Invoice, Payment

        pending_invoices = Invoice.objects.filter(
            student__user=user, status__in=["issued", "overdue"]
        ).order_by("-issue_date")[:5]
        finance_data = {
            "pending_invoices": pending_invoices,
            "recent_payments": Payment.objects.filter(student__user=user)
            .select_related("invoice")
            .order_by("-payment_date")[:5],
            "total_outstanding": pending_invoices.aggregate(total=Sum("balance_due"))[
                "total"
            ]
            or 0,
        }
    except ImportError:
        finance_data = {}

    try:
        # Library data
        from apps.library.models import BookBorrow

        current_borrows = (
            BookBorrow.objects.filter(student__user=user, return_date__isnull=True)
            .select_related("book")
            .order_by("-borrow_date")[:10]
        )

        # Calculate overdue books count
        overdue_count = BookBorrow.objects.filter(
            student__user=user, return_date__isnull=True, due_date__lt=timezone.now()
        ).count()

        library_data = {
            "current_borrows": current_borrows,
            "overdue_books": overdue_count,
        }
    except ImportError:
        library_data = {}

    try:
        # Health data
        from apps.health.models import MedicalRecord

        health_data = {
            "medical_records": MedicalRecord.objects.filter(
                student__user=user
            ).order_by("-visit_date")[:5],
        }
    except ImportError:
        health_data = {}

    try:
        # Transport data
        from apps.transport.models import TransportEnrollment

        transport_data = {
            "transport_enrollment": TransportEnrollment.objects.filter(
                student__user=user, is_active=True
            ).first(),
        }
    except ImportError:
        transport_data = {}

    # ===== FORM HANDLING =====
    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()

            # Log profile update
            AuditLog.objects.create(
                user=user,
                action=AuditLog.ActionType.UPDATE,
                model_name="users.UserProfile",
                object_id=str(profile.id),
                ip_address=get_client_ip(request),
                details={"action": "Profile updated"},
            )

            messages.success(request, _("Profile updated successfully!"))
            return redirect("users:profile")
    else:
        user_form = UserUpdateForm(instance=user)
        profile_form = UserProfileForm(instance=profile)

    # Determine status badge for application
    application_status_badge = "secondary"
    if student_application:
        application_status = student_application.get_application_status_display()
        if student_application.application_status == "approved":
            application_status_badge = "success"
        elif student_application.application_status in ["pending", "under_review"]:
            application_status_badge = "warning"
        elif student_application.application_status == "rejected":
            application_status_badge = "danger"
    elif staff_application:
        application_status = staff_application.get_application_status_display()
        if staff_application.application_status == "approved":
            application_status_badge = "success"
        elif staff_application.application_status in [
            "pending",
            "under_review",
            "interview_scheduled",
        ]:
            application_status_badge = "warning"
        elif staff_application.application_status == "rejected":
            application_status_badge = "danger"

    context = {
        "title": _("My Profile"),
        "user_form": user_form,
        "profile_form": profile_form,
        "active_tab": "profile",
        "student_application": student_application,
        "staff_application": staff_application,
        "application_status_badge": application_status_badge,
        # New comprehensive data
        "academic_data": academic_data,
        "assessment_data": assessment_data,
        "attendance_data": attendance_data,
        "activity_data": activity_data,
        "relationships_data": relationships_data,
        "finance_data": finance_data,
        "library_data": library_data,
        "health_data": health_data,
        "transport_data": transport_data,
        # Helper flags for template rendering
        "has_student_data": bool(academic_data.get("student_profile")),
        "has_teacher_data": bool(academic_data.get("teacher_profile")),
        "has_parent_data": bool(relationships_data.get("children")),
        "has_academic_data": bool(academic_data),
        "has_assessment_data": any(assessment_data.values()),
        "has_attendance_data": any(attendance_data.values()),
        "has_activity_data": any(activity_data.values()),
        "has_finance_data": any(finance_data.values()),
        "has_library_data": any(library_data.values()),
        "has_health_data": any(health_data.values()),
        "has_transport_data": any(transport_data.values()),
    }
    return render(request, "users/profile/profile.html", context)


@login_required
def password_change_view(request):
    """
    Custom password change view.
    """
    if request.method == "POST":
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            # Log before change
            old_password_hash = request.user.password

            # Save the password change
            user = form.save()

            # Force refresh from database to ensure changes are persisted
            user.refresh_from_db()

            # Verify password actually changed
            new_password_hash = user.password
            password_changed = old_password_hash != new_password_hash

            logger.info(
                f"Password change attempt for user {user.email}: form valid, password_changed={password_changed}"
            )

            if password_changed:
                # Create password history entry
                PasswordHistory.objects.create(
                    user=user,
                    password_hash=new_password_hash,
                    changed_by=user,
                    change_reason="regular",
                )

                # Log password change
                AuditLog.objects.create(
                    user=user,
                    action=AuditLog.ActionType.UPDATE,
                    model_name="users.User",
                    object_id=str(user.id),
                    ip_address=get_client_ip(request),
                    details={"action": "Password changed"},
                )

                # Send confirmation email
                send_password_change_email(user, request)

                messages.success(request, _("Password changed successfully!"))
                return redirect("users:profile")
            else:
                logger.error(
                    f"Password change failed for user {user.email}: password hash did not change"
                )
                messages.error(request, _("Password change failed. Please try again."))
        else:
            logger.warning(
                f"Password change form invalid for user {request.user.email}: {form.errors}"
            )
    else:
        form = CustomPasswordChangeForm(request.user)

    # Get password history for template (if exists)
    try:
        password_history = request.user.password_history.last()
        last_changed_time = password_history.changed_at if password_history else None
    except Exception:
        last_changed_time = None

    context = {
        "title": _("Change Password"),
        "form": form,
        "active_tab": "password",
        "last_changed_time": last_changed_time,
    }
    return render(request, "users/profile/password_change.html", context)


# =============================================================================
# ADMIN USER MANAGEMENT VIEWS
# =============================================================================


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def user_list(request):
    """
    List all users with filtering and search capabilities.
    """
    # Filter users by institution for multitenancy
    current_user_institution = request.user.current_institution
    if request.user.is_superuser:
        # Superusers can see all users
        users = (
            User.objects.all()
            .select_related("profile")
            .prefetch_related("user_roles__role")
            .distinct()
        )
    elif current_user_institution:
        users = (
            User.objects.filter(
                institution_memberships__institution=current_user_institution,
                institution_memberships__is_primary=True,
            )
            .select_related("profile")
            .prefetch_related("user_roles__role")
            .distinct()
        )
    else:
        # Fallback for staff users without primary institution
        # Try to get users from any institution they belong to
        from apps.core.models import InstitutionUser

        accessible_institution_ids = InstitutionUser.objects.filter(
            user=request.user, institution__is_active=True
        ).values_list("institution_id", flat=True)

        if accessible_institution_ids:
            users = (
                User.objects.filter(
                    institution_memberships__institution_id__in=accessible_institution_ids,
                    institution_memberships__is_primary=True,
                )
                .select_related("profile")
                .prefetch_related("user_roles__role")
                .distinct()
            )
        else:
            users = User.objects.none()

    # Filtering
    role_filter = request.GET.get("role")
    status_filter = request.GET.get("status")
    search_query = request.GET.get("q")

    if role_filter:
        users = users.filter(user_roles__role__role_type=role_filter)

    if status_filter:
        users = users.filter(is_active=bool(status_filter == "active"))

    if search_query:
        users = users.filter(
            Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(mobile__icontains=search_query)
        )

    # Also filter roles by institution if they've been scoped
    try:
        from apps.core.middleware import get_user_accessible_institutions

        if request.user.is_superuser:
            roles = Role.objects.all()
        else:
            accessible_insts = get_user_accessible_institutions(request.user)
            roles = Role.objects.filter(institution__in=accessible_insts)
    except Exception:
        roles = Role.objects.all()

    context = {
        "title": _("User Management"),
        "users": users.distinct(),
        "roles": roles,
        "active_tab": "users",
    }
    return render(request, "users/admin/users/user_list.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_create(request):
    """
    Create new user (admin only).
    """
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Log user creation
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.ActionType.CREATE,
                model_name="users.User",
                object_id=str(user.id),
                ip_address=get_client_ip(request),
                details={"action": "User created by admin"},
            )

            messages.success(request, _("User created successfully!"))
            return redirect("users:user_list")
    else:
        form = UserCreationForm()

    context = {
        "title": _("Create User"),
        "form": form,
        "active_tab": "users",
    }
    return render(request, "users/admin/users/user_form.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def user_detail(request, user_id):
    """
    User detail view with all related information.
    """
    # Superusers can access all users, staff users can only access users from their institution
    if request.user.is_superuser:
        user = get_object_or_404(User, id=user_id)
    else:
        user = get_object_or_404(
            User.objects.filter(
                institution_memberships__institution=request.user.current_institution,
                institution_memberships__is_primary=True,
            ),
            id=user_id,
        )

    # Security check - staff can view some actions, superuser can edit all
    can_edit = request.user.is_superuser or request.user.is_staff

    # Get recent login history
    recent_logins = LoginHistory.objects.filter(user=user).order_by("-created_at")[:5]

    # Get user's application data if it exists
    try:
        student_application = user.student_application
    except User.student_application.RelatedObjectDoesNotExist:
        student_application = None

    try:
        staff_application = user.staff_application
    except User.staff_application.RelatedObjectDoesNotExist:
        staff_application = None

    # Determine status badge for application
    application_status_badge = "secondary"
    if student_application:
        if student_application.application_status == "approved":
            application_status_badge = "success"
        elif student_application.application_status in ["pending", "under_review"]:
            application_status_badge = "warning"
        elif student_application.application_status == "rejected":
            application_status_badge = "danger"
        else:
            application_status_badge = "secondary"
    elif staff_application:
        if staff_application.application_status == "approved":
            application_status_badge = "success"
        elif staff_application.application_status in [
            "pending",
            "under_review",
            "interview_scheduled",
        ]:
            application_status_badge = "warning"
        elif staff_application.application_status == "rejected":
            application_status_badge = "danger"
        else:
            application_status_badge = "secondary"

    context = {
        "title": _("User Details"),
        "user_obj": user,
        "can_edit": can_edit,
        "active_tab": "users",
        "recent_logins": recent_logins,
        "student_application": student_application,
        "staff_application": staff_application,
        "application_status_badge": application_status_badge,
    }
    return render(request, "users/admin/users/user_detail.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_update(request, user_id):
    """
    Update user information (superuser only).
    """
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()

            # Log user update
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.ActionType.UPDATE,
                model_name="users.User",
                object_id=str(user.id),
                ip_address=get_client_ip(request),
                details={"action": "User updated by admin"},
            )

            messages.success(request, _("User updated successfully!"))
            return redirect("users:user_detail", user_id=user.id)
    else:
        form = UserUpdateForm(instance=user)

    context = {
        "title": _("Edit User"),
        "form": form,
        "user_obj": user,
        "active_tab": "users",
    }
    return render(request, "users/admin/users/user_form.html", context)


@login_required
@user_passes_test(can_assign_roles)
def user_roles_manage(request, user_id):
    """
    Manage user roles and assignments.
    """
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        form = UserRoleAssignmentForm(request.POST)
        if form.is_valid():
            user_role = form.save(commit=False)
            user_role.user = user

            # Set audit context
            user_role._audit_user = request.user
            user_role._audit_ip = get_client_ip(request)
            user_role._audit_user_agent = request.META.get("HTTP_USER_AGENT", "")

            user_role.save()

            # Log the activity
            UserRoleActivity.log_activity(
                user=user,
                role=user_role.role,
                action_type=UserRoleActivity.ActionType.ASSIGNED,
                performed_by=request.user,
                academic_session=user_role.academic_session,
                details=f"Role assigned to user {user.display_name}",
            )

            messages.success(request, _("Role assigned successfully!"))
            return redirect("users:user_roles_manage", user_id=user.id)
    else:
        form = UserRoleAssignmentForm()

    # Get user roles
    user_roles = user.user_roles.all().select_related("role", "academic_session")

    # Calculate effective permissions from active roles
    effective_permissions = set()
    for user_role in user_roles.filter(status="active"):
        permissions = user_role.role.permissions.all()
        effective_permissions.update(perm.codename for perm in permissions)
    effective_permissions = list(effective_permissions)

    # Get roles available for quick assignment
    quick_roles = Role.objects.filter(status="active", is_system_role=False)

    # Calculate role statistics
    primary_roles_count = user_roles.filter(is_primary=True).count()
    active_roles_count = user_roles.filter(status="active").count()
    inactive_roles_count = user_roles.filter(status="inactive").count()

    context = {
        "title": _("Manage User Roles"),
        "target_user": user,
        "form": form,
        "user_roles": user_roles,
        "effective_permissions": effective_permissions,
        "quick_roles": quick_roles,
        "primary_roles_count": primary_roles_count,
        "active_roles_count": active_roles_count,
        "inactive_roles_count": inactive_roles_count,
        "active_tab": "users",
    }
    return render(request, "users/admin/users/user_roles.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_role_set_primary(request, user_id):
    """
    Set a user role as primary.
    """
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        user_role_id = request.POST.get("user_role_id")
        try:
            user_role = get_object_or_404(UserRole, id=user_role_id, user=user)

            # Set audit context
            user_role._audit_user = request.user
            user_role._audit_ip = get_client_ip(request)
            user_role._audit_user_agent = request.META.get("HTTP_USER_AGENT", "")

            user_role.is_primary = True
            user_role.save()

            # Log the activity
            UserRoleActivity.log_activity(
                user=user,
                role=user_role.role,
                action_type=UserRoleActivity.ActionType.SET_PRIMARY,
                performed_by=request.user,
                academic_session=user_role.academic_session,
                details=f"Set as primary role for user {user.display_name}",
            )

            messages.success(request, _("Role set as primary successfully!"))
        except Exception as e:
            logger.error(f"Error setting role as primary: {e}")
            messages.error(request, _("Error setting role as primary."))

    return redirect("users:user_roles_manage", user_id=user.id)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_role_set_secondary(request, user_id):
    """
    Set a user role as secondary.
    """
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        user_role_id = request.POST.get("user_role_id")
        try:
            user_role = get_object_or_404(UserRole, id=user_role_id, user=user)

            # Set audit context
            user_role._audit_user = request.user
            user_role._audit_ip = get_client_ip(request)
            user_role._audit_user_agent = request.META.get("HTTP_USER_AGENT", "")

            user_role.is_primary = False
            user_role.save()

            # Log the activity
            UserRoleActivity.log_activity(
                user=user,
                role=user_role.role,
                action_type=UserRoleActivity.ActionType.SET_SECONDARY,
                performed_by=request.user,
                academic_session=user_role.academic_session,
                details=f"Set as secondary role for user {user.display_name}",
            )

            messages.success(request, _("Role set as secondary successfully!"))
        except Exception as e:
            logger.error(f"Error setting role as secondary: {e}")
            messages.error(request, _("Error setting role as secondary."))

    return redirect("users:user_roles_manage", user_id=user.id)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_role_remove(request, user_id):
    """
    Remove a role from a user.
    """
    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        user_role_id = request.POST.get("user_role_id")
        try:
            user_role = get_object_or_404(UserRole, id=user_role_id, user=user)
            role_name = user_role.role.name

            # Set audit context
            user_role._audit_user = request.user
            user_role._audit_ip = get_client_ip(request)
            user_role._audit_user_agent = request.META.get("HTTP_USER_AGENT", "")

            # Log the activity before deleting
            UserRoleActivity.log_activity(
                user=user,
                role=user_role.role,
                action_type=UserRoleActivity.ActionType.REMOVED,
                performed_by=request.user,
                academic_session=user_role.academic_session,
                details=f"Role removed from user {user.display_name}",
            )

            user_role.delete()

            # Check if request is AJAX
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                # Calculate updated statistics
                user_roles = user.user_roles.all()
                primary_roles_count = user_roles.filter(is_primary=True).count()
                active_roles_count = user_roles.filter(status="active").count()
                inactive_roles_count = user_roles.filter(status="inactive").count()

                # Calculate effective permissions
                effective_permissions = set()
                for ur in user_roles.filter(status="active"):
                    permissions = ur.role.permissions.all()
                    effective_permissions.update(perm.codename for perm in permissions)
                effective_permissions = list(effective_permissions)

                return JsonResponse(
                    {
                        "success": True,
                        "message": _('Role "{}" removed successfully!').format(
                            role_name
                        ),
                        "statistics": {
                            "total": user_roles.count(),
                            "primary": primary_roles_count,
                            "active": active_roles_count,
                            "inactive": inactive_roles_count,
                        },
                        "permissions": effective_permissions[
                            :10
                        ],  # Limit for performance
                        "permissions_count": len(effective_permissions),
                    }
                )

            messages.success(
                request, _('Role "{}" removed successfully!').format(role_name)
            )
        except Exception as e:
            logger.error(f"Error removing role: {e}")

            # Check if request is AJAX for error response
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "message": _("Error removing role.")}, status=400
                )

            messages.error(request, _("Error removing role."))

    return redirect("users:user_roles_manage", user_id=user.id)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_toggle_status(request, user_id):
    """
    Activate/Deactivate user account.
    """
    user = get_object_or_404(User, id=user_id)

    if user.is_active:
        user.is_active = False
        action = "deactivated"
    else:
        user.is_active = True
        action = "activated"

    user.save()

    # Log status change
    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.ActionType.UPDATE,
        model_name="users.User",
        object_id=str(user.id),
        ip_address=get_client_ip(request),
        details={"action": f"User {action}"},
    )

    messages.success(request, _(f"User {action} successfully!"))
    return redirect("users:user_detail", user_id=user.id)


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.user_roles.filter(
        role__role_type__in=["admin", "principal"], status="active"
    ).exists()
)
def user_delete(request, user_id):
    """
    Permanently delete a user account (superuser and school admin only).
    """
    user_to_delete = get_object_or_404(User, id=user_id)

    # Prevent self-deletion
    if request.user.id == user_to_delete.id:
        messages.error(request, _("You cannot delete your own account."))
        return redirect("users:user_detail", user_id=user_id)

    # Additional safety check for superusers
    if user_to_delete.is_superuser and not request.user.is_superuser:
        messages.error(
            request, _("Only superusers can delete other superuser accounts.")
        )
        return redirect("users:user_detail", user_id=user_id)

    if request.method == "POST":
        try:
            # Store user details for logging before deletion
            user_name = user_to_delete.display_name
            user_email = user_to_delete.email
            user_id_deleted = user_to_delete.id

            # Check for related academic records that will be affected
            related_models = []
            try:
                from apps.academics.models import Student

                if Student.objects.filter(user=user_to_delete).exists():
                    related_models.append("Student profile")
            except:
                pass

            try:
                from apps.academics.models import Teacher

                if Teacher.objects.filter(user=user_to_delete).exists():
                    related_models.append("Teacher profile")
            except:
                pass

            # Log the deletion with details
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.ActionType.DELETE,
                model_name="users.User",
                object_id=str(user_id_deleted),
                ip_address=get_client_ip(request),
                details={
                    "action": "User account permanently deleted",
                    "deleted_user_name": user_name,
                    "deleted_user_email": user_email,
                    "related_models_affected": related_models,
                },
            )

            # Delete the user (cascading delete will handle related data)
            user_to_delete.delete()

            # Add message warning about cascade effects
            if related_models:
                messages.success(
                    request,
                    _(
                        f'User "{user_name}" and associated {", ".join(related_models)} have been permanently deleted.'
                    ),
                )
            else:
                messages.success(
                    request, _(f'User "{user_name}" has been permanently deleted.')
                )

            return redirect("users:user_list")

        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            messages.error(
                request,
                _("An error occurred while deleting the user. Please try again."),
            )

    return redirect("users:user_detail", user_id=user_id)


# =============================================================================
# APPLICATION MANAGEMENT VIEWS
# =============================================================================


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.has_perm("users.approve_applications")
    or u.user_roles.filter(role__role_type="admin", status="active").exists()
)
def pending_applications(request):
    """
    View and manage pending applications.
    """
    student_applications = (
        StudentApplication.objects.filter(
            application_status__in=["pending", "under_review"]
        )
        .select_related("academic_session")
        .order_by("-application_date")
    )

    staff_applications = (
        StaffApplication.objects.filter(
            application_status__in=["pending", "under_review"]
        )
        .select_related("position_applied_for", "academic_session")
        .order_by("-application_date")
    )

    context = {
        "title": _("Pending Applications"),
        "student_applications": student_applications,
        "staff_applications": staff_applications,
        "active_tab": "applications",
    }
    return render(
        request, "users/admin/applications/pending_applications.html", context
    )


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.has_perm("users.approve_applications")
    or u.user_roles.filter(role__role_type="admin", status="active").exists()
)
def approve_application(request, application_id, application_type):
    """
    Approve an application and create user account.
    Supports both AJAX and regular POST requests.
    """
    try:
        with transaction.atomic():
            logger.info(
                f"Starting approval process for {application_type} application {application_id}"
            )

            if application_type == "student":
                application = get_object_or_404(StudentApplication, id=application_id)
                logger.info(f"Found student application: {application}")
                user, temporary_password = create_user_from_student_application(
                    application, request.user
                )

            elif application_type == "staff":
                application = get_object_or_404(StaffApplication, id=application_id)
                logger.info(f"Found staff application: {application}")
                user, temporary_password = create_user_from_staff_application(
                    application, request.user
                )

            else:
                error_msg = _("Invalid application type.")
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {"success": False, "message": error_msg}, status=400
                    )
                messages.error(request, error_msg)
                return redirect("users:pending_applications")

            # Update application status
            application.application_status = "approved"
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.user_account = user
            application.save()

            logger.info(
                f"Application approved successfully, user created: {user.email}"
            )

            # Log approval
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.ActionType.UPDATE,
                model_name=f"users.{application_type.capitalize()}Application",
                object_id=str(application.id),
                ip_address=get_client_ip(request),
                details={
                    "action": "Application approved",
                    "application_number": application.application_number,
                    "user_created_id": str(user.id),
                },
            )

            # Send approval email to student
            send_approval_email(request, application, user, temporary_password)

            # Send approval notification emails to parents
            if application_type == "student":
                # Find parents for this student
                parent_relationships = ParentStudentRelationship.objects.filter(
                    student=user, status="active"
                ).select_related("parent")

                for relationship in parent_relationships:
                    try:
                        send_parent_approval_email(
                            request, application, user, relationship.parent
                        )
                        logger.info(
                            f"Parent approval email sent to {relationship.parent.email}"
                        )
                    except Exception as parent_email_error:
                        logger.error(
                            f"Failed to send parent approval email to {relationship.parent.email}: {parent_email_error}"
                        )

            success_msg = _("Application approved and user account created!")

            # Handle AJAX request
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "message": success_msg,
                        "application_id": str(application.id),
                        "user_email": user.email,
                    }
                )

            messages.success(request, success_msg)

    except Exception as e:
        logger.error(f"Error approving application {application_id}: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        error_msg = _("Error approving application. Please try again.")

        # Handle AJAX request
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": False, "message": error_msg}, status=500)

        messages.error(request, error_msg)

    return redirect("users:pending_applications")


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.has_perm("users.approve_applications")
    or u.user_roles.filter(role__role_type="admin", status="active").exists()
)
def reject_application(request, application_id, application_type):
    """
    Reject an application with reason.
    """
    if request.method == "POST":
        review_notes = request.POST.get("review_notes", "")

        try:
            with transaction.atomic():
                if application_type == "student":
                    application = get_object_or_404(
                        StudentApplication, id=application_id
                    )
                elif application_type == "staff":
                    application = get_object_or_404(StaffApplication, id=application_id)
                else:
                    messages.error(request, _("Invalid application type."))
                    return redirect("users:pending_applications")

                # Update application status
                application.application_status = "rejected"
                application.reviewed_by = request.user
                application.reviewed_at = timezone.now()
                application.review_notes = review_notes
                application.save()

                # Log rejection
                AuditLog.objects.create(
                    user=request.user,
                    action=AuditLog.ActionType.UPDATE,
                    model_name=f"users.{application_type.capitalize()}Application",
                    object_id=str(application.id),
                    ip_address=get_client_ip(request),
                    details={
                        "action": "Application rejected",
                        "application_number": application.application_number,
                        "review_notes": review_notes[:100],  # First 100 chars
                    },
                )

                # Send rejection email
                send_rejection_email(application, review_notes)

                messages.success(request, _("Application rejected successfully."))

        except Exception as e:
            logger.error(f"Error rejecting application {application_id}: {e}")
            messages.error(request, _("Error rejecting application. Please try again."))

    return redirect("users:pending_applications")


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.has_perm("users.approve_applications")
    or u.user_roles.filter(role__role_type="admin", status="active").exists()
)
def mark_application_under_review(request, application_id, application_type):
    """
    Mark an application as 'under_review' with optional notes.
    """
    if request.method == "POST":
        review_notes = request.POST.get("review_notes", "")

        try:
            with transaction.atomic():
                if application_type == "student":
                    application = get_object_or_404(
                        StudentApplication, id=application_id
                    )
                elif application_type == "staff":
                    application = get_object_or_404(StaffApplication, id=application_id)
                else:
                    messages.error(request, _("Invalid application type."))
                    return redirect("users:pending_applications")

                # Update application status
                application.application_status = "under_review"
                application.reviewed_by = request.user
                application.reviewed_at = timezone.now()
                application.review_notes = review_notes
                application.save()

                # Log the action
                AuditLog.objects.create(
                    user=request.user,
                    action=AuditLog.ActionType.UPDATE,
                    model_name=f"users.{application_type.capitalize()}Application",
                    object_id=str(application.id),
                    ip_address=get_client_ip(request),
                    details={
                        "action": "Application marked under review",
                        "application_number": application.application_number,
                        "review_notes": review_notes[:100],  # First 100 chars
                    },
                )

                messages.success(
                    request, _('Application marked as "Under Review" successfully.')
                )

        except Exception as e:
            logger.error(
                f"Error marking application {application_id} under review: {e}"
            )
            messages.error(
                request, _("Error marking application under review. Please try again.")
            )

    return redirect("users:pending_applications")


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.has_perm("users.approve_applications")
    or u.user_roles.filter(role__role_type="admin", status="active").exists()
)
def schedule_interview(request, application_id):
    """
    Schedule interview for a staff application.
    """
    application = get_object_or_404(StaffApplication, id=application_id)

    if request.method == "POST":
        from .forms import InterviewScheduleForm

        form = InterviewScheduleForm(request.POST)

        if form.is_valid():
            interview_date = form.cleaned_data["interview_date"]
            review_notes = form.cleaned_data["review_notes"]

            try:
                with transaction.atomic():
                    # Update application with interview details
                    application.interview_date = interview_date
                    application.review_notes = review_notes
                    application.reviewed_by = request.user
                    application.reviewed_at = timezone.now()
                    application.save()

                    # Log the interview scheduling
                    AuditLog.objects.create(
                        user=request.user,
                        action=AuditLog.ActionType.UPDATE,
                        model_name="users.StaffApplication",
                        object_id=str(application.id),
                        ip_address=get_client_ip(request),
                        details={
                            "action": "Interview scheduled",
                            "application_number": application.application_number,
                            "interview_date": str(interview_date),
                            "review_notes": (
                                review_notes[:100] if review_notes else ""
                            ),  # First 100 chars
                        },
                    )

                    # Send interview scheduling email
                    send_interview_email(
                        application, interview_date, review_notes, request.user
                    )

                    messages.success(request, _("Interview scheduled successfully."))
                    return redirect("users:pending_applications")

            except Exception as e:
                logger.error(
                    f"Error scheduling interview for application {application_id}: {e}"
                )
                messages.error(
                    request, _("Error scheduling interview. Please try again.")
                )

        else:
            # Form has errors, fall through to show form again
            pass

    else:
        from .forms import InterviewScheduleForm

        form = InterviewScheduleForm()

    # For GET request or invalid form, show the form
    context = {
        "title": _("Schedule Interview"),
        "form": form,
        "application": application,
        "active_tab": "applications",
    }

    return render(request, "users/admin/applications/schedule_interview.html", context)


# =============================================================================
# ROLE MANAGEMENT VIEWS
# =============================================================================


@login_required
@user_passes_test(lambda u: u.is_superuser)
def role_list(request):
    """
    List all roles in the system.
    """
    roles = Role.objects.all().prefetch_related("permissions")

    # Calculate statistics
    system_roles_count = roles.filter(is_system_role=True).count()
    user_roles_count = roles.filter(is_system_role=False).count()

    # Get recent role activity
    from .models import UserRoleActivity

    recent_activities = UserRoleActivity.objects.select_related(
        "user", "role", "performed_by", "academic_session"
    ).order_by("-created_at")[:15]

    context = {
        "title": _("Role Management"),
        "roles": roles,
        "system_roles_count": system_roles_count,
        "user_roles_count": user_roles_count,
        "recent_activities": recent_activities,
        "active_tab": "roles",
    }
    return render(request, "users/admin/roles/role_list.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def role_create(request):
    """
    Create new role or edit existing role.
    """
    role = None
    editing = False
    edit_id = request.GET.get("edit")

    if edit_id:
        try:
            role = Role.objects.get(id=edit_id)
            editing = True
        except Role.DoesNotExist:
            messages.error(request, _("Role not found."))
            return redirect("users:role_list")

    if request.method == "POST":
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            saved_role = form.save()
            action = AuditLog.ActionType.UPDATE if role else AuditLog.ActionType.CREATE
            message_key = (
                _("Role updated successfully!")
                if role
                else _("Role created successfully!")
            )

            # Log role creation/update
            AuditLog.objects.create(
                user=request.user,
                action=action,
                model_name="users.Role",
                object_id=str(saved_role.id),
                ip_address=get_client_ip(request),
            )

            messages.success(request, message_key)
            return redirect("users:role_list")
    else:
        form = RoleForm(instance=role)

    context = {
        "title": _("Edit Role") if role else _("Create Role"),
        "form": form,
        "role": role,
        "role_permissions": (
            list(role.permissions.values_list("codename", flat=True)) if role else []
        ),
        "active_tab": "roles",
    }
    return render(request, "users/admin/roles/role_form.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def role_delete(request, role_id):
    """
    Delete a role (superuser only).
    """
    role = get_object_or_404(Role, id=role_id)

    # Prevent deletion of system roles
    if role.is_system_role:
        messages.error(request, _("System roles cannot be deleted."))
        return redirect("users:role_list")

    # Check if role has users assigned
    user_count = UserRole.objects.filter(role=role).count()
    if user_count > 0:
        messages.error(
            request,
            _(
                "Cannot delete role because it is assigned to {} user(s). Please remove the role from all users first."
            ).format(user_count),
        )
        return redirect("users:role_list")

    if request.method == "POST":
        try:
            role_name = role.name
            role.delete()

            # Log role deletion
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.ActionType.DELETE,
                model_name="users.Role",
                object_id=role_id,
                ip_address=get_client_ip(request),
                details={"action": "Role deleted", "role_name": role_name},
            )

            messages.success(request, _("Role deleted successfully!"))
        except Exception as e:
            logger.error(f"Error deleting role {role_id}: {e}")
            messages.error(request, _("Error deleting role. Please try again."))

    return redirect("users:role_list")


# =============================================================================
# PARENT-STUDENT RELATIONSHIP VIEWS
# =============================================================================


@login_required
def parent_student_relationships(request):
    """
    View and manage parent-student relationships.
    """
    if request.user.has_perm("academics.view_student") or has_role_or_perm(
        request.user, perm="academics.view_student", role_type="parent"
    ):
        # Parent view - show their children
        relationships = ParentStudentRelationship.objects.filter(parent=request.user)
    elif (
        request.user.has_perm("academics.view_student")
        or request.user.user_roles.filter(role__role_type="student").exists()
    ):
        if has_role_or_perm(
            request.user, perm="academics.view_enrollment", role_type="student"
        ):
            pass
    else:
        # Admin/staff view - show relationships within user's accessible institutions
        from apps.core.middleware import get_user_accessible_institutions

        if request.user.is_superuser:
            relationships = ParentStudentRelationship.objects.all()
        else:
            accessible_insts = get_user_accessible_institutions(request.user)
            relationships = ParentStudentRelationship.objects.filter(
                institution__in=accessible_insts
            )

    context = {
        "title": _("Parent-Student Relationships"),
        "relationships": relationships.select_related("parent", "student"),
        "active_tab": "relationships",
    }
    return render(
        request, "users/relationships/parent_student_relationships.html", context
    )


# =============================================================================
# PARENT PORTAL VIEWS
# =============================================================================


class ParentRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a parent."""

    def test_func(self):
        return self.request.user.has_perm("academics.view_student") or has_role_or_perm(
            self.request.user, perm="academics.view_student", role_type="parent"
        )

    def handle_no_permission(self):
        messages.error(
            self.request, _("You don't have permission to access this page.")
        )
        return redirect("users:dashboard")


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_student")
    or has_role_or_perm(u, perm="academics.view_student", role_type="parent"),
    login_url=reverse_lazy("users:dashboard"),
)
def parent_dashboard(request):
    """
    Parent dashboard showing overview of all children.
    """
    # Get all children linked to this parent
    children_relationships = ParentStudentRelationship.objects.filter(
        parent=request.user, status="active"
    ).select_related("student__user", "student__student_profile")

    children = []
    for relationship in children_relationships:
        child = relationship.student

        # Get current class enrollment
        current_enrollment = (
            child.enrollments.filter(
                academic_session__is_current=True, enrollment_status="active"
            )
            .select_related("class_enrolled")
            .first()
        )

        # Get current attendance percentage
        current_session = AcademicSession.objects.filter(is_current=True).first()
        attendance_percentage = None
        if current_session:
            from apps.attendance.models import AttendanceSummary

            try:
                attendance_summary = AttendanceSummary.objects.get(
                    student=child,
                    academic_session=current_session,
                    month=timezone.now().month,
                    year=timezone.now().year,
                )
                attendance_percentage = attendance_summary.attendance_percentage
            except AttendanceSummary.DoesNotExist:
                # Calculate from daily attendance if summary doesn't exist
                from apps.attendance.models import DailyAttendance
                from django.db.models import Q

                current_month_attendance = DailyAttendance.objects.filter(
                    student=child,
                    date__year=timezone.now().year,
                    date__month=timezone.now().month,
                    attendance_session__academic_session=current_session,
                )
                if current_month_attendance.exists():
                    total_days = current_month_attendance.count()
                    present_days = current_month_attendance.filter(
                        Q(status="present") | Q(status="late") | Q(status="half_day")
                    ).count()
                    if total_days > 0:
                        attendance_percentage = round(
                            (present_days / total_days) * 100, 1
                        )

        # Get latest grade from results
        latest_result = None
        latest_grade = None
        from apps.assessment.models import Result

        try:
            latest_result = (
                Result.objects.filter(
                    student=child, academic_class__academic_session__is_current=True
                )
                .select_related("grade")
                .order_by("-created_at")
                .first()
            )
            if latest_result and latest_result.grade:
                latest_grade = latest_result.grade.grade
        except:
            pass

        # Get pending fees
        pending_fees = 0
        if current_session:
            from apps.finance.models import Invoice

            pending_invoices = Invoice.objects.filter(
                student=child,
                academic_session=current_session,
                status__in=["issued", "partial", "overdue"],
            )
            pending_fees = sum(
                float(invoice.balance_due) for invoice in pending_invoices
            )

        # Get recent notifications for this child
        from apps.communication.models import RealTimeNotification

        child_notifications = RealTimeNotification.objects.filter(
            recipient=request.user,
            content_type__model="student",
            object_id=str(child.id),
        ).order_by("-created_at")[:3]

        children.append(
            {
                "student": child,
                "relationship": relationship,
                "current_class": (
                    current_enrollment.class_enrolled if current_enrollment else None
                ),
                "current_attendance_percentage": attendance_percentage,
                "latest_grade": latest_grade,
                "pending_fees": pending_fees,
                "recent_notifications": child_notifications,
            }
        )

    # Get recent general notifications for parent
    from apps.communication.models import RealTimeNotification

    recent_notifications = RealTimeNotification.objects.filter(
        recipient=request.user
    ).order_by("-created_at")[:5]

    # Get unread notification count
    unread_count = RealTimeNotification.objects.filter(
        recipient=request.user, is_read=False
    ).count()

    context = {
        "title": _("Parent Dashboard"),
        "children": children,
        "recent_notifications": recent_notifications,
        "unread_count": unread_count,
    }
    return render(request, "users/dashboard/parent_dashboard.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_student")
    or has_role_or_perm(u, perm="academics.view_student", role_type="parent"),
    login_url=reverse_lazy("users:dashboard"),
)
def child_academic_records(request, child_id):
    """
    View child's academic records.
    """
    # Verify parent has access to this child
    try:
        relationship = ParentStudentRelationship.objects.get(
            parent=request.user, student_id=child_id, status="active"
        )
        child = relationship.student
    except ParentStudentRelationship.DoesNotExist:
        messages.error(
            request, _("You don't have permission to view this child's records.")
        )
        return redirect("users:dashboard")

    # Get academic records (same logic as student view)
    academic_records = (
        AcademicRecord.objects.filter(student=child)
        .select_related("class_enrolled", "academic_session")
        .order_by("-academic_session__start_date")
    )

    # Get detailed marks
    from apps.assessment.models import Mark, Result, ResultSubject

    marks = (
        Mark.objects.filter(student=child)
        .select_related("exam", "exam__subject", "exam__exam_type")
        .order_by("-exam__exam_date")
    )

    # Subject-wise performance analysis
    subject_performance = {}
    for mark in marks:
        subject_name = mark.exam.subject.name
        if subject_name not in subject_performance:
            subject_performance[subject_name] = {
                "marks": [],
                "exams": 0,
                "average": 0,
                "highest": 0,
                "lowest": 100,
                "trend": [],
            }

        subject_performance[subject_name]["marks"].append(mark.percentage)
        subject_performance[subject_name]["exams"] += 1

        if mark.percentage > subject_performance[subject_name]["highest"]:
            subject_performance[subject_name]["highest"] = mark.percentage
        if mark.percentage < subject_performance[subject_name]["lowest"]:
            subject_performance[subject_name]["lowest"] = mark.percentage

    # Calculate averages
    for subject_name, data in subject_performance.items():
        if data["marks"]:
            data["average"] = sum(data["marks"]) / len(data["marks"])

    # Results and report cards
    results = (
        Result.objects.filter(student=child)
        .select_related("academic_class", "exam_type", "grade")
        .prefetch_related("subject_marks")
    )

    # Attendance summary
    attendance_summary = None
    current_session = AcademicSession.objects.filter(is_current=True).first()
    if current_session:
        from apps.attendance.models import DailyAttendance

        attendance_records = DailyAttendance.objects.filter(
            student=child, academic_session=current_session
        )

        total_days = attendance_records.count()
        if total_days > 0:
            present_days = attendance_records.filter(
                attendance_status="present"
            ).count()
            attendance_percentage = (present_days / total_days) * 100

            attendance_summary = {
                "total_days": total_days,
                "present_days": present_days,
                "attendance_percentage": round(attendance_percentage, 1),
                "current_session": current_session,
            }

    context = {
        "child": child,
        "academic_records": academic_records,
        "subject_performance": subject_performance,
        "marks": marks[:20],  # Recent marks
        "results": results,
        "attendance_summary": attendance_summary,
        "total_exams": marks.count(),
        "average_percentage": (
            marks.aggregate(avg=models.Avg("percentage"))["avg"] if marks else 0
        ),
    }

    return render(request, "users/parent/child_records.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_student")
    or has_role_or_perm(u, perm="academics.view_student", role_type="parent"),
    login_url=reverse_lazy("users:dashboard"),
)
def child_attendance(request, child_id):
    """
    View child's attendance records.
    """
    # Verify parent has access to this child
    try:
        relationship = ParentStudentRelationship.objects.get(
            parent=request.user, student_id=child_id, status="active"
        )
        child = relationship.student
    except ParentStudentRelationship.DoesNotExist:
        messages.error(
            request, _("You don't have permission to view this child's attendance.")
        )
        return redirect("users:dashboard")

    # Get attendance data
    current_session = AcademicSession.objects.filter(is_current=True).first()

    from apps.attendance.models import DailyAttendance, AttendanceSummary

    # Current session attendance
    attendance_records = (
        DailyAttendance.objects.filter(
            student=child, academic_session=current_session
        ).order_by("-date")
        if current_session
        else []
    )

    # Monthly summaries
    monthly_summaries = AttendanceSummary.objects.filter(student=child).order_by(
        "-year", "-month"
    )[:12]

    # Calculate current month stats
    current_month = timezone.now().month
    current_year = timezone.now().year

    current_month_summary = AttendanceSummary.objects.filter(
        student=child, month=current_month, year=current_year
    ).first()

    context = {
        "child": child,
        "attendance_records": attendance_records[:30],  # Last 30 days
        "monthly_summaries": monthly_summaries,
        "current_month_summary": current_month_summary,
        "current_session": current_session,
    }

    return render(request, "users/parent/child_attendance.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_student")
    or has_role_or_perm(u, perm="academics.view_student", role_type="parent"),
    login_url=reverse_lazy("users:dashboard"),
)
def child_fee_status(request, child_id):
    """
    View child's fee status and payment history.
    """
    # Verify parent has access to this child
    try:
        relationship = ParentStudentRelationship.objects.get(
            parent=request.user, student_id=child_id, status="active"
        )
        child = relationship.student
    except ParentStudentRelationship.DoesNotExist:
        messages.error(
            request,
            _("You don't have permission to view this child's fee information."),
        )
        return redirect("users:dashboard")

    from apps.finance.models import Invoice, Payment

    current_session = AcademicSession.objects.filter(is_current=True).first()

    # Get invoices for current session
    invoices = (
        Invoice.objects.filter(
            student=child, academic_session=current_session
        ).order_by("-issue_date")
        if current_session
        else []
    )

    # Get payment history
    payments = (
        Payment.objects.filter(student=child)
        .select_related("invoice")
        .order_by("-payment_date")[:10]
    )

    # Calculate totals
    total_invoiced = sum(invoice.total_amount for invoice in invoices)
    total_paid = sum(invoice.amount_paid for invoice in invoices)
    total_pending = sum(invoice.balance_due for invoice in invoices)

    context = {
        "child": child,
        "invoices": invoices,
        "payments": payments,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_pending": total_pending,
        "current_session": current_session,
    }

    return render(request, "users/parent/child_fees.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_student")
    or u.user_roles.filter(role__role_type="parent").exists(),
    login_url=reverse_lazy("users:dashboard"),
)
def message_teacher(request, teacher_id=None):
    """
    Allow parents to message teachers about their children.
    """
    from apps.communication.models import Message
    from apps.communication.forms import MessageForm

    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.message_type = "direct"
            message.save()

            # Add recipients
            teacher_user = form.cleaned_data["teacher"]
            message.recipients.add(teacher_user)

            messages.success(request, _("Message sent successfully!"))
            return redirect("communication:inbox")
    else:
        initial = {}
        if teacher_id:
            # Pre-select teacher if provided
            try:
                from apps.academics.models import Teacher

                teacher = Teacher.objects.get(id=teacher_id)
                initial["recipients"] = [teacher.user]
            except Teacher.DoesNotExist:
                pass

        form = MessageForm(initial=initial)

    # Get list of teachers for the parent's children
    children_relationships = ParentStudentRelationship.objects.filter(
        parent=request.user, status="active"
    ).select_related("student")

    teacher_ids = set()
    for relationship in children_relationships:
        # Get teachers for this child's classes
        child = relationship.student
        current_enrollment = child.enrollments.filter(
            academic_session__is_current=True
        ).first()

        if current_enrollment:
            # Get subject assignments for this class
            subject_assignments = (
                current_enrollment.class_enrolled.subject_assignments.filter(
                    academic_session__is_current=True
                ).select_related("teacher")
            )

            for assignment in subject_assignments:
                teacher_ids.add(assignment.teacher.id)

    teachers = []
    if teacher_ids:
        from apps.academics.models import Teacher

        teachers = Teacher.objects.filter(
            id__in=teacher_ids, status="active"
        ).select_related("user", "department")

    context = {
        "title": _("Message Teacher"),
        "form": form,
        "teachers": teachers,
    }

    return render(request, "users/parent/message_teacher.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def download_bulk_user_sample(request):
    """
    Download the test sample CSV file with one user for each role type.
    """
    # Generate the test sample data
    sample_data = """email,first_name,last_name,mobile,gender,nationality,address,city,state,postal_code,country,date_of_birth,role
admin@nexussms.com,John,Admin,+1234567890,male,American,123 Admin Street,Washington,DC,20500,USA,1980-01-15,super_admin
administrator@nexussms.com,Jane,Administrator,+1234567891,female,American,456 Admin Ave,Washington,DC,20501,USA,1982-03-22,admin
principal@nexussms.com,Michael,Principal,+1234567892,male,American,789 School Lane,Education City,CA,90210,USA,1975-08-10,principal
depthead@nexussms.com,Sarah,Head,+1234567893,female,American,321 Department Rd,Department Town,NY,10001,USA,1978-12-05,department_head
counselor@nexussms.com,David,Counselor,+1234567894,male,American,654 Counseling St,Counsel City,TX,75001,USA,1982-05-18,counselor
teacher@nexussms.com,Amy,Teacher,+1234567895,female,American,987 Classroom Ave,Learning Town,CA,95014,USA,1985-09-30,teacher
student@nexussms.com,Alex,Student,+1234567896,male,American,147 Student Dorm,College City,FL,33101,USA,2005-02-14,student
parent@nexussms.com,Mary,Parent,+1234567897,female,American,258 Parent Home,Family Town,GA,30301,USA,1970-11-28,parent
accountant@nexussms.com,Robert,Accountant,+1234567898,male,American,369 Finance St,Money City,NY,10002,USA,1977-07-12,accountant
librarian@nexussms.com,Laura,Librarian,+1234567899,female,American,741 Book Library,Reading City,WA,98102,USA,1980-04-25,librarian
driver@nexussms.com,James,Driver,+1234567800,male,American,852 Transport Rd,Driver Town,TX,77001,USA,1976-06-08,driver
support@nexussms.com,Linda,Support,+1234567801,female,American,963 Support Center,Help City,CA,94103,USA,1983-10-17,support
transport@nexussms.com,Mark,Transport,+1234567802,male,American,174 Fleet Management,Transport Hub,IL,60602,USA,1979-01-20,transport_manager
warden@nexussms.com,Patricia,Warden,+1234567803,female,American,285 Hostel Complex,Residence City,AZ,85002,USA,1974-12-03,hostel_warden"""

    # Log the download action
    AuditLog.objects.create(
        user=request.user,
        action=AuditLog.ActionType.DOWNLOAD,
        model_name="users.User",
        object_id="bulk_import_sample",
        ip_address=get_client_ip(request),
        details={"action": "Downloaded bulk user import sample file"},
    )

    # Return the CSV file as a download
    response = HttpResponse(sample_data, content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="bulk_user_import_sample_{timezone.now().strftime("%Y%m%d")}.csv"'
    )
    return response


@login_required
@user_passes_test(lambda u: u.is_superuser or u.has_perm("users.manage_relationships"))
def parent_student_relationship_create(request):
    """
    Create new parent-student relationship.
    """
    if request.method == "POST":
        form = ParentStudentRelationshipForm(request.POST)
        if form.is_valid():
            relationship = form.save()

            messages.success(request, _("Relationship created successfully!"))
            return redirect("users:parent_student_relationships")
    else:
        form = ParentStudentRelationshipForm()

    context = {
        "title": _("Create Relationship"),
        "form": form,
        "active_tab": "relationships",
    }
    return render(request, "users/parent_student_relationship_form.html", context)


# =============================================================================
# BULK OPERATIONS
# =============================================================================


@login_required
@user_passes_test(can_assign_roles)
def user_bulk_action(request):
    """
    Perform bulk actions on users.
    """
    if request.method == "POST":
        form = UserBulkActionForm(request.POST)
        if form.is_valid():
            users = form.cleaned_data["users"]
            action = form.cleaned_data["action"]

            try:
                with transaction.atomic():
                    if action == "activate":
                        users.update(is_active=True)
                        message = _("Users activated successfully!")
                    elif action == "deactivate":
                        users.update(is_active=False)
                        message = _("Users deactivated successfully!")
                    elif action == "assign_role":
                        role = form.cleaned_data["role"]

                        # Validate permission to assign this specific role
                        if not _can_assign_specific_role(request.user, role):
                            messages.error(
                                request,
                                _(
                                    "You do not have permission to assign the selected role."
                                ),
                            )
                            return redirect("users:user_list")

                        # Get current academic session for role assignment
                        current_session = AcademicSession.objects.filter(
                            is_current=True
                        ).first()

                        for user in users:
                            # Check if user already has this role to avoid duplicates
                            existing_role = UserRole.objects.filter(
                                user=user, role=role, academic_session=current_session
                            ).first()

                            if not existing_role:
                                UserRole.objects.create(
                                    user=user,
                                    role=role,
                                    is_primary=False,  # Bulk assignments are not primary by default
                                    academic_session=current_session,
                                )

                                # Log individual role assignment
                                UserRoleActivity.log_activity(
                                    user=user,
                                    role=role,
                                    action_type=UserRoleActivity.ActionType.ASSIGNED,
                                    performed_by=request.user,
                                    academic_session=current_session,
                                    details=f"Role assigned via bulk action",
                                )

                        message = _("Role assigned to users successfully!")
                    elif action == "delete":
                        # Check permissions for bulk delete (same as individual delete)
                        if not (
                            request.user.is_superuser
                            or request.user.user_roles.filter(
                                role__role_type__in=["admin", "principal"],
                                status="active",
                            ).exists()
                        ):
                            messages.error(
                                request,
                                _("You do not have permission to delete users."),
                            )
                            return redirect("users:user_list")

                        deleted_users = []
                        failed_deletions = []

                        for user in users:
                            try:
                                # Prevent self-deletion
                                if request.user.id == user.id:
                                    failed_deletions.append(
                                        f"{user.display_name} (cannot delete yourself)"
                                    )
                                    continue

                                # Additional safety check for superusers
                                if user.is_superuser and not request.user.is_superuser:
                                    failed_deletions.append(
                                        f"{user.display_name} (only superusers can delete other superusers)"
                                    )
                                    continue

                                # Store user details for logging before deletion
                                user_name = user.display_name
                                user_email = user.email
                                user_id_deleted = user.id

                                # Check for related academic records that will be affected
                                related_models = []
                                try:
                                    from apps.academics.models import Student

                                    if Student.objects.filter(user=user).exists():
                                        related_models.append("Student profile")
                                except:
                                    pass

                                try:
                                    from apps.academics.models import Teacher

                                    if Teacher.objects.filter(user=user).exists():
                                        related_models.append("Teacher profile")
                                except:
                                    pass

                                # Log the deletion
                                AuditLog.objects.create(
                                    user=request.user,
                                    action=AuditLog.ActionType.DELETE,
                                    model_name="users.User",
                                    object_id=str(user_id_deleted),
                                    ip_address=get_client_ip(request),
                                    details={
                                        "action": "User account permanently deleted (bulk)",
                                        "deleted_user_name": user_name,
                                        "deleted_user_email": user_email,
                                        "related_models_affected": related_models,
                                    },
                                )

                                # Delete the user (cascading delete will handle related data)
                                user.delete()
                                deleted_users.append(user_name)

                            except Exception as e:
                                logger.error(
                                    f"Error deleting user {user.id} in bulk operation: {e}"
                                )
                                failed_deletions.append(
                                    f"{user.display_name} ({str(e)})"
                                )

                        # Construct success message
                        if deleted_users:
                            message = _(
                                f'Successfully deleted {len(deleted_users)} user(s): {", ".join(deleted_users[:3])}'
                            )
                            if len(deleted_users) > 3:
                                message += _(f" and {len(deleted_users) - 3} more.")
                        else:
                            message = _("No users were deleted.")

                        if failed_deletions:
                            message += _(
                                f' Failed to delete: {", ".join(failed_deletions[:2])}'
                            )
                            if len(failed_deletions) > 2:
                                message += _(f" and {len(failed_deletions) - 2} more.")

                        if deleted_users:
                            messages.success(request, message)
                        else:
                            messages.warning(request, message)

                    # Log bulk action (skip for delete since we log individual deletions above)
                    if action != "delete":
                        AuditLog.objects.create(
                            user=request.user,
                            action=AuditLog.ActionType.UPDATE,
                            model_name="users.User",
                            object_id="bulk",
                            ip_address=get_client_ip(request),
                            details={"action": f"Bulk {action}", "count": len(users)},
                        )

                    # Only show success message for non-delete actions
                    if action != "delete":
                        messages.success(request, message)

            except Exception as e:
                logger.error(f"Error performing bulk action: {e}")
                messages.error(request, _("Error performing bulk action."))

            return redirect("users:user_list")
    else:
        form = UserBulkActionForm()

    context = {
        "title": _("Bulk User Actions"),
        "form": form,
    }
    return render(request, "users/admin/users/user_bulk_action.html", context)


def _can_assign_specific_role(user, target_role):
    """
    Check if user can assign a specific role based on hierarchy.
    Super admins can assign any role.
    School admins can assign roles below their level.
    """
    if user.is_superuser:
        return True

    # Get user's highest role level
    user_roles = user.user_roles.filter(status="active").select_related("role")
    if not user_roles:
        return False

    user_max_level = max(role.role.hierarchy_level for role in user_roles)

    # User can only assign roles with lower or equal hierarchy level
    # But school admins (admin/principal) can assign most staff roles
    admin_role_types = ["admin", "principal"]
    user_is_admin = any(role.role.role_type in admin_role_types for role in user_roles)

    if user_is_admin:
        # Admins can assign most roles except super_admin
        return target_role.role_type != "super_admin"
    else:
        # Non-admin users can only assign roles at or below their level
        return target_role.hierarchy_level <= user_max_level


# =============================================================================
# API & AJAX VIEWS
# =============================================================================


@login_required
@user_passes_test(lambda u: u.is_superuser)
def test_email_configuration(request):
    """
    Test email configuration by sending a test email.
    """
    if request.method == "POST":
        test_email = request.POST.get("test_email", "").strip()

        if not test_email:
            messages.error(request, _("Please provide a test email address."))
            return redirect("users:test_email_configuration")

        try:
            subject = _("Test Email - {}").format(
                getattr(settings, "SCHOOL_NAME", "School Management System")
            )
            message = _(
                "This is a test email to verify that the email configuration is working correctly."
            )

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [test_email],
                fail_silently=False,
            )

            messages.success(
                request, _("Test email sent successfully to {}").format(test_email)
            )
            logger.info(f"Test email sent successfully to {test_email}")

        except Exception as e:
            messages.error(request, _("Failed to send test email: {}").format(str(e)))
            logger.error(f"Failed to send test email to {test_email}: {e}")

        return redirect("users:test_email_configuration")

    context = {
        "title": _("Test Email Configuration"),
        "active_tab": "settings",
    }
    return render(request, "users/admin/test_email.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_bulk_import(request):
    """
    Bulk import users from CSV/Excel file.
    """
    if request.method == "POST":
        form = UserImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]
            send_welcome_email = form.cleaned_data["send_welcome_email"]
            generate_passwords = form.cleaned_data["generate_passwords"]

            try:
                # Process the uploaded file
                import_results = process_bulk_import(
                    csv_file, send_welcome_email, generate_passwords, request.user
                )

                # Log the bulk import action
                AuditLog.objects.create(
                    user=request.user,
                    action=AuditLog.ActionType.IMPORT,
                    model_name="users.User",
                    object_id="bulk_import",
                    ip_address=get_client_ip(request),
                    details={
                        "action": "Bulk user import",
                        "total_processed": import_results["total_processed"],
                        "successful": import_results["successful"],
                        "failed": import_results["failed"],
                    },
                )

                # Store results in session for display
                request.session["import_results"] = import_results

                messages.success(
                    request,
                    _(
                        "Bulk import completed! {} users processed, {} successful, {} failed."
                    ).format(
                        import_results["total_processed"],
                        import_results["successful"],
                        import_results["failed"],
                    ),
                )

                return redirect("users:user_bulk_import")

            except Exception as e:
                logger.error(f"Error during bulk import: {e}")
                messages.error(
                    request,
                    _("Error processing file. Please check the format and try again."),
                )

    else:
        form = UserImportForm()

    # Get import results from session if available
    import_results = request.session.pop("import_results", None)

    context = {
        "title": _("Bulk User Import"),
        "form": form,
        "import_results": import_results,
        "active_tab": "users",
    }
    return render(request, "users/admin/users/user_bulk_import.html", context)


# =============================================================================
# STAFF MANAGEMENT VIEWS
# =============================================================================


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def staff_list(request):
    """
    List all staff members with filtering and search capabilities.
    Staff members are users with any role other than 'student' or 'parent'.
    """
    staff_roles = Role.objects.exclude(role_type__in=["student", "parent"]).values_list(
        "id", flat=True
    )
    current_user_institution = request.user.current_institution
    if current_user_institution:
        staff_users = (
            User.objects.filter(
                institution_memberships__institution=current_user_institution,
                institution_memberships__is_primary=True,
                user_roles__role__id__in=staff_roles,
                is_active=True,
            )
            .distinct()
            .select_related("profile")
            .prefetch_related("user_roles__role")
        )
    else:
        # Fallback for users without primary institution (like during setup)
        staff_users = (
            User.objects.filter(user_roles__role__id__in=staff_roles, is_active=True)
            .distinct()
            .select_related("profile")
            .prefetch_related("user_roles__role")
        )

    # Filtering
    role_filter = request.GET.get("role")
    search_query = request.GET.get("q")

    if role_filter:
        staff_users = staff_users.filter(user_roles__role__role_type=role_filter)

    if search_query:
        staff_users = staff_users.filter(
            Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(profile__employee_id__icontains=search_query)
        )

    context = {
        "title": _("Staff Management"),
        "staff_members": staff_users,
        "roles": Role.objects.exclude(role_type__in=["student", "parent"]),
        "active_tab": "staff",
    }
    return render(request, "users/admin/staff/staff_list.html", context)


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def staff_detail(request, user_id):
    """
    Staff member detail view with profile and role management.
    """
    # First check if user exists and belongs to same institution for security
    user_obj = get_object_or_404(
        User.objects.filter(
            institution_memberships__institution=request.user.current_institution,
            institution_memberships__is_primary=True,
        ),
        id=user_id,
    )
    staff_member = user_obj

    # Ensure the user is actually a staff member
    if not staff_member.user_roles.filter(
        role__role_type__in=Role.STAFF_ROLES
    ).exists():
        messages.error(request, _("The requested user is not a staff member."))
        return redirect("users:staff_list")

    profile = staff_member.profile

    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=staff_member)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()

            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.ActionType.UPDATE,
                model_name="users.UserProfile",
                object_id=str(profile.id),
                ip_address=get_client_ip(request),
                details={"action": "Staff profile updated"},
            )

            messages.success(request, _("Staff profile updated successfully!"))
            return redirect("users:staff_detail", user_id=staff_member.id)
    else:
        user_form = UserUpdateForm(instance=staff_member)
        profile_form = UserProfileForm(instance=profile)

    # Get user roles
    user_roles = staff_member.user_roles.all().select_related(
        "role", "academic_session"
    )

    context = {
        "title": _("Staff Details"),
        "staff_member": staff_member,
        "user_form": user_form,
        "profile_form": profile_form,
        "user_roles": user_roles,
        "active_tab": "staff",
    }
    return render(request, "users/admin/staff/staff_detail.html", context)


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.has_perm("users.view_studentapplication")
    or u.has_perm("users.view_staffapplication")
)
def export_applications(request, application_type):
    """
    Export student or staff applications to CSV or Excel.
    """
    format = request.GET.get("format", "csv")
    status_filter = request.GET.get("status", "all")
    search_query = request.GET.get("q", "")
    if application_type == "student":
        queryset = StudentApplication.objects.all().select_related("academic_session")
        if not request.user.is_superuser:
            from apps.core.middleware import get_user_accessible_institutions

            accessible_insts = get_user_accessible_institutions(request.user)
            queryset = queryset.filter(institution__in=accessible_insts)
        filename_prefix = "student_applications"
        fields = [
            "application_number",
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_of_birth",
            "gender",
            "nationality",
            "address",
            "city",
            "state",
            "postal_code",
            "country",
            "grade_applying_for",
            "previous_school",
            "previous_grade",
            "academic_achievements",
            "parent_first_name",
            "parent_last_name",
            "parent_email",
            "parent_phone",
            "parent_relationship",
            "application_status",
            "academic_session__name",
            "application_date",
            "reviewed_by__email",
            "reviewed_at",
            "review_notes",
            "user_account__email",
        ]
        field_titles = [
            _("Application Number"),
            _("First Name"),
            _("Last Name"),
            _("Email"),
            _("Phone"),
            _("Date of Birth"),
            _("Gender"),
            _("Nationality"),
            _("Address"),
            _("City"),
            _("State"),
            _("Postal Code"),
            _("Country"),
            _("Grade Applying For"),
            _("Previous School"),
            _("Previous Grade"),
            _("Academic Achievements"),
            _("Parent First Name"),
            _("Parent Last Name"),
            _("Parent Email"),
            _("Parent Phone"),
            _("Parent Relationship"),
            _("Application Status"),
            _("Academic Session"),
            _("Application Date"),
            _("Reviewed By"),
            _("Reviewed At"),
            _("Review Notes"),
            _("User Account"),
        ]
    elif application_type == "staff":
        queryset = StaffApplication.objects.all().select_related(
            "position_applied_for", "academic_session"
        )
        if not request.user.is_superuser:
            from apps.core.middleware import get_user_accessible_institutions

            accessible_insts = get_user_accessible_institutions(request.user)
            queryset = queryset.filter(institution__in=accessible_insts)
        filename_prefix = "staff_applications"
        fields = [
            "application_number",
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_of_birth",
            "gender",
            "nationality",
            "address",
            "city",
            "state",
            "postal_code",
            "country",
            "position_applied_for__name",
            "position_type",
            "expected_salary",
            "highest_qualification",
            "institution",
            "year_graduated",
            "years_of_experience",
            "previous_employer",
            "previous_position",
            "reference1_name",
            "reference1_position",
            "reference1_contact",
            "reference2_name",
            "reference2_position",
            "reference2_contact",
            "application_status",
            "academic_session__name",
            "application_date",
            "reviewed_by__email",
            "reviewed_at",
            "review_notes",
            "interview_date",
            "user_account__email",
        ]
        field_titles = [
            _("Application Number"),
            _("First Name"),
            _("Last Name"),
            _("Email"),
            _("Phone"),
            _("Date of Birth"),
            _("Gender"),
            _("Nationality"),
            _("Address"),
            _("City"),
            _("State"),
            _("Postal Code"),
            _("Country"),
            _("Position Applied For"),
            _("Position Type"),
            _("Expected Salary"),
            _("Highest Qualification"),
            _("Institution"),
            _("Year Graduated"),
            _("Years of Experience"),
            _("Previous Employer"),
            _("Previous Position"),
            _("Reference 1 Name"),
            _("Reference 1 Position"),
            _("Reference 1 Contact"),
            _("Reference 2 Name"),
            _("Reference 2 Position"),
            _("Reference 2 Contact"),
            _("Application Status"),
            _("Academic Session"),
            _("Application Date"),
            _("Reviewed By"),
            _("Reviewed At"),
            _("Review Notes"),
            _("Interview Date"),
            _("User Account"),
        ]
    else:
        messages.error(request, _("Invalid application type for export."))
        return redirect("users:pending_applications")

    # Apply filters
    if status_filter != "all":
        queryset = queryset.filter(application_status=status_filter)
        # Scope to user's accessible institutions for non-superusers
        if not request.user.is_superuser:
            from apps.core.middleware import get_user_accessible_institutions

            accessible_insts = get_user_accessible_institutions(request.user)
            queryset = queryset.filter(institution__in=accessible_insts)

    if search_query:
        queryset = queryset.filter(
            Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(application_number__icontains=search_query)
        )

    if format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{filename_prefix}_{timezone.now().strftime("%Y%m%d")}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(field_titles)
        for obj in queryset:
            row = []
            for field_name in fields:
                # Handle related fields
                if "__" in field_name:
                    parts = field_name.split("__")
                    value = obj
                    for part in parts:
                        if value is None:
                            break
                        value = getattr(value, part, None)
                else:
                    value = getattr(obj, field_name, None)

                # Format specific fields
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(value, date):
                    value = value.strftime("%Y-%m-%d")
                elif value is None:
                    value = ""
                row.append(str(value))
            writer.writerow(row)
        return response

    elif format == "excel":
        output = BytesIO()
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = filename_prefix.replace("_", " ").title()

        # Write headers
        for col_num, title in enumerate(field_titles, 1):
            sheet.cell(row=1, column=col_num).value = title

        # Write data rows
        current_row = 2
        for obj in queryset:
            current_col = 1
            for field_name in fields:
                # Get field value
                if "__" in field_name:
                    parts = field_name.split("__")
                    value = obj
                    for part in parts:
                        if value is None:
                            break
                        value = getattr(value, part, None)
                else:
                    value = getattr(obj, field_name, None)

                # Format value
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(value, date):
                    value = value.strftime("%Y-%m-%d")
                elif value is None:
                    value = ""

                # Set cell value as string to prevent type detection issues
                sheet.cell(row=current_row, column=current_col).value = str(value)
                current_col += 1
            current_row += 1

        workbook.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename_prefix}_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        )
        return response

    messages.error(request, _("Invalid export format."))
    return redirect("users:pending_applications")


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def export_users(request):
    """
    Export users to CSV or Excel.
    """
    format = request.GET.get("format", "csv")
    roles = request.GET.getlist("fields")  # Get selected role fields
    include_inactive = request.GET.get("include_inactive", "false").lower() == "true"

    # Base queryset
    from apps.core.middleware import get_user_accessible_institutions

    if request.user.is_superuser:
        queryset = (
            User.objects.all()
            .select_related("profile")
            .prefetch_related("user_roles__role")
        )
    else:
        accessible_insts = get_user_accessible_institutions(request.user)
        queryset = (
            User.objects.filter(
                institution_memberships__institution__in=accessible_insts
            )
            .select_related("profile")
            .prefetch_related("user_roles__role")
            .distinct()
        )

    # Apply filters
    if not include_inactive:
        queryset = queryset.filter(is_active=True)

    # Fields to export based on selection
    fields = [
        "email",
        "first_name",
        "last_name",
        "mobile",
        "is_active",
        "is_verified",
        "is_staff",
        "is_superuser",
        "last_login",
        "created_at",
    ]

    # Add profile fields if available
    profile_fields = [
        "profile__date_of_birth",
        "profile__gender",
        "profile__nationality",
        "profile__address_line_1",
        "profile__city",
        "profile__state",
        "profile__postal_code",
        "profile__country",
    ]
    fields.extend(profile_fields)

    field_titles = [
        _("Email"),
        _("First Name"),
        _("Last Name"),
        _("Mobile"),
        _("Active"),
        _("Verified"),
        _("Staff"),
        _("Superuser"),
        _("Last Login"),
        _("Created Date"),
        _("Date of Birth"),
        _("Gender"),
        _("Nationality"),
        _("Address"),
        _("City"),
        _("State"),
        _("Postal Code"),
        _("Country"),
    ]

    # Add roles information
    # We handle roles separately since it's a many-to-many relationship

    if format == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="users_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(field_titles + [_("Roles"), _("Primary Role")])
        for user in queryset:
            row = []
            for field_name in fields:
                # Handle profile fields
                if "__" in field_name:
                    parts = field_name.split("__")
                    value = user
                    for part in parts:
                        if value is None:
                            break
                        value = getattr(value, part, None)
                else:
                    value = getattr(user, field_name, None)

                # Format specific fields
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(value, date):
                    value = value.strftime("%Y-%m-%d")
                elif isinstance(value, bool):
                    value = "Yes" if value else "No"
                elif value is None:
                    value = ""
                elif hasattr(value, "__str__"):
                    value = str(value)
                row.append(str(value))

            # Add roles information
            user_roles = user.user_roles.all()
            roles_str = ", ".join([ur.role.name for ur in user_roles])
            primary_role = user_roles.filter(is_primary=True).first()
            primary_role_name = primary_role.role.name if primary_role else ""

            row.extend([roles_str, primary_role_name])
            writer.writerow(row)
        return response

    elif format == "excel":
        output = BytesIO()
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Users Export"

        # Write headers
        for col_num, title in enumerate(
            field_titles + [_("Roles"), _("Primary Role")], 1
        ):
            sheet.cell(row=1, column=col_num).value = title

        # Write data rows
        current_row = 2
        for user in queryset:
            current_col = 1
            for field_name in fields:
                # Handle profile fields
                if "__" in field_name:
                    parts = field_name.split("__")
                    value = user
                    for part in parts:
                        if value is None:
                            break
                        value = getattr(value, part, None)
                else:
                    value = getattr(user, field_name, None)

                # Format value
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(value, date):
                    value = value.strftime("%Y-%m-%d")
                elif isinstance(value, bool):
                    value = "Yes" if value else "No"
                elif value is None:
                    value = ""
                elif hasattr(value, "__str__"):
                    value = str(value)

                # Set cell value as string to prevent type detection issues
                sheet.cell(row=current_row, column=current_col).value = str(value)
                current_col += 1

            # Add roles information
            user_roles = user.user_roles.all()
            roles_str = ", ".join([ur.role.name for ur in user_roles])
            primary_role = user_roles.filter(is_primary=True).first()
            primary_role_name = primary_role.role.name if primary_role else ""

            sheet.cell(row=current_row, column=current_col).value = roles_str
            sheet.cell(row=current_row, column=current_col + 1).value = (
                primary_role_name
            )
            current_row += 1

        workbook.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="users_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        )
        return response

    elif format == "json":
        # JSON export
        users_data = []
        for user in queryset:
            user_data = {}
            for field_name, title in zip(fields, field_titles):
                # Handle profile fields
                if "__" in field_name:
                    parts = field_name.split("__")
                    value = user
                    for part in parts:
                        if value is None:
                            break
                        value = getattr(value, part, None)
                else:
                    value = getattr(user, field_name, None)

                # Format specific fields for JSON
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(value, date):
                    value = value.strftime("%Y-%m-%d")
                elif isinstance(value, bool):
                    value = bool(value)
                elif value is None:
                    value = None
                else:
                    value = str(value)

                user_data[field_name.replace("__", "_")] = value

            # Add roles information
            user_roles = user.user_roles.all()
            user_data["roles"] = [ur.role.name for ur in user_roles]
            primary_role = user_roles.filter(is_primary=True).first()
            user_data["primary_role"] = primary_role.role.name if primary_role else None

            users_data.append(user_data)

        response = JsonResponse({"users": users_data})
        response["Content-Disposition"] = (
            f'attachment; filename="users_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
        )
        return response

    messages.error(request, _("Invalid export format."))
    return redirect("users:user_list")


@login_required
def get_user_suggestions(request):
    """
    AJAX view for user search suggestions.
    """
    query = request.GET.get("q", "")
    role_type = request.GET.get("role_type", "")

    users = User.objects.filter(
        Q(email__icontains=query)
        | Q(first_name__icontains=query)
        | Q(last_name__icontains=query)
    ).filter(is_active=True)

    if role_type:
        users = users.filter(user_roles__role__role_type=role_type)

    suggestions = [
        {"id": user.id, "text": f"{user.get_full_name()} ({user.email})"}
        for user in users[:10]
    ]

    return JsonResponse({"results": suggestions})


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def get_application_counts(request):
    """
    AJAX view to get current counts of pending student and staff applications.
    """
    student_count = StudentApplication.objects.filter(
        application_status__in=["pending", "under_review"]
    ).count()
    staff_count = StaffApplication.objects.filter(
        application_status__in=["pending", "under_review"]
    ).count()

    return JsonResponse({"student_count": student_count, "staff_count": staff_count})


@login_required
def check_email_availability(request):
    """
    AJAX view to check if email is available.
    """
    email = request.GET.get("email", "")
    user_id = request.GET.get("user_id")

    users = User.objects.filter(email=email)
    if user_id:
        users = users.exclude(id=user_id)

    available = not users.exists()

    return JsonResponse({"available": available})


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)
def get_user_roles_ajax(request, user_id):
    """
    AJAX view to get a user's roles and primary role status.
    """
    user = get_object_or_404(User, id=user_id)
    user_roles = user.user_roles.all().select_related("role")

    roles_data = []
    for user_role in user_roles:
        roles_data.append(
            {
                "id": str(user_role.id),
                "role_name": user_role.role.name,
                "role_type": user_role.role.role_type,
                "is_primary": user_role.is_primary,
                "status": user_role.status,
                "academic_session": (
                    user_role.academic_session.name
                    if user_role.academic_session
                    else None
                ),
                "context_id": user_role.context_id,
            }
        )

    primary_roles = [role for role in roles_data if role["is_primary"]]

    return JsonResponse(
        {
            "user_id": str(user.id),
            "roles": roles_data,
            "primary_roles": primary_roles,
            "display_name": user.display_name,
            "initials": user.get_initials(),
            "profile_picture_url": (
                user.profile.profile_picture.url
                if user.profile.profile_picture
                else None
            ),
        }
    )


@login_required
def upload_profile_picture(request):
    """
    AJAX view to handle profile picture upload.
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "message": "Method not allowed"}, status=405
        )

    user = request.user

    # Check if profile_picture is in request.FILES
    if "profile_picture" not in request.FILES:
        return JsonResponse({"success": False, "message": "No file uploaded"})

    profile_picture = request.FILES["profile_picture"]

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if profile_picture.content_type not in allowed_types:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed.",
            }
        )

    # Validate file size (5MB limit)
    max_size = 5 * 1024 * 1024
    if profile_picture.size > max_size:
        return JsonResponse(
            {"success": False, "message": "File too large. Maximum size is 5MB."}
        )

    try:
        # Update user's profile picture
        profile = user.profile
        profile.profile_picture = profile_picture
        profile.save()

        # Log the profile picture update
        AuditLog.objects.create(
            user=user,
            action=AuditLog.ActionType.UPDATE,
            model_name="users.UserProfile",
            object_id=str(profile.id),
            ip_address=get_client_ip(request),
            details={"action": "Profile picture updated"},
        )

        # Trigger guardian notifications if user is a student
        if user.user_roles.filter(role__role_type="student").exists():
            guardians = get_student_guardians(user)
            if guardians:
                notify_guardians_profile_update(user, guardians, ["profile_picture"])

        return JsonResponse(
            {
                "success": True,
                "message": "Profile picture updated successfully!",
                "picture_url": (
                    profile.profile_picture.url if profile.profile_picture else None
                ),
            }
        )

    except Exception as e:
        logger.error(f"Error uploading profile picture for user {user.id}: {e}")
        return JsonResponse(
            {
                "success": False,
                "message": "An error occurred while uploading the picture. Please try again.",
            },
            status=500,
        )


# =============================================================================
# INSTITUTION TRANSFER REQUEST VIEWS
# =============================================================================


@login_required
def institution_transfer_request_form(request, transfer_type=None):
    """
    View for students and staff to submit institution transfer requests.
    """
    user = request.user

    # Determine transfer type from user's primary role if not specified
    if not transfer_type:
        primary_role = user.user_roles.filter(is_primary=True, status="active").first()
        if primary_role and primary_role.role.role_type == "student":
            transfer_type = "student"
        elif primary_role and primary_role.role.role_type in Role.STAFF_ROLES:
            transfer_type = "staff"
        else:
            # Check any active role
            any_role = user.user_roles.filter(status="active").first()
            if any_role:
                if any_role.role.role_type == "student":
                    transfer_type = "student"
                elif any_role.role.role_type in Role.STAFF_ROLES:
                    transfer_type = "staff"

    # Validate user can submit this type of transfer request
    if transfer_type == "student":
        can_submit = user.user_roles.filter(
            role__role_type="student", status="active"
        ).exists()
        transfer_type_display = _("Student Transfer")
    elif transfer_type == "staff":
        can_submit = user.user_roles.filter(
            role__role_type__in=Role.STAFF_ROLES, status="active"
        ).exists()
        transfer_type_display = _("Staff Transfer")
    else:
        can_submit = False
        transfer_type_display = _("Transfer Request")

    if not can_submit:
        messages.error(
            request, _("You are not eligible to submit this type of transfer request.")
        )
        return redirect("users:dashboard")

    if request.method == "POST":
        from .forms import InstitutionTransferRequestForm

        form = InstitutionTransferRequestForm(
            request.POST, user=user, transfer_type=transfer_type
        )

        if form.is_valid():
            transfer_request = form.save()

            # Log the transfer request submission
            AuditLog.objects.create(
                user=user,
                action=AuditLog.ActionType.CREATE,
                model_name="users.InstitutionTransferRequest",
                object_id=str(transfer_request.id),
                ip_address=get_client_ip(request),
                details={
                    "action": "Institution transfer request submitted",
                    "transfer_type": transfer_request.get_transfer_type_display(),
                    "requested_institution": transfer_request.requested_institution.name,
                },
            )

            # Send notification emails
            try:
                # Notify admins
                from apps.users.models import User

                admin_users = User.objects.filter(
                    Q(is_superuser=True)
                    | Q(
                        user_roles__role__role_type__in=["admin", "principal"],
                        user_roles__status="active",
                    )
                ).distinct()

                for admin in admin_users:
                    # TODO: Send email notification to admin
                    pass

            except Exception as e:
                logger.warning(
                    f"Failed to send notification emails for transfer request {transfer_request.id}: {e}"
                )

            messages.success(
                request,
                _(
                    "Your transfer request has been submitted successfully and is pending review."
                ),
            )
            return redirect("users:user_transfer_requests")
        else:
            messages.error(request, _("Please correct the errors in the form."))
    else:
        from .forms import InstitutionTransferRequestForm

        form = InstitutionTransferRequestForm(user=user, transfer_type=transfer_type)

    # Get user's current institution
    from apps.core.models import InstitutionUser

    current_institution_user = (
        InstitutionUser.objects.filter(user=user, is_primary=True)
        .select_related("institution")
        .first()
    )

    context = {
        "title": _("Submit Transfer Request"),
        "form": form,
        "transfer_type": transfer_type,
        "transfer_type_display": transfer_type_display,
        "current_institution": (
            current_institution_user.institution if current_institution_user else None
        ),
        "page_title": f"{transfer_type_display} Request",
    }

    return render(request, "users/transfer_request_form.html", context)


@login_required
def institution_transfer_requests_list(request):
    """
    View for users to see their own transfer requests.
    """
    user = request.user

    transfer_requests = (
        InstitutionTransferRequest.objects.filter(requesting_user=user)
        .select_related(
            "current_institution",
            "requested_institution",
            "reviewed_by",
            "completed_by",
            "academic_session",
            "current_role",
        )
        .order_by("-created_at")
    )

    context = {
        "title": _("My Transfer Requests"),
        "transfer_requests": transfer_requests,
        "page_title": _("My Transfer Requests"),
    }

    return render(request, "users/user_transfer_requests.html", context)


@login_required
def institution_transfer_request_detail(request, request_id):
    """
    View details of a specific transfer request.
    """
    user = request.user
    transfer_request = get_object_or_404(
        InstitutionTransferRequest, id=request_id, requesting_user=user
    )

    context = {
        "title": _("Transfer Request Details"),
        "transfer_request": transfer_request,
        "page_title": _("Transfer Request Details"),
    }

    return render(request, "users/transfer_request_detail.html", context)


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.user_roles.filter(
        role__role_type__in=["admin", "principal"], status="active"
    ).exists()
)
def admin_transfer_requests_list(request):
    """
    Admin view for managing all institution transfer requests.
    """
    transfer_requests = InstitutionTransferRequest.objects.select_related(
        "requesting_user",
        "current_institution",
        "requested_institution",
        "reviewed_by",
        "completed_by",
        "academic_session",
        "current_role",
    ).order_by("-created_at")

    # Scope transfer requests to institutions accessible by the user (unless superuser)
    if not request.user.is_superuser:
        from apps.core.middleware import get_user_accessible_institutions
        from django.db.models import Q

        accessible_insts = get_user_accessible_institutions(request.user)
        transfer_requests = transfer_requests.filter(
            Q(current_institution__in=accessible_insts)
            | Q(requested_institution__in=accessible_insts)
        )

    # Apply filters
    status_filter = request.GET.get("status")
    transfer_type_filter = request.GET.get("transfer_type")
    search_query = request.GET.get("q")

    if status_filter:
        transfer_requests = transfer_requests.filter(request_status=status_filter)

    if transfer_type_filter:
        transfer_requests = transfer_requests.filter(transfer_type=transfer_type_filter)

    if search_query:
        transfer_requests = transfer_requests.filter(
            Q(request_number__icontains=search_query)
            | Q(requesting_user__email__icontains=search_query)
            | Q(requesting_user__first_name__icontains=search_query)
            | Q(requesting_user__last_name__icontains=search_query)
        )

    # Get statistics
    stats = {
        "total": InstitutionTransferRequest.objects.count(),
        "pending": InstitutionTransferRequest.objects.filter(
            request_status="pending"
        ).count(),
        "under_review": InstitutionTransferRequest.objects.filter(
            request_status="under_review"
        ).count(),
        "approved": InstitutionTransferRequest.objects.filter(
            request_status="approved"
        ).count(),
        "completed": InstitutionTransferRequest.objects.filter(
            request_status="completed"
        ).count(),
        "rejected": InstitutionTransferRequest.objects.filter(
            request_status="rejected"
        ).count(),
    }

    context = {
        "title": _("Manage Transfer Requests"),
        "transfer_requests": transfer_requests,
        "stats": stats,
        "current_filters": {
            "status": status_filter,
            "transfer_type": transfer_type_filter,
            "q": search_query,
        },
        "page_title": _("Institution Transfer Requests"),
        "active_tab": "transfer_requests",
    }

    return render(request, "users/admin/transfer_requests_list.html", context)


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.user_roles.filter(
        role__role_type__in=["admin", "principal"], status="active"
    ).exists()
)
def admin_approve_transfer_request(request, request_id):
    """
    Admin view to approve a transfer request.
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "message": "Method not allowed"}, status=405
        )

    transfer_request = get_object_or_404(InstitutionTransferRequest, id=request_id)

    if not transfer_request.can_be_approved_by(request.user):
        return JsonResponse(
            {
                "success": False,
                "message": "You do not have permission to approve this request.",
            },
            status=403,
        )

    try:
        review_notes = request.POST.get("review_notes", "")
        transfer_request.approve(request.user, review_notes)

        # Log the approval
        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.ActionType.UPDATE,
            model_name="users.InstitutionTransferRequest",
            object_id=str(transfer_request.id),
            ip_address=get_client_ip(request),
            details={
                "action": "Transfer request approved",
                "request_number": transfer_request.request_number,
            },
        )

        # TODO: Send email notification to user

        return JsonResponse(
            {
                "success": True,
                "message": f"Transfer request {transfer_request.request_number} has been approved.",
            }
        )

    except Exception as e:
        logger.error(f"Error approving transfer request {request_id}: {e}")
        return JsonResponse(
            {"success": False, "message": f"Error approving request: {str(e)}"},
            status=500,
        )


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.user_roles.filter(
        role__role_type__in=["admin", "principal"], status="active"
    ).exists()
)
def admin_reject_transfer_request(request, request_id):
    """
    Admin view to reject a transfer request.
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "message": "Method not allowed"}, status=405
        )

    transfer_request = get_object_or_404(InstitutionTransferRequest, id=request_id)

    if not transfer_request.can_be_approved_by(request.user):
        return JsonResponse(
            {
                "success": False,
                "message": "You do not have permission to reject this request.",
            },
            status=403,
        )

    try:
        review_notes = request.POST.get("review_notes", "")
        transfer_request.reject(request.user, review_notes)

        # Log the rejection
        AuditLog.objects.create(
            user=request.user,
            action=AuditLog.ActionType.UPDATE,
            model_name="users.InstitutionTransferRequest",
            object_id=str(transfer_request.id),
            ip_address=get_client_ip(request),
            details={
                "action": "Transfer request rejected",
                "request_number": transfer_request.request_number,
                "review_notes": review_notes[:100],  # First 100 chars
            },
        )

        # TODO: Send email notification to user

        return JsonResponse(
            {
                "success": True,
                "message": f"Transfer request {transfer_request.request_number} has been rejected.",
            }
        )

    except Exception as e:
        logger.error(f"Error rejecting transfer request {request_id}: {e}")
        return JsonResponse(
            {"success": False, "message": f"Error rejecting request: {str(e)}"},
            status=500,
        )


@login_required
@user_passes_test(
    lambda u: u.is_superuser
    or u.user_roles.filter(
        role__role_type__in=["admin", "principal"], status="active"
    ).exists()
)
def admin_complete_transfer_request(request, request_id):
    """
    Admin view to complete an approved transfer request.
    This involves actually transferring the user to the new institution.
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "message": "Method not allowed"}, status=405
        )

    transfer_request = get_object_or_404(
        InstitutionTransferRequest,
        id=request_id,
        request_status=InstitutionTransferRequest.RequestStatus.APPROVED,
    )

    try:
        with transaction.atomic():
            user = transfer_request.requesting_user

            # Update user's primary institution association
            from apps.core.models import InstitutionUser

            institution_user, created = InstitutionUser.objects.get_or_create(
                user=user,
                institution=transfer_request.requested_institution,
                defaults={
                    "is_primary": True,
                    "employee_id": f"{transfer_request.transfer_type}_{transfer_request.requested_institution.code}_{user.id}",
                },
            )

            if not created:
                # Update existing association to be primary
                institution_user.is_primary = True
                institution_user.save()

            # Remove primary flag from old institution association (if different)
            if (
                transfer_request.current_institution
                != transfer_request.requested_institution
            ):
                InstitutionUser.objects.filter(
                    user=user,
                    institution=transfer_request.current_institution,
                    is_primary=True,
                ).update(is_primary=False)

            # Mark the transfer request as completed
            transfer_request.complete_transfer(request.user)

            # Log the completion
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.ActionType.UPDATE,
                model_name="users.InstitutionTransferRequest",
                object_id=str(transfer_request.id),
                ip_address=get_client_ip(request),
                details={
                    "action": "Transfer request completed",
                    "request_number": transfer_request.request_number,
                    "user_moved": f"{user.get_full_name()} ({user.email})",
                    "from_institution": transfer_request.current_institution.name,
                    "to_institution": transfer_request.requested_institution.name,
                },
            )

            # TODO: Send email notification to user about successful transfer

            return JsonResponse(
                {
                    "success": True,
                    "message": f"Transfer request {transfer_request.request_number} has been completed. User has been transferred to {transfer_request.requested_institution.name}.",
                }
            )

    except Exception as e:
        logger.error(f"Error completing transfer request {request_id}: {e}")
        return JsonResponse(
            {"success": False, "message": f"Error completing transfer: {str(e)}"},
            status=500,
        )


# =============================================================================
# BULK IMPORT UTILITIES
# =============================================================================


def process_bulk_import(csv_file, send_welcome_email, generate_passwords, performed_by):
    """
    Process bulk user import from CSV/Excel file.
    Returns a dictionary with import results.
    """
    import pandas as pd
    from io import BytesIO

    results = {
        "total_processed": 0,
        "successful": 0,
        "failed": 0,
        "errors": [],
        "created_users": [],
    }

    try:
        # Read the file
        if csv_file.name.endswith(".csv"):
            df = pd.read_csv(csv_file)
        elif csv_file.name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(csv_file)
        else:
            raise ValueError(
                "Unsupported file format. Please upload a CSV or Excel file."
            )

        # Normalize column names (convert to lowercase and replace spaces with underscores)
        df.columns = df.columns.str.lower().str.replace(" ", "_").str.replace("-", "_")

        # Required columns
        required_columns = ["email", "first_name", "last_name"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

        # Process each row
        for index, row in df.iterrows():
            results["total_processed"] += 1

            try:
                with transaction.atomic():
                    # Extract user data
                    email = str(row.get("email", "")).strip()
                    first_name = str(row.get("first_name", "")).strip()
                    last_name = str(row.get("last_name", "")).strip()
                    mobile = (
                        str(row.get("mobile", "")).strip()
                        if pd.notna(row.get("mobile"))
                        else ""
                    )
                    role_type = str(row.get("role", "student")).strip().lower()

                    # Validate required fields
                    if not email or not first_name or not last_name:
                        raise ValueError(
                            "Email, first name, and last name are required"
                        )

                    # Check if user already exists
                    if User.objects.filter(email=email).exists():
                        raise ValueError(f"User with email {email} already exists")

                    # Generate password
                    if generate_passwords:
                        password = "".join(
                            secrets.choice(
                                string.ascii_letters
                                + string.digits
                                + string.punctuation
                            )
                            for _ in range(12)
                        )
                    else:
                        password = "changeme123"  # Default password

                    # Create user
                    user = User.objects.create_user(
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        mobile=mobile if mobile else None,
                        is_active=True,
                        is_verified=True,
                    )

                    # Update profile with additional data
                    profile = user.profile
                    if pd.notna(row.get("date_of_birth")):
                        profile.date_of_birth = row.get("date_of_birth")
                    if pd.notna(row.get("gender")):
                        profile.gender = str(row.get("gender")).strip().lower()
                    if pd.notna(row.get("nationality")):
                        profile.nationality = str(row.get("nationality")).strip()
                    if pd.notna(row.get("address")):
                        profile.address_line_1 = str(row.get("address")).strip()
                    if pd.notna(row.get("city")):
                        profile.city = str(row.get("city")).strip()
                    if pd.notna(row.get("state")):
                        profile.state = str(row.get("state")).strip()
                    if pd.notna(row.get("postal_code")):
                        profile.postal_code = str(row.get("postal_code")).strip()
                    if pd.notna(row.get("country")):
                        profile.country = str(row.get("country")).strip()
                    profile.save()

                    # Assign role
                    role = Role.objects.filter(
                        role_type=role_type, status="active"
                    ).first()
                    if not role:
                        # Try to find by name or create default student role
                        if role_type == "student":
                            role = Role.objects.filter(role_type="student").first()
                            if not role:
                                role = Role.objects.create(
                                    name="Student",
                                    role_type="student",
                                    description="Student role",
                                    hierarchy_level=10,
                                    is_system_role=True,
                                    status="active",
                                )
                        else:
                            raise ValueError(f"Invalid role type: {role_type}")

                    # Get current academic session
                    current_session = AcademicSession.objects.filter(
                        is_current=True
                    ).first()

                    UserRole.objects.create(
                        user=user,
                        role=role,
                        is_primary=True,
                        academic_session=current_session,
                    )

                    # Set staff permissions if needed
                    if role.role_type in ["admin", "principal", "teacher"]:
                        user.is_staff = True
                        user.save()

                    # Send welcome email if requested
                    if send_welcome_email:
                        try:
                            subject = _("Welcome to {}").format(
                                getattr(settings, "SCHOOL_NAME", "Our School")
                            )
                            context = {
                                "user": user,
                                "password": password,
                                "login_url": (
                                    f"{settings.SITE_URL}/users/login/"
                                    if hasattr(settings, "SITE_URL")
                                    else "/users/login/"
                                ),
                                "school_name": getattr(
                                    settings, "SCHOOL_NAME", "Our School"
                                ),
                            }

                            message = render_to_string(
                                "users/emails/bulk_import_welcome.html", context
                            )
                            send_mail(
                                subject,
                                strip_tags(message),
                                settings.DEFAULT_FROM_EMAIL,
                                [user.email],
                                html_message=message,
                                fail_silently=True,
                            )
                        except Exception as email_error:
                            logger.warning(
                                f"Failed to send welcome email to {user.email}: {email_error}"
                            )

                    results["successful"] += 1
                    results["created_users"].append(
                        {
                            "id": user.id,
                            "email": user.email,
                            "name": user.get_full_name(),
                            "role": role.name,
                        }
                    )

            except Exception as e:
                results["failed"] += 1
                results["errors"].append(
                    {
                        "row": index
                        + 2,  # +2 because pandas is 0-indexed and header row
                        "email": str(row.get("email", "")),
                        "error": str(e),
                    }
                )
                logger.error(f"Error importing user at row {index + 2}: {e}")

    except Exception as e:
        logger.error(f"Error processing bulk import file: {e}")
        raise

    return results


# =============================================================================
# ERROR HANDLING
# =============================================================================


def handler403(request, exception):
    """
    Custom 403 error handler.
    """
    context = {"title": _("Access Denied"), "exception": exception}
    return render(request, "errors/403.html", context, status=403)


def handler404(request, exception):
    """
    Custom 404 error handler.
    """
    context = {"title": _("Page Not Found"), "exception": exception}
    return render(request, "errors/404.html", context, status=404)


def handler500(request):
    """
    Custom 500 error handler.
    """
    context = {"title": _("Server Error")}
    return render(request, "errors/500.html", context, status=500)


# =============================================================================
# TEACHER PORTAL VIEWS
# =============================================================================


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_class")
    or has_role_or_perm(u, perm="academics.view_class", role_type="teacher"),
    login_url=reverse_lazy("users:dashboard"),
)
def teacher_dashboard(request):
    """
    Enhanced teacher dashboard with comprehensive overview.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    # Get teacher's classes and assignments
    teacher_assignments = teacher.subject_assignments.filter(
        academic_session=current_session
    ).select_related("subject", "class_assigned", "academic_session")

    # Calculate statistics
    total_classes = teacher_assignments.values("class_assigned").distinct().count()
    total_subjects = teacher_assignments.values("subject").distinct().count()
    total_periods = (
        teacher_assignments.aggregate(total=models.Sum("periods_per_week"))["total"]
        or 0
    )

    # Get today's classes
    today_classes = []
    if current_session:
        from datetime import datetime

        today_weekday = datetime.now().strftime("%A").lower()

        today_timetable = (
            teacher.timetable_entries.filter(
                academic_session=current_session, day_of_week=today_weekday
            )
            .select_related("class_assigned", "subject")
            .order_by("start_time")
        )

        today_classes = list(today_timetable)

    # Get pending grading tasks
    from apps.assessment.models import Assignment

    pending_grading = Assignment.objects.filter(
        teacher=teacher,
        student__isnull=False,
        submission_status__in=["submitted", "late"],
        graded_date__isnull=True,
    ).count()

    # Get recent activities
    from apps.assessment.models import Mark

    recent_marks = (
        Mark.objects.filter(entered_by=teacher)
        .select_related("exam", "student")
        .order_by("-entered_at")[:5]
    )

    # Get attendance summary for today
    from apps.attendance.models import DailyAttendance
    from django.utils import timezone

    today = timezone.now().date()

    today_attendance_count = DailyAttendance.objects.filter(
        marked_by=request.user, date=today
    ).count()

    context = {
        "title": _("Teacher Dashboard"),
        "teacher": teacher,
        "current_session": current_session,
        "teacher_assignments": teacher_assignments,
        "total_classes": total_classes,
        "total_subjects": total_subjects,
        "total_periods": total_periods,
        "today_classes": today_classes,
        "pending_grading": pending_grading,
        "recent_marks": recent_marks,
        "today_attendance_count": today_attendance_count,
    }

    return render(request, "users/teacher/dashboard.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_class")
    or has_role_or_perm(u, perm="academics.view_class", role_type="teacher"),
    login_url=reverse_lazy("users:dashboard"),
)
def teacher_classes(request):
    """
    View all classes assigned to the teacher.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    # Get all classes taught by this teacher
    teacher_assignments = teacher.subject_assignments.filter(
        academic_session=current_session
    ).select_related("subject", "class_assigned", "academic_session")

    # Group by class
    classes_data = {}
    for assignment in teacher_assignments:
        class_obj = assignment.class_assigned
        if class_obj.id not in classes_data:
            classes_data[class_obj.id] = {
                "class": class_obj,
                "subjects": [],
                "total_students": class_obj.enrollments.filter(
                    status="active", academic_session=current_session
                ).count(),
                "total_periods": 0,
            }
        classes_data[class_obj.id]["subjects"].append(assignment.subject)
        classes_data[class_obj.id]["total_periods"] += assignment.periods_per_week

    classes_list = list(classes_data.values())

    context = {
        "title": _("My Classes"),
        "teacher": teacher,
        "current_session": current_session,
        "classes_list": classes_list,
    }

    return render(request, "users/teacher/classes.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_class")
    or has_role_or_perm(u, perm="academics.view_class", role_type="teacher"),
    login_url=reverse_lazy("users:dashboard"),
)
def teacher_class_attendance(request, class_id):
    """
    Take attendance for a specific class.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    # Verify teacher teaches this class
    class_obj = get_object_or_404(
        Class.objects.select_related("academic_session"),
        id=class_id,
        academic_session=current_session,
    )

    # Check if teacher is assigned to this class
    has_assignment = teacher.subject_assignments.filter(
        class_assigned=class_obj, academic_session=current_session
    ).exists()

    if not has_assignment and not request.user.is_staff:
        messages.error(request, _("You are not assigned to teach this class."))
        return redirect("users:teacher_classes")

    # Get students in this class
    enrollments = class_obj.enrollments.filter(
        status="active", academic_session=current_session
    ).select_related("student__user")

    students = [enrollment.student for enrollment in enrollments]

    # Get today's date and check if attendance already exists
    from django.utils import timezone

    today = timezone.now().date()

    from apps.attendance.models import DailyAttendance, AttendanceSession

    attendance_session = AttendanceSession.objects.filter(
        academic_session=current_session, is_active=True
    ).first()

    if not attendance_session:
        messages.error(request, _("No active attendance session found."))
        return redirect("users:teacher_classes")

    # Check if attendance already taken today
    existing_attendance = DailyAttendance.objects.filter(
        class_obj=class_obj, date=today, attendance_session=attendance_session
    ).select_related("student")

    attendance_taken = existing_attendance.exists()
    attendance_data = {}

    if attendance_taken:
        # Load existing attendance
        for attendance in existing_attendance:
            attendance_data[attendance.student.id] = {
                "status": attendance.status,
                "check_in_time": attendance.check_in_time,
                "remarks": attendance.remarks,
            }

    if request.method == "POST":
        # Process attendance submission
        attendance_records = []

        for student in students:
            status = request.POST.get(f"status_{student.id}", "absent")
            remarks = request.POST.get(f"remarks_{student.id}", "")

            attendance, created = DailyAttendance.objects.get_or_create(
                student=student,
                date=today,
                attendance_session=attendance_session,
                defaults={
                    "status": status,
                    "remarks": remarks,
                    "marked_by": request.user,
                    "check_in_time": (
                        timezone.now() if status in ["present", "late"] else None
                    ),
                },
            )

            if not created:
                # Update existing
                attendance.status = status
                attendance.remarks = remarks
                attendance.marked_by = request.user
                if status in ["present", "late"] and not attendance.check_in_time:
                    attendance.check_in_time = timezone.now()
                attendance.save()

            attendance_records.append(attendance)

        messages.success(
            request,
            _("Attendance recorded successfully for {} students.").format(
                len(attendance_records)
            ),
        )
        return redirect("users:teacher_class_attendance", class_id=class_id)

    context = {
        "title": _("Take Attendance"),
        "teacher": teacher,
        "class_obj": class_obj,
        "students": students,
        "today": today,
        "attendance_taken": attendance_taken,
        "attendance_data": attendance_data,
        "current_session": current_session,
    }

    return render(request, "users/teacher/class_attendance.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_class")
    or has_role_or_perm(u, perm="academics.view_class", role_type="teacher"),
    login_url=reverse_lazy("users:dashboard"),
)
def teacher_class_materials(request, class_id):
    """
    View and manage materials for a specific class.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    # Verify teacher teaches this class
    class_obj = get_object_or_404(
        Class.objects.select_related("academic_session"),
        id=class_id,
        academic_session=current_session,
    )

    # Check if teacher is assigned to this class
    has_assignment = teacher.subject_assignments.filter(
        class_assigned=class_obj, academic_session=current_session
    ).exists()

    if not has_assignment and not request.user.is_staff:
        messages.error(request, _("You are not assigned to teach this class."))
        return redirect("users:teacher_classes")

    # Get materials for this class and teacher
    from apps.academics.models import ClassMaterial

    materials = ClassMaterial.objects.filter(
        class_assigned=class_obj, teacher=teacher, academic_session=current_session
    ).order_by("-publish_date")

    context = {
        "title": _("Class Materials"),
        "teacher": teacher,
        "class_obj": class_obj,
        "materials": materials,
        "current_session": current_session,
    }

    return render(request, "users/teacher/class_materials.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_class")
    or has_role_or_perm(u, perm="academics.view_class", role_type="teacher"),
    login_url=reverse_lazy("users:dashboard"),
)
def teacher_material_upload(request):
    """
    Upload new material for classes.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    # Get classes taught by this teacher
    teacher_assignments = teacher.subject_assignments.filter(
        academic_session=current_session
    ).select_related("class_assigned", "subject")

    classes_subjects = {}
    for assignment in teacher_assignments:
        class_id = str(assignment.class_assigned.id)
        if class_id not in classes_subjects:
            classes_subjects[class_id] = {
                "class": assignment.class_assigned,
                "subjects": [],
            }
        classes_subjects[class_id]["subjects"].append(assignment.subject)

    if request.method == "POST":
        from apps.academics.forms import ClassMaterialForm

        form = ClassMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.teacher = teacher
            material.academic_session = current_session
            material.save()

            messages.success(request, _("Material uploaded successfully!"))
            return redirect(
                "users:teacher_class_materials", class_id=material.class_assigned.id
            )
    else:
        from apps.academics.forms import ClassMaterialForm

        form = ClassMaterialForm()

    context = {
        "title": _("Upload Material"),
        "teacher": teacher,
        "form": form,
        "classes_subjects": classes_subjects,
        "current_session": current_session,
    }

    return render(request, "users/teacher/material_upload.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_class")
    or has_role_or_perm(u, perm="academics.view_class", role_type="teacher"),
    login_url=reverse_lazy("users:dashboard"),
)
def teacher_students(request):
    """
    View all students taught by the teacher.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    # Get all students taught by this teacher
    taught_classes = Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session=current_session,
    ).distinct()

    enrollments = Enrollment.objects.filter(
        class_enrolled__in=taught_classes,
        status="active",
        academic_session=current_session,
    ).select_related("student__user", "class_enrolled")

    # Group students by class
    students_by_class = {}
    for enrollment in enrollments:
        class_name = enrollment.class_enrolled.name
        if class_name not in students_by_class:
            students_by_class[class_name] = []
        students_by_class[class_name].append(enrollment.student)

    context = {
        "title": _("My Students"),
        "teacher": teacher,
        "students_by_class": students_by_class,
        "current_session": current_session,
    }

    return render(request, "users/teacher/students.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_class")
    or has_role_or_perm(u, perm="academics.view_class", role_type="teacher"),
    login_url=reverse_lazy("users:dashboard"),
)
def teacher_student_progress(request, student_id):
    """
    View detailed progress for a specific student.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    student = get_object_or_404(Student, id=student_id)

    # Verify teacher teaches this student
    teaches_student = Enrollment.objects.filter(
        student=student,
        class_enrolled__subject_assignments__teacher=teacher,
        status="active",
        academic_session=current_session,
    ).exists()

    if not teaches_student and not request.user.is_staff:
        messages.error(request, _("You do not teach this student."))
        return redirect("users:teacher_students")

    # Get student's academic records
    from apps.academics.models import AcademicRecord

    academic_records = AcademicRecord.objects.filter(
        student=student, academic_session=current_session
    ).select_related("class_enrolled")

    # Get assessment results
    from apps.assessment.models import Result, ResultSubject

    results = Result.objects.filter(
        student=student, academic_class__academic_session=current_session
    ).select_related("exam_type", "grade")

    # Get behavior records
    from apps.academics.models import BehaviorRecord

    behavior_records = (
        BehaviorRecord.objects.filter(student=student)
        .select_related("reported_by")
        .order_by("-incident_date")[:10]
    )

    # Get attendance summary
    from apps.attendance.models import AttendanceSummary

    attendance_summary = AttendanceSummary.objects.filter(
        student=student, academic_session=current_session
    ).order_by("-month", "-year")[:6]

    context = {
        "title": _("Student Progress"),
        "teacher": teacher,
        "student": student,
        "academic_records": academic_records,
        "results": results,
        "behavior_records": behavior_records,
        "attendance_summary": attendance_summary,
        "current_session": current_session,
    }

    return render(request, "users/teacher/student_progress.html", context)


@login_required
@user_passes_test(
    lambda u: u.has_perm("academics.view_class")
    or has_role_or_perm(u, perm="academics.view_class", role_type="teacher"),
    login_url=reverse_lazy("users:dashboard"),
)
def teacher_assessment(request):
    """
    Teacher assessment overview and management.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    # Get exams created by teacher
    from apps.assessment.models import Exam

    exams = (
        Exam.objects.filter(
            academic_class__subject_assignments__teacher=teacher,
            academic_session=current_session,
        )
        .select_related("subject", "exam_type", "academic_class")
        .distinct()
    )

    # Get assignments created by teacher
    from apps.assessment.models import Assignment

    assignments = Assignment.objects.filter(
        teacher=teacher,
        academic_session=current_session,
        student__isnull=True,  # Template assignments
    ).select_related("subject", "academic_class")

    # Get pending grading
    pending_grading = Assignment.objects.filter(
        teacher=teacher,
        student__isnull=False,
        submission_status__in=["submitted", "late"],
        graded_date__isnull=True,
    ).select_related("student__user", "subject")

    context = {
        "title": _("Assessment Management"),
        "teacher": teacher,
        "exams": exams,
        "assignments": assignments,
        "pending_grading": pending_grading,
        "current_session": current_session,
    }

    return render(request, "users/teacher/assessment.html", context)


@login_required
@user_passes_test(
    lambda u: has_role_or_perm(u, perm="academics.view_class", role_type="teacher"),
    login_url=reverse_lazy("users:dashboard"),
)
def teacher_timetable(request):
    """
    View teacher's timetable/schedule.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    # Get teacher's timetable
    from apps.academics.models import Timetable

    timetable_entries = (
        Timetable.objects.filter(teacher=teacher, academic_session=current_session)
        .select_related("class_assigned", "subject")
        .order_by("day_of_week", "period_number")
    )

    # Group by day
    timetable_by_day = {}
    days = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]

    for day in days:
        day_entries = timetable_entries.filter(day_of_week=day)
        if day_entries.exists():
            timetable_by_day[day] = list(day_entries)

    context = {
        "title": _("My Timetable"),
        "teacher": teacher,
        "timetable_by_day": timetable_by_day,
        "current_session": current_session,
    }

    return render(request, "users/teacher/timetable.html", context)


@login_required
@user_passes_test(
    lambda u: has_role_or_perm(u, perm="academics.view_class", role_type="teacher"),
    login_url=reverse_lazy("users:dashboard"),
)
def teacher_communication(request):
    """
    Teacher communication hub for parent interactions.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    # Get recent messages
    from apps.communication.models import Message

    sent_messages = (
        Message.objects.filter(sender=request.user)
        .select_related("recipients")
        .order_by("-created_at")[:10]
    )

    received_messages = (
        Message.objects.filter(recipients=request.user)
        .select_related("sender")
        .order_by("-created_at")[:10]
    )

    # Get students' parents for messaging
    taught_classes = Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session=current_session,
    ).distinct()

    # Get parent contacts
    from apps.users.models import ParentStudentRelationship

    parent_relationships = (
        ParentStudentRelationship.objects.filter(
            student__enrollments__class_enrolled__in=taught_classes, status="active"
        )
        .select_related("parent__user", "student__user")
        .distinct()
    )

    context = {
        "title": _("Communication"),
        "teacher": teacher,
        "sent_messages": sent_messages,
        "received_messages": received_messages,
        "parent_relationships": parent_relationships,
        "current_session": current_session,
    }

    return render(request, "users/teacher/communication.html", context)
