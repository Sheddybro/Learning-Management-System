"""Database-backed checks for school-scoped leave application workflows."""

from datetime import timedelta
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.attendance.models import LeaveApplication, LeaveType
from apps.attendance.views import LeaveApplicationCreateView, LeaveApplicationListView
from apps.core.models import Institution, InstitutionUser
from apps.users.models import User


class LeaveWorkflowIntegrationTests(TestCase):
    def setUp(self):
        temporary_media = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_media.cleanup)
        media_settings = override_settings(MEDIA_ROOT=temporary_media.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.factory = RequestFactory()
        self.school_a = Institution.objects.create(name="School A", code="SCH-A")
        self.school_b = Institution.objects.create(name="School B", code="SCH-B")
        self.user_a = User.objects.create_user(email="teacher-a@example.test", password="example-test-password")
        self.user_b = User.objects.create_user(email="teacher-b@example.test", password="example-test-password")
        InstitutionUser.objects.create(user=self.user_a, institution=self.school_a, is_primary=True)
        InstitutionUser.objects.create(user=self.user_b, institution=self.school_b, is_primary=True)
        self.leave_type = LeaveType.objects.create(
            institution=self.school_a, name="Sick leave", code="SICK-A"
        )

    def test_submission_saves_application_and_uploaded_document(self):
        start = timezone.localdate() + timedelta(days=2)
        uploaded = SimpleUploadedFile("doctor-note.pdf", b"small test document", content_type="application/pdf")
        request = self.factory.post(
            reverse("attendance:leave_create"),
            {
                "leave_type": str(self.leave_type.pk),
                "start_date": str(start),
                "end_date": str(start + timedelta(days=1)),
                "reason": "Medical appointment",
                "supporting_documents": uploaded,
            },
        )
        request.user = self.user_a
        from django.contrib.messages.storage.fallback import FallbackStorage
        request.session = {}
        request._messages = FallbackStorage(request)

        with patch("apps.attendance.views.get_current_institution", return_value=self.school_a):
            response = LeaveApplicationCreateView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        application = LeaveApplication.objects.get(applicant=self.user_a)
        self.assertEqual(application.institution, self.school_a)
        self.assertEqual(application.total_days, 2)
        attachments = list(application.supporting_documents.all())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].institution, self.school_a)
        self.assertEqual(attachments[0].uploaded_by, self.user_a)

    def test_other_school_cannot_find_leave_record(self):
        application = LeaveApplication.objects.create(
            institution=self.school_a,
            applicant=self.user_a,
            leave_type=self.leave_type,
            start_date=timezone.localdate() + timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=1),
            reason="Family appointment",
        )
        view = LeaveApplicationListView()
        view.request = self.factory.get(reverse("attendance:leave_list"))
        view.request.user = self.user_b
        with patch("apps.attendance.views.get_current_institution", return_value=self.school_b):
            self.assertFalse(view.get_queryset().filter(pk=application.pk).exists())
