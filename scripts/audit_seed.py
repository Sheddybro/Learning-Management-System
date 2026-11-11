"""Create fictional users exclusively in the isolated UI audit database."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.audit_settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from apps.core.models import Institution, InstitutionUser  # noqa: E402
from apps.users.models import Role, UserRole  # noqa: E402


ROLES = ("school_admin", "teacher", "student", "parent", "accountant", "librarian")
PASSWORD = "OnlyForLocalScreenshotAudit2026!"


def main():
    if settings.SETTINGS_MODULE != "config.audit_settings":
        raise RuntimeError("Audit fixtures must never be created outside config.audit_settings")
    school, _ = Institution.objects.get_or_create(code="DEFAULT", defaults={"name": "Nexus UI Test School"})
    User = get_user_model()
    for kind in ROLES:
        role, _ = Role.objects.get_or_create(
            role_type=kind, institution=school,
            defaults={"name": kind.replace("_", " ").title(), "hierarchy_level": 20},
        )
        email = f"ui-{kind}@example.test"
        user, created = User.objects.get_or_create(email=email, defaults={"is_active": True, "is_verified": True})
        if created:
            user.set_password(PASSWORD)
            user.save(update_fields=["password"])
        InstitutionUser.objects.get_or_create(user=user, institution=school, defaults={"is_primary": True})
        UserRole.objects.get_or_create(user=user, role=role, institution=school, defaults={"is_primary": True})
        print("AUDIT_USER", kind, email)
    superuser, created = User.objects.get_or_create(email="ui-superadmin@example.test", defaults={"is_active": True, "is_verified": True, "is_staff": True, "is_superuser": True})
    if created:
        superuser.set_password(PASSWORD)
        superuser.save(update_fields=["password"])
    InstitutionUser.objects.get_or_create(user=superuser, institution=school, defaults={"is_primary": True})
    print("AUDIT_USER superadmin", superuser.email)


if __name__ == "__main__":
    main()
