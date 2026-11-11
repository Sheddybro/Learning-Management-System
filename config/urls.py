from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="users:guest_home"), name="home"),
    path("users/", include("apps.users.urls", namespace="users")),
    path("academics/", include("apps.academics.urls", namespace="academics")),
    path("health/", include("apps.health.urls", namespace="health")),
    path(
        "communication/", include("apps.communication.urls", namespace="communication")
    ),
    path("audit/", include("apps.audit.urls", namespace="audit")),
    path("analytics/", include("apps.analytics.urls", namespace="analytics")),
    path("finance/", include("apps.finance.urls", namespace="finance")),
    path("library/", include("apps.library.urls", namespace="library")),
    path("activities/", include("apps.activities.urls", namespace="activities")),
    path("transport/", include("apps.transport.urls", namespace="transport")),
    path("hostels/", include("apps.hostels.urls", namespace="hostels")),
    path("assessment/", include("apps.assessment.urls", namespace="assessment")),
    path("attendance/", include("apps.attendance.urls", namespace="attendance")),
    path("support/", include("apps.support.urls", namespace="support")),
    path("core/", include("apps.core.urls", namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Debug toolbar
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns

# Admin site customization
admin.site.site_header = "Nexus Intelligence School Management System Administration"
admin.site.site_title = "NEXUS Admin"
admin.site.index_title = "Welcome to Nexus School Management System"
