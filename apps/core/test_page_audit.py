"""GET-only page audit using a disposable Django test database.

The audit writes a response matrix; it does not assert every page should return
200, because authentication, permissions and API method restrictions vary.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client, TestCase
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.core.models import Institution


SKIP_WORDS = (
    "delete", "logout", "cancel", "approve", "reject", "process",
    "export", "download", "payment", "callback", "webhook", "upload",
    "send", "sync", "generate", "mark_", "verify", "activate", "deactivate",
    "import", "recalculate", "reset", "purge", "clear", "archive",
)


def routes(patterns, namespace=()):
    for item in patterns:
        if isinstance(item, URLResolver):
            current = namespace + ((item.namespace,) if item.namespace else ())
            yield from routes(item.url_patterns, current)
        elif isinstance(item, URLPattern) and item.name:
            name = ":".join((*namespace, item.name))
            try:
                yield name, reverse(name)
            except Exception:
                continue


class PageResponseAudit(TestCase):
    def test_parameterless_pages_for_guest_and_admin(self):
        Institution.objects.create(name="Audit School", code="DEFAULT")
        user = get_user_model().objects.create_superuser(
            email="ui-audit@example.test", password="test-only-credential"
        )
        guest_client = Client(raise_request_exception=False)
        admin_client = Client(raise_request_exception=False)
        admin_client.force_login(user)
        rows = []
        for name, path in sorted(set(routes(get_resolver().url_patterns))):
            if any(word in name.lower() for word in SKIP_WORDS):
                rows.append((name, path, "SKIPPED_ACTION", "SKIPPED_ACTION"))
                continue
            try:
                with transaction.atomic():
                    guest = guest_client.get(path, follow=False).status_code
                    if guest >= 500:
                        transaction.set_rollback(True)
            except Exception as exc:
                guest = "EXCEPTION: " + type(exc).__name__
            try:
                with transaction.atomic():
                    admin = admin_client.get(path, follow=False).status_code
                    if admin >= 500:
                        transaction.set_rollback(True)
            except Exception as exc:
                admin = "EXCEPTION: " + type(exc).__name__
            rows.append((name, path, guest, admin))
            if len(rows) % 100 == 0:
                print(f"Audited {len(rows)} parameterless routes", flush=True)

        output = Path(settings.BASE_DIR) / "docs" / "audit" / "page_response_matrix.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(("name", "path", "guest_status", "admin_status"))
            writer.writerows(rows)
        failures = [r for r in rows if r[2] == 500 or r[3] == 500 or "EXCEPTION" in str(r[2]) or "EXCEPTION" in str(r[3])]
        self.assertFalse(failures, f"Page exceptions: {failures[:20]} (total={len(failures)})")
