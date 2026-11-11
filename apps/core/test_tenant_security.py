"""Regression coverage for cross-institution session and hostname routing."""

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.core.middleware import TenantMiddleware, get_current_institution


class TenantRoutingSecurityTests(SimpleTestCase):
    def setUp(self):
        self.middleware = TenantMiddleware(lambda request: None)
        self.factory = RequestFactory()
        self.school_a = SimpleNamespace(id="school-a")
        self.school_b = SimpleNamespace(id="school-b")
        self.user = SimpleNamespace(is_authenticated=True, is_superuser=False)

    def make_request(self, host="example.com", session=None, user=None):
        request = self.factory.get("/", HTTP_HOST=host)
        request.session = {} if session is None else session
        request.user = self.user if user is None else user
        return request

    @patch("apps.core.middleware.user_can_access_institution")
    @patch.object(TenantMiddleware, "_get_institution_from_user")
    @patch.object(TenantMiddleware, "_get_institution_from_session")
    @patch.object(TenantMiddleware, "_get_institution_from_subdomain")
    def test_unauthorized_session_cannot_select_school(
        self, hostname, session_lookup, user_lookup, has_access
    ):
        hostname.return_value = None
        session_lookup.return_value = self.school_b
        user_lookup.return_value = self.school_a
        has_access.return_value = False
        request = self.make_request(session={"current_institution_id": "school-b"})

        self.middleware.process_request(request)

        self.assertIs(request.institution, self.school_a)
        self.assertEqual(request.session["current_institution_id"], "school-a")
        self.middleware.process_response(request, None)

    @patch("apps.core.middleware.user_can_access_institution", return_value=False)
    @patch.object(TenantMiddleware, "_get_institution_from_subdomain")
    def test_unauthorized_school_hostname_is_forbidden(self, hostname, has_access):
        hostname.return_value = self.school_b
        request = self.make_request(host="school-b.example.com")

        with self.assertRaises(PermissionDenied):
            self.middleware.process_request(request)
        self.assertIsNone(get_current_institution())

    @patch.object(TenantMiddleware, "_get_institution_from_user")
    @patch.object(TenantMiddleware, "_get_institution_from_session")
    @patch.object(TenantMiddleware, "_get_institution_from_subdomain")
    def test_anonymous_session_cannot_reuse_school(
        self, hostname, session_lookup, user_lookup
    ):
        hostname.return_value = None
        session_lookup.return_value = self.school_b
        request = self.make_request(
            session={"current_institution_id": "school-b"}, user=AnonymousUser()
        )

        self.middleware.process_request(request)

        self.assertIsNone(request.institution)
        self.assertNotIn("current_institution_id", request.session)
        user_lookup.assert_not_called()
        self.middleware.process_response(request, None)

    @override_settings(
        TENANT_DOMAIN="example.com",
        ALLOWED_HOSTS=["school.example.com.attacker.test"],
    )
    @patch("apps.core.middleware.Institution.objects.get")
    def test_lookalike_domain_cannot_resolve_subdomain(self, lookup):
        request = self.make_request(host="school.example.com.attacker.test")
        self.assertIsNone(self.middleware._get_institution_from_subdomain(request))
        lookup.assert_not_called()
