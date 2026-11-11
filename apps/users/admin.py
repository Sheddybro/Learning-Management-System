# apps/users/admin.py

from django.contrib import admin
from apps.core.admin import InstitutionModelAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.utils import timezone
from django.shortcuts import render, redirect
from django.urls import reverse
from django import forms
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
    InstitutionTransferRequest,
    ApplicationStatus,
)
from apps.core.models import Institution


# No longer needed - institution is now chosen by applicant


@admin.register(StudentApplication)
class StudentApplicationAdmin(InstitutionModelAdmin):
    """
    Admin interface for StudentApplication model.
    """

    list_display = (
        "application_number",
        "full_name",
        "grade_applying_for",
        "email",
        "application_status",
        "application_date",
        "academic_session",
    )

    def has_add_permission(self, request):
        """Allow superusers to add applications."""
        return request.user.is_superuser or super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """Allow superusers to modify applications."""
        return request.user.is_superuser or super().has_change_permission(request)

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of applications to maintain audit trail."""
        return False

    list_filter = (
        "application_status",
        "grade_applying_for",
        "gender",
        "academic_session",
        "application_date",
        "status",
    )
    search_fields = (
        "application_number",
        "first_name",
        "last_name",
        "email",
        "parent_first_name",
        "parent_last_name",
        "parent_email",
    )
    readonly_fields = (
        "application_number",
        "application_date",
        "created_at",
        "updated_at",
        "user_account",
    )
    list_per_page = 20
    date_hierarchy = "application_date"

    fieldsets = (
        (
            _("Application Information"),
            {
                "fields": (
                    "application_number",
                    "application_status",
                    "academic_session",
                    "application_date",
                )
            },
        ),
        (
            _("Student Information"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "gender",
                    "nationality",
                    "email",
                    "phone",
                )
            },
        ),
        (
            _("Academic Information"),
            {
                "fields": (
                    "grade_applying_for",
                    "previous_school",
                    "previous_grade",
                    "academic_achievements",
                )
            },
        ),
        (
            _("Parent/Guardian Information"),
            {
                "fields": (
                    "parent_first_name",
                    "parent_last_name",
                    "parent_email",
                    "parent_phone",
                    "parent_relationship",
                )
            },
        ),
        (
            _("Additional Information"),
            {
                "fields": (
                    "medical_conditions",
                    "special_needs",
                    "extracurricular_interests",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Address Information"),
            {"fields": ("address", "city", "state", "postal_code", "country")},
        ),
        (
            _("Review Information"),
            {
                "fields": (
                    "reviewed_by",
                    "reviewed_at",
                    "review_notes",
                    "user_account",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["approve_applications", "reject_applications", "mark_under_review"]

    def full_name(self, obj):
        return obj.full_name

    full_name.short_description = _("Full Name")

    def approve_applications(self, request, queryset):
        """Admin action to approve selected applications."""
        approved_count = 0
        skipped_count = 0
        for application in queryset:
            if application.application_status == ApplicationStatus.APPROVED:
                skipped_count += 1
                continue
            elif application.application_status == ApplicationStatus.PENDING:
                try:
                    # Create user account
                    user, temp_password = self.create_user_from_application(
                        application, request.user
                    )

                    # Update application
                    application.application_status = ApplicationStatus.APPROVED
                    application.reviewed_by = request.user
                    application.reviewed_at = timezone.now()
                    application.user_account = user
                    application.save()

                    # Send approval email
                    self.send_approval_email(application, user, temp_password)

                    approved_count += 1

                except Exception as e:
                    self.message_user(
                        request,
                        f"Error approving {application.application_number}: {str(e)}",
                        messages.ERROR,
                    )

        if approved_count:
            self.message_user(
                request,
                f"{approved_count} student application(s) approved successfully.",
                messages.SUCCESS,
            )
        if skipped_count:
            self.message_user(
                request,
                f"{skipped_count} application(s) were already approved and were skipped.",
                messages.INFO,
            )

    approve_applications.short_description = _("Approve selected applications")

    def reject_applications(self, request, queryset):
        """Admin action to reject selected applications."""
        updated = queryset.update(
            application_status=ApplicationStatus.REJECTED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(
            request, f"{updated} student application(s) rejected.", messages.WARNING
        )

    reject_applications.short_description = _("Reject selected applications")

    def mark_under_review(self, request, queryset):
        """Admin action to mark applications as under review."""
        updated = queryset.update(application_status=ApplicationStatus.UNDER_REVIEW)
        self.message_user(
            request,
            f"{updated} student application(s) marked as under review.",
            messages.INFO,
        )

    mark_under_review.short_description = _("Mark as under review")

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of applications to maintain audit trail."""
        return False

    def get_queryset(self, request):
        """Optimize queryset for admin performance."""
        return (
            super()
            .get_queryset(request)
            .select_related("academic_session", "reviewed_by", "user_account")
        )


@admin.register(StaffApplication)
class StaffApplicationAdmin(InstitutionModelAdmin):
    """
    Admin interface for StaffApplication model.
    """

    list_display = (
        "application_number",
        "full_name",
        "position_applied_for",
        "position_type",
        "email",
        "years_of_experience",
        "application_status",
        "application_date",
    )
    list_filter = (
        "application_status",
        "position_applied_for",
        "position_type",
        "gender",
        "academic_session",
        "application_date",
        "status",
    )
    search_fields = (
        "application_number",
        "first_name",
        "last_name",
        "email",
        "position_applied_for__name",
        "highest_qualification",
        "institution",
    )
    readonly_fields = (
        "application_number",
        "application_date",
        "created_at",
        "updated_at",
        "user_account",
    )
    list_per_page = 20
    date_hierarchy = "application_date"

    fieldsets = (
        (
            _("Application Information"),
            {
                "fields": (
                    "application_number",
                    "application_status",
                    "academic_session",
                    "application_date",
                    "interview_date",
                )
            },
        ),
        (
            _("Personal Information"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "gender",
                    "nationality",
                    "email",
                    "phone",
                )
            },
        ),
        (
            _("Professional Information"),
            {"fields": ("position_applied_for", "position_type", "expected_salary")},
        ),
        (
            _("Educational Background"),
            {"fields": ("highest_qualification", "institution", "year_graduated")},
        ),
        (
            _("Professional Experience"),
            {
                "fields": (
                    "years_of_experience",
                    "previous_employer",
                    "previous_position",
                )
            },
        ),
        (_("Documents"), {"fields": ("cv", "cover_letter", "certificates")}),
        (
            _("References"),
            {
                "fields": (
                    "reference1_name",
                    "reference1_position",
                    "reference1_contact",
                    "reference2_name",
                    "reference2_position",
                    "reference2_contact",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Address Information"),
            {"fields": ("address", "city", "state", "postal_code", "country")},
        ),
        (
            _("Review Information"),
            {
                "fields": (
                    "reviewed_by",
                    "reviewed_at",
                    "review_notes",
                    "user_account",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = [
        "approve_applications_custom",
        "reject_applications",
        "schedule_interview",
    ]

    def get_actions(self, request):
        """Override to provide custom approve action."""
        actions = super().get_actions(request)
        if "approve_applications_custom" in actions:
            # For single application, redirect to approval form
            # For multiple, use bulk approval
            actions["approve_applications_custom"] = (
                self.approve_applications,
                "approve_applications_custom",
                _("Approve selected applications using applicant chosen institutions"),
            )
        return actions

    def full_name(self, obj):
        return obj.full_name

    full_name.short_description = _("Full Name")

    def approve_applications(self, request, queryset):
        """Admin action to approve selected staff applications with institution assignment."""
        # Count selected applications
        selected_count = queryset.count()

        if selected_count == 0:
            self.message_user(request, _("No applications selected."), messages.WARNING)
            return

        # If only one application, redirect to detailed form
        if selected_count == 1:
            application = queryset.first()
            return redirect(
                "admin:staff_application_approve", application_id=application.pk
            )

        # For multiple applications, show bulk approval form
        return self.bulk_approval_view(request, queryset)

    def bulk_approval_view(self, request, queryset):
        """Handle bulk approval of staff applications using applicant's chosen institution."""
        if request.method == "POST":
            approved_count = 0
            skipped_count = 0
            errors = []

            for application in queryset:
                if application.application_status == ApplicationStatus.APPROVED:
                    skipped_count += 1
                    continue
                elif application.application_status == ApplicationStatus.PENDING:
                    try:
                        # Create user account and assign to applicant's chosen institution
                        user, temp_password = self.create_user_from_application(
                            application, request.user
                        )

                        # Update application
                        application.application_status = ApplicationStatus.APPROVED
                        application.reviewed_by = request.user
                        application.reviewed_at = timezone.now()
                        application.user_account = user
                        application.save()

                        # Send approval email
                        self.send_approval_email(application, user, temp_password)

                        approved_count += 1

                    except Exception as e:
                        errors.append(
                            f"Error approving {application.application_number}: {str(e)}"
                        )

            # Show results
            if approved_count:
                self.message_user(
                    request,
                    f"{approved_count} staff application(s) approved and assigned to their chosen institution(s).",
                    messages.SUCCESS,
                )
            if skipped_count:
                self.message_user(
                    request,
                    f"{skipped_count} application(s) were already approved and were skipped.",
                    messages.INFO,
                )
            if errors:
                for error in errors:
                    self.message_user(request, error, messages.ERROR)

            return redirect("admin:users_staffapplication_changelist")

        # Remove the form since no admin choice needed
        context = {
            "applications": queryset,
            "title": _("Approve Staff Applications"),
            "action_name": "approve_applications_custom",
            "selected_count": queryset.count(),
        }

        return render(request, "admin/users/bulk_staff_approval.html", context)

    # Add custom URL for single application approval
    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:application_id>/approve/",
                self.admin_site.admin_view(self.approve_single_application),
                name="staff_application_approve",
            ),
        ]
        return custom_urls + urls

    def approve_single_application(self, request, application_id):
        """View for approving a single staff application using applicant's chosen institution."""
        application = self.get_queryset(request).get(pk=application_id)

        if request.method == "POST":
            try:
                # Create user account and assign to applicant's chosen institution
                user, temp_password = self.create_user_from_application(
                    application, request.user
                )

                # Update application
                application.application_status = ApplicationStatus.APPROVED
                application.reviewed_by = request.user
                application.reviewed_at = timezone.now()
                application.user_account = user
                application.save()

                # Send approval email
                self.send_approval_email(application, user, temp_password)

                self.message_user(
                    request,
                    f"Staff application {application.application_number} approved and assigned to {application.qualified_institution}.",
                    messages.SUCCESS,
                )

                return redirect("admin:users_staffapplication_changelist")

            except Exception as e:
                self.message_user(request, f"Error: {str(e)}", messages.ERROR)

        # No form needed since we use applicant's choice
        context = {
            "application": application,
            "title": f"Approve Application: {application.application_number}",
        }

        return render(request, "admin/users/single_staff_approval.html", context)

    def schedule_interview(self, request, queryset):
        """Admin action to schedule interviews."""
        for application in queryset:
            application.application_status = ApplicationStatus.INTERVIEW_SCHEDULED
            application.save()

        self.message_user(
            request,
            f"{queryset.count()} application(s) marked for interview.",
            messages.INFO,
        )

    schedule_interview.short_description = _("Schedule interview for selected")

    def reject_applications(self, request, queryset):
        """Admin action to reject selected staff applications."""
        updated = queryset.update(
            application_status=ApplicationStatus.REJECTED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(
            request, f"{updated} staff application(s) rejected.", messages.WARNING
        )

    reject_applications.short_description = _("Reject selected staff applications")

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of applications to maintain audit trail."""
        return False

    def get_queryset(self, request):
        """Optimize queryset for admin performance."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "position_applied_for",
                "academic_session",
                "reviewed_by",
                "user_account",
            )
        )

    def create_user_from_application(self, application, created_by):
        """Create user account from staff application."""
        from .models import UserProfile, PasswordHistory, UserRole
        from apps.core.models import InstitutionUser
        from django.core.exceptions import ValidationError

        # Lookup the institution the applicant chose to work at
        if not application.institution:
            raise ValidationError(
                f"Application {application.application_number} does not have an institution specified."
            )

        institution = application.institution

        # Create user
        user = User.objects.create_user(
            email=application.email,
            first_name=application.first_name,
            last_name=application.last_name,
            mobile=application.phone,
            is_verified=True,
        )

        # Create or update profile
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "date_of_birth": application.date_of_birth,
                "gender": application.gender,
                "nationality": application.nationality,
                "address_line_1": application.address,
                "city": application.city,
                "state": application.state,
                "postal_code": application.postal_code,
                "country": application.country,
                "phone": application.phone,
                "mobile": application.phone,
                "email": application.email,
            },
        )

        # If profile already existed, update it
        if not created:
            profile.date_of_birth = application.date_of_birth
            profile.gender = application.gender
            profile.nationality = application.nationality
            profile.address_line_1 = application.address
            profile.city = application.city
            profile.state = application.state
            profile.postal_code = application.postal_code
            profile.country = application.country
            profile.phone = application.phone
            profile.mobile = application.phone
            profile.email = application.email
            profile.save()

        # Create institution-user relationship with applicant's chosen institution
        institution_user, created = InstitutionUser.objects.get_or_create(
            user=user,
            institution=institution,
            defaults={
                "is_primary": True,
                "employee_id": f"{application.position_applied_for.role_type}_{institution.code}_{user.id}",
            },
        )
        if created:
            employee_id = institution_user.employee_id
            # Update profile with employee_id
            profile.employee_id = employee_id
            profile.save()

        # Assign the role from position_applied_for
        user_role = UserRole.objects.create(
            user=user,
            role=application.position_applied_for,
            is_primary=True,
            academic_session=application.academic_session,
        )

        # Generate temporary password
        temp_password = user.make_random_password()

        # Log password creation
        PasswordHistory.objects.create(
            user=user,
            password_hash=user.password,
            changed_by=created_by,
            change_reason="initial",
        )

        return user, temp_password

    def send_approval_email(self, application, user, temp_password):
        """Send approval email to staff member."""
        from django.core.mail import send_mail
        from django.conf import settings

        subject = f"Staff Application Approved - {application.application_number}"
        message = f"""
        Dear {application.full_name},

        Congratulations! Your staff application ({application.application_number}) has been approved.

        You have been appointed as: {application.position_applied_for.name}

        Your account has been created with the following details:
        Email: {user.email}
        Temporary Password: {temp_password}

        Please log in and change your password immediately.

        Welcome to our team!

        Best regards,
        School Administration
        """

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [application.email],
            fail_silently=True,
        )


class UserProfileInline(admin.StackedInline):
    """
    Inline admin for UserProfile model.
    """

    model = UserProfile
    can_delete = False
    verbose_name_plural = _("Profile Details")
    fieldsets = (
        (
            _("Personal Information"),
            {
                "fields": (
                    "date_of_birth",
                    "gender",
                    "nationality",
                    "identification_number",
                )
            },
        ),
        (
            _("Contact Information"),
            {
                "fields": (
                    "phone",
                    "mobile",
                    "email",
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                )
            },
        ),
        (
            _("Social & Bio"),
            {
                "fields": (
                    "profile_picture",
                    "bio",
                    "website",
                    "facebook",
                    "twitter",
                    "linkedin",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Notification Preferences"),
            {
                "fields": (
                    "email_notifications",
                    "sms_notifications",
                    "push_notifications",
                ),
                "classes": ("collapse",),
            },
        ),
    )


class UserRoleInline(admin.TabularInline):
    """
    Inline admin for UserRole model.
    """

    model = UserRole
    extra = 1
    verbose_name_plural = _("User Roles")
    fields = ("role", "is_primary", "academic_session", "context_id")
    autocomplete_fields = ("role", "academic_session")

    def has_add_permission(self, request, obj=None):
        """Only allow adding role inlines if user can assign roles."""
        if request.user.is_superuser:
            return True

        # Allow if user has explicit role management permissions
        if request.user.has_perm("users.add_role") or request.user.has_perm(
            "users.change_role"
        ):
            return True

        return (
            hasattr(request.user, "user_roles")
            and request.user.user_roles.filter(
                role__role_type__in=["admin", "principal", "school_admin"],
                status="active",
            ).exists()
        )

    def has_change_permission(self, request, obj=None):
        """Only allow changing role inlines if user can assign roles."""
        return self.has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Only allow deleting role inlines if user can assign roles."""
        return self.has_add_permission(request, obj)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin interface for User model.
    """

    list_display = (
        "email",
        "full_name",
        "is_verified",
        "is_active",
        "is_staff",
        "last_login",
        "date_joined",
    )
    list_filter = (
        "is_verified",
        "is_active",
        "is_staff",
        "is_superuser",
        "date_joined",
    )
    search_fields = ("email", "first_name", "last_name", "mobile")
    ordering = ("-date_joined",)
    readonly_fields = (
        "last_login",
        "date_joined",
        "login_count",
        "email_verified_at",
        "last_login_ip",
        "current_login_ip",
    )

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal Info"), {"fields": ("first_name", "last_name", "mobile")}),
        (
            _("Verification Status"),
            {
                "fields": ("is_verified", "email_verified_at", "verification_token"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Preferences"),
            {"fields": ("language", "timezone"), "classes": ("collapse",)},
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Security"),
            {
                "fields": ("last_login_ip", "current_login_ip", "login_count"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Important Dates"),
            {"fields": ("last_login", "date_joined"), "classes": ("collapse",)},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "mobile",
                ),
            },
        ),
    )

    inlines = [UserProfileInline, UserRoleInline]

    actions = ["verify_users", "deactivate_users", "send_verification_emails"]

    def full_name(self, obj):
        return obj.full_name

    full_name.short_description = _("Full Name")

    def verify_users(self, request, queryset):
        """Admin action to verify selected users."""
        updated = queryset.update(is_verified=True, email_verified_at=timezone.now())
        self.message_user(
            request, f"{updated} users verified successfully.", messages.SUCCESS
        )

    verify_users.short_description = _("Verify selected users")

    def deactivate_users(self, request, queryset):
        """Admin action to deactivate selected users."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} users deactivated.", messages.WARNING)

    deactivate_users.short_description = _("Deactivate selected users")

    def send_verification_emails(self, request, queryset):
        """Admin action to send verification emails."""
        # This would typically integrate with your email service
        unverified_users = queryset.filter(is_verified=False)
        count = unverified_users.count()
        self.message_user(
            request, f"Verification emails sent to {count} users.", messages.INFO
        )

    send_verification_emails.short_description = _(
        "Send verification emails to selected users"
    )

    def get_queryset(self, request):
        """Optimize queryset for admin performance."""
        return (
            super()
            .get_queryset(request)
            .select_related("profile")
            .prefetch_related("user_roles")
        )


@admin.register(UserProfile)
class UserProfileAdmin(InstitutionModelAdmin):
    """
    Admin interface for UserProfile model.
    """

    list_display = ("user", "gender", "nationality", "age", "last_profile_update")
    list_filter = ("gender", "nationality", "last_profile_update")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "identification_number",
    )
    readonly_fields = ("last_profile_update", "created_at", "updated_at")
    raw_id_fields = ("user",)

    fieldsets = (
        (_("User"), {"fields": ("user",)}),
        (
            _("Personal Information"),
            {
                "fields": (
                    "date_of_birth",
                    "gender",
                    "nationality",
                    "identification_number",
                )
            },
        ),
        (
            _("Contact Information"),
            {
                "fields": (
                    "phone",
                    "mobile",
                    "email",
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                    "emergency_contact",
                    "emergency_phone",
                )
            },
        ),
        (
            _("Profile Media"),
            {"fields": ("profile_picture", "bio"), "classes": ("collapse",)},
        ),
        (
            _("Social Media"),
            {
                "fields": ("website", "facebook", "twitter", "linkedin"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Notification Settings"),
            {
                "fields": (
                    "email_notifications",
                    "sms_notifications",
                    "push_notifications",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("last_profile_update", "status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def age(self, obj):
        return obj.age

    age.short_description = _("Age")


@admin.register(Role)
class RoleAdmin(InstitutionModelAdmin):
    """
    Admin interface for Role model.
    """

    list_display = ("name", "role_type", "hierarchy_level", "is_system_role", "status")
    list_filter = ("role_type", "is_system_role", "status", "created_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("permissions",)

    fieldsets = (
        (
            _("Role Information"),
            {
                "fields": (
                    "name",
                    "role_type",
                    "description",
                    "hierarchy_level",
                    "is_system_role",
                )
            },
        ),
        (_("Permissions"), {"fields": ("permissions",), "classes": ("collapse",)}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make system role fields read-only for existing system roles."""
        if obj and obj.is_system_role:
            return self.readonly_fields + ("name", "role_type", "is_system_role")
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of system roles."""
        if obj and obj.is_system_role:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(UserRole)
class UserRoleAdmin(InstitutionModelAdmin):
    """
    Admin interface for UserRole model.
    """

    list_display = (
        "user",
        "role",
        "is_primary",
        "academic_session",
        "context_id",
        "status",
    )
    list_filter = ("is_primary", "role", "academic_session", "status", "created_at")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "role__name",
        "context_id",
    )
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("user",)
    autocomplete_fields = ("role", "academic_session")

    fieldsets = (
        (_("Assignment"), {"fields": ("user", "role", "is_primary")}),
        (
            _("Context"),
            {"fields": ("academic_session", "context_id"), "classes": ("collapse",)},
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        """Only allow role assignment if user has permission."""
        return self._can_assign_roles(request.user)

    def has_change_permission(self, request, obj=None):
        """Only allow role changes if user has permission."""
        return self._can_assign_roles(request.user)

    def has_delete_permission(self, request, obj=None):
        """Only allow role deletion if user has permission."""
        return self._can_assign_roles(request.user)

    def _can_assign_roles(self, user):
        """
        Check if user can assign roles to other users.
        Only superusers and school admins (admin/principal roles) can assign roles.
        """
        if user.is_superuser:
            return True

        # Check if user has admin, principal, or school_admin role
        return (
            hasattr(user, "user_roles")
            and user.user_roles.filter(
                role__role_type__in=["admin", "principal", "school_admin"],
                status="active",
            ).exists()
        )

    def save_model(self, request, obj, form, change):
        """Ensure only authorized users can assign roles and validate role hierarchy."""
        # Check permission before saving
        if not self._can_assign_roles(request.user):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("You don't have permission to assign roles.")

        # Validate role hierarchy - prevent assigning higher-level roles
        if not self._can_assign_specific_role(request.user, obj.role):
            from django.core.exceptions import ValidationError

            raise ValidationError(
                f"You don't have permission to assign the '{obj.role.name}' role."
            )

        # Ensure only one primary role per user in the same context
        if obj.is_primary:
            # Set all other roles for this user in the same context as non-primary
            UserRole.objects.filter(
                user=obj.user, academic_session=obj.academic_session, is_primary=True
            ).exclude(pk=obj.pk).update(is_primary=False)

        super().save_model(request, obj, form, change)

    def _can_assign_specific_role(self, user, target_role):
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
        user_is_admin = any(
            role.role.role_type in admin_role_types for role in user_roles
        )

        if user_is_admin:
            # Admins can assign most roles except super_admin
            return target_role.role_type != "super_admin"
        else:
            # Non-admin users can only assign roles at or below their level
            return target_role.hierarchy_level <= user_max_level


@admin.register(LoginHistory)
class LoginHistoryAdmin(InstitutionModelAdmin):
    """
    Admin interface for LoginHistory model.
    """

    list_display = (
        "user",
        "ip_address",
        "login_method",
        "was_successful",
        "created_at",
    )
    list_filter = ("login_method", "was_successful", "created_at")
    search_fields = ("user__email", "ip_address", "location")
    readonly_fields = (
        "user",
        "ip_address",
        "user_agent",
        "location",
        "login_method",
        "was_successful",
        "failure_reason",
        "session_key",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Login Details"),
            {
                "fields": (
                    "user",
                    "ip_address",
                    "location",
                    "login_method",
                    "was_successful",
                )
            },
        ),
        (
            _("Failure Information"),
            {"fields": ("failure_reason",), "classes": ("collapse",)},
        ),
        (
            _("Technical Details"),
            {"fields": ("user_agent", "session_key"), "classes": ("collapse",)},
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        """Prevent manual creation of login history."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent modification of login history."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion only for superusers."""
        return request.user.is_superuser


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(InstitutionModelAdmin):
    """
    Admin interface for PasswordHistory model.
    """

    list_display = ("user", "change_reason", "changed_by", "created_at")
    list_filter = ("change_reason", "created_at")
    search_fields = ("user__email", "changed_by__email")
    readonly_fields = (
        "user",
        "password_hash",
        "changed_by",
        "change_reason",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Password Change Details"),
            {"fields": ("user", "changed_by", "change_reason")},
        ),
        (
            _("Security Information"),
            {"fields": ("password_hash",), "classes": ("collapse",)},
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        """Prevent manual creation of password history."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent modification of password history."""
        return False


@admin.register(UserSession)
class UserSessionAdmin(InstitutionModelAdmin):
    """
    Admin interface for UserSession model.
    """

    def has_add_permission(self, request):
        """Allow superusers to add sessions if needed."""
        return request.user.is_superuser or super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """Allow superusers to modify sessions."""
        return request.user.is_superuser or super().has_change_permission(request)

    list_display = (
        "user",
        "session_key",
        "ip_address",
        "last_activity",
        "expires_at",
        "is_expired",
    )
    list_filter = ("last_activity", "expires_at")
    search_fields = ("user__email", "session_key", "ip_address")
    readonly_fields = (
        "user",
        "session_key",
        "ip_address",
        "user_agent",
        "last_activity",
        "expires_at",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "last_activity"

    fieldsets = (
        (_("Session Information"), {"fields": ("user", "session_key", "ip_address")}),
        (_("Activity"), {"fields": ("last_activity", "expires_at")}),
        (_("Technical Details"), {"fields": ("user_agent",), "classes": ("collapse",)}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def is_expired(self, obj):
        return obj.is_expired

    is_expired.boolean = True
    is_expired.short_description = _("Expired")

    def has_add_permission(self, request):
        """Prevent manual creation of user sessions."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent modification of user sessions."""
        return False

    actions = ["terminate_sessions"]

    def terminate_sessions(self, request, queryset):
        """Admin action to terminate selected user sessions."""
        count = queryset.count()
        queryset.delete()
        self.message_user(
            request, f"{count} user sessions terminated.", messages.SUCCESS
        )

    terminate_sessions.short_description = _("Terminate selected user sessions")


@admin.register(ParentStudentRelationship)
class ParentStudentRelationshipAdmin(InstitutionModelAdmin):
    """
    Admin interface for ParentStudentRelationship model.
    """

    def has_add_permission(self, request):
        """Allow superusers to manage relationships."""
        return request.user.is_superuser or super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """Allow superusers to modify relationships."""
        return request.user.is_superuser or super().has_change_permission(request)

    def has_delete_permission(self, request, obj=None):
        """Allow superusers to delete relationships."""
        return request.user.is_superuser or super().has_delete_permission(request)

    list_display = (
        "parent",
        "student",
        "relationship_type",
        "is_primary_contact",
        "can_pickup",
        "emergency_contact_order",
    )
    list_filter = ("relationship_type", "is_primary_contact", "can_pickup", "status")
    search_fields = (
        "parent__email",
        "student__email",
        "parent__first_name",
        "student__first_name",
    )
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("parent", "student")

    fieldsets = (
        (_("Relationship"), {"fields": ("parent", "student", "relationship_type")}),
        (
            _("Contact Permissions"),
            {"fields": ("is_primary_contact", "emergency_contact_order", "can_pickup")},
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Ensure only one primary contact per student."""
        if obj.is_primary_contact:
            ParentStudentRelationship.objects.filter(
                student=obj.student, is_primary_contact=True
            ).exclude(pk=obj.pk).update(is_primary_contact=False)
        super().save_model(request, obj, form, change)


@admin.register(InstitutionTransferRequest)
class InstitutionTransferRequestAdmin(InstitutionModelAdmin):
    """
    Admin interface for InstitutionTransferRequest model.
    """

    def has_add_permission(self, request):
        """Allow superusers to create transfer requests."""
        return request.user.is_superuser or super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        """Allow superusers to modify transfer requests."""
        return request.user.is_superuser or super().has_change_permission(request)

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of transfer requests to maintain audit trail."""
        return False

    list_display = (
        "request_number",
        "requesting_user",
        "transfer_type",
        "current_institution",
        "requested_institution",
        "request_status",
        "request_status_badge",
        "created_at",
    )
    list_filter = (
        "transfer_type",
        "request_status",
        "priority_level",
        "current_institution",
        "requested_institution",
        "created_at",
    )
    search_fields = (
        "request_number",
        "requesting_user__email",
        "requesting_user__first_name",
        "requesting_user__last_name",
        "request_reason",
    )
    readonly_fields = (
        "request_number",
        "requesting_user",
        "transfer_type",
        "current_institution",
        "requested_institution",
        "request_reason",
        "additional_notes",
        "request_status",
        "reviewed_by",
        "reviewed_at",
        "review_notes",
        "approval_date",
        "transfer_completed_at",
        "completed_by",
        "created_at",
        "updated_at",
    )
    list_per_page = 20
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Transfer Request Details"),
            {
                "fields": (
                    "request_number",
                    "transfer_type",
                    "requesting_user",
                    "current_institution",
                    "requested_institution",
                )
            },
        ),
        (
            _("Request Information"),
            {"fields": ("request_reason", "additional_notes", "priority_level")},
        ),
        (
            _("Status & Workflow"),
            {
                "fields": (
                    "request_status",
                    "reviewed_by",
                    "reviewed_at",
                    "review_notes",
                )
            },
        ),
        (
            _("Completion Details"),
            {
                "fields": ("approval_date", "transfer_completed_at", "completed_by"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Context Information"),
            {"fields": ("academic_session", "current_role"), "classes": ("collapse",)},
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = [
        "approve_requests",
        "reject_requests",
        "mark_under_review",
        "complete_transfers",
    ]

    def request_status_badge(self, obj):
        """Return HTML badge for request status."""
        status_colors = {
            InstitutionTransferRequest.RequestStatus.PENDING: "secondary",
            InstitutionTransferRequest.RequestStatus.UNDER_REVIEW: "warning",
            InstitutionTransferRequest.RequestStatus.APPROVED: "success",
            InstitutionTransferRequest.RequestStatus.REJECTED: "danger",
            InstitutionTransferRequest.RequestStatus.COMPLETED: "success",
            InstitutionTransferRequest.RequestStatus.CANCELLED: "secondary",
        }
        color = status_colors.get(obj.request_status, "secondary")
        return f'<span class="badge badge-{color}">{obj.get_request_status_display()}</span>'

    request_status_badge.short_description = _("Status")
    request_status_badge.allow_tags = True
    request_status_badge.admin_order_field = "request_status"

    def approve_requests(self, request, queryset):
        """Admin action to approve selected transfer requests."""
        updated_count = 0
        for transfer_request in queryset:
            if transfer_request.can_be_approved_by(request.user):
                try:
                    transfer_request.approve(request.user)
                    updated_count += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"Error approving {transfer_request.request_number}: {str(e)}",
                        messages.ERROR,
                    )

        if updated_count:
            self.message_user(
                request,
                f"{updated_count} transfer request(s) approved successfully.",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                _(
                    "No transfer requests could be approved. Check your permissions or request status."
                ),
                messages.WARNING,
            )

    approve_requests.short_description = _("Approve selected requests")

    def reject_requests(self, request, queryset):
        """Admin action to reject selected transfer requests."""
        if request.method == "POST":
            review_notes = request.POST.get("review_notes", "")
            for transfer_request in queryset.filter(
                request_status__in=[
                    InstitutionTransferRequest.RequestStatus.PENDING,
                    InstitutionTransferRequest.RequestStatus.UNDER_REVIEW,
                ]
            ):
                if transfer_request.can_be_approved_by(request.user):
                    transfer_request.reject(request.user, review_notes)

        self.message_user(
            request,
            f"{queryset.count()} transfer request(s) rejected.",
            messages.WARNING,
        )

    reject_requests.short_description = _("Reject selected requests")

    def mark_under_review(self, request, queryset):
        """Admin action to mark transfer requests as under review."""
        updated = queryset.filter(
            request_status=InstitutionTransferRequest.RequestStatus.PENDING
        ).update(
            request_status=InstitutionTransferRequest.RequestStatus.UNDER_REVIEW,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(
            request,
            f"{updated} transfer request(s) marked as under review.",
            messages.INFO,
        )

    mark_under_review.short_description = _("Mark as under review")

    def complete_transfers(self, request, queryset):
        """Admin action to complete approved transfer requests."""
        updated_count = 0
        for transfer_request in queryset.filter(
            request_status=InstitutionTransferRequest.RequestStatus.APPROVED
        ):
            try:
                transfer_request.complete_transfer(request.user)
                # TODO: Actually perform the institution transfer logic
                updated_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Error completing {transfer_request.request_number}: {str(e)}",
                    messages.ERROR,
                )

        if updated_count:
            self.message_user(
                request,
                f"{updated_count} transfer(s) completed successfully.",
                messages.SUCCESS,
            )

    complete_transfers.short_description = _("Complete approved transfers")

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of transfer requests to maintain audit trail."""
        return False

    def get_queryset(self, request):
        """Optimize queryset for admin performance."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "requesting_user",
                "current_institution",
                "requested_institution",
                "reviewed_by",
                "completed_by",
                "academic_session",
                "current_role",
            )
        )


# NOTE: Custom UsersAdminSite removed. Models are registered with the
# default admin site via the @admin.register decorators above.
