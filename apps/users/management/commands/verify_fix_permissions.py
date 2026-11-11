from django.core.management.base import BaseCommand
from django.core.management import call_command
from apps.users.models import Role


class Command(BaseCommand):
    help = "Verify role/permission consistency and optionally fix by reassigning permissions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Run `assign_role_permissions` and `sync_permissions` to fix issues.",
        )

    def handle(self, *args, **options):
        fix = options.get("fix")

        self.stdout.write("Scanning roles for issues...")

        roles = Role.objects.all().select_related("institution")
        missing_institution = []
        zero_permissions = []

        for role in roles:
            if not getattr(role, "institution", None):
                missing_institution.append(role)
                continue

            if role.permissions.count() == 0:
                zero_permissions.append(role)

        self.stdout.write(f"Total roles: {roles.count()}")
        self.stdout.write(f"Roles with missing institution: {len(missing_institution)}")
        for r in missing_institution:
            self.stdout.write(
                f" - {r} (institution_id={getattr(r, 'institution_id', None)})"
            )

        self.stdout.write(f"Roles with zero permissions: {len(zero_permissions)}")
        for r in zero_permissions:
            inst_name = getattr(
                r.institution, "name", getattr(r, "institution_id", None)
            )
            self.stdout.write(f" - {r} (Institution: {inst_name})")

        if fix:
            self.stdout.write("Running assign_role_permissions...")
            call_command("assign_role_permissions")
            self.stdout.write("Running sync_permissions...")
            call_command("sync_permissions")
            self.stdout.write(
                self.style.SUCCESS(
                    "Fix attempted: assign_role_permissions + sync_permissions executed."
                )
            )
        else:
            self.stdout.write(
                "No changes made. Re-run with --fix to attempt automatic fixes (will call assign_role_permissions and sync_permissions)."
            )
