"""Install metadata for the shared desktop/mobile web client.

The service worker intentionally does not cache pages or API responses:
school records, credentials and cross-tenant sessions must remain online-only.
"""

from django.http import HttpResponse, JsonResponse
from django.urls import reverse


def web_manifest(request):
    icon = "/static/images/Nexus.png"
    response = JsonResponse(
        {
            "name": "Nexus School Management",
            "short_name": "Nexus School",
            "description": "Secure school management for administrators, teachers, students and parents.",
            "id": "/",
            "start_url": reverse("users:guest_home"),
            "scope": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": "#174ea6",
            "icons": [{"src": icon, "sizes": "1024x1024", "type": "image/png", "purpose": "any"}],
        }
    )
    response["Content-Type"] = "application/manifest+json"
    response["Cache-Control"] = "public, max-age=3600"
    return response


def service_worker(request):
    script = """// Network-only: never persist student, tenant, or authentication data.
self.addEventListener('install', event => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
"""
    response = HttpResponse(script, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-store"
    return response
