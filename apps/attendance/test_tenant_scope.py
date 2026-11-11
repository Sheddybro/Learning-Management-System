"""Regression tests for tenant-scoped student attendance views."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.academics.models import Student
from apps.attendance.views import StudentAttendanceView


class StudentAttendanceTenantScopeTests(SimpleTestCase):
    def test_student_can_only_resolve_their_own_profile(self):
        student = object()
        user = SimpleNamespace(student_profile=student)
        view = StudentAttendanceView()
        view.request = SimpleNamespace(user=user)
        view.kwargs = {"pk": "another-student"}

        self.assertIs(view.get_object(), student)

    @patch("apps.attendance.views.get_object_or_404")
    @patch("apps.attendance.views.get_current_institution", return_value=None)
    @patch("apps.attendance.views.filter_queryset_by_institution")
    def test_staff_student_lookup_uses_accessible_institution_queryset(
        self, scope_queryset, current_institution, lookup
    ):
        user = SimpleNamespace(
            is_authenticated=True,
            is_staff=True,
            is_superuser=False,
        )
        request = RequestFactory().get("/attendance/student/")
        request.user = user
        view = StudentAttendanceView()
        view.request = request
        view.kwargs = {"pk": "student-id"}
        scope_queryset.return_value = Student.objects.none()
        student = object()
        lookup.return_value = student

        self.assertIs(view.get_object(), student)
        self.assertIs(scope_queryset.call_args.args[0].model, Student)
        self.assertIs(scope_queryset.call_args.args[1], user)
        lookup.assert_called_once()
        self.assertEqual(lookup.call_args.kwargs["pk"], "student-id")
