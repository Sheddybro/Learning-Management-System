"""Enrollment form API must not expose another institution's data."""

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Institution
from .models import AcademicSession


class EnrollmentApiTests(TestCase):
    def setUp(self):
        self.school = Institution.objects.create(name="Home School", code="DEFAULT")
        self.other_school = Institution.objects.create(name="Other School", code="OTHER")
        self.user = get_user_model().objects.create_superuser(
            email="api-admin@example.com", password="test-only-password"
        )
        self.session = AcademicSession.objects.create(
            name="Other School Session", institution=self.other_school,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )

    def test_endpoints_require_authentication(self):
        for name in (
            "academics:api_students_available",
            "academics:api_session_info",
            "academics:api_classes_by_session",
            "academics:api_check_roll_number",
        ):
            with self.subTest(route=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)

    def test_other_school_session_cannot_be_fetched(self):
        self.client.force_login(self.user)
        for name in ("academics:api_session_info", "academics:api_classes_by_session"):
            with self.subTest(route=name):
                response = self.client.get(reverse(name), {"session_id": str(self.session.pk)})
                self.assertEqual(response.status_code, 404)

    def test_enrollment_list_excludes_other_school_sessions(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("academics:enrollment_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.session, list(response.context["sessions"]))

    def test_regular_user_cannot_read_student_lookup(self):
        ordinary_user = get_user_model().objects.create_user(
            email="ordinary@example.com", password="test-only-password"
        )
        self.client.force_login(ordinary_user)
        response = self.client.get(reverse("academics:api_students_available"))
        self.assertEqual(response.status_code, 403)

    def test_roll_number_rejects_cross_school_session(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("academics:api_check_roll_number"),
            data=json.dumps({"roll_number": 1, "class_id": str(self.session.pk),
                             "session_id": str(self.session.pk)}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["available"])
