"""Compile every UI template and reject newly introduced parser failures.

The tracked exceptions are existing defects, not passing features. Remove each
entry as its template is repaired; the long-term target is an empty set.
"""

from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase


KNOWN_BROKEN_TEMPLATES = {
    "activities/activity_detail.html",
    "activities/enrollment_list.html",
    "principal/principal_teacher_management.html",
    "academics/holidays/holiday_detail.html",
    "academics/students/academic_records.html",
    "library/books/book_detail.html",
    "library/reports/member_activity.html",
    "transport/attendants/attendant_detail.html",
    "users/parent/message_teacher.html",
    "support/security/user_sessions.html",
    "support/cases/case_escalate.html",
    "support/cases/case_bulk_actions.html",
    "support/cases/case_confirm_delete.html",
    "support/cases/case_form.html",
    "support/cases/case_detail.html",
    "support/cases/case_list.html",
    "assessment/results/assessment_results.html",
    "communication/sms/smstemplate_form.html",
    "communication/noticeboards/noticeboard_display.html",
    "health/appointments/appointment_list.html",
    "health/dashboard/dashboard.html",
}


class TemplateCompilationTests(SimpleTestCase):
    def test_no_new_template_compilation_errors(self):
        root = Path(settings.BASE_DIR) / "templates"
        errors = {}
        for path in root.rglob("*.html"):
            name = path.relative_to(root).as_posix()
            try:
                get_template(name)
            except Exception as exc:
                errors[name] = str(exc)

        unexpected = {name: error for name, error in errors.items()
                      if name not in KNOWN_BROKEN_TEMPLATES}
        self.assertFalse(unexpected, f"New broken UI templates: {unexpected}")
