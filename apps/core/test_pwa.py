"""Install metadata must be public without persisting private school records."""

from django.test import SimpleTestCase
from django.urls import reverse


class InstallableWebClientTests(SimpleTestCase):
    def test_manifest_is_public_and_scoped_to_website(self):
        response = self.client.get(reverse("app_manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/manifest+json"))
        body = response.json()
        self.assertEqual(body["display"], "standalone")
        self.assertEqual(body["scope"], "/")
        self.assertEqual(body["start_url"], reverse("users:guest_home"))

    def test_service_worker_does_not_store_private_responses(self):
        response = self.client.get(reverse("app_service_worker"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotIn("caches.open", response.content.decode())
        self.assertNotIn("fetch", response.content.decode())
