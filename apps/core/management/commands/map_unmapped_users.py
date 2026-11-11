#!/usr/bin/env python
"""
Management command to automatically map unmapped users to institutions.
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.users.models import User, Role, UserRole
from apps.core.models import Institution, InstitutionUser


class Command(BaseCommand):
    help = "Automatically map users without institution assignments to appropriate institutions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--institution",
            type=str,
            help="Specific institution code to map users to (optional)",
            default=None,
        )
        parser.add_argument(
            "--auto-assign",
            action="store_true",
            help="Automatically assign to first available institution",
            default=True,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making changes",
            default=False,
        )

    def handle(self, *args, **options):
        institution_code = options.get("institution")
        auto_assign = options.get("auto_assign", True)
        dry_run = options.get("dry_run", False)

        self.stdout.write(self.style.SUCCESS("Institution User Mapping Tool"))
        self.stdout.write("=" * 50)

        # Find unmapped staff users
        staff_role_types = [
            "super_admin",
            "school admin",
            "admin",
            "principal",
            "department_head",
            "counselor",
            "teacher",
            "accountant",
            "librarian",
            "driver",
            "support",
            "transport_manager",
            "hostel_warden",
        ]

        # Users with staff roles but no primary institution mapping
        unmapped_users = User.objects.filter(
            Q(
                user_roles__role__role_type__in=staff_role_types,
                user_roles__status="active",
            )
            & ~Q(institution_memberships__is_primary=True)
        ).distinct()

        if not unmapped_users:
            self.stdout.write(self.style.SUCCESS("No unmapped users found!"))
            return

        self.stdout.write(f"Found {len(unmapped_users)} unmapped user(s):")
        for user in unmapped_users:
            roles = [role.role.name for role in user.user_roles.filter(status="active")]
            self.stdout.write(f'  - {user.email}: {", ".join(roles)}')

        # Determine target institution
        if institution_code:
            try:
                institution = Institution.objects.get(
                    code=institution_code, is_active=True
                )
                self.stdout.write(
                    f"Using specified institution: {institution.name} ({institution.code})"
                )
            except Institution.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f'Institution with code "{institution_code}" not found!'
                    )
                )
                return
        elif auto_assign:
            institution = Institution.objects.filter(is_active=True).first()
            if not institution:
                self.stdout.write(self.style.ERROR("No active institutions found!"))
                return
            self.stdout.write(
                f"Auto-selected institution: {institution.name} ({institution.code})"
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    "No institution specified and auto-assign is disabled!"
                )
            )
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN - No changes will be made"))
            self.stdout.write(
                f"Would map {len(unmapped_users)} users to: {institution.name}"
            )
            return

        # Perform the mappings
        mapped_count = 0
        errors = []

        for user in unmapped_users:
            try:
                # Get the user's primary role for employee ID generation
                primary_role = user.user_roles.filter(
                    is_primary=True, status="active"
                ).first()

                if primary_role:
                    role_type = primary_role.role.role_type
                else:
                    # Use the first active role
                    first_role = user.user_roles.filter(status="active").first()
                    role_type = first_role.role.role_type if first_role else "staff"

                # Generate employee ID
                employee_id = f"{role_type}_{institution.code}_{user.id}"

                # Check if mapping already exists (double check)
                existing_mapping = InstitutionUser.objects.filter(
                    user=user, institution=institution
                ).first()

                if existing_mapping:
                    self.stdout.write(
                        self.style.WARNING(
                            f"User {user.email} already mapped to {institution.code}"
                        )
                    )
                    continue

                # Create the mapping
                institution_user = InstitutionUser.objects.create(
                    user=user,
                    institution=institution,
                    is_primary=True,
                    employee_id=employee_id,
                )

                # Update user profile with employee ID
                if hasattr(user, "profile") and user.profile:
                    user.profile.employee_id = employee_id
                    user.profile.save()

                mapped_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Mapped {user.email} to {institution.code} with ID {employee_id}"
                    )
                )

            except Exception as e:
                error_msg = f"Error mapping {user.email}: {str(e)}"
                errors.append(error_msg)
                self.stdout.write(self.style.ERROR(error_msg))

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(
                f"Mapping complete! Successfully mapped {mapped_count} users."
            )
        )

        if errors:
            self.stdout.write(
                self.style.WARNING(f"Encountered {len(errors)} error(s).")
            )
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))

        # Show final statistics
        total_staff = (
            User.objects.filter(
                user_roles__role__role_type__in=staff_role_types,
                user_roles__status="active",
            )
            .distinct()
            .count()
        )

        mapped_staff = (
            User.objects.filter(
                user_roles__role__role_type__in=staff_role_types,
                user_roles__status="active",
                institution_memberships__is_primary=True,
            )
            .distinct()
            .count()
        )

        unmapped_after = total_staff - mapped_staff

        self.stdout.write(f"\nInstitution Statistics:")
        self.stdout.write(f"  - Total staff users: {total_staff}")
        self.stdout.write(f"  - Mapped to institutions: {mapped_staff}")
        self.stdout.write(f"  - Still unmapped: {unmapped_after}")
