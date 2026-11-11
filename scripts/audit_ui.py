"""Read-only inventory of Django pages and their static UX risks.

Usage: python -m scripts.audit_ui

Does not access or mutate application data. Dynamic authorization and form
submissions require separate isolated-database integration tests.
"""

import csv
import os
import re
from collections import Counter
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.template.loader import get_template  # noqa: E402
from django.urls import URLPattern, URLResolver, get_resolver, reverse  # noqa: E402


def walk_patterns(patterns, namespace=()):
    for item in patterns:
        if isinstance(item, URLResolver):
            ns = namespace + ((item.namespace,) if item.namespace else ())
            yield from walk_patterns(item.url_patterns, ns)
        elif isinstance(item, URLPattern):
            name = ":".join((*namespace, item.name)) if item.name else ""
            yield name, str(item.pattern), item.callback


def main():
    root = Path(settings.BASE_DIR)
    output = root / "docs" / "audit"
    output.mkdir(parents=True, exist_ok=True)
    template_rows = []
    for file in sorted((root / "templates").rglob("*.html")):
        name = file.relative_to(root / "templates").as_posix()
        source = file.read_text(encoding="utf-8")
        failures = []
        try:
            get_template(name)
        except Exception as exc:
            failures.append("TEMPLATE_ERROR: " + str(exc))
        if re.search(r'href\s*=\s*[\"\']#[\"\']', source):
            failures.append("PLACEHOLDER_ANCHOR")
        if re.search(r'<button\b[^>]*\bdisabled\b', source, re.I | re.S):
            failures.append("DISABLED_BUTTON")
        if re.search(r'\bonclick\s*=', source):
            failures.append("INLINE_CLICK_HANDLER")
        if re.search(r'<form\b[^>]*\bmethod\s*=\s*[\"\']post[\"\']', source, re.I | re.S) and "{% csrf_token %}" not in source:
            failures.append("CHECK_POST_CSRF")
        template_rows.append((name, ";".join(failures) or "NO_STATIC_FLAGS"))

    route_rows = []
    for name, pattern, callback in walk_patterns(get_resolver().url_patterns):
        note = ""
        path = ""
        if not name:
            note = "UNNAMED"
        else:
            try:
                path = reverse(name)
            except Exception:
                note = "REQUIRES_ARGUMENTS_OR_NOT_REVERSIBLE"
        route_rows.append((name, pattern, path, getattr(callback, "__module__", ""), getattr(callback, "__name__", ""), note))

    with (output / "template_inventory.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("template", "static_flags"))
        writer.writerows(template_rows)
    with (output / "route_inventory.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("name", "pattern", "reversed_path", "view_module", "view", "static_note"))
        writer.writerows(route_rows)

    flag_counts = Counter(flag for _, flags in template_rows for flag in flags.split(";") if flag != "NO_STATIC_FLAGS")
    print("TEMPLATES", len(template_rows), "ROUTES", len(route_rows))
    print("STATIC_FLAGS", dict(sorted(flag_counts.items())))
    print("OUTPUT", output)


if __name__ == "__main__":
    main()
