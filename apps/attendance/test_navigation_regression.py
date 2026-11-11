"""Regression checks for attendance links exposed by the user interface."""

import uuid
from unittest.mock import Mock, patch
from types import SimpleNamespace

from django.test import SimpleTestCase, RequestFactory
from django.urls import resolve, reverse

from apps.attendance.views import (
    AttendanceConfigUpdateView,
    AttendanceSessionCreateView,
    AttendanceSessionUpdateView,
    DailyAttendanceCreateView,
    DailyAttendanceUpdateView,
    DailyAttendanceDeleteView,
    LeaveApplicationCreateView,
    LeaveApplicationUpdateView,
    LeaveApplicationDeleteView,
    BehaviorRecordCreateView,
    BehaviorRecordUpdateView,
    BehaviorRecordDeleteView,
    LeaveApplicationListView,
)


class AttendanceNavigationTests(SimpleTestCase):
    def test_success_redirects_are_namespaced(self):
        expected = {
            AttendanceConfigUpdateView: "attendance:config",
            AttendanceSessionCreateView: "attendance:session_list",
            AttendanceSessionUpdateView: "attendance:session_list",
            DailyAttendanceDeleteView: "attendance:daily_list",
            LeaveApplicationDeleteView: "attendance:leave_list",
            BehaviorRecordCreateView: "attendance:behavior_list",
            BehaviorRecordUpdateView: "attendance:behavior_list",
            BehaviorRecordDeleteView: "attendance:behavior_list",
        }
        for view, route in expected.items():
            with self.subTest(view=view.__name__):
                self.assertEqual(str(view.success_url), reverse(route))

    def test_dynamic_success_redirects(self):
        for view, route in (
            (DailyAttendanceCreateView, "attendance:daily_list"),
            (DailyAttendanceUpdateView, "attendance:daily_list"),
            (LeaveApplicationCreateView, "attendance:leave_list"),
            (LeaveApplicationUpdateView, "attendance:leave_list"),
        ):
            with self.subTest(view=view.__name__):
                self.assertEqual(str(view().get_success_url()), reverse(route))

    def test_leave_record_links_accept_uuid_primary_keys(self):
        record_id = uuid.uuid4()
        for route in ("attendance:leave_review", "attendance:leave_delete"):
            with self.subTest(route=route):
                url = reverse(route, kwargs={"pk": record_id})
                match = resolve(url)
                self.assertEqual(match.view_name, route)
                self.assertEqual(match.kwargs["pk"], record_id)

    def test_leave_search_uses_existing_email_field(self):
        # Avoid querying the database: validate the generated SQL for a search.
        # User has no username field, so the old lookup raised FieldError.
        view = LeaveApplicationListView()
        request = RequestFactory().get("/attendance/leaves/?search=example")
        request.user = type("UserStub", (), {"is_staff": True})()
        view.request = request
        with patch('apps.attendance.views.filter_queryset_by_institution', side_effect=lambda qs, user: qs), patch('apps.attendance.views.get_current_institution', return_value=None):
            queryset = view.get_queryset()
        self.assertIn("email", str(queryset.query).lower())

    def test_leave_submission_requires_an_authorized_school(self):
        view = LeaveApplicationCreateView()
        view.request = RequestFactory().post('/attendance/leaves/create/')
        view.request.user = Mock()
        form = Mock()
        view.form_invalid = Mock(return_value='invalid form')
        with patch('apps.attendance.views.get_current_institution', return_value=None):
            self.assertEqual(view.form_valid(form), 'invalid form')
        form.add_error.assert_called_once()

    def test_leave_submission_rejects_oversize_documents(self):
        view = LeaveApplicationCreateView()
        view.request = RequestFactory().post('/attendance/leaves/create/')
        view.request.user = Mock()
        view.request.FILES.getlist = Mock(return_value=[
            SimpleNamespace(name='oversize.pdf', size=11 * 1024 * 1024)
        ])
        form = Mock()
        view.form_invalid = Mock(return_value='invalid form')
        with patch('apps.attendance.views.get_current_institution', return_value=Mock()), patch('apps.attendance.views.user_can_access_institution', return_value=True):
            self.assertEqual(view.form_valid(form), 'invalid form')
        form.add_error.assert_called_once()
