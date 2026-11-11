"""Enrollment form API must not expose another institution's data."""

import json
from datetime import date, time
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Institution
from .models import AcademicSession, Class, Student, Teacher, Timetable, Enrollment
from apps.core.models import InstitutionUser


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
        self.other_class = Class.objects.create(
            name="Other School Class", code="OTHER-C1",
            academic_session=self.session, institution=self.other_school,
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

    def test_enrollment_list_malformed_filters_do_not_crash(self):
        self.client.force_login(self.user)
        for key in ("class", "session"):
            with self.subTest(key=key):
                response = self.client.get(reverse("academics:enrollment_list"), {
                    key: "invalid-uuid",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context["enrollments"]), [])

    def test_timetable_pages_do_not_expose_other_school(self):
        entry = Timetable.objects.create(
            institution=self.other_school, academic_session=self.session,
            class_assigned=self.other_class, day_of_week="monday", period_number=1,
            start_time=time(8, 0), end_time=time(9, 0), is_published=True,
        )
        self.client.force_login(self.user)
        listing = self.client.get(reverse("academics:timetable_list"))
        self.assertEqual(listing.status_code, 200)
        self.assertNotIn(entry, list(listing.context["timetable_entries"]))
        for name in ("academics:timetable_detail", "academics:timetable_update"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name, kwargs={"pk": entry.pk}))
                self.assertEqual(response.status_code, 404)

    def test_timetable_create_form_excludes_other_school_session(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("academics:timetable_create"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            self.session,
            list(response.context["form"].fields["academic_session"].queryset),
        )

    def test_bulk_enrollment_form_excludes_other_school_classes(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("academics:bulk_enrollment"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            self.other_class,
            list(response.context["form"].fields["class_enrolled"].queryset),
        )

    def test_bulk_enrollment_rejects_other_school_class(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("academics:bulk_enrollment"), {
            "students": [],
            "class_enrolled": str(self.other_class.pk),
            "academic_session": str(self.session.pk),
            "enrollment_date": "2026-04-02",
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("class_enrolled", response.context["form"].errors)

    def test_bulk_enrollment_creates_real_school_scoped_records(self):
        session = AcademicSession.objects.create(
            name="Home Session", institution=self.school,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        school_class = Class.objects.create(
            name="Home Class", code="HOME-C1", institution=self.school,
            academic_session=session,
        )
        student_user = get_user_model().objects.create_user(
            email="bulk-student@example.com", password="test-only-password"
        )
        student = Student.objects.create(
            user=student_user, institution=self.school,
            student_id="HOME-STU", admission_number="HOME-001",
            admission_date=date(2026, 1, 1),
            date_of_birth=date(2010, 1, 1), gender="female",
        )
        self.client.force_login(self.user)
        response = self.client.post(reverse("academics:bulk_enrollment"), {
            "students": [str(student.pk)],
            "class_enrolled": str(school_class.pk),
            "academic_session": str(session.pk),
            "enrollment_date": "2026-04-02",
        })
        self.assertRedirects(response, reverse("academics:enrollment_list"))
        record = Enrollment.objects.get(student=student, academic_session=session)
        self.assertEqual(record.institution, self.school)
        self.assertEqual(record.class_enrolled, school_class)

    def test_csv_bulk_enrollment_imports_existing_school_student(self):
        session = AcademicSession.objects.create(
            name="CSV Session", institution=self.school,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        school_class = Class.objects.create(
            name="CSV Class", code="CSV-C1", institution=self.school,
            academic_session=session,
        )
        account = get_user_model().objects.create_user(
            email="csv-student@example.com", password="test-only-password"
        )
        student = Student.objects.create(
            user=account, institution=self.school, student_id="CSV-STU",
            admission_number="CSV-001", admission_date=date(2026, 1, 1),
            date_of_birth=date(2010, 1, 1), gender="female",
        )
        self.client.force_login(self.user)
        response = self.client.post(reverse("academics:bulk_enrollment"), {
            "import_type": "csv", "class_enrolled": str(school_class.pk),
            "academic_session": str(session.pk), "enrollment_date": "2026-04-02",
            "csv_file": SimpleUploadedFile("students.csv", b"student_id\nCSV-STU\n", content_type="text/csv"),
        })
        self.assertRedirects(response, reverse("academics:enrollment_list"))
        self.assertTrue(Enrollment.objects.filter(student=student, institution=self.school).exists())

    def test_csv_bulk_enrollment_rejects_unknown_student_without_writing(self):
        self.client.force_login(self.user)
        before = Enrollment.objects.count()
        response = self.client.post(reverse("academics:bulk_enrollment"), {
            "import_type": "csv", "class_enrolled": str(self.other_class.pk),
            "academic_session": str(self.session.pk), "enrollment_date": "2026-04-02",
            "csv_file": SimpleUploadedFile("students.csv", b"student_id\nNOT-HERE\n", content_type="text/csv"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("class_enrolled", response.context["csv_form"].errors)
        self.assertIn("academic_session", response.context["csv_form"].errors)
        self.assertEqual(Enrollment.objects.count(), before)

    def test_enrollment_form_excludes_other_school_sessions(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("academics:enrollment_create"))
        self.assertEqual(response.status_code, 200)
        available_sessions = response.context["form"].fields["academic_session"].queryset
        self.assertNotIn(self.session, list(available_sessions))

    def test_regular_user_cannot_read_student_lookup(self):
        ordinary_user = get_user_model().objects.create_user(
            email="ordinary@example.com", password="test-only-password"
        )
        self.client.force_login(ordinary_user)
        response = self.client.get(reverse("academics:api_students_available"))
        self.assertEqual(response.status_code, 403)

    def test_class_info_does_not_expose_other_school(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("academics:api_class_info"), {
            "class_id": str(self.other_class.pk),
        })
        self.assertEqual(response.status_code, 404)

    def test_class_info_rejects_malformed_identifier(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("academics:api_class_info"), {
            "class_id": "not-a-uuid",
        })
        self.assertEqual(response.status_code, 400)

    def test_grade_class_lookup_does_not_expose_other_school(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("academics:api_classes_by_grade"), {
            "grade_level_id": str(uuid4()), "session_id": str(self.session.pk),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["classes"], [])

    def test_timetable_lookup_does_not_expose_other_school(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("academics:api_timetable_by_class", kwargs={
            "class_id": self.other_class.pk,
        }))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["timetable"], [])

    def test_class_list_and_detail_do_not_expose_other_school(self):
        self.client.force_login(self.user)
        listing = self.client.get(reverse("academics:class_list"))
        self.assertEqual(listing.status_code, 200)
        self.assertNotIn(self.other_class, list(listing.context["classes"]))
        detail = self.client.get(reverse("academics:class_detail", kwargs={
            "pk": self.other_class.pk,
        }))
        self.assertEqual(detail.status_code, 404)

    def test_class_update_cannot_edit_other_school(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("academics:class_update", kwargs={
            "pk": self.other_class.pk,
        }))
        self.assertEqual(response.status_code, 404)

    def test_class_create_form_excludes_other_school_session(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("academics:class_create"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            self.session,
            list(response.context["form"].fields["academic_session"].queryset),
        )

    def test_class_list_invalid_filters_do_not_crash(self):
        self.client.force_login(self.user)
        for key in ("grade_level", "session"):
            with self.subTest(key=key):
                response = self.client.get(reverse("academics:class_list"), {
                    key: "not-a-uuid",
                })
                self.assertEqual(response.status_code, 200)

    def test_student_and_teacher_edit_reject_other_school(self):
        outsider = get_user_model().objects.create_user(
            email="outsider@example.com", password="test-only-password"
        )
        student = Student.objects.create(
            user=outsider, institution=self.other_school,
            student_id="OUT-STU", admission_number="OUT-001",
            admission_date=date(2026, 1, 1),
            date_of_birth=date(2010, 1, 1), gender="female",
        )
        teacher_user = get_user_model().objects.create_user(
            email="other-teacher@example.com", password="test-only-password"
        )
        teacher = Teacher.objects.create(
            user=teacher_user, institution=self.other_school,
            teacher_id="OUT-TCH", employee_id="OUT-EMP",
            joining_date=date(2026, 1, 1),
        )
        self.client.force_login(self.user)
        for name, pk in (("academics:student_update", student.pk),
                         ("academics:teacher_update", teacher.pk)):
            with self.subTest(name=name):
                response = self.client.get(reverse(name, kwargs={"pk": pk}))
                self.assertEqual(response.status_code, 404)

    def test_student_and_teacher_create_exclude_other_school_account(self):
        outsider = get_user_model().objects.create_user(
            email="other-member@example.com", password="test-only-password"
        )
        InstitutionUser.objects.create(user=outsider, institution=self.other_school)
        self.client.force_login(self.user)
        for name in ("academics:student_create", "academics:teacher_create"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(
                    outsider, list(response.context["form"].fields["user"].queryset)
                )

    def test_calendar_excludes_other_school_session(self):
        self.client.force_login(self.user)
        self.session.is_current = True
        self.session.save()
        response = self.client.get(reverse("academics:academic_calendar"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["current_session"])

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
