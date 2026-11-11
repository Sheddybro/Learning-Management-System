#!/usr/bin/env python
"""
Management command to create a new institution (school) in the multi-tenant system.
"""

import uuid
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.validators import validate_email, ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.models import Institution, InstitutionConfig, SystemConfig
from apps.users.models import User, UserProfile, UserRole, Role


class Command(BaseCommand):
    help = "Create a new institution (school) with initial setup"

    def add_arguments(self, parser):
        parser.add_argument("name", type=str, help="Name of the institution")
        parser.add_argument(
            "code", type=str, help="Unique code for the institution (used in subdomain)"
        )
        parser.add_argument(
            "--admin_email",
            type=str,
            help="Email of the institution administrator",
            required=True,
        )
        parser.add_argument(
            "--admin_name",
            type=str,
            help="Name of the institution administrator (optional, will extract from email if not provided)",
        )
        parser.add_argument(
            "--description", type=str, default="", help="Description of the institution"
        )
        parser.add_argument(
            "--phone", type=str, default="", help="Phone number of the institution"
        )
        parser.add_argument(
            "--address", type=str, default="", help="Street address of the institution"
        )
        parser.add_argument(
            "--city", type=str, default="", help="City of the institution"
        )
        parser.add_argument(
            "--state", type=str, default="", help="State/province of the institution"
        )
        parser.add_argument(
            "--country", type=str, default="", help="Country of the institution"
        )
        parser.add_argument(
            "--website", type=str, default="", help="Website URL of the institution"
        )
        parser.add_argument(
            "--max_students",
            type=int,
            default=1000,
            help="Maximum number of students (default: 1000)",
        )
        parser.add_argument(
            "--max_staff",
            type=int,
            default=100,
            help="Maximum number of staff (default: 100)",
        )
        parser.add_argument(
            "--institution_type",
            type=str,
            choices=[
                "preschool",
                "elementary",
                "middle_school",
                "high_school",
                "college",
                "vocational",
                "special_education",
                "international",
            ],
            default="high_school",
            help="Type of institution (default: high_school)",
        )
        parser.add_argument(
            "--ownership_type",
            type=str,
            choices=["public", "private", "charter", "religious", "international"],
            default="private",
            help="Ownership type of institution (default: private)",
        )
        parser.add_argument(
            "--set_default",
            action="store_true",
            help="Set this institution as the default institution",
        )
        parser.add_argument(
            "--skip_admin",
            action="store_true",
            help="Skip creating admin user (useful if admin already exists)",
        )

    def handle(self, *args, **options):
        name = options["name"]
        code = options["code"]
        admin_email = options["admin_email"]
        admin_name = options.get("admin_name")

        # Validate inputs
        try:
            validate_email(admin_email)
        except ValidationError:
            raise CommandError(_("Invalid admin email address"))

        if Institution.objects.filter(code__iexact=code).exists():
            raise CommandError(_('Institution with code "%s" already exists') % code)

        if Institution.objects.filter(name__iexact=name).exists():
            raise CommandError(_('Institution with name "%s" already exists') % name)

        # Validate subdomain code (should be URL-friendly)
        if not code.replace("_", "").replace("-", "").isalnum():
            raise CommandError(
                _(
                    "Institution code can only contain letters, numbers, underscores, and hyphens"
                )
            )

        # Extract name from email if not provided
        if not admin_name:
            admin_name = admin_email.split("@")[0].replace(".", " ").title()

        with transaction.atomic():
            try:
                # Create the institution
                institution = Institution.objects.create(
                    id=uuid.uuid4(),
                    name=name,
                    code=code.lower(),
                    short_name=name[:50],
                    description=options["description"],
                    phone=options["phone"],
                    address_line_1=options["address"],
                    city=options["city"],
                    state=options["state"],
                    country=options["country"],
                    website=options["website"],
                    max_students=options["max_students"],
                    max_staff=options["max_staff"],
                    institution_type=options["institution_type"],
                    ownership_type=options["ownership_type"],
                    is_active=True,
                    allows_online_enrollment=True,
                    requires_parent_approval=True,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        _('Successfully created institution "%s" (%s)')
                        % (institution.name, institution.code)
                    )
                )

                # Set as default if requested
                if options["set_default"]:
                    # Remove default from others first
                    Institution.objects.filter(code="DEFAULT").update(
                        code="DEFAULT_OLD"
                    )
                    institution.code = "DEFAULT"
                    institution.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            _('Set "%s" as the default institution') % institution.name
                        )
                    )

                # Create admin user if not skipped
                if not options["skip_admin"]:
                    admin_user = self._create_institution_admin(
                        institution,
                        admin_email,
                        admin_name,
                        name_parts=self._split_name(admin_name),
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            _('Created admin user "%s" (%s)')
                            % (admin_user.get_full_name(), admin_user.email)
                        )
                    )

                # Create default system configurations for the institution
                self._create_default_configs(institution)

                self.stdout.write(
                    self.style.SUCCESS(_("Institution setup completed successfully!"))
                )
                self.stdout.write(_("Institution details:"))
                self.stdout.write(_("  Name: %s") % institution.name)
                self.stdout.write(_("  Code: %s") % institution.code)
                self.stdout.write(
                    _("  Subdomain: %s.%s")
                    % (
                        institution.code,
                        getattr(settings, "TENANT_DOMAIN", "localhost"),
                    )
                )
                self.stdout.write(_("  Max Students: %d") % institution.max_students)
                self.stdout.write(_("  Max Staff: %d") % institution.max_staff)

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(_("Error creating institution: %s") % str(e))
                )
                raise

    def _split_name(self, full_name):
        """Split full name into first and last name."""
        parts = full_name.strip().split()
        if len(parts) >= 2:
            first_name = " ".join(parts[:-1])
            last_name = parts[-1]
        else:
            first_name = full_name
            last_name = ""
        return first_name, last_name

    def _create_institution_admin(self, institution, email, full_name, name_parts):
        """Create an institution admin user."""
        first_name, last_name = name_parts

        # Check if user already exists
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
                "is_verified": True,
            },
        )

        if created:
            # Set a random password - admin can change later
            temp_password = user.make_random_password()
            self.stdout.write(
                self.style.WARNING(
                    _("Temporary password generated for admin user: %s") % temp_password
                )
            )

        # Create or get user profile
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                "employee_id": f"ADMIN_{institution.code.upper()}_001",
            },
        )

        # Get or create admin role for this institution
        admin_role, _ = Role.objects.get_or_create(
            role_type=Role.RoleType.ADMIN,
            institution=institution,
            defaults={
                "name": "Institution Administrator",
                "description": "Administrator for an institution with full access",
                "hierarchy_level": 80,  # High level but below super admin
            },
        )

        # Get current academic session or create one if none exists
        current_session = self._get_or_create_current_session(institution)

        # Create user role if not exists
        user_role, _ = UserRole.objects.get_or_create(
            user=user,
            role=admin_role,
            institution=institution,
            academic_session=current_session,
            defaults={
                "is_primary": True,
            },
        )

        # Create institution-user relationship if not exists
        from apps.core.models import InstitutionUser

        institution_user, _ = InstitutionUser.objects.get_or_create(
            user=user,
            institution=institution,
            defaults={
                "is_primary": True,
                "employee_id": profile.employee_id,
            },
        )

        return user

    def _get_or_create_current_session(self, institution):
        """Get current academic session - no longer creates default one."""
        from apps.academics.models import AcademicSession

        # Just return the current session if it exists, otherwise return None
        # User roles can be created without requiring an academic session initially
        current_session = AcademicSession.objects.filter(is_current=True).first()
        return current_session

    def _create_default_configs(self, institution):
        """Create default system configurations for the institution."""
        # Common system config keys that might be institution-specific
        default_configs = [
            {
                "key": "institution_timezone",
                "value": institution.timezone or "UTC",
                "config_type": "general",
            },
            {
                "key": "institution_currency",
                "value": "USD",
                "config_type": "finance",
            },
            {
                "key": "working_days",
                "value": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "config_type": "academic",
            },
            {
                "key": "academic_year_start_month",
                "value": 7,  # July
                "config_type": "academic",
            },
            {
                "key": "grading_scale",
                "value": {
                    "A": {"min": 90, "max": 100, "points": 4.0},
                    "B": {"min": 80, "max": 89, "points": 3.0},
                    "C": {"min": 70, "max": 79, "points": 2.0},
                    "D": {"min": 60, "max": 69, "points": 1.0},
                    "F": {"min": 0, "max": 59, "points": 0.0},
                },
                "config_type": "academic",
            },
        ]

        for config_data in default_configs:
            # Get or create system config
            system_config, _ = SystemConfig.objects.get_or_create(
                key=config_data["key"],
                defaults={
                    "value": config_data["value"],
                    "config_type": config_data["config_type"],
                    "description": f'Default {config_data["key"]} for institutions',
                    "is_public": True,
                    "allows_institution_override": True,
                },
            )

            # Create institution-specific config
            InstitutionConfig.objects.get_or_create(
                institution=institution,
                system_config=system_config,
                defaults={
                    "override_value": config_data["value"],
                    "is_active": True,
                },
            )


# Import settings at the end to avoid circular imports
from django.conf import settings
