"""Repeatable, read-only checks of repaired school-system pages by role."""
import csv
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.audit_settings")

import django
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


PAGES = [
    "activities:activity_list",
    "activities:activity_create",
    "activities:competition_list",
    "activities:my_activities",
    "activities:enrollment_list",
    "activities:equipment_list",
    "activities:equipment_create",
    "activities:budget_list",
    "attendance:student_my_attendance",
    "academics:class_create",
    "academics:committee_dashboard",
    "core:principal_teacher_management",
    "transport:reports",
    "library:login",
    "hostels:api_hostel_list",
    "analytics:dashboard",
    "analytics:report_list",
    "analytics:report_type_picker",
    "analytics:api_report_types",
    "analytics:export_reports",
]
ROLES = ["guest", "superadmin", "school_admin", "teacher", "student", "parent", "accountant", "librarian"]


def main():
    if settings.SETTINGS_MODULE != "config.audit_settings":
        raise RuntimeError("Audit tests must only use config.audit_settings")
    path = Path(settings.BASE_DIR) / "docs/audit/targeted_regression_matrix.csv"
    User = get_user_model()
    failed = []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["role", "route", "status", "location", "result"])
        for role in ROLES:
            client = Client(raise_request_exception=True)
            if role != "guest":
                client.force_login(User.objects.get(email=f"ui-{role}@example.test"))
            for name in PAGES:
                try:
                    response = client.get(reverse(name))
                    status = response.status_code
                    location = response.get("Location", "")
                    result = "PASS" if status < 500 else "FAIL"
                    if role == "guest" and name != "library:login":
                        result = "PASS" if status in (302, 403) else "REVIEW"
                except Exception as error:
                    status = type(error).__name__
                    location = str(error)[:160]
                    result = "FAIL"
                writer.writerow([role, name, status, location, result])
                if result != "PASS":
                    failed.append((role, name, status, result))
    print(f"Checked={len(PAGES)*len(ROLES)} review_or_fail={len(failed)} file={path}")
    for item in failed[:20]:
        print(item)


if __name__ == "__main__":
    main()
