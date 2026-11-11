"""Read-only multi-role GET matrix against the isolated local screenshot database."""

import csv
import logging
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.audit_settings")

import django  # noqa: E402

django.setup()
logging.disable(logging.CRITICAL)

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db import transaction  # noqa: E402
from django.test import Client  # noqa: E402

from apps.core.test_page_audit import SKIP_WORDS, routes  # noqa: E402
from django.urls import get_resolver  # noqa: E402


def main():
    if settings.SETTINGS_MODULE != "config.audit_settings":
        raise RuntimeError("Never run this audit against production settings")

    roles = ["guest", "superadmin", "school_admin", "teacher", "student", "parent", "accountant", "librarian"]
    clients = {}
    User = get_user_model()
    for role in roles:
        client = Client(raise_request_exception=True)
        if role != "guest":
            email = f"ui-{role}@example.test"
            client.force_login(User.objects.get(email=email))
        clients[role] = client

    output = Path(settings.BASE_DIR) / "docs" / "audit" / "role_permission_matrix.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    failures = []
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "path", *roles])
        for index, (name, path) in enumerate(sorted(set(routes(get_resolver().url_patterns))), 1):
            row = [name, path]
            for role, client in clients.items():
                if any(word in name.lower() for word in SKIP_WORDS):
                    row.append("SKIP_ACTION")
                    continue
                try:
                    with transaction.atomic():
                        status = client.get(path, follow=False).status_code
                        if status >= 500:
                            transaction.set_rollback(True)
                    row.append(str(status))
                except Exception as exc:
                    message = f"ERROR {type(exc).__name__}: {str(exc)[:100]}"
                    row.append(message)
                    failures.append((name, role, message))
            writer.writerow(row)
            if index % 100 == 0:
                handle.flush()
                print(f"ROLE_AUDIT {index} routes", flush=True)
    print(f"ROLE_AUDIT_DONE routes={index} exceptions={len(failures)} output={output}")


if __name__ == "__main__":
    main()
