import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file in setup directory
load_dotenv(BASE_DIR / "setup" / ".env")

# Add apps directory to Python path
sys.path.insert(0, str(BASE_DIR / "apps"))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("SECRET_KEY")

# Check if we're on PythonAnywhere (defined early for CHANNEL_LAYERS)
ON_PYTHONANYWHERE = "PYTHONANYWHERE_DOMAIN" in os.environ
SITE_HOSTNAME = os.environ.get("SITE_DOMAIN", "learningmanagementsystem.pythonanywhere.com").lower()

# ============================
# SECURITY & DEBUG SETTINGS
# ============================

if ON_PYTHONANYWHERE:
    # Production settings for PythonAnywhere
    DEBUG = False
    ALLOWED_HOSTS = [SITE_HOSTNAME]
else:
    # Development settings
    DEBUG = True
    # Include 'testserver' so Django test client requests don't raise DisallowedHost
    ALLOWED_HOSTS = os.environ.get(
        "ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
    ).split(",")

# ============================
# APPLICATION DEFINITION
# ============================

INSTALLED_APPS = [
    # Custom apps
    "apps.core",
    "apps.users",
    "apps.academics",
    "apps.audit",
    "apps.analytics",
    "apps.attendance",
    "apps.assessment",
    "apps.communication",
    "apps.finance",
    "apps.library",
    "apps.transport",
    "apps.hostels",
    "apps.support",
    "apps.activities",
    "apps.health",
    # Django built-in apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",
    # Third-party apps
    "rest_framework",
    "templated_mail",
    "crispy_forms",
    "crispy_bootstrap5",
    "django_extensions",
    "channels",
    # Authentication & Social Auth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]

# Default sites framework site id (used by django.contrib.sites.get_current)
SITE_ID = int(os.environ.get("SITE_ID", 1))

# Crispy Forms Configuration
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ============================
# MIDDLEWARE CONFIGURATION
# ============================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # For serving static files
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Multi-tenancy middleware (must come after AuthenticationMiddleware)
    "apps.core.middleware.TenantMiddleware",
    # Allauth middleware
    "allauth.account.middleware.AccountMiddleware",
]

# ============================
# URL & TEMPLATE CONFIGURATION
# ============================

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "builtins": [
                "django.templatetags.i18n",
                "django.templatetags.static",
                "apps.attendance.templatetags.attendance_filters",
                "apps.users.templatetags.user_filters",
                "apps.communication.templatetags.communication_tags",
                "apps.core.templatetags.filters",
                "apps.academics.templatetags.academics_filters",
                "apps.activities.templatetags.activity_filters",
                "apps.assessment.templatetags.assessment_tags",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.site_context_processor.site",
                "apps.communication.context_processors.notification_count",
                "apps.communication.context_processors.noticeboard_data",
                "apps.communication.context_processors.active_announcements",
                "apps.users.context_processors.user_roles",
                "apps.core.context_processors.sidebar_menu_context",
                "apps.core.context_processors.ui_config_context",
                # Tenant context processors
                "apps.core.context_processors.current_institution",
                "apps.core.context_processors.tenant_context",
            ],
        },
    },
]

# ============================
# WSGI & ASGI CONFIGURATION
# ============================

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ============================
# DATABASE CONFIGURATION
# ============================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ============================
# CHANNELS CONFIGURATION
# ============================

if ON_PYTHONANYWHERE:
    # PythonAnywhere doesn't support WebSockets on free tier, so we disable Channels
    # For paid tier, you can enable Redis
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }
else:
    # For local development, use InMemoryChannelLayer (Note: For production, use Redis)
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# ============================
# PASSWORD VALIDATION
# ============================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ============================
# INTERNATIONALIZATION
# ============================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ============================
# STATIC & MEDIA FILES
# ============================

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
MEDIA_URL = "/media/"

if ON_PYTHONANYWHERE:
    # Production static files setup for PythonAnywhere
    STATIC_ROOT = BASE_DIR / "staticfiles"
    STATICFILES_DIRS = [BASE_DIR / "static"]
    MEDIA_ROOT = BASE_DIR / "media"
else:
    # Development static files setup
    STATICFILES_DIRS = [BASE_DIR / "static"]
    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_ROOT = BASE_DIR / "media"

# WhiteNoise configuration for static files
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ============================
# AUTHENTICATION
# ============================

# Custom user model
AUTH_USER_MODEL = "users.User"

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Login URLs
LOGIN_URL = "/users/login/"
LOGIN_REDIRECT_URL = "/dashboard/"

# Django Allauth Settings
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_CONFIRMATION_HMAC = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_CONFIRMATION_COOLDOWN = 180

# Disable automatic signup via social accounts - we only allow account linking
ACCOUNT_ADAPTER = "apps.users.adapters.CustomAccountAdapter"
SOCIALACCOUNT_ADAPTER = "apps.users.adapters.CustomSocialAccountAdapter"

# Social account settings
SOCIALACCOUNT_AUTO_SIGNUP = False  # Don't automatically sign up users
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"  # We'll handle email verification ourselves
SOCIALACCOUNT_QUERY_EMAIL = True  # Ask for email permission from Google

# Social account providers
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "APP": {
            "client_id": "YOUR_GOOGLE_CLIENT_ID_HERE",  # Replace with actual client ID
            "secret": "YOUR_GOOGLE_CLIENT_SECRET_HERE",  # Replace with actual client secret
            "key": "",
        },
    }
}

# ============================
# DEFAULT PRIMARY KEY FIELD TYPE
# ============================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============================
# ADMINISTRATORS
# ============================

ADMINS = [("Nexus Admin", "supereaglepilot@gmail.com")]
MANAGERS = ADMINS

# ============================
# EMAIL CONFIGURATION
# ============================

# Email Backend Configuration
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "30"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "webmaster@localhost")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Gmail-specific settings for better compatibility
if EMAIL_HOST == "smtp.gmail.com":
    # Ensure TLS is enabled for Gmail
    EMAIL_USE_TLS = True
    EMAIL_USE_SSL = False
    # Gmail requires authentication
    if (
        EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend"
        and (not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD)
    ):
        logger.warning(
            "Gmail SMTP configured but EMAIL_HOST_USER or EMAIL_HOST_PASSWORD not set"
        )

# ============================
# SECURITY SETTINGS
# ============================

if ON_PYTHONANYWHERE:
    # Production security settings
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

    # CSRF trusted origins for PythonAnywhere
    CSRF_TRUSTED_ORIGINS = [f"https://{SITE_HOSTNAME}"]
else:
    # Development mode overrides
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False

    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:8000",
        "https://localhost:8000",
        "http://127.0.0.1:8000",
        "https://127.0.0.1:8000",
    ]

# ============================
# MULTI-TENANCY SETTINGS
# ============================

# Default tenant domain used by TenantMiddleware when resolving subdomains
TENANT_DOMAIN = os.environ.get("TENANT_DOMAIN", SITE_HOSTNAME if ON_PYTHONANYWHERE else "localhost")

# Control implicit creation of a DEFAULT institution from model/save/signals.
# Set to False to prevent automatic creation of default institutions.
# All institutions must be created explicitly through management commands or admin interface.
ALLOW_IMPLICIT_INSTITUTION_CREATION = False

# Default institution for single-tenant fallback
DEFAULT_INSTITUTION_CODE = (
    None  # Set to an institution code if you want a default fallback
)

# Enable tenant subdomain routing (disable for single institution mode)
TENANT_SUBDOMAIN_ENABLED = True

# Allow users to switch institutions (if they have access to multiple)
ALLOW_INSTITUTION_SWITCHING = True

# Cache timeout for institution data (in seconds)
INSTITUTION_CACHE_TIMEOUT = 3600  # 1 hour

# Enable institution-specific branding
INSTITUTION_BRANDING_ENABLED = True

# Maximum institutions per user account
MAX_INSTITUTIONS_PER_USER = 5

# Enable tenant data isolation (always True for security)
TENANT_DATA_ISOLATION = True

# ============================
# SITE FRAMEWORK SETTINGS
# ============================

SITE_ID = 1
SITE_NAME = "Nexus Intelligence School Management System"
SITE_DOMAIN = SITE_HOSTNAME

# ============================
# LOGGING CONFIGURATION
# ============================

# Create logs directory if it doesn't exist
logs_dir = BASE_DIR / "logs"
logs_dir.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "production.log",
            "maxBytes": 1024 * 1024 * 5,  # 5 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "include_html": True,
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["mail_admins", "file"],
            "level": "ERROR",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# Configure production site
def configure_production_site():
    """Configure the Site model for production with correct domain."""
    try:
        from django.contrib.sites.models import Site

        site_domain = SITE_DOMAIN
        site_name = os.environ.get(
            "SITE_NAME", "Nexus Intelligence School Management System"
        )

        site, created = Site.objects.get_or_create(
            id=1, defaults={"name": site_name, "domain": site_domain}
        )
        if not created:
            site.name = site_name
            site.domain = site_domain
            site.save()

        print(f"Site configured: {site_name} - {site_domain}")
    except Exception as e:
        print(f"Warning: Could not configure site: {e}")


# Configure site after Django is ready
from django.apps import apps
from django.db.models.signals import post_migrate


def configure_site_after_migrate(sender, **kwargs):
    configure_production_site()


post_migrate.connect(configure_site_after_migrate)
