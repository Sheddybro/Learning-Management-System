"""Regression checks for attendance links exposed by the user interface."""

import uuid

from django.test import SimpleTestCase
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
