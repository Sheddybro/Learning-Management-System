"""Protect password-reset credentials and avoid user enumeration."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_RESET_TIMEOUT=3600,
)
class PasswordResetSecurityTests(TestCase):
    def test_existing_account_receives_token_without_password_change(self):
        user = get_user_model().objects.create_user(
            email="teacher@example.com", password="a-long-unique-original-password"
        )
        original_hash = user.password

        response = self.client.post(
            reverse("users:password_reset"), {"email": user.email}
        )

        self.assertRedirects(response, reverse("users:password_reset_done"))
        user.refresh_from_db()
        self.assertEqual(user.password, original_hash)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/users/password-reset-confirm/", mail.outbox[0].body)
        self.assertNotIn("a-long-unique-original-password", mail.outbox[0].body)

    def test_unknown_account_has_same_success_redirect(self):
        response = self.client.post(
            reverse("users:password_reset"), {"email": "unknown@example.com"}
        )

        self.assertRedirects(response, reverse("users:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
