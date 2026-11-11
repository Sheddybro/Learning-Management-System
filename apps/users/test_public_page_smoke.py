"""Public entry points must render, not merely resolve their URLs."""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.core.models import Institution


class PublicPageSmokeTests(TestCase):
    def test_public_pages_render_without_server_errors(self):
        names = (
            "home",
            "users:guest_home",
            "users:application_portal",
            "users:student_application",
            "users:staff_application",
            "users:application_submitted",
            "users:login",
            "users:password_reset",
            "users:password_reset_done",
            "users:password_reset_complete",
        )
        for name in names:
            with self.subTest(page=name):
                response = self.client.get(reverse(name), follow=True)
                self.assertEqual(response.status_code, 200)

    def test_private_navigation_redirects_anonymous_visitors(self):
        for name in ("users:dashboard", "users:profile", "core:school_admin_dashboard"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertIn(response.status_code, (301, 302, 403))

    def test_authenticated_user_can_open_dashboard_and_profile(self):
        Institution.objects.create(
            name="Smoke Test School", code="DEFAULT", short_name="Smoke",
            institution_type="high_school", ownership_type="private",
        )
        user = get_user_model().objects.create_user(
            email="smoke@example.com", password="test-only-password"
        )
        self.client.force_login(user)
        for name in ("users:dashboard", "users:profile"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name), follow=True)
                self.assertEqual(response.status_code, 200)
