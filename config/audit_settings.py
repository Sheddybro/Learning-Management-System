"""Fast disposable test schema for broad UI response auditing only.

Not for production, release verification, or migration compatibility testing.
"""

from .settings import *  # noqa: F403,F401
import os

SECRET_KEY = "throwaway-only-for-isolated-ui-audit-tests-never-deploy"
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
DATABASES["default"]["NAME"] = os.environ.get("NEXUS_AUDIT_DB", "/tmp/nexus-ui-audit.sqlite3")
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
ADMINS = []

MIGRATION_MODULES = {
    app.rsplit(".", 1)[-1]: None
    for app in INSTALLED_APPS  # noqa: F405
    if app.startswith("apps.")
}
