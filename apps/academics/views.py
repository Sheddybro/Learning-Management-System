# apps/academics/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.views import View
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy
from django.db import models
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
import csv
from uuid import UUID
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _

from .models import (
    AcademicSession,
    Department,
    Subject,
    GradeLevel,
    Class,
    Student,
    Teacher,
    Enrollment,
    SubjectAssignment,
    AcademicRecord,
    Timetable,
    AttendanceSchedule,
    ClassMaterial,
    BehaviorRecord,
    Achievement,
    ParentGuardian,
    StudentParentRelationship,
    ClassTransferHistory,
    AcademicWarning,
    Holiday,
    SchoolPolicy,
    CounselingSession,
    CareerGuidance,
    CounselingReferral,
    AcademicPlanningCommittee,
    CommitteeMeeting,
    DepartmentBudget,
)
from apps.assessment.models import Assignment
from .forms import (
    DepartmentForm,
    SubjectForm,
    GradeLevelForm,
    ClassForm,
    StudentForm,
    TeacherForm,
    EnrollmentForm,
    SubjectAssignmentForm,
    TimetableForm,
    ClassMaterialForm,
    BehaviorRecordForm,
    AchievementForm,
    ParentGuardianForm,
    StudentParentRelationshipForm,
    ClassTransferHistoryForm,
    AcademicWarningForm,
    HolidayForm,
    FileAttachmentForm,
    SchoolPolicyForm,
    StudentSearchForm,
    TeacherSearchForm,
    BulkEnrollmentForm,
)
from apps.users.forms import (
    UserCreationForm,
    UserUpdateForm,
    UserProfileForm,
    RoleForm,
    UserRoleAssignmentForm,
)  # Import user-related forms
from apps.communication.forms import ContactTeacherForm
from apps.communication.services import EmailService
from .forms import AcademicSessionForm
from apps.core.mixins import (
    InstitutionPermissionMixin,  # Import for tenant filtering
    StudentRequiredMixin,
    TeacherRequiredMixin,
    StaffRequiredMixin,
    AdminRequiredMixin,
    CounselorRequiredMixin,
    CommitteeRequiredMixin,
    DepartmentHeadRequiredMixin,
    AcademicsAccessMixin,
)


# =============================================================================
# MIXINS AND BASE CLASSES
# =============================================================================


# =============================================================================
# DASHBOARD VIEWS
# =============================================================================


class StudentAcademicRecordsView(StudentRequiredMixin, View):
    """Comprehensive student academic records view."""

    def get(self, request):
        student = request.user.student_profile

        # Get all academic records (historical results)
        academic_records = (
            AcademicRecord.objects.filter(student=student)
            .select_related("class_enrolled", "academic_session")
            .order_by("-academic_session__start_date")
        )

        # Get detailed marks for subject performance breakdown
        from apps.assessment.models import Mark, Result, ResultSubject

        marks = (
            Mark.objects.filter(student=student)
            .select_related("exam", "exam__subject", "exam__exam_type")
            .order_by("-exam__exam_date")
        )

        # Subject-wise performance analysis
        subject_performance = self._get_subject_performance(student, marks)

        # Results and report cards
        results = (
            Result.objects.filter(student=student)
            .select_related("academic_class", "exam_type", "grade")
            .prefetch_related("subject_marks")
        )

        # Attendance summary
        attendance_summary = self._get_attendance_summary(student)

        # Progress trends
        progress_trends = self._get_progress_trends(student, academic_records)

        context = {
            "student": student,
            "academic_records": academic_records,
            "subject_performance": subject_performance,
            "marks": marks[:20],  # Recent marks
            "results": results,
            "attendance_summary": attendance_summary,
            "progress_trends": progress_trends,
            "total_exams": marks.count(),
            "average_percentage": (
                marks.aggregate(avg=models.Avg("percentage"))["avg"] if marks else 0
            ),
        }

        return render(request, "academics/students/academic_records.html", context)

    def _get_subject_performance(self, student, marks):
        """Calculate subject-wise performance breakdown."""
        from django.db.models import Avg, Count, Max, Min
        from collections import defaultdict

        subject_data = defaultdict(
            lambda: {
                "marks": [],
                "exams": 0,
                "average": 0,
                "highest": 0,
                "lowest": 100,
                "trend": [],
            }
        )

        for mark in marks:
            subject_name = mark.exam.subject.name
            percentage = mark.percentage

            subject_data[subject_name]["marks"].append(percentage)
            subject_data[subject_name]["exams"] += 1

            if percentage > subject_data[subject_name]["highest"]:
                subject_data[subject_name]["highest"] = percentage
            if percentage < subject_data[subject_name]["lowest"]:
                subject_data[subject_name]["lowest"] = percentage

        # Calculate averages and trends
        for subject_name, data in subject_data.items():
            if data["marks"]:
                data["average"] = sum(data["marks"]) / len(data["marks"])
                # Simple trend calculation (last 3 vs first 3)
                if len(data["marks"]) >= 3:
                    first_half = data["marks"][: len(data["marks"]) // 2]
                    second_half = data["marks"][len(data["marks"]) // 2 :]
                    data["trend"] = (
                        "improving"
                        if sum(second_half) / len(second_half)
                        > sum(first_half) / len(first_half)
                        else "declining"
                    )

        return dict(subject_data)

    def _get_attendance_summary(self, student):
        """Get comprehensive attendance summary."""
        from apps.attendance.models import DailyAttendance, AttendanceSummary

        # Current session attendance
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            attendance_records = DailyAttendance.objects.filter(
                student=student, academic_session=current_session
            )

            total_days = attendance_records.count()
            present_days = attendance_records.filter(
                attendance_status="present"
            ).count()
            absent_days = attendance_records.filter(attendance_status="absent").count()
            late_days = attendance_records.filter(is_late=True).count()

            attendance_percentage = (
                (present_days / total_days * 100) if total_days > 0 else 0
            )

            return {
                "total_days": total_days,
                "present_days": present_days,
                "absent_days": absent_days,
                "late_days": late_days,
                "attendance_percentage": round(attendance_percentage, 1),
                "current_session": current_session,
            }

        return None

    def _get_progress_trends(self, student, academic_records):
        """Calculate academic progress trends over time."""
        trends = []
        for record in academic_records[:10]:  # Last 10 sessions
            trends.append(
                {
                    "session": record.academic_session.name,
                    "percentage": record.percentage or 0,
                    "grade": record.overall_grade or "N/A",
                    "rank": record.rank_in_class or "N/A",
                }
            )
        return trends


class StudentDashboardView(StudentRequiredMixin, View):
    """Comprehensive student dashboard integrating all user story requirements."""

    def get(self, request):
        student = request.user.student_profile
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Get current enrollment
        current_enrollment = (
            student.enrollments.filter(
                academic_session=current_session, enrollment_status="active"
            ).first()
            if current_session
            else None
        )

        context = {
            "student": student,
            "current_session": current_session,
            "current_enrollment": current_enrollment,
        }

        if current_enrollment:
            context.update(
                self._get_dashboard_data(student, current_enrollment, current_session)
            )

        return render(request, "academics/students/dashboard.html", context)

    def _get_dashboard_data(self, student, current_enrollment, current_session):
        """Get all dashboard data for the student."""
        # Today's timetable
        today_timetable = self._get_today_timetable(student, current_enrollment)

        # Recent announcements
        recent_announcements = self._get_recent_announcements(
            student, current_enrollment
        )

        # Upcoming assignments
        upcoming_assignments = self._get_upcoming_assignments(
            student, current_enrollment
        )

        # Today's attendance status
        today_attendance = self._get_today_attendance(student)

        # Quick performance stats
        performance_stats = self._get_performance_stats(student, current_session)

        # Recent grades
        recent_grades = self._get_recent_grades(student)

        # Library status
        library_status = self._get_library_status(student)

        # Enrolled subjects
        enrolled_subjects = self._get_enrolled_subjects(
            student, current_enrollment, current_session
        )

        return {
            "today_timetable": today_timetable,
            "recent_announcements": recent_announcements,
            "upcoming_assignments": upcoming_assignments,
            "today_attendance": today_attendance,
            "performance_stats": performance_stats,
            "recent_grades": recent_grades,
            "library_status": library_status,
            "enrolled_subjects": enrolled_subjects,
        }

    def _get_today_timetable(self, student, current_enrollment):
        """Get today's timetable for the student."""
        from datetime import datetime

        today = datetime.now().strftime("%A").lower()

        return (
            Timetable.objects.filter(
                class_assigned=current_enrollment.class_enrolled,
                academic_session=current_enrollment.academic_session,
                day_of_week=today,
                is_published=True,
            )
            .select_related("subject", "teacher")
            .order_by("period_number")
        )

    def _get_recent_announcements(self, student, current_enrollment):
        """Get recent announcements for the student."""
        from apps.communication.models import Announcement

        # Get announcements targeted at students, the student's class, or all users
        announcements = (
            Announcement.objects.filter(is_published=True, expires_at__isnull=True)
            .filter(
                models.Q(target_audience="all")
                | models.Q(target_audience="students")
                | models.Q(specific_classes=current_enrollment.class_enrolled)
            )
            .order_by("-published_at")[:5]
        )

        return announcements

    def _get_upcoming_assignments(self, student, current_enrollment):
        """Get upcoming assignments for the student."""
        from apps.assessment.models import Assignment
        from django.utils import timezone

        return (
            Assignment.objects.filter(
                academic_class=current_enrollment.class_enrolled,
                due_date__gte=timezone.now(),
                is_published=True,
            )
            .exclude(
                # Exclude assignments already submitted by this student
                submissions__student=student
            )
            .select_related("subject", "teacher")
            .order_by("due_date")[:5]
        )

    def _get_today_attendance(self, student):
        """Get today's attendance status."""
        from apps.attendance.models import DailyAttendance
        from django.utils import timezone

        today = timezone.now().date()
        current_session = AcademicSession.objects.filter(is_current=True).first()

        if current_session:
            attendance = DailyAttendance.objects.filter(
                student=student,
                date=today,
                attendance_session__academic_session=current_session,
            ).first()
            return attendance
        return None

    def _get_performance_stats(self, student, current_session):
        """Get quick performance statistics."""
        from apps.assessment.models import Mark, Result

        if not current_session:
            return None

        # Current session marks
        marks = Mark.objects.filter(
            student=student, exam__academic_class__academic_session=current_session
        )

        if marks.exists():
            avg_percentage = marks.aggregate(avg=models.Avg("percentage"))["avg"] or 0
            total_exams = marks.count()
            passed_exams = (
                marks.filter(is_absent=False)
                .exclude(marks_obtained__lt=models.F("exam__passing_marks"))
                .count()
            )

            return {
                "average_percentage": round(avg_percentage, 1),
                "total_exams": total_exams,
                "passed_exams": passed_exams,
                "pass_rate": (
                    round((passed_exams / total_exams * 100), 1)
                    if total_exams > 0
                    else 0
                ),
            }
        return None

    def _get_recent_grades(self, student):
        """Get recent grades for the student."""
        from apps.assessment.models import Mark

        return (
            Mark.objects.filter(student=student)
            .select_related("exam__subject", "exam__exam_type")
            .order_by("-exam__exam_date")[:3]
        )

    def _get_library_status(self, student):
        """Get library borrowing status for the student."""
        from apps.library.models import BorrowRecord, LibraryMember

        try:
            member = LibraryMember.objects.get(user=student.user)
            current_borrows = (
                BorrowRecord.objects.filter(
                    member=member, status__in=["borrowed", "overdue"]
                )
                .select_related("book_copy__book")
                .order_by("due_date")[:3]
            )

            overdue_count = current_borrows.filter(status="overdue").count()

            return {
                "current_borrows": current_borrows,
                "overdue_count": overdue_count,
                "can_borrow_more": member.can_borrow_more,
            }
        except LibraryMember.DoesNotExist:
            return None

    def _get_enrolled_subjects(self, student, current_enrollment, current_session):
        """Get all subjects the student is enrolled in for the current session."""
        if not current_enrollment or not current_session:
            return []

        # Get all subject assignments for the student's class
        subject_assignments = (
            SubjectAssignment.objects.filter(
                class_assigned=current_enrollment.class_enrolled,
                academic_session=current_session,
                status="active",
            )
            .select_related("subject", "teacher")
            .order_by("subject__name")
        )

        enrolled_subjects = []
        for assignment in subject_assignments:
            enrolled_subjects.append(
                {
                    "subject": assignment.subject,
                    "teacher": assignment.teacher,
                    "periods_per_week": assignment.periods_per_week,
                    "is_primary_teacher": assignment.is_primary_teacher,
                }
            )

        return enrolled_subjects


class StudentMaterialsView(StudentRequiredMixin, View):
    """Student view for accessing learning materials."""

    def get(self, request):
        student = request.user.student_profile
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Get current enrollment
        current_enrollment = (
            student.enrollments.filter(
                academic_session=current_session, enrollment_status="active"
            ).first()
            if current_session
            else None
        )

        if not current_enrollment:
            messages.info(request, _("You are not currently enrolled in any class."))
            return render(
                request,
                "academics/students/materials.html",
                {"student": student, "materials": [], "assignments": []},
            )

        # Get materials for the student's class
        materials = (
            ClassMaterial.objects.filter(
                class_assigned=current_enrollment.class_enrolled,
                is_public=True,
                publish_date__lte=timezone.now(),
            )
            .select_related("subject", "teacher")
            .order_by("-publish_date")
        )

        # Get assignments for the student's class
        assignments = (
            Assignment.objects.filter(
                academic_class=current_enrollment.class_enrolled, is_published=True
            )
            .exclude(
                # Exclude assignments already submitted by this student
                submissions__student=student
            )
            .select_related("subject", "teacher")
            .order_by("due_date")
        )

        # Get submitted assignments
        submitted_assignments = (
            Assignment.objects.filter(
                student=student,
                submission_status__in=["submitted", "late", "under_review", "graded"],
            )
            .select_related("subject", "teacher")
            .order_by("-submission_date")
        )

        context = {
            "student": student,
            "current_enrollment": current_enrollment,
            "materials": materials,
            "assignments": assignments,
            "submitted_assignments": submitted_assignments,
        }

        return render(request, "academics/students/materials.html", context)


class StudentPerformanceView(StudentRequiredMixin, View):
    """Enhanced student performance view with visualizations."""

    def get(self, request):
        student = request.user.student_profile
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Get all academic records (historical results)
        academic_records = (
            AcademicRecord.objects.filter(student=student)
            .select_related("class_enrolled", "academic_session")
            .order_by("-academic_session__start_date")
        )

        # Get detailed marks for subject performance breakdown
        from apps.assessment.models import Mark, Result, ResultSubject

        marks = (
            Mark.objects.filter(student=student)
            .select_related("exam", "exam__subject", "exam__exam_type")
            .order_by("-exam__exam_date")
        )

        # Subject-wise performance analysis
        subject_performance = self._get_subject_performance(student, marks)

        # Results and report cards
        results = (
            Result.objects.filter(student=student)
            .select_related("academic_class", "exam_type", "grade")
            .prefetch_related("subject_marks")
        )

        # Attendance summary
        attendance_summary = self._get_attendance_summary(student)

        # Progress trends
        progress_trends = self._get_progress_trends(student, academic_records)

        # Performance statistics
        performance_stats = self._get_performance_stats(student, current_session)

        context = {
            "student": student,
            "academic_records": academic_records,
            "subject_performance": subject_performance,
            "marks": marks[:20],  # Recent marks
            "results": results,
            "attendance_summary": attendance_summary,
            "progress_trends": progress_trends,
            "performance_stats": performance_stats,
            "total_exams": marks.count(),
            "average_percentage": (
                marks.aggregate(avg=models.Avg("percentage"))["avg"] if marks else 0
            ),
        }

        return render(request, "academics/students/performance.html", context)

    def _get_subject_performance(self, student, marks):
        """Calculate subject-wise performance breakdown."""
        from django.db.models import Avg, Count, Max, Min
        from collections import defaultdict

        subject_data = defaultdict(
            lambda: {
                "marks": [],
                "exams": 0,
                "average": 0,
                "highest": 0,
                "lowest": 100,
                "trend": [],
            }
        )

        for mark in marks:
            subject_name = mark.exam.subject.name
            percentage = mark.percentage

            subject_data[subject_name]["marks"].append(percentage)
            subject_data[subject_name]["exams"] += 1

            if percentage > subject_data[subject_name]["highest"]:
                subject_data[subject_name]["highest"] = percentage
            if percentage < subject_data[subject_name]["lowest"]:
                subject_data[subject_name]["lowest"] = percentage

        # Calculate averages and trends
        for subject_name, data in subject_data.items():
            if data["marks"]:
                data["average"] = sum(data["marks"]) / len(data["marks"])
                # Simple trend calculation (last 3 vs first 3)
                if len(data["marks"]) >= 3:
                    first_half = data["marks"][: len(data["marks"]) // 2]
                    second_half = data["marks"][len(data["marks"]) // 2 :]
                    data["trend"] = (
                        "improving"
                        if sum(second_half) / len(second_half)
                        > sum(first_half) / len(first_half)
                        else "declining"
                    )

        return dict(subject_data)

    def _get_attendance_summary(self, student):
        """Get comprehensive attendance summary."""
        from apps.attendance.models import DailyAttendance, AttendanceSummary

        # Current session attendance
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            attendance_records = DailyAttendance.objects.filter(
                student=student, academic_session=current_session
            )

            total_days = attendance_records.count()
            present_days = attendance_records.filter(
                attendance_status="present"
            ).count()
            absent_days = attendance_records.filter(attendance_status="absent").count()
            late_days = attendance_records.filter(is_late=True).count()

            attendance_percentage = (
                (present_days / total_days * 100) if total_days > 0 else 0
            )

            return {
                "total_days": total_days,
                "present_days": present_days,
                "absent_days": absent_days,
                "late_days": late_days,
                "attendance_percentage": round(attendance_percentage, 1),
                "current_session": current_session,
            }

        return None

    def _get_progress_trends(self, student, academic_records):
        """Calculate academic progress trends over time."""
        trends = []
        for record in academic_records[:10]:  # Last 10 sessions
            trends.append(
                {
                    "session": record.academic_session.name,
                    "percentage": record.percentage or 0,
                    "grade": record.overall_grade or "N/A",
                    "rank": record.rank_in_class or "N/A",
                }
            )
        return trends

    def _get_performance_stats(self, student, current_session):
        """Get comprehensive performance statistics."""
        from apps.assessment.models import Mark

        if not current_session:
            return None

        # Current session marks
        current_marks = Mark.objects.filter(
            student=student, exam__academic_class__academic_session=current_session
        )

        if current_marks.exists():
            avg_percentage = (
                current_marks.aggregate(avg=models.Avg("percentage"))["avg"] or 0
            )
            total_exams = current_marks.count()
            passed_exams = (
                current_marks.filter(is_absent=False)
                .exclude(marks_obtained__lt=models.F("exam__passing_marks"))
                .count()
            )

            # Grade distribution
            grade_distribution = (
                current_marks.values("exam__subject__name")
                .annotate(avg_percentage=models.Avg("percentage"))
                .order_by("-avg_percentage")
            )

            return {
                "average_percentage": round(avg_percentage, 1),
                "total_exams": total_exams,
                "passed_exams": passed_exams,
                "pass_rate": (
                    round((passed_exams / total_exams * 100), 1)
                    if total_exams > 0
                    else 0
                ),
                "grade_distribution": list(grade_distribution),
            }
        return None


class StudentAttendanceView(StudentRequiredMixin, View):
    """Student view for personal attendance records."""

    def get(self, request):
        student = request.user.student_profile
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Get attendance records for current session
        attendance_records = []
        attendance_summary = None

        if current_session:
            from apps.attendance.models import DailyAttendance, AttendanceSummary

            attendance_records = (
                DailyAttendance.objects.filter(
                    student=student,
                    attendance_session__academic_session=current_session,
                )
                .select_related("attendance_session")
                .order_by("-date")
            )

            # Get attendance summary
            try:
                attendance_summary = AttendanceSummary.objects.get(
                    student=student, academic_session=current_session
                )
            except AttendanceSummary.DoesNotExist:
                # Calculate summary if not exists
                attendance_summary = self._calculate_attendance_summary(
                    student, current_session
                )

        # Monthly breakdown
        monthly_stats = self._get_monthly_attendance(student, current_session)

        # Recent attendance (last 30 days)
        recent_attendance = attendance_records[:30] if attendance_records else []

        context = {
            "student": student,
            "current_session": current_session,
            "attendance_records": attendance_records,
            "attendance_summary": attendance_summary,
            "monthly_stats": monthly_stats,
            "recent_attendance": recent_attendance,
        }

        return render(request, "academics/students/attendance.html", context)

    def _calculate_attendance_summary(self, student, current_session):
        """Calculate attendance summary for the student."""
        from apps.attendance.models import DailyAttendance
        from django.db.models import Count

        attendance_records = DailyAttendance.objects.filter(
            student=student, attendance_session__academic_session=current_session
        )

        total_days = attendance_records.count()
        if total_days == 0:
            return None

        present_days = attendance_records.filter(attendance_status="present").count()
        absent_days = attendance_records.filter(attendance_status="absent").count()
        late_days = attendance_records.filter(is_late=True).count()
        half_days = attendance_records.filter(attendance_status="half_day").count()

        attendance_percentage = present_days / total_days * 100

        return {
            "total_school_days": total_days,
            "days_present": present_days,
            "days_absent": absent_days,
            "days_late": late_days,
            "days_half_day": half_days,
            "attendance_percentage": round(attendance_percentage, 1),
            "consecutive_absences": 0,  # Would need more complex calculation
        }

    def _get_monthly_attendance(self, student, current_session):
        """Get monthly attendance breakdown."""
        from apps.attendance.models import DailyAttendance
        from django.db.models import Count
        from calendar import month_name

        monthly_data = []

        if current_session:
            # Group by month
            monthly_records = (
                DailyAttendance.objects.filter(
                    student=student,
                    attendance_session__academic_session=current_session,
                )
                .extra(select={"month": "EXTRACT(MONTH FROM date)"})
                .values("month")
                .annotate(
                    total_days=Count("id"),
                    present_days=Count(
                        "id", filter=models.Q(attendance_status="present")
                    ),
                    absent_days=Count(
                        "id", filter=models.Q(attendance_status="absent")
                    ),
                    late_days=Count("id", filter=models.Q(is_late=True)),
                )
                .order_by("month")
            )

            for record in monthly_records:
                month_num = int(record["month"])
                percentage = (
                    (record["present_days"] / record["total_days"] * 100)
                    if record["total_days"] > 0
                    else 0
                )

                monthly_data.append(
                    {
                        "month": month_name[month_num],
                        "month_num": month_num,
                        "total_days": record["total_days"],
                        "present_days": record["present_days"],
                        "absent_days": record["absent_days"],
                        "late_days": record["late_days"],
                        "percentage": round(percentage, 1),
                    }
                )

        return monthly_data


class AcademicsDashboardView(InstitutionPermissionMixin, AcademicsAccessMixin, View):
    """Academic dashboard view with role-based content."""

    def get(self, request):
        user = request.user

        # For admin/staff users, redirect directly to sessions management
        # to avoid institution selection requirement
        if (
            user.is_staff
            or user.has_perm("academics.change_academicsession")
            or user.user_roles.filter(
                role__role_type__in=["admin", "principal", "super_admin"],
                status="active",
            ).exists()
        ):
            return redirect("academics:session_list")

        context = {}

        # Common context for all users
        current_session = AcademicSession.objects.filter(is_current=True).first()
        context["current_session"] = current_session

        # Role-specific context
        if hasattr(user, "student_profile"):
            context.update(self._get_student_context(user))
        elif hasattr(user, "teacher_profile"):
            context.update(self._get_teacher_context(user))

        return render(request, "academics/dashboard/dashboard.html", context)

    def _get_student_context(self, user):
        """Get context for student dashboard."""
        student = user.student_profile
        current_enrollment = student.enrollments.filter(
            academic_session__is_current=True
        ).first()

        return {
            "student": student,
            "current_class": (
                current_enrollment.class_enrolled if current_enrollment else None
            ),
            "recent_grades": AcademicRecord.objects.filter(student=student).order_by(
                "-academic_session__start_date"
            )[:5],
            "upcoming_assignments": ClassMaterial.objects.filter(
                class_assigned=(
                    current_enrollment.class_enrolled if current_enrollment else None
                ),
                publish_date__gte=timezone.now(),
            )[:5],
            "attendance_stats": self._get_student_attendance_stats(student),
        }

    def _get_teacher_context(self, user):
        """Get context for teacher dashboard."""
        teacher = user.teacher_profile
        current_assignments = teacher.subject_assignments.filter(
            academic_session__is_current=True
        )

        return {
            "teacher": teacher,
            "current_assignments": current_assignments,
            "total_students": self._get_teacher_student_count(teacher),
            "upcoming_classes": Timetable.objects.filter(
                teacher=teacher, day_of_week=timezone.now().strftime("%A").lower()
            ).order_by("start_time"),
            "pending_grading": self._get_pending_grading_count(teacher),
        }

    def _get_staff_context(self, user):
        """Get context for staff dashboard."""
        return {
            "total_students": Student.objects.filter(status="active").count(),
            "total_teachers": Teacher.objects.filter(status="active").count(),
            "total_classes": Class.objects.filter(status="active").count(),
            "total_subjects": Subject.objects.filter(status="active").count(),
            "total_grade_levels": GradeLevel.objects.filter(status="active").count(),
            "recent_enrollments": Enrollment.objects.filter(
                enrollment_status="active"
            ).order_by("-enrollment_date")[:10],
            "upcoming_holidays": Holiday.objects.filter(
                date__gte=timezone.now().date()
            ).order_by("date")[:5],
        }

    def _get_student_attendance_stats(self, student):
        """Calculate student attendance statistics."""
        from apps.attendance.models import DailyAttendance

        # Get current session attendance
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            attendance_records = DailyAttendance.objects.filter(
                student=student, academic_session=current_session
            )

            total_days = attendance_records.count()
            if total_days > 0:
                present_days = attendance_records.filter(
                    attendance_status="present"
                ).count()
                absent_days = attendance_records.filter(
                    attendance_status="absent"
                ).count()
                late_days = attendance_records.filter(is_late=True).count()

                present_percentage = int((present_days / total_days) * 100)
                absent_percentage = int((absent_days / total_days) * 100)
                late_percentage = int((late_days / total_days) * 100)

                return {
                    "present": present_percentage,
                    "absent": absent_percentage,
                    "late": late_percentage,
                }

        return {"present": 0, "absent": 0, "late": 0}

    def _get_teacher_student_count(self, teacher):
        """Get total students taught by teacher."""
        classes = Class.objects.filter(
            subject_assignments__teacher=teacher,
            subject_assignments__academic_session__is_current=True,
        ).distinct()

        return Enrollment.objects.filter(
            class_enrolled__in=classes, enrollment_status="active"
        ).count()

    def _get_pending_grading_count(self, teacher):
        """Get count of assignments pending grading."""
        # Count assignments that are submitted but not yet graded
        return Assignment.objects.filter(
            teacher=teacher,
            is_published=True,
            student__isnull=False,  # Ensure it's a student submission
            submission_status__in=[
                Assignment.SubmissionStatus.SUBMITTED,
                Assignment.SubmissionStatus.LATE,
                Assignment.SubmissionStatus.UNDER_REVIEW,
            ],
        ).count()


# =============================================================================
# ACADEMIC SESSION VIEWS
# =============================================================================

# apps/academics/views.py - Updated Academic Session Views


class AcademicSessionListView(InstitutionPermissionMixin, LoginRequiredMixin, ListView):
    """List all academic sessions with role-based access."""

    model = AcademicSession
    template_name = "academics/sessions/session_list.html"
    context_object_name = "sessions"
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()

        # Role-based permissions - allow admin/principal roles to manage sessions
        can_manage_sessions = (
            user.is_staff
            or user.is_superuser
            or user.has_perm("academics.change_academicsession")
        )
        if not can_manage_sessions:
            # Check if user has admin or principal role
            can_manage_sessions = user.user_roles.filter(
                role__role_type__in=["admin", "principal", "school_admin"],
                status="active",
            ).exists()

        context["can_manage_sessions"] = can_manage_sessions
        context["is_teacher"] = hasattr(user, "teacher_profile")
        context["is_student"] = hasattr(user, "student_profile")
        context["today"] = today

        # Statistics for dashboard cards
        all_sessions = AcademicSession.objects.all()
        context["total_sessions"] = all_sessions.count()
        context["active_sessions"] = all_sessions.filter(is_current=True).count()
        context["upcoming_sessions"] = all_sessions.filter(start_date__gt=today).count()
        context["completed_sessions"] = all_sessions.filter(end_date__lt=today).count()

        # Apply filters from GET parameters
        context["active_filter"] = self.request.GET.get("status", "")
        context["year_filter"] = self.request.GET.get("year", "")

        return context

    def get_queryset(self):
        queryset = AcademicSession.objects.all().order_by("-start_date")

        # Apply filters
        status_filter = self.request.GET.get("status")
        year_filter = self.request.GET.get("year")
        today = timezone.now().date()

        if status_filter:
            if status_filter == "current":
                queryset = queryset.filter(is_current=True)
            elif status_filter == "upcoming":
                queryset = queryset.filter(start_date__gt=today)
            elif status_filter == "completed":
                queryset = queryset.filter(end_date__lt=today)
            elif status_filter == "active":
                queryset = queryset.filter(start_date__lte=today, end_date__gte=today)

        if year_filter:
            queryset = queryset.filter(
                Q(start_date__year=year_filter) | Q(end_date__year=year_filter)
            )

        return queryset

    def post(self, request, *args, **kwargs):
        """Handle setting/removing current session."""
        if not request.user.is_staff:
            messages.error(
                request, _("Only staff members can manage academic sessions.")
            )
            return redirect("academics:session_list")

        session_id = request.POST.get("session_id")
        action = request.POST.get("action")

        if action == "set_current" and session_id:
            try:
                session = AcademicSession.objects.get(id=session_id)
                # First, check if there are any existing current sessions
                existing_count = AcademicSession.objects.filter(is_current=True).count()
                if existing_count > 0:
                    messages.warning(
                        request,
                        _(
                            f"There are currently {existing_count} active session(s). Setting '{session.name}' as current will deactivate the previous ones automatically."
                        ),
                    )

                # This will automatically update other sessions via save method
                session.is_current = True
                session.save()
                messages.success(
                    request, _(f"'{session.name}' is now the current session.")
                )
            except AcademicSession.DoesNotExist:
                messages.error(request, _("Session not found."))

        elif action == "deactivate_current":
            # Deactivate all current sessions
            deactivated_count = AcademicSession.objects.filter(is_current=True).update(
                is_current=False
            )
            if deactivated_count > 0:
                messages.success(
                    request,
                    _(
                        f"Successfully deactivated {deactivated_count} current session(s). You can now set a new session as current."
                    ),
                )
            else:
                messages.info(request, _("No current sessions to deactivate."))

        return redirect("academics:session_list")


class AcademicSessionCreateView(
    InstitutionPermissionMixin, AdminRequiredMixin, CreateView
):
    """Create a new academic session."""

    model = AcademicSession
    form_class = AcademicSessionForm
    template_name = "academics/sessions/session_form.html"
    success_url = reverse_lazy("academics:session_list")

    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _("Academic session created successfully."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = _("Create New Academic Session")
        context["submit_text"] = _("Create Session")
        # Pass user role info to template
        context["is_super_admin"] = (
            self.request.user.user_roles.filter(
                role__role_type="super_admin", status="active"
            ).exists()
            or self.request.user.is_superuser
        )
        return context


class AcademicSessionDetailView(LoginRequiredMixin, DetailView):
    """Display details of a single academic session."""

    model = AcademicSession
    template_name = "academics/sessions/session_detail.html"
    context_object_name = "session"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.object

        # Get related classes for this session
        context["classes"] = (
            session.classes.filter(status="active")
            .select_related("grade_level", "class_teacher")
            .order_by("grade_level__name", "name")
        )

        # Get related policies for this session
        context["policies"] = session.school_policies.filter(is_active=True).order_by(
            "-effective_date"
        )

        # Get related holidays for this session
        context["holidays"] = session.holidays.order_by("date")

        # Calculate session progress
        context["progress_percentage"] = session.progress_percentage()

        return context


class AcademicSessionUpdateView(
    InstitutionPermissionMixin, AdminRequiredMixin, UpdateView
):
    """Update an academic session."""

    model = AcademicSession
    form_class = AcademicSessionForm
    template_name = "academics/sessions/session_form.html"
    success_url = reverse_lazy("academics:session_list")

    def dispatch(self, request, *args, **kwargs):
        # Deny access if user is a teacher
        if hasattr(request.user, "teacher_profile") and not request.user.is_staff:
            messages.error(
                request, _("Teachers are not allowed to edit academic sessions.")
            )
            return redirect("academics:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _("Academic session updated successfully."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = _("Update Academic Session")
        context["submit_text"] = _("Update Session")
        # Pass user role info to template
        context["is_super_admin"] = (
            self.request.user.user_roles.filter(
                role__role_type="super_admin", status="active"
            ).exists()
            or self.request.user.is_superuser
        )
        return context


class AcademicSessionDeleteView(AdminRequiredMixin, DeleteView):
    """Delete an academic session with safety checks."""

    model = AcademicSession
    template_name = "academics/sessions/session_confirm_delete.html"
    success_url = reverse_lazy("academics:session_list")

    def dispatch(self, request, *args, **kwargs):
        # Additional permission check for deletion
        user = request.user
        if not (
            user.is_superuser
            or user.has_perm("academics.delete_academicsession")
            or user.user_roles.filter(
                role__role_type__in=["super_admin", "admin"], status="active"
            ).exists()
        ):
            messages.error(
                request, _("Only super administrators can delete academic sessions.")
            )
            return redirect("academics:session_list")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.object

        # Check for related data that would be deleted
        related_counts = self._get_related_data_counts(session)
        context["related_counts"] = related_counts
        context["total_related_items"] = sum(related_counts.values())
        context["can_delete_safely"] = self._can_delete_safely(session)

        return context

    def _get_related_data_counts(self, session):
        """Get counts of related data that would be affected by deletion."""
        return {
            "classes": session.classes.count(),
            "enrollments": session.enrollments.count(),
            "subject_assignments": session.subject_assignments.count(),
            "timetables": session.timetables.count(),
            "materials": session.materials.count(),
            "academic_records": session.academic_records.count(),
            "holidays": session.holidays.count(),
            "counseling_sessions": session.counseling_sessions.count(),
            "career_guidance": session.career_guidance.count(),
            "counseling_referrals": session.counseling_referrals.count(),
            "department_budgets": session.department_budgets.count(),
        }

    def _can_delete_safely(self, session):
        """Check if the session can be safely deleted."""
        # Don't allow deletion of current session
        if session.is_current:
            return False

        # Check for critical data that should prevent deletion
        critical_counts = self._get_related_data_counts(session)

        # If there are enrollments or academic records, it's not safe to delete
        if (
            critical_counts["enrollments"] > 0
            or critical_counts["academic_records"] > 0
            or critical_counts["classes"] > 0
        ):
            return False

        return True

    def delete(self, request, *args, **kwargs):
        session = self.get_object()

        # Final safety check
        if not self._can_delete_safely(session):
            messages.error(
                request,
                _("Cannot delete this session as it contains critical academic data."),
            )
            return redirect("academics:session_list")

        # Log the deletion
        messages.warning(
            request,
            _(f"Academic session '{session.name}' has been permanently deleted."),
        )

        return super().delete(request, *args, **kwargs)


# =============================================================================
# DEPARTMENT VIEWS
# =============================================================================


class DepartmentListView(InstitutionPermissionMixin, ListView):
    """List all departments."""

    model = Department
    template_name = "academics/departments/department_list.html"
    context_object_name = "departments"
    paginate_by = 12

    def dispatch(self, request, *args, **kwargs):
        # Departments are core academic entities that should be accessible
        # without institution selection for all authenticated users
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Bypass institution requirement and proceed directly
        return super(InstitutionPermissionMixin.__bases__[0], self).dispatch(
            request, *args, **kwargs
        )

    def get_queryset(self):
        # Departments are core academic entities accessible to all authenticated users
        # Exclude soft-deleted departments (is_deleted=False)
        return Department.objects.filter(
            status="active", is_deleted=False
        ).select_related("head_of_department")


class DepartmentDetailView(AcademicsAccessMixin, DetailView):
    """Department detail view."""

    model = Department
    template_name = "academics/departments/department_detail.html"
    context_object_name = "department"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subjects"] = self.object.subjects.filter(status="active")
        context["teachers"] = self.object.teachers.filter(status="active")
        return context


class DepartmentCreateView(InstitutionPermissionMixin, AdminRequiredMixin, CreateView):
    """Create a new department."""

    model = Department
    form_class = DepartmentForm
    template_name = "academics/departments/department_form.html"
    success_url = reverse_lazy("academics:department_list")

    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Let the InstitutionPermissionMixin handle institution assignment
        result = super().form_valid(form)

        # Add debug logging
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Created department: {form.instance.name} in institution: {form.instance.institution}"
        )

        return result


class DepartmentUpdateView(AdminRequiredMixin, UpdateView):
    """Update a department."""

    model = Department
    form_class = DepartmentForm
    template_name = "academics/departments/department_form.html"
    success_url = reverse_lazy("academics:department_list")

    def form_valid(self, form):
        messages.success(self.request, _("Department updated successfully."))
        return super().form_valid(form)


class DepartmentDeleteView(AdminRequiredMixin, DeleteView):
    """Delete a department with safety checks."""

    model = Department
    template_name = "academics/departments/department_confirm_delete.html"
    success_url = reverse_lazy("academics:department_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object

        # Check for related data that would be affected
        related_counts = {
            "subjects": department.subjects.count(),
            "teachers": department.teachers.count(),
            "students": department.students.count(),
        }

        context["related_counts"] = related_counts
        context["total_related_items"] = sum(related_counts.values())
        context["can_delete_safely"] = sum(related_counts.values()) == 0

        return context

    def delete(self, request, *args, **kwargs):
        department = self.get_object()
        messages.success(
            request, _(f"Department '{department.name}' deleted successfully.")
        )
        return super().delete(request, *args, **kwargs)


# =============================================================================
# SUBJECT VIEWS
# =============================================================================


class SubjectListView(AcademicsAccessMixin, ListView):
    """List all subjects."""

    model = Subject
    template_name = "academics/subjects/subject_list.html"
    context_object_name = "subjects"
    paginate_by = 15

    def get_queryset(self):
        queryset = Subject.objects.filter(status="active").select_related("department")

        # Filter by department if provided
        department_id = self.request.GET.get("department")
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["departments"] = Department.objects.filter(status="active")
        return context


class SubjectDetailView(AcademicsAccessMixin, DetailView):
    """Subject detail view."""

    model = Subject
    template_name = "academics/subjects/subject_detail.html"
    context_object_name = "subject"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_session = AcademicSession.objects.filter(is_current=True).first()

        if current_session:
            context["current_assignments"] = self.object.subject_assignments.filter(
                academic_session=current_session
            ).select_related("teacher", "class_assigned")

            context["materials"] = self.object.materials.filter(
                is_public=True, publish_date__lte=timezone.now()
            ).order_by("-publish_date")[:10]

        return context


class SubjectCreateView(InstitutionPermissionMixin, AdminRequiredMixin, CreateView):
    """Create a new subject."""

    model = Subject
    form_class = SubjectForm
    template_name = "academics/subjects/subject_form.html"
    success_url = reverse_lazy("academics:subject_list")

    def get_form_kwargs(self):
        """Pass the current user to the form."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _("Subject created successfully."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_subjects"] = Subject.objects.filter(status="active").order_by(
            "name"
        )
        return context


class SubjectUpdateView(AdminRequiredMixin, UpdateView):
    """Update a subject."""

    model = Subject
    form_class = SubjectForm
    template_name = "academics/subjects/subject_form.html"
    success_url = reverse_lazy("academics:subject_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["all_subjects"] = (
            Subject.objects.filter(status="active")
            .exclude(pk=self.object.pk)
            .order_by("name")
        )
        return context

    def form_valid(self, form):
        messages.success(self.request, _("Subject updated successfully."))
        return super().form_valid(form)


# =============================================================================
# CLASS VIEWS
# =============================================================================


class ClassListView(AcademicsAccessMixin, ListView):
    """List all classes."""

    model = Class
    template_name = "academics/classes/class_list.html"
    context_object_name = "classes"
    paginate_by = 12

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        queryset = Class.objects.filter(
            status="active", institution=get_current_institution()
        ).select_related(
            "grade_level", "class_teacher", "academic_session"
        )

        # Filter by grade level if provided
        grade_level_id = self.request.GET.get("grade_level")
        if grade_level_id:
            try:
                queryset = queryset.filter(grade_level_id=UUID(grade_level_id))
            except (ValueError, TypeError, AttributeError):
                return queryset.none()

        # Filter by academic session if provided
        session_id = self.request.GET.get("session")
        if session_id:
            try:
                queryset = queryset.filter(academic_session_id=UUID(session_id))
            except (ValueError, TypeError, AttributeError):
                return queryset.none()

        return queryset

    def get_context_data(self, **kwargs):
        from apps.core.middleware import get_current_institution

        context = super().get_context_data(**kwargs)
        context["grade_levels"] = GradeLevel.objects.filter(status="active")
        context["sessions"] = AcademicSession.objects.filter(
            institution=get_current_institution()
        )
        return context


class ClassDetailView(AcademicsAccessMixin, DetailView):
    """Class detail view."""

    model = Class
    template_name = "academics/classes/class_detail.html"
    context_object_name = "class_obj"

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        return super().get_queryset().filter(institution=get_current_institution())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current enrollments
        context["enrollments"] = self.object.enrollments.filter(
            enrollment_status="active"
        ).select_related("student__user")

        # Get subject assignments
        context["subject_assignments"] = self.object.subject_assignments.filter(
            status="active"
        ).select_related("teacher", "subject")

        # Get timetable
        context["timetable"] = self.object.timetables.filter(
            is_published=True
        ).order_by("day_of_week", "period_number")

        # Get class materials
        context["materials"] = self.object.materials.filter(
            is_public=True, publish_date__lte=timezone.now()
        ).order_by("-publish_date")[:10]

        return context


class ClassCreateView(AdminRequiredMixin, CreateView):
    """Create a new class."""

    model = Class
    form_class = ClassForm
    template_name = "academics/classes/class_form.html"
    success_url = reverse_lazy("academics:class_list")

    def get_form_kwargs(self):
        from apps.core.middleware import get_current_institution

        kwargs = super().get_form_kwargs()
        kwargs["institution"] = get_current_institution()
        return kwargs

    def form_valid(self, form):
        from apps.core.middleware import get_current_institution

        form.instance.institution = get_current_institution()
        messages.success(self.request, _("Class created successfully."))
        return super().form_valid(form)


class ClassUpdateView(AdminRequiredMixin, UpdateView):
    """Update a class."""

    model = Class
    form_class = ClassForm
    template_name = "academics/classes/class_form.html"
    success_url = reverse_lazy("academics:class_list")

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        return super().get_queryset().filter(institution=get_current_institution())

    def get_form_kwargs(self):
        from apps.core.middleware import get_current_institution

        kwargs = super().get_form_kwargs()
        kwargs["institution"] = get_current_institution()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _("Class updated successfully."))
        return super().form_valid(form)


# =============================================================================
# STUDENT VIEWS
# =============================================================================


class StudentListView(AcademicsAccessMixin, ListView):
    """List all students with search and filtering."""

    model = Student
    template_name = "academics/students/student_list.html"
    context_object_name = "students"
    paginate_by = 20

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        queryset = Student.objects.filter(
            status="active", institution=get_current_institution()
        ).select_related("user")

        # Apply search filters
        form = StudentSearchForm(self.request.GET)
        if form.is_valid():
            name = form.cleaned_data.get("name")
            student_id = form.cleaned_data.get("student_id")
            class_enrolled = form.cleaned_data.get("class_enrolled")
            department = form.cleaned_data.get("department")
            student_type = form.cleaned_data.get("student_type")
            status = form.cleaned_data.get("status")

            if name:
                queryset = queryset.filter(
                    Q(user__first_name__icontains=name)
                    | Q(user__last_name__icontains=name)
                )

            if student_id:
                queryset = queryset.filter(student_id__icontains=student_id)

            if class_enrolled:
                queryset = queryset.filter(
                    enrollments__class_enrolled=class_enrolled,
                    enrollments__enrollment_status="active",
                )

            if department:
                # Filter by department (either primary department or enrollment department)
                queryset = queryset.filter(
                    Q(department=department)
                    | Q(
                        enrollments__department=department,
                        enrollments__enrollment_status="active",
                    )
                )

            if student_type:
                queryset = queryset.filter(student_type=student_type)

            if status:
                queryset = queryset.filter(status=status)

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        from apps.core.middleware import get_current_institution

        context = super().get_context_data(**kwargs)
        context["search_form"] = StudentSearchForm(self.request.GET)
        context["classes"] = Class.objects.filter(
            status="active", institution=get_current_institution()
        )
        return context


class StudentDetailView(AcademicsAccessMixin, DetailView):
    """Student detail view."""

    model = Student
    template_name = "academics/students/student_detail.html"
    context_object_name = "student"

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        return super().get_queryset().filter(institution=get_current_institution())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.object

        # Enrollment history
        context["enrollments"] = student.enrollments.select_related(
            "class_enrolled", "academic_session"
        ).order_by("-academic_session__start_date")

        # Academic records
        context["academic_records"] = student.academic_records.select_related(
            "class_enrolled", "academic_session"
        ).order_by("-academic_session__start_date")

        # Behavior records
        context["behavior_records"] = student.behavior_records.filter(
            status="active"
        ).order_by("-incident_date")[:10]

        # Achievements
        context["achievements"] = student.achievements.filter(status="active").order_by(
            "-achievement_date"
        )[:10]

        # Parent relationships
        context["parent_relationships"] = student.parent_relationships.select_related(
            "parent"
        )

        return context


class StudentCreateView(AdminRequiredMixin, CreateView):
    """Create a new student profile."""

    model = Student
    form_class = StudentForm
    template_name = "academics/students/student_form.html"
    success_url = reverse_lazy("academics:student_list")

    def get_form_kwargs(self):
        from apps.core.middleware import get_current_institution

        kwargs = super().get_form_kwargs()
        kwargs["institution"] = get_current_institution()
        return kwargs

    def form_valid(self, form):
        from apps.core.middleware import get_current_institution

        form.instance.institution = get_current_institution()
        messages.success(self.request, _("Student profile created successfully."))
        return super().form_valid(form)


class StudentUpdateView(AdminRequiredMixin, UpdateView):
    """Update a student profile."""

    model = Student
    form_class = StudentForm
    template_name = "academics/students/student_form.html"
    success_url = reverse_lazy("academics:student_list")

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        return super().get_queryset().filter(institution=get_current_institution())

    def get_form_kwargs(self):
        from apps.core.middleware import get_current_institution

        kwargs = super().get_form_kwargs()
        kwargs["institution"] = get_current_institution()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _("Student profile updated successfully."))
        return super().form_valid(form)


# =============================================================================
# TEACHER VIEWS
# =============================================================================


class TeacherListView(AcademicsAccessMixin, ListView):
    """List all teachers with search and filtering."""

    model = Teacher
    template_name = "academics/teachers/teacher_list.html"
    context_object_name = "teachers"
    paginate_by = 20

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        queryset = Teacher.objects.filter(
            status="active", institution=get_current_institution()
        ).select_related(
            "user", "department"
        )

        # Apply search filters
        form = TeacherSearchForm(self.request.GET)
        if form.is_valid():
            name = form.cleaned_data.get("name")
            teacher_id = form.cleaned_data.get("teacher_id")
            department = form.cleaned_data.get("department")
            teacher_type = form.cleaned_data.get("teacher_type")

            if name:
                queryset = queryset.filter(
                    Q(user__first_name__icontains=name)
                    | Q(user__last_name__icontains=name)
                )

            if teacher_id:
                queryset = queryset.filter(teacher_id__icontains=teacher_id)

            if department:
                queryset = queryset.filter(department=department)

            if teacher_type:
                queryset = queryset.filter(teacher_type=teacher_type)

        return queryset

    def get_context_data(self, **kwargs):
        from apps.core.middleware import get_current_institution

        context = super().get_context_data(**kwargs)
        context["search_form"] = TeacherSearchForm(self.request.GET)
        context["departments"] = Department.objects.filter(
            status="active", institution=get_current_institution()
        )
        return context


class TeacherDetailView(AcademicsAccessMixin, DetailView):
    """Teacher detail view."""

    model = Teacher
    template_name = "academics/teachers/teacher_detail.html"
    context_object_name = "teacher"

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        return super().get_queryset().filter(institution=get_current_institution())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher = self.object
        current_session = AcademicSession.objects.filter(
            is_current=True, institution=teacher.institution
        ).first()

        if current_session:
            # Current subject assignments
            context["current_assignments"] = teacher.subject_assignments.filter(
                academic_session=current_session
            ).select_related("subject", "class_assigned")

            # Timetable
            context["timetable"] = teacher.timetable_entries.filter(
                academic_session=current_session, is_published=True
            ).order_by("day_of_week", "period_number")

        # Class materials
        context["materials"] = teacher.materials.filter(is_public=True).order_by(
            "-publish_date"
        )[:10]

        return context


class TeacherCreateView(AdminRequiredMixin, CreateView):
    """Create a new teacher profile."""

    model = Teacher
    form_class = TeacherForm
    template_name = "academics/teachers/teacher_form.html"
    success_url = reverse_lazy("academics:teacher_list")

    def get_form_kwargs(self):
        from apps.core.middleware import get_current_institution

        kwargs = super().get_form_kwargs()
        kwargs["institution"] = get_current_institution()
        return kwargs

    def form_valid(self, form):
        from apps.core.middleware import get_current_institution

        form.instance.institution = get_current_institution()
        messages.success(self.request, _("Teacher profile created successfully."))
        return super().form_valid(form)


class TeacherUpdateView(AdminRequiredMixin, UpdateView):
    """Update a teacher profile."""

    model = Teacher
    form_class = TeacherForm
    template_name = "academics/teachers/teacher_form.html"
    success_url = reverse_lazy("academics:teacher_list")

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        return super().get_queryset().filter(institution=get_current_institution())

    def get_form_kwargs(self):
        from apps.core.middleware import get_current_institution

        kwargs = super().get_form_kwargs()
        kwargs["institution"] = get_current_institution()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _("Teacher profile updated successfully."))
        return super().form_valid(form)


# =============================================================================
# ENROLLMENT VIEWS
# =============================================================================


class EnrollmentListView(StaffRequiredMixin, ListView):
    """List all enrollments."""

    model = Enrollment
    template_name = "academics/enrollments/enrollment_list.html"
    context_object_name = "enrollments"
    paginate_by = 25

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        queryset = Enrollment.objects.select_related(
            "student__user", "class_enrolled", "academic_session", "department"
        ).filter(institution=get_current_institution())

        # Filter by class if provided
        class_id = self.request.GET.get("class")
        if class_id:
            try:
                queryset = queryset.filter(class_enrolled_id=UUID(class_id))
            except (ValueError, TypeError, AttributeError):
                return queryset.none()

        # Filter by academic session if provided
        session_id = self.request.GET.get("session")
        if session_id:
            try:
                queryset = queryset.filter(academic_session_id=UUID(session_id))
            except (ValueError, TypeError, AttributeError):
                return queryset.none()

        # Filter by status if provided
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(enrollment_status=status)

        return queryset.order_by("-enrollment_date")

    def get_context_data(self, **kwargs):
        from apps.core.middleware import get_current_institution

        context = super().get_context_data(**kwargs)
        context["classes"] = Class.objects.filter(
            status="active", institution=get_current_institution()
        )
        context["sessions"] = AcademicSession.objects.filter(
            institution=get_current_institution()
        )
        return context


class EnrollmentCreateView(StaffRequiredMixin, CreateView):
    """Create a new enrollment."""

    model = Enrollment
    form_class = EnrollmentForm
    template_name = "academics/enrollments/enrollment_form.html"
    success_url = reverse_lazy("academics:enrollment_list")

    def get_form_kwargs(self):
        from apps.core.middleware import get_current_institution

        kwargs = super().get_form_kwargs()
        kwargs["institution"] = get_current_institution()
        return kwargs

    def form_valid(self, form):
        from apps.core.middleware import get_current_institution

        institution = get_current_institution()
        if not institution:
            form.add_error(None, _("Select a school before creating an enrollment."))
            return self.form_invalid(form)
        if (
            form.cleaned_data["student"].institution_id != institution.pk
            or form.cleaned_data["class_enrolled"].institution_id != institution.pk
            or (form.cleaned_data.get("academic_session") and form.cleaned_data["academic_session"].institution_id != institution.pk)
        ):
            form.add_error(None, _("Student, class, and session must belong to the selected school."))
            return self.form_invalid(form)
        form.instance.institution = institution
        messages.success(self.request, _("Enrollment created successfully."))
        return super().form_valid(form)


class EnrollmentUpdateView(StaffRequiredMixin, UpdateView):
    """Update an enrollment."""

    model = Enrollment
    form_class = EnrollmentForm
    template_name = "academics/enrollments/enrollment_form.html"
    success_url = reverse_lazy("academics:enrollment_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["institution"] = self.object.institution
        return kwargs

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        return super().get_queryset().filter(institution=get_current_institution())

    def form_valid(self, form):
        institution = self.object.institution
        if (
            form.cleaned_data["student"].institution_id != institution.pk
            or form.cleaned_data["class_enrolled"].institution_id != institution.pk
            or (form.cleaned_data.get("academic_session") and form.cleaned_data["academic_session"].institution_id != institution.pk)
        ):
            form.add_error(None, _("Student, class, and session must belong to this school."))
            return self.form_invalid(form)
        messages.success(self.request, _("Enrollment updated successfully."))
        return super().form_valid(form)


class EnrollmentDeleteView(StudentRequiredMixin, DeleteView):
    """Allow students to delete their own enrollments (withdraw from classes)."""

    model = Enrollment
    template_name = "academics/enrollments/enrollment_confirm_delete.html"
    success_url = reverse_lazy("academics:student_dashboard")

    def get_queryset(self):
        """Students can only delete their own enrollments."""
        return Enrollment.objects.filter(student=self.request.user.student_profile)

    def dispatch(self, request, *args, **kwargs):
        """Additional checks for enrollment deletion."""
        enrollment = self.get_object()

        # Check if enrollment belongs to student
        if enrollment.student != request.user.student_profile:
            messages.error(request, _("You can only delete your own enrollments."))
            return redirect("academics:student_dashboard")

        # Check if enrollment is active
        if enrollment.enrollment_status != "active":
            messages.error(request, _("You can only withdraw from active enrollments."))
            return redirect("academics:student_dashboard")

        # Check if withdrawal is allowed (e.g., before certain date)
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            # Allow withdrawal only within first 2 weeks of session
            from django.utils import timezone

            days_since_start = (timezone.now().date() - current_session.start_date).days
            if days_since_start > 14:  # 2 weeks
                messages.error(
                    request, _("Withdrawal period has expired. Contact administration.")
                )
                return redirect("academics:student_dashboard")

        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        enrollment = self.get_object()
        class_name = enrollment.class_enrolled.name

        # Update enrollment status instead of hard delete
        enrollment.enrollment_status = "withdrawn"
        enrollment.notes = f"Self-withdrawn by student on {timezone.now().date()}"
        enrollment.save()

        messages.success(
            request, _(f"You have successfully withdrawn from {class_name}.")
        )
        return redirect(self.success_url)


class BulkEnrollmentView(StaffRequiredMixin, View):
    """Bulk enroll students in a class."""

    def get(self, request):
        form = BulkEnrollmentForm()
        return render(
            request, "academics/enrollments/bulk_enrollment.html", {"form": form}
        )

    def post(self, request):
        form = BulkEnrollmentForm(request.POST)

        if form.is_valid():
            students = form.cleaned_data["students"]
            class_enrolled = form.cleaned_data["class_enrolled"]
            academic_session = form.cleaned_data["academic_session"]
            enrollment_date = form.cleaned_data["enrollment_date"]

            enrollments_created = 0
            for student in students:
                # Check if student is already enrolled in this session
                existing_enrollment = Enrollment.objects.filter(
                    student=student, academic_session=academic_session
                ).exists()

                if not existing_enrollment:
                    # Generate roll number (next available in class)
                    last_roll = (
                        Enrollment.objects.filter(
                            class_enrolled=class_enrolled,
                            academic_session=academic_session,
                        )
                        .order_by("-roll_number")
                        .first()
                    )

                    roll_number = last_roll.roll_number + 1 if last_roll else 1

                    Enrollment.objects.create(
                        student=student,
                        class_enrolled=class_enrolled,
                        academic_session=academic_session,
                        enrollment_date=enrollment_date,
                        roll_number=roll_number,
                        enrollment_status="active",
                    )
                    enrollments_created += 1

            messages.success(
                request,
                _(
                    f"Successfully enrolled {enrollments_created} students in {class_enrolled}."
                ),
            )
            return redirect("academics:enrollment_list")

        return render(
            request, "academics/enrollments/bulk_enrollment.html", {"form": form}
        )


# =============================================================================
# TIMETABLE VIEWS
# =============================================================================


class TimetableListView(AcademicsAccessMixin, ListView):
    """List timetable entries."""

    model = Timetable
    template_name = "academics/timetable/timetable_list.html"
    context_object_name = "timetable_entries"
    paginate_by = 25

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        queryset = (
            super()
            .get_queryset()
            .filter(status="active", is_published=True, institution=get_current_institution())
            .select_related("class_assigned", "subject", "teacher", "academic_session")
            .order_by(
                "academic_session", "class_assigned", "day_of_week", "period_number"
            )
        )
        return queryset


class TimetableDetailView(AcademicsAccessMixin, DetailView):
    """Timetable detail view."""

    model = Timetable
    template_name = "academics/timetable/timetable_detail.html"
    context_object_name = "timetable"

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        return Timetable.objects.filter(
            is_published=True, institution=get_current_institution()
        ).select_related("class_assigned", "subject", "teacher", "academic_session")


class StudentTimetableView(StudentRequiredMixin, View):
    """Student's personal timetable."""

    def get(self, request):
        student = request.user.student_profile
        current_enrollment = student.enrollments.filter(
            academic_session__is_current=True
        ).first()

        if not current_enrollment:
            messages.info(request, _("You are not currently enrolled in any class."))
            return render(
                request,
                "academics/timetable/student_timetable.html",
                {
                    "student": student,
                    "timetable_data": {},
                    "days_of_week": [],
                    "periods": [],
                    "academic_sessions": AcademicSession.objects.all(),
                    "current_session": None,
                    "current_term": None,
                },
            )

        current_session = AcademicSession.objects.filter(is_current=True).first()

        timetable_entries = (
            Timetable.objects.filter(
                class_assigned=current_enrollment.class_enrolled,
                academic_session=current_session,
                is_published=True,
            )
            .select_related("subject", "teacher")
            .order_by("day_of_week", "period_number")
        )

        # Group by day and period for template compatibility
        timetable_data = {}
        periods = set()
        days_of_week = set()

        for entry in timetable_entries:
            if entry.day_of_week not in timetable_data:
                timetable_data[entry.day_of_week] = {}
                days_of_week.add(entry.day_of_week)
            timetable_data[entry.day_of_week][entry.period_number] = entry
            periods.add(entry.period_number)

        # Sort periods and days
        periods = sorted(list(periods))
        days_of_week = sorted(
            list(days_of_week),
            key=lambda x: [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ].index(x),
        )

        # Get all periods for the class (including empty ones)
        all_periods = (
            Timetable.objects.filter(
                class_assigned=current_enrollment.class_enrolled,
                academic_session=current_session,
            )
            .values_list("period_number", flat=True)
            .distinct()
            .order_by("period_number")
        )

        periods = list(all_periods) if all_periods else periods

        context = {
            "student": student,
            "current_class": current_enrollment.class_enrolled,
            "timetable_data": timetable_data,
            "days_of_week": days_of_week,
            "periods": periods,
            "academic_sessions": AcademicSession.objects.all(),
            "current_session": current_session,
            "current_term": None,  # Can be enhanced later if terms are implemented
        }

        return render(request, "academics/timetable/student_timetable.html", context)


class TeacherTimetableView(TeacherRequiredMixin, View):
    """Teacher's personal timetable."""

    def get(self, request):
        teacher = request.user.teacher_profile
        current_session = AcademicSession.objects.filter(is_current=True).first()

        timetable_entries = (
            Timetable.objects.filter(
                teacher=teacher, academic_session=current_session, is_published=True
            )
            .select_related("class_assigned", "subject")
            .order_by("day_of_week", "period_number")
        )

        # Group by day
        timetable_data = {}
        for entry in timetable_entries:
            if entry.day_of_week not in timetable_data:
                timetable_data[entry.day_of_week] = []
            timetable_data[entry.day_of_week].append(entry)

        context = {
            "teacher": teacher,
            "timetable_data": timetable_data,
        }

        return render(request, "academics/timetable/teacher_timetable.html", context)


class TimetableCreateView(StaffRequiredMixin, CreateView):
    """Create a new timetable entry."""

    model = Timetable
    form_class = TimetableForm
    template_name = "academics/timetable/timetable_form.html"
    success_url = reverse_lazy("academics:timetable_list")

    def get_form_kwargs(self):
        from apps.core.middleware import get_current_institution

        kwargs = super().get_form_kwargs()
        kwargs["institution"] = get_current_institution()
        return kwargs

    def form_valid(self, form):
        from apps.core.middleware import get_current_institution

        form.instance.institution = get_current_institution()
        messages.success(self.request, _("Timetable entry created successfully."))
        return super().form_valid(form)


class TimetableUpdateView(StaffRequiredMixin, UpdateView):
    """Update a timetable entry."""

    model = Timetable
    form_class = TimetableForm
    template_name = "academics/timetable/timetable_form.html"
    success_url = reverse_lazy("academics:timetable_list")

    def get_queryset(self):
        from apps.core.middleware import get_current_institution

        return super().get_queryset().filter(institution=get_current_institution())

    def get_form_kwargs(self):
        from apps.core.middleware import get_current_institution

        kwargs = super().get_form_kwargs()
        kwargs["institution"] = get_current_institution()
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, _("Timetable entry updated successfully."))
        return super().form_valid(form)


# =============================================================================
# CLASS MATERIAL VIEWS
# =============================================================================


class ClassMaterialListView(AcademicsAccessMixin, ListView):
    """List class materials."""

    model = ClassMaterial
    template_name = "academics/materials/material_list.html"
    context_object_name = "materials"
    paginate_by = 15

    def get_queryset(self):
        queryset = ClassMaterial.objects.filter(
            is_public=True, publish_date__lte=timezone.now()
        ).select_related("subject", "class_assigned", "teacher")

        # Filter by subject if provided
        subject_id = self.request.GET.get("subject")
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        # Filter by class if provided
        class_id = self.request.GET.get("class")
        if class_id:
            queryset = queryset.filter(class_assigned_id=class_id)

        # Filter by material type if provided
        material_type = self.request.GET.get("type")
        if material_type:
            queryset = queryset.filter(material_type=material_type)

        return queryset.order_by("-publish_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subjects"] = Subject.objects.filter(status="active")
        context["classes"] = Class.objects.filter(status="active")
        return context


class ClassMaterialDetailView(AcademicsAccessMixin, DetailView):
    """Class material detail view."""

    model = ClassMaterial
    template_name = "academics/materials/material_detail.html"
    context_object_name = "material"

    def get(self, request, *args, **kwargs):
        # Increment view count
        self.object = self.get_object()
        self.object.increment_view_count()

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class ClassMaterialCreateView(TeacherRequiredMixin, CreateView):
    """Create a new class material."""

    model = ClassMaterial
    form_class = ClassMaterialForm
    template_name = "academics/materials/material_form.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        user = self.request.user

        if not hasattr(user, "teacher_profile"):
            if "teacher" in form.fields:
                form.fields.pop("teacher")

        return form

    def form_valid(self, form):
        user = self.request.user

        if hasattr(user, "teacher_profile"):
            form.instance.teacher = user.teacher_profile
        else:
            # User is admin/staff without teacher profile, assign system admin teacher
            admin_teacher = self.get_or_create_system_admin_teacher()
            form.instance.teacher = admin_teacher

        messages.success(self.request, _("Class material created successfully."))
        return super().form_valid(form)

    def get_or_create_system_admin_teacher(self):
        """Get or create the system admin teacher account."""
        from apps.users.models import User, Role

        # Try to find existing system admin teacher
        admin_teacher = Teacher.objects.filter(is_system_admin=True).first()
        if admin_teacher:
            return admin_teacher

        # Create a system user for admin if it doesn't exist
        admin_role = Role.objects.filter(role_type=Role.RoleType.ADMIN).first()
        if not admin_role:
            # Fallback to first admin-like role
            admin_role = Role.objects.filter(
                role_type__in=["admin", "principal", "super_admin"]
            ).first()

        system_user, created = User.objects.get_or_create(
            username="system_admin_teacher",
            defaults={
                "first_name": "System",
                "last_name": "Admin Teacher",
                "email": "admin@school.local",
                "is_staff": True,
                "is_superuser": False,
            },
        )

        # Assign admin role if not already assigned
        if admin_role and not system_user.user_roles.filter(role=admin_role).exists():
            system_user.user_roles.create(role=admin_role)

        # Create the teacher profile
        admin_teacher = Teacher.objects.create(
            user=system_user,
            teacher_id="SYSTEM_ADMIN",
            employee_id="SYS_ADMIN_001",
            joining_date=timezone.now().date(),
            is_system_admin=True,
            bio="System Administrator Teacher account for materials uploaded by admin users.",
        )

        return admin_teacher

    def get_success_url(self):
        return reverse_lazy("academics:material_detail", kwargs={"pk": self.object.pk})


class ClassMaterialUpdateView(TeacherRequiredMixin, UpdateView):
    """Update a class material."""

    model = ClassMaterial
    form_class = ClassMaterialForm
    template_name = "academics/materials/material_form.html"

    def form_valid(self, form):
        messages.success(self.request, _("Class material updated successfully."))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("academics:material_detail", kwargs={"pk": self.object.pk})


# =============================================================================
# SCHOOL POLICY VIEWS
# =============================================================================


class SchoolPolicyListView(AcademicsAccessMixin, ListView):
    """List all school policies."""

    model = SchoolPolicy
    template_name = "academics/policies/policy_list.html"
    context_object_name = "policies"
    paginate_by = 10

    def get_queryset(self):
        queryset = (
            SchoolPolicy.objects.filter(status="active")
            .select_related("academic_session", "department")
            .prefetch_related("attachments")
        )

        # Apply filters
        policy_type = self.request.GET.get("policy_type")
        academic_session_id = self.request.GET.get("academic_session")
        department_id = self.request.GET.get("department")
        is_active = self.request.GET.get("is_active")

        if policy_type:
            queryset = queryset.filter(policy_type=policy_type)
        if academic_session_id:
            queryset = queryset.filter(academic_session_id=academic_session_id)
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        if is_active:
            queryset = queryset.filter(is_active=(is_active.lower() == "true"))

        return queryset.order_by("-effective_date", "policy_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["policy_types"] = SchoolPolicy.PolicyType.choices
        context["academic_sessions"] = AcademicSession.objects.filter(status="active")
        context["departments"] = Department.objects.filter(status="active")

        # Pass current filter values for form pre-population
        context["current_policy_type"] = self.request.GET.get("policy_type", "")
        context["current_academic_session"] = self.request.GET.get(
            "academic_session", ""
        )
        context["current_department"] = self.request.GET.get("department", "")
        context["current_is_active"] = self.request.GET.get("is_active", "")

        return context


class SchoolPolicyDetailView(AcademicsAccessMixin, DetailView):
    """School policy detail view."""

    model = SchoolPolicy
    template_name = "academics/policies/policy_detail.html"
    context_object_name = "policy"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["attachments"] = self.object.attachments.all()
        return context


class SchoolPolicyCreateView(StaffRequiredMixin, CreateView):
    """Create a new school policy."""

    model = SchoolPolicy
    form_class = SchoolPolicyForm
    template_name = "academics/policies/policy_form.html"
    success_url = reverse_lazy("academics:policy_list")

    def form_valid(self, form):
        messages.success(self.request, _("School policy created successfully."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = _("Create New School Policy")
        context["submit_text"] = _("Create Policy")
        return context


class SchoolPolicyUpdateView(StaffRequiredMixin, UpdateView):
    """Update a school policy."""

    model = SchoolPolicy
    form_class = SchoolPolicyForm
    template_name = "academics/policies/policy_form.html"
    success_url = reverse_lazy("academics:policy_list")

    def form_valid(self, form):
        messages.success(self.request, _("School policy updated successfully."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = _("Update School Policy")
        context["submit_text"] = _("Update Policy")
        return context


# =============================================================================
# API AND AJAX VIEWS
# =============================================================================


class GetClassInfoView(AcademicsAccessMixin, View):
    """API view to get detailed class information including grade level education stage."""

    def get(self, request):
        from apps.core.middleware import get_current_institution

        class_id = request.GET.get("class_id")

        if not class_id:
            return JsonResponse(
                {"success": False, "message": "Class ID is required"}, status=400
            )

        try:
            class_obj = Class.objects.select_related(
                "grade_level", "class_teacher__user", "academic_session"
            ).get(id=class_id, institution=get_current_institution())

            # Get current enrollment count
            current_students = class_obj.enrollments.filter(
                enrollment_status="active"
            ).count()

            class_info = {
                "id": str(class_obj.id),
                "name": class_obj.name,
                "code": class_obj.code,
                "grade_level": (
                    class_obj.grade_level.name if class_obj.grade_level else ""
                ),
                "education_stage": (
                    class_obj.grade_level.education_stage
                    if class_obj.grade_level
                    else ""
                ),
                "class_type": class_obj.get_class_type_display(),
                "capacity": class_obj.capacity,
                "current_students": current_students,
                "available_seats": class_obj.capacity - current_students,
                "teacher": (
                    class_obj.class_teacher.user.get_full_name()
                    if class_obj.class_teacher
                    else None
                ),
                "room_number": class_obj.room_number,
                "academic_session": class_obj.academic_session.name,
                "is_tertiary": (
                    class_obj.grade_level.is_tertiary_level
                    if class_obj.grade_level
                    else False
                ),
            }

            return JsonResponse({"success": True, "class_info": class_info})

        except Class.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "Class not found"}, status=404
            )
        except (ValueError, TypeError, ValidationError):
            return JsonResponse(
                {"success": False, "message": "Invalid class ID"}, status=400
            )


class GetClassesByGradeView(AcademicsAccessMixin, View):
    """AJAX view to get classes by grade level."""

    def get(self, request):
        from apps.core.middleware import get_current_institution

        grade_level_id = request.GET.get("grade_level_id")
        session_id = request.GET.get("session_id")

        if not grade_level_id:
            return JsonResponse({"classes": []})
        try:
            from uuid import UUID

            UUID(str(grade_level_id))
            if session_id:
                UUID(str(session_id))
        except (ValueError, TypeError):
            return JsonResponse({"classes": [], "error": "Invalid identifier"}, status=400)

        classes = Class.objects.filter(
            grade_level_id=grade_level_id,
            status="active",
            institution=get_current_institution(),
        )

        if session_id:
            classes = classes.filter(academic_session_id=session_id)

        class_list = [{"id": cls.id, "name": cls.name} for cls in classes]

        return JsonResponse({"classes": class_list})


class GetTimetableByClassView(AcademicsAccessMixin, View):
    """AJAX view to get timetable for a class."""

    def get(self, request, class_id=None, *args, **kwargs):
        from apps.core.middleware import get_current_institution
        from uuid import UUID

        # Accept `class_id` either as path kwarg or GET param
        if not class_id:
            class_id = request.GET.get("class_id")
        session_id = request.GET.get("session_id")

        if not class_id:
            return JsonResponse({"error": "Class ID required"}, status=400)

        try:
            UUID(str(class_id))
            if session_id:
                UUID(str(session_id))
        except (ValueError, TypeError):
            return JsonResponse({"error": "Invalid identifier"}, status=400)

        timetable_entries = Timetable.objects.filter(
            class_assigned_id=class_id,
            institution=get_current_institution(),
            is_published=True,
        )

        if session_id:
            timetable_entries = timetable_entries.filter(academic_session_id=session_id)
        else:
            current_session = AcademicSession.objects.filter(
                is_current=True, institution=get_current_institution()
            ).first()
            if current_session:
                timetable_entries = timetable_entries.filter(
                    academic_session=current_session
                )

        timetable_data = []
        for entry in timetable_entries.order_by("day_of_week", "period_number"):
            timetable_data.append(
                {
                    "day": entry.get_day_of_week_display(),
                    "period": entry.period_number,
                    "subject": entry.subject.name if entry.subject else entry.title,
                    "teacher": (
                        entry.teacher.user.get_full_name() if entry.teacher else ""
                    ),
                    "start_time": entry.start_time.strftime("%H:%M"),
                    "end_time": entry.end_time.strftime("%H:%M"),
                    "room": entry.room_number,
                }
            )

        return JsonResponse({"timetable": timetable_data})


class AcademicCalendarView(AcademicsAccessMixin, View):
    """Academic calendar view."""

    def get(self, request):
        from apps.core.middleware import get_current_institution

        school = get_current_institution()
        current_session = AcademicSession.objects.filter(
            is_current=True, institution=school
        ).first()
        if current_session is None:
            return render(request, "academics/calendar/no_session.html", {
                "current_session": None,
            })
        holidays = Holiday.objects.filter(
            academic_session=current_session, institution=school
        )

        context = {
            "current_session": current_session,
            "holidays": holidays,
        }

        return render(request, "academics/calendar/academic_calendar.html", context)


# =============================================================================
# ENROLLMENT API VIEWS
# =============================================================================


class BulkUpdateEnrollmentsView(StaffRequiredMixin, View):
    """API view for bulk updating enrollment records."""

    def post(self, request):
        import json
        from django.db import transaction

        try:
            data = json.loads(request.body)
            enrollment_ids = data.get("enrollment_ids", [])
            new_status = data.get("status")
            effective_date = data.get("effective_date")
            reason = data.get("reason", "")

            if not enrollment_ids or not new_status:
                return JsonResponse(
                    {
                        "success": False,
                        "message": _(
                            "Missing required fields: enrollment_ids and status"
                        ),
                    },
                    status=400,
                )

            if new_status not in [
                "active",
                "completed",
                "transferred",
                "withdrawn",
                "suspended",
            ]:
                return JsonResponse(
                    {"success": False, "message": _("Invalid status value")}, status=400
                )

            enrollments = Enrollment.objects.filter(id__in=enrollment_ids)

            if len(enrollments) != len(enrollment_ids):
                return JsonResponse(
                    {
                        "success": False,
                        "message": _("One or more enrollments not found"),
                    },
                    status=404,
                )

            updated_count = 0
            with transaction.atomic():
                for enrollment in enrollments:
                    enrollment.enrollment_status = new_status
                    if reason:
                        enrollment.notes = reason
                    enrollment.save()
                    updated_count += 1

            return JsonResponse(
                {
                    "success": True,
                    "message": _(f"Successfully updated {updated_count} enrollments"),
                    "updated_count": updated_count,
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "message": _("Invalid JSON data")}, status=400
            )
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)


class TransferStudentView(StaffRequiredMixin, View):
    """API view for transferring a student to a different class."""

    def post(self, request):
        import json
        from django.db import transaction

        try:
            data = json.loads(request.body)
            enrollment_id = data.get("enrollment_id")
            target_class_id = data.get("target_class_id")
            transfer_date = data.get("transfer_date")
            reason = data.get("reason", "")

            if not all([enrollment_id, target_class_id, transfer_date]):
                return JsonResponse(
                    {
                        "success": False,
                        "message": _(
                            "Missing required fields: enrollment_id, target_class_id, and transfer_date"
                        ),
                    },
                    status=400,
                )

            try:
                enrollment = Enrollment.objects.select_related(
                    "student", "class_enrolled", "academic_session"
                ).get(id=enrollment_id)
            except Enrollment.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": _("Enrollment not found")}, status=404
                )

            try:
                target_class = Class.objects.get(id=target_class_id)
            except Class.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": _("Target class not found")},
                    status=404,
                )

            # Check if student is already enrolled in target class for same session
            existing_enrollment = Enrollment.objects.filter(
                student=enrollment.student,
                academic_session=enrollment.academic_session,
                class_enrolled=target_class,
                enrollment_status="active",
            ).exists()

            if existing_enrollment:
                return JsonResponse(
                    {
                        "success": False,
                        "message": _("Student is already enrolled in the target class"),
                    },
                    status=400,
                )

            with transaction.atomic():
                # Update enrollment status to transferred
                enrollment.enrollment_status = "transferred"
                enrollment.notes = (
                    f"Transferred to {target_class.name}. Reason: {reason}"
                )
                enrollment.save()

                # Create new enrollment
                last_roll = (
                    Enrollment.objects.filter(
                        class_enrolled=target_class,
                        academic_session=enrollment.academic_session,
                    )
                    .order_by("-roll_number")
                    .first()
                )

                new_roll_number = last_roll.roll_number + 1 if last_roll else 1

                new_enrollment = Enrollment.objects.create(
                    student=enrollment.student,
                    class_enrolled=target_class,
                    academic_session=enrollment.academic_session,
                    enrollment_date=transfer_date,
                    roll_number=new_roll_number,
                    enrollment_status="active",
                    notes=f"Transferred from {enrollment.class_enrolled.name}. Reason: {reason}",
                )

            return JsonResponse(
                {
                    "success": True,
                    "message": _(
                        f"Student {enrollment.student.user.get_full_name} transferred to {target_class.name}"
                    ),
                    "new_enrollment_id": str(new_enrollment.id),
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "message": _("Invalid JSON data")}, status=400
            )
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)


class WithdrawStudentView(StaffRequiredMixin, View):
    """API view for withdrawing a student from enrollment."""

    def post(self, request):
        import json

        try:
            data = json.loads(request.body)
            enrollment_id = data.get("enrollment_id")
            withdrawal_date = data.get("withdrawal_date")
            reason = data.get("reason")
            details = data.get("details", "")

            if not all([enrollment_id, withdrawal_date, reason]):
                return JsonResponse(
                    {
                        "success": False,
                        "message": _(
                            "Missing required fields: enrollment_id, withdrawal_date, and reason"
                        ),
                    },
                    status=400,
                )

            try:
                enrollment = Enrollment.objects.select_related(
                    "student", "class_enrolled"
                ).get(id=enrollment_id)
            except Enrollment.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": _("Enrollment not found")}, status=404
                )

            enrollment.enrollment_status = "withdrawn"
            enrollment.notes = (
                f"Withdrawn on {withdrawal_date}. Reason: {reason}. Details: {details}"
            )
            enrollment.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": _(
                        f"Student {enrollment.student.user.get_full_name} withdrawn from {enrollment.class_enrolled.name}"
                    ),
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "message": _("Invalid JSON data")}, status=400
            )
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)


class ExportEnrollmentsView(AcademicsAccessMixin, View):
    """API view for exporting enrollment data."""

    def get(self, request):
        import csv
        from django.http import HttpResponse

        # Get filters from query parameters
        class_id = request.GET.get("class")
        session_id = request.GET.get("session")
        status = request.GET.get("status")
        export_format = request.GET.get("format", "csv")

        enrollments = Enrollment.objects.select_related(
            "student__user", "class_enrolled__grade_level", "academic_session"
        )

        if class_id:
            enrollments = enrollments.filter(class_enrolled_id=class_id)
        if session_id:
            enrollments = enrollments.filter(academic_session_id=session_id)
        if status:
            enrollments = enrollments.filter(enrollment_status=status)

        # Prepare response based on format
        if export_format.lower() == "excel":
            return self._export_excel(enrollments)
        else:
            return self._export_csv(enrollments)

    def _export_csv(self, enrollments):
        """Export enrollments as CSV."""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="enrollments.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Student ID",
                "Student Name",
                "Class",
                "Grade Level",
                "Roll Number",
                "Academic Session",
                "Enrollment Date",
                "Status",
                "Student Type",
            ]
        )

        for enrollment in enrollments:
            writer.writerow(
                [
                    enrollment.student.student_id,
                    enrollment.student.user.get_full_name,
                    enrollment.class_enrolled.name,
                    enrollment.class_enrolled.grade_level.name,
                    enrollment.roll_number,
                    enrollment.academic_session.name,
                    enrollment.enrollment_date.strftime("%Y-%m-%d"),
                    enrollment.get_enrollment_status_display(),
                    enrollment.student.get_student_type_display(),
                ]
            )

        return response

    def _export_excel(self, enrollments):
        """Export enrollments as Excel (CSV format with .xlsx extension)."""
        response = HttpResponse(content_type="application/vnd.ms-excel")
        response["Content-Disposition"] = 'attachment; filename="enrollments.xlsx"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Student ID",
                "Student Name",
                "Class",
                "Grade Level",
                "Roll Number",
                "Academic Session",
                "Enrollment Date",
                "Status",
                "Student Type",
                "Notes",
            ]
        )

        for enrollment in enrollments:
            writer.writerow(
                [
                    enrollment.student.student_id,
                    enrollment.student.user.get_full_name,
                    enrollment.class_enrolled.name,
                    enrollment.class_enrolled.grade_level.name,
                    enrollment.roll_number,
                    enrollment.academic_session.name,
                    enrollment.enrollment_date.strftime("%Y-%m-%d"),
                    enrollment.get_enrollment_status_display(),
                    enrollment.student.get_student_type_display(),
                    enrollment.notes or "",
                ]
            )

        return response


# =============================================================================
# REPORT VIEWS
# =============================================================================


class StudentProgressReportView(StaffRequiredMixin, View):
    """Generate student progress report."""

    def get(self, request, student_id):
        student = get_object_or_404(Student, id=student_id)
        current_enrollment = student.enrollments.filter(
            academic_session__is_current=True
        ).first()

        if not current_enrollment:
            messages.error(request, _("Student is not currently enrolled."))
            return redirect("academics:student_list")

        academic_records = student.academic_records.filter(
            academic_session=current_enrollment.academic_session
        ).select_related("subject")

        context = {
            "student": student,
            "current_class": current_enrollment.class_enrolled,
            "academic_records": academic_records,
        }

        return render(
            request, "academics/reports/student_progress_report.html", context
        )


class ClassReportView(StaffRequiredMixin, View):
    """Generate class report."""

    def get(self, request, class_id):
        class_obj = get_object_or_404(Class, id=class_id)
        enrollments = class_obj.enrollments.filter(
            enrollment_status="active"
        ).select_related("student__user")

        context = {
            "class_obj": class_obj,
            "enrollments": enrollments,
        }

        return render(request, "academics/reports/class_report.html", context)


class EnrollmentReportsDashboardView(StaffRequiredMixin, View):
    """Comprehensive enrollment reports dashboard."""

    def get(self, request):
        # Get current session or use the most recent one
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if not current_session:
            current_session = AcademicSession.objects.order_by("-start_date").first()

        # Basic enrollment statistics
        total_students = Student.objects.filter(status="active").count()
        total_enrollments = (
            Enrollment.objects.filter(
                academic_session=current_session, enrollment_status="active"
            ).count()
            if current_session
            else 0
        )

        # Enrollment by grade level
        grade_enrollments = []
        if current_session:
            grade_stats = (
                Enrollment.objects.filter(
                    academic_session=current_session, enrollment_status="active"
                )
                .values(
                    "class_enrolled__grade_level__name",
                    "class_enrolled__grade_level__code",
                )
                .annotate(count=Count("id"))
                .order_by("class_enrolled__grade_level__code")
            )

            grade_enrollments = list(grade_stats)

        # Transfer statistics
        transfer_stats = {}
        if current_session:
            transfers_in = ClassTransferHistory.objects.filter(
                academic_session=current_session,
                to_class__academic_session=current_session,
            ).count()

            transfers_out = ClassTransferHistory.objects.filter(
                academic_session=current_session,
                from_class__academic_session=current_session,
            ).count()

            transfer_stats = {
                "transfers_in": transfers_in,
                "transfers_out": transfers_out,
                "net_transfers": transfers_in - transfers_out,
            }

        # Withdrawals and suspensions
        withdrawal_stats = {}
        if current_session:
            withdrawals = Enrollment.objects.filter(
                academic_session=current_session, enrollment_status="withdrawn"
            ).count()

            suspensions = Enrollment.objects.filter(
                academic_session=current_session, enrollment_status="suspended"
            ).count()

            withdrawal_stats = {
                "withdrawals": withdrawals,
                "suspensions": suspensions,
                "total_exits": withdrawals + suspensions,
            }

        # Enrollment trends (last 5 sessions)
        enrollment_trends = []
        recent_sessions = AcademicSession.objects.order_by("-start_date")[:5]
        for session in recent_sessions:
            count = Enrollment.objects.filter(
                academic_session=session, enrollment_status="active"
            ).count()
            enrollment_trends.append(
                {
                    "session": session.name,
                    "count": count,
                    "year": session.start_date.year,
                }
            )

        # Class capacity utilization
        class_utilization = []
        if current_session:
            classes = Class.objects.filter(academic_session=current_session)
            for class_obj in classes:
                enrolled = class_obj.enrollments.filter(
                    enrollment_status="active"
                ).count()
                utilization = (
                    (enrolled / class_obj.capacity * 100)
                    if class_obj.capacity > 0
                    else 0
                )
                class_utilization.append(
                    {
                        "class_name": class_obj.name,
                        "capacity": class_obj.capacity,
                        "enrolled": enrolled,
                        "utilization": round(utilization, 1),
                        "available": class_obj.capacity - enrolled,
                    }
                )

        # Student type distribution
        student_types = []
        if current_session:
            type_stats = (
                Enrollment.objects.filter(
                    academic_session=current_session, enrollment_status="active"
                )
                .values("student__student_type")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            for stat in type_stats:
                student_types.append(
                    {"type": stat["student__student_type"], "count": stat["count"]}
                )

        context = {
            "title": _("Enrollment Reports Dashboard"),
            "current_session": current_session,
            "total_students": total_students,
            "total_enrollments": total_enrollments,
            "grade_enrollments": grade_enrollments,
            "transfer_stats": transfer_stats,
            "withdrawal_stats": withdrawal_stats,
            "enrollment_trends": enrollment_trends,
            "class_utilization": class_utilization,
            "student_types": student_types,
            "sessions": AcademicSession.objects.all().order_by("-start_date"),
        }

        return render(request, "academics/reports/enrollment_dashboard.html", context)


# =============================================================================
# HOLIDAY VIEWS
# =============================================================================


class HolidayListView(AcademicsAccessMixin, ListView):
    """List all holidays."""

    model = Holiday
    template_name = "academics/holidays/holiday_list.html"
    context_object_name = "holidays"
    paginate_by = 15

    def get_queryset(self):
        queryset = Holiday.objects.select_related("academic_session")

        # Filter by academic session if provided
        session_id = self.request.GET.get("session")
        if session_id:
            queryset = queryset.filter(academic_session_id=session_id)

        # Filter by year if provided
        year = self.request.GET.get("year")
        if year:
            queryset = queryset.filter(date__year=year)

        return queryset.order_by("date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sessions"] = AcademicSession.objects.all().order_by("-start_date")
        return context


class HolidayDetailView(AcademicsAccessMixin, DetailView):
    """Holiday detail view."""

    model = Holiday
    template_name = "academics/holidays/holiday_detail.html"
    context_object_name = "holiday"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["other_holidays"] = (
            self.object.academic_session.holidays.exclude(pk=self.object.pk)
            .order_by("date")
            if self.object.academic_session_id else []
        )
        return context


class HolidayCreateView(StaffRequiredMixin, CreateView):
    """Create a new holiday."""

    model = Holiday
    form_class = HolidayForm
    template_name = "academics/holidays/holiday_form.html"
    success_url = reverse_lazy("academics:holiday_list")

    def form_valid(self, form):
        messages.success(self.request, _("Holiday created successfully."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = _("Create New Holiday")
        context["submit_text"] = _("Create Holiday")
        return context


class HolidayUpdateView(StaffRequiredMixin, UpdateView):
    """Update a holiday."""

    model = Holiday
    form_class = HolidayForm
    template_name = "academics/holidays/holiday_form.html"
    success_url = reverse_lazy("academics:holiday_list")

    def form_valid(self, form):
        messages.success(self.request, _("Holiday updated successfully."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = _("Update Holiday")
        context["submit_text"] = _("Update Holiday")
        return context


class HolidayDeleteView(StaffRequiredMixin, DeleteView):
    """Delete a holiday."""

    model = Holiday
    template_name = "academics/holidays/holiday_confirm_delete.html"
    success_url = reverse_lazy("academics:holiday_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Holiday deleted successfully."))
        return super().delete(request, *args, **kwargs)


# =============================================================================
# DEPARTMENT HEAD VIEWS
# =============================================================================


class DepartmentHeadRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a department head."""

    def test_func(self):
        user = self.request.user
        if hasattr(user, "teacher_profile"):
            return user.teacher_profile.is_department_head
        return False


class DepartmentHeadDashboardView(DepartmentHeadRequiredMixin, View):
    """Department Head dashboard with comprehensive department overview."""

    def get(self, request):
        department_head = request.user.teacher_profile
        department = department_head.department
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Department statistics
        department_stats = self._get_department_stats(department, current_session)

        # Recent activities
        recent_activities = self._get_recent_activities(department, current_session)

        # Department alerts and notifications
        alerts = self._get_department_alerts(department, current_session)

        # Budget overview
        budget_overview = self._get_budget_overview(department, current_session)

        # Performance metrics
        performance_metrics = self._get_performance_metrics(department, current_session)

        context = {
            "department_head": department_head,
            "department": department,
            "current_session": current_session,
            "department_stats": department_stats,
            "recent_activities": recent_activities,
            "alerts": alerts,
            "budget_overview": budget_overview,
            "performance_metrics": performance_metrics,
        }

        return render(request, "academics/department_head/dashboard.html", context)

    def _get_department_stats(self, department, current_session):
        """Get comprehensive department statistics."""
        if not current_session:
            return {}

        # Teacher statistics
        teachers = department.teachers.filter(status="active")
        total_teachers = teachers.count()

        # Student statistics
        department_subjects = department.subjects.filter(status="active")
        classes_with_dept_subjects = Class.objects.filter(
            subject_assignments__subject__in=department_subjects,
            academic_session=current_session,
        ).distinct()

        total_students = Enrollment.objects.filter(
            class_enrolled__in=classes_with_dept_subjects, enrollment_status="active"
        ).count()

        # Subject assignments
        subject_assignments = SubjectAssignment.objects.filter(
            subject__department=department,
            academic_session=current_session,
            status="active",
        )

        # Class materials
        materials_count = ClassMaterial.objects.filter(
            subject__department=department, publish_date__gte=current_session.start_date
        ).count()

        return {
            "total_teachers": total_teachers,
            "total_students": total_students,
            "total_subjects": department_subjects.count(),
            "total_classes": classes_with_dept_subjects.count(),
            "subject_assignments": subject_assignments.count(),
            "materials_count": materials_count,
        }

    def _get_recent_activities(self, department, current_session):
        """Get recent department activities."""
        activities = []

        # Recent materials uploaded
        recent_materials = (
            ClassMaterial.objects.filter(
                subject__department=department,
                publish_date__gte=(
                    current_session.start_date
                    if current_session
                    else timezone.now() - timezone.timedelta(days=30)
                ),
            )
            .select_related("teacher", "subject")
            .order_by("-publish_date")[:5]
        )

        for material in recent_materials:
            activities.append(
                {
                    "type": "material_upload",
                    "title": f"New material: {material.title}",
                    "teacher": material.teacher.user.get_full_name(),
                    "date": material.publish_date,
                    "subject": material.subject.name,
                }
            )

        # Recent assignments created
        from apps.assessment.models import Assignment

        recent_assignments = (
            Assignment.objects.filter(
                subject__department=department,
                academic_session=current_session,
                created_at__gte=(
                    current_session.start_date
                    if current_session
                    else timezone.now() - timezone.timedelta(days=30)
                ),
            )
            .select_related("teacher", "subject")
            .order_by("-created_at")[:5]
        )

        for assignment in recent_assignments:
            activities.append(
                {
                    "type": "assignment_created",
                    "title": f"New assignment: {assignment.title}",
                    "teacher": assignment.teacher.user.get_full_name(),
                    "date": assignment.created_at,
                    "subject": assignment.subject.name,
                }
            )

        # Sort activities by date
        activities.sort(key=lambda x: x["date"], reverse=True)
        return activities[:10]

    def _get_department_alerts(self, department, current_session):
        """Get department alerts and notifications."""
        alerts = []

        # Check for teachers without subject assignments
        unassigned_teachers = (
            department.teachers.filter(status="active")
            .exclude(
                subject_assignments__academic_session=current_session,
                subject_assignments__status="active",
            )
            .distinct()
        )

        if unassigned_teachers.exists():
            alerts.append(
                {
                    "type": "warning",
                    "message": f"{unassigned_teachers.count()} teachers have no subject assignments for current session",
                    "action_url": reverse_lazy("academics:department_teachers"),
                }
            )

        # Check for subjects without teachers
        department_subjects = department.subjects.filter(status="active")
        unassigned_subjects = department_subjects.exclude(
            subject_assignments__academic_session=current_session,
            subject_assignments__status="active",
        ).distinct()

        if unassigned_subjects.exists():
            alerts.append(
                {
                    "type": "warning",
                    "message": f"{unassigned_subjects.count()} subjects have no teacher assignments",
                    "action_url": reverse_lazy("academics:department_subjects"),
                }
            )

        # Budget alerts
        if current_session:
            budget_items = DepartmentBudget.objects.filter(
                department=department, academic_session=current_session
            )

            overspent_items = budget_items.filter(
                spent_amount__gt=models.F("allocated_amount")
            )

            if overspent_items.exists():
                alerts.append(
                    {
                        "type": "danger",
                        "message": f"{overspent_items.count()} budget items are overspent",
                        "action_url": reverse_lazy("academics:department_budget"),
                    }
                )

        return alerts

    def _get_budget_overview(self, department, current_session):
        """Get department budget overview."""
        if not current_session:
            return None

        budget_items = DepartmentBudget.objects.filter(
            department=department, academic_session=current_session
        )

        total_allocated = (
            budget_items.aggregate(total=models.Sum("allocated_amount"))["total"] or 0
        )

        total_spent = (
            budget_items.aggregate(total=models.Sum("spent_amount"))["total"] or 0
        )

        return {
            "total_allocated": total_allocated,
            "total_spent": total_spent,
            "remaining": total_allocated - total_spent,
            "utilization_percentage": (
                (total_spent / total_allocated * 100) if total_allocated > 0 else 0
            ),
        }

    def _get_performance_metrics(self, department, current_session):
        """Get department performance metrics."""
        if not current_session:
            return {}

        # Average class performance in department subjects
        department_subjects = department.subjects.filter(status="active")

        # Get marks for department subjects
        from apps.assessment.models import Mark

        marks = Mark.objects.filter(
            exam__subject__in=department_subjects,
            exam__academic_class__academic_session=current_session,
        )

        if marks.exists():
            avg_marks = marks.aggregate(
                avg_percentage=models.Avg("percentage"),
                total_exams=models.Count("id", distinct=True),
                total_students=models.Count("student", distinct=True),
            )

            return {
                "average_percentage": round(avg_marks["avg_percentage"] or 0, 1),
                "total_exams": avg_marks["total_exams"],
                "total_students": avg_marks["total_students"],
            }

        return {}


class DepartmentTeachersView(DepartmentHeadRequiredMixin, ListView):
    """Department Head view for managing department teachers."""

    model = Teacher
    template_name = "academics/department_head/teachers.html"
    context_object_name = "teachers"
    paginate_by = 20

    def get_queryset(self):
        department = self.request.user.teacher_profile.department
        return department.teachers.filter(status="active").select_related(
            "user", "department"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.request.user.teacher_profile.department
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Add subject assignment information
        for teacher in context["teachers"]:
            if current_session:
                teacher.current_assignments = teacher.subject_assignments.filter(
                    academic_session=current_session, status="active"
                ).select_related("subject", "class_assigned")
            else:
                teacher.current_assignments = []

        context["department"] = department
        context["current_session"] = current_session
        return context


class DepartmentStudentsView(DepartmentHeadRequiredMixin, ListView):
    """Department Head view for department students."""

    model = Student
    template_name = "academics/department_head/students.html"
    context_object_name = "students"
    paginate_by = 20

    def get_queryset(self):
        department = self.request.user.teacher_profile.department
        current_session = AcademicSession.objects.filter(is_current=True).first()

        if not current_session:
            return Student.objects.none()

        # Get students enrolled in classes that have department subjects
        department_subjects = department.subjects.filter(status="active")
        classes_with_dept_subjects = Class.objects.filter(
            subject_assignments__subject__in=department_subjects,
            academic_session=current_session,
        ).distinct()

        students = (
            Student.objects.filter(
                enrollments__class_enrolled__in=classes_with_dept_subjects,
                enrollments__enrollment_status="active",
                status="active",
            )
            .select_related("user")
            .distinct()
        )

        return students

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.request.user.teacher_profile.department
        current_session = AcademicSession.objects.filter(is_current=True).first()

        context["department"] = department
        context["current_session"] = current_session
        return context


class DepartmentSubjectsView(DepartmentHeadRequiredMixin, ListView):
    """Department Head view for department subjects."""

    model = Subject
    template_name = "academics/department_head/subjects.html"
    context_object_name = "subjects"
    paginate_by = 15

    def get_queryset(self):
        department = self.request.user.teacher_profile.department
        return department.subjects.filter(status="active").prefetch_related(
            "subject_assignments"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.request.user.teacher_profile.department
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Add assignment information for current session
        for subject in context["subjects"]:
            if current_session:
                subject.current_assignments = subject.subject_assignments.filter(
                    academic_session=current_session, status="active"
                ).select_related("teacher", "class_assigned")
            else:
                subject.current_assignments = []

        context["department"] = department
        context["current_session"] = current_session
        return context


class DepartmentBudgetView(DepartmentHeadRequiredMixin, ListView):
    """Department Head view for department budget management."""

    model = DepartmentBudget
    template_name = "academics/department_head/budget.html"
    context_object_name = "budget_items"
    paginate_by = 15

    def get_queryset(self):
        department = self.request.user.teacher_profile.department
        current_session = AcademicSession.objects.filter(is_current=True).first()

        if current_session:
            return department.budgets.filter(academic_session=current_session)
        return DepartmentBudget.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.request.user.teacher_profile.department
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Budget summary
        budget_items = context["budget_items"]
        total_allocated = (
            budget_items.aggregate(total=models.Sum("allocated_amount"))["total"] or 0
        )
        total_spent = (
            budget_items.aggregate(total=models.Sum("spent_amount"))["total"] or 0
        )

        context.update(
            {
                "department": department,
                "current_session": current_session,
                "total_allocated": total_allocated,
                "total_spent": total_spent,
                "remaining_budget": total_allocated - total_spent,
                "utilization_percentage": (
                    (total_spent / total_allocated * 100) if total_allocated > 0 else 0
                ),
            }
        )

        return context


class DepartmentReportsView(DepartmentHeadRequiredMixin, View):
    """Department Head reports and analytics."""

    def get(self, request):
        department = request.user.teacher_profile.department
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Performance report data
        performance_data = self._get_performance_report(department, current_session)

        # Teacher workload report
        workload_data = self._get_workload_report(department, current_session)

        # Student progress report
        progress_data = self._get_progress_report(department, current_session)

        context = {
            "department": department,
            "current_session": current_session,
            "performance_data": performance_data,
            "workload_data": workload_data,
            "progress_data": progress_data,
        }

        return render(request, "academics/department_head/reports.html", context)

    def _get_performance_report(self, department, current_session):
        """Generate department performance report."""
        if not current_session:
            return {}

        department_subjects = department.subjects.filter(status="active")

        from apps.assessment.models import Mark

        marks = Mark.objects.filter(
            exam__subject__in=department_subjects,
            exam__academic_class__academic_session=current_session,
        ).select_related("exam__subject", "student")

        if not marks.exists():
            return {}

        # Subject-wise performance
        subject_performance = (
            marks.values("exam__subject__name")
            .annotate(
                avg_percentage=models.Avg("percentage"),
                total_marks=models.Count("id"),
                total_students=models.Count("student", distinct=True),
            )
            .order_by("-avg_percentage")
        )

        # Grade distribution
        grade_distribution = self._get_grade_distribution(marks)

        return {
            "subject_performance": list(subject_performance),
            "grade_distribution": grade_distribution,
            "overall_average": marks.aggregate(avg=models.Avg("percentage"))["avg"]
            or 0,
            "total_assessments": marks.count(),
        }

    def _get_workload_report(self, department, current_session):
        """Generate teacher workload report."""
        if not current_session:
            return []

        teachers = department.teachers.filter(status="active")

        workload_data = []
        for teacher in teachers:
            assignments = teacher.subject_assignments.filter(
                academic_session=current_session, status="active"
            )

            workload_data.append(
                {
                    "teacher": teacher,
                    "total_assignments": assignments.count(),
                    "classes_count": assignments.values("class_assigned")
                    .distinct()
                    .count(),
                    "subjects_count": assignments.values("subject").distinct().count(),
                    "total_periods": assignments.aggregate(
                        total=models.Sum("periods_per_week")
                    )["total"]
                    or 0,
                }
            )

        return workload_data

    def _get_progress_report(self, department, current_session):
        """Generate student progress report."""
        if not current_session:
            return {}

        # Get students in department classes
        department_subjects = department.subjects.filter(status="active")
        classes_with_dept_subjects = Class.objects.filter(
            subject_assignments__subject__in=department_subjects,
            academic_session=current_session,
        ).distinct()

        students = Student.objects.filter(
            enrollments__class_enrolled__in=classes_with_dept_subjects,
            enrollments__enrollment_status="active",
        ).distinct()

        # Progress statistics
        total_students = students.count()

        # Students with good performance (>80%)
        from apps.assessment.models import Mark

        high_performers = (
            Mark.objects.filter(
                exam__subject__in=department_subjects,
                exam__academic_class__academic_session=current_session,
                percentage__gte=80,
            )
            .values("student")
            .distinct()
            .count()
        )

        # Students needing attention (<50%)
        low_performers = (
            Mark.objects.filter(
                exam__subject__in=department_subjects,
                exam__academic_class__academic_session=current_session,
                percentage__lt=50,
            )
            .values("student")
            .distinct()
            .count()
        )

        return {
            "total_students": total_students,
            "high_performers": high_performers,
            "low_performers": low_performers,
            "high_performer_percentage": (
                (high_performers / total_students * 100) if total_students > 0 else 0
            ),
            "low_performer_percentage": (
                (low_performers / total_students * 100) if total_students > 0 else 0
            ),
        }

    def _get_grade_distribution(self, marks):
        """Calculate grade distribution."""
        # Assuming grading system with A, B, C, D, F grades
        distribution = {
            "A": marks.filter(percentage__gte=90).count(),
            "B": marks.filter(percentage__gte=80, percentage__lt=90).count(),
            "C": marks.filter(percentage__gte=70, percentage__lt=80).count(),
            "D": marks.filter(percentage__gte=60, percentage__lt=70).count(),
            "F": marks.filter(percentage__lt=60).count(),
        }
        return distribution


# =============================================================================
# COUNSELOR VIEWS
# =============================================================================


class CounselorRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a counselor."""

    def test_func(self):
        user = self.request.user
        if hasattr(user, "teacher_profile"):
            return user.teacher_profile.is_counselor
        return False


class CounselorDashboardView(CounselorRequiredMixin, View):
    """Counselor dashboard with counseling activities overview."""

    def get(self, request):
        counselor = request.user.teacher_profile
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Counseling statistics
        counseling_stats = self._get_counseling_stats(counselor, current_session)

        # Today's sessions
        today_sessions = self._get_today_sessions(counselor)

        # Pending referrals
        pending_referrals = self._get_pending_referrals(counselor)

        # Recent activities
        recent_activities = self._get_recent_activities(counselor)

        # Student alerts
        student_alerts = self._get_student_alerts(counselor, current_session)

        context = {
            "counselor": counselor,
            "current_session": current_session,
            "counseling_stats": counseling_stats,
            "today_sessions": today_sessions,
            "pending_referrals": pending_referrals,
            "recent_activities": recent_activities,
            "student_alerts": student_alerts,
        }

        return render(request, "academics/counselor/dashboard.html", context)

    def _get_counseling_stats(self, counselor, current_session):
        """Get counseling statistics."""
        if not current_session:
            return {}

        # Session statistics
        total_sessions = CounselingSession.objects.filter(
            counselor=counselor, academic_session=current_session
        ).count()

        completed_sessions = CounselingSession.objects.filter(
            counselor=counselor,
            academic_session=current_session,
            session_status="completed",
        ).count()

        upcoming_sessions = CounselingSession.objects.filter(
            counselor=counselor,
            scheduled_date__gte=timezone.now().date(),
            session_status="scheduled",
        ).count()

        # Referral statistics
        total_referrals = CounselingReferral.objects.filter(
            counselor=counselor, referral_date__gte=current_session.start_date
        ).count()

        resolved_referrals = CounselingReferral.objects.filter(
            counselor=counselor,
            referral_status="resolved",
            referral_date__gte=current_session.start_date,
        ).count()

        # Career guidance sessions
        career_sessions = CareerGuidance.objects.filter(
            counselor=counselor, session_date__gte=current_session.start_date
        ).count()

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "upcoming_sessions": upcoming_sessions,
            "completion_rate": (
                (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
            ),
            "total_referrals": total_referrals,
            "resolved_referrals": resolved_referrals,
            "resolution_rate": (
                (resolved_referrals / total_referrals * 100)
                if total_referrals > 0
                else 0
            ),
            "career_sessions": career_sessions,
        }

    def _get_today_sessions(self, counselor):
        """Get today's counseling sessions."""
        today = timezone.now().date()
        return (
            CounselingSession.objects.filter(counselor=counselor, scheduled_date=today)
            .select_related("student")
            .order_by("scheduled_time")
        )

    def _get_pending_referrals(self, counselor):
        """Get pending referrals."""
        return (
            CounselingReferral.objects.filter(
                counselor=counselor, referral_status__in=["pending", "in_progress"]
            )
            .select_related("student")
            .order_by("-referral_date")[:5]
        )

    def _get_recent_activities(self, counselor):
        """Get recent counseling activities."""
        activities = []

        # Recent sessions
        recent_sessions = (
            CounselingSession.objects.filter(counselor=counselor)
            .select_related("student")
            .order_by("-scheduled_date")[:3]
        )

        for session in recent_sessions:
            activities.append(
                {
                    "type": "session",
                    "title": f"Session with {session.student.user.get_full_name()}",
                    "date": session.scheduled_date,
                    "status": session.session_status,
                }
            )

        # Recent referrals
        recent_referrals = (
            CounselingReferral.objects.filter(counselor=counselor)
            .select_related("student")
            .order_by("-referral_date")[:3]
        )

        for referral in recent_referrals:
            activities.append(
                {
                    "type": "referral",
                    "title": f"Referral: {referral.student.user.get_full_name()}",
                    "date": referral.referral_date,
                    "status": referral.referral_status,
                }
            )

        # Sort by date
        activities.sort(key=lambda x: x["date"], reverse=True)
        return activities[:5]

    def _get_student_alerts(self, counselor, current_session):
        """Get student alerts requiring counselor attention."""
        alerts = []

        if not current_session:
            return alerts

        # Students with multiple behavior records
        students_with_behavior = (
            BehaviorRecord.objects.filter(
                incident_date__gte=current_session.start_date,
                severity__in=["high", "critical"],
            )
            .values("student")
            .annotate(incident_count=models.Count("id"))
            .filter(incident_count__gte=3)
            .values_list("student", flat=True)
        )

        if students_with_behavior:
            alerts.append(
                {
                    "type": "warning",
                    "message": f"{len(students_with_behavior)} students have multiple serious behavior incidents",
                    "action_url": reverse_lazy("academics:counselor_behavior_records"),
                }
            )

        # Students with declining academic performance
        # This would require more complex logic to detect trends

        # Students with frequent absences
        from apps.attendance.models import DailyAttendance

        students_with_absences = (
            DailyAttendance.objects.filter(
                attendance_session__academic_session=current_session,
                attendance_status="absent",
                date__gte=current_session.start_date,
            )
            .values("student")
            .annotate(absence_count=models.Count("id"))
            .filter(absence_count__gte=10)
            .values_list("student", flat=True)
        )

        if students_with_absences:
            alerts.append(
                {
                    "type": "info",
                    "message": f"{len(students_with_absences)} students have frequent absences",
                    "action_url": reverse_lazy("academics:counselor_students"),
                }
            )

        return alerts


class CounselingSessionsView(CounselorRequiredMixin, ListView):
    """Counselor view for managing counseling sessions."""

    model = CounselingSession
    template_name = "academics/counselor/sessions.html"
    context_object_name = "sessions"
    paginate_by = 15

    def get_queryset(self):
        counselor = self.request.user.teacher_profile
        return (
            CounselingSession.objects.filter(counselor=counselor)
            .select_related("student", "academic_session")
            .order_by("-scheduled_date")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counselor = self.request.user.teacher_profile

        # Session statistics
        total_sessions = context["sessions"].count()
        completed_sessions = (
            context["sessions"].filter(session_status="completed").count()
        )
        upcoming_sessions = (
            context["sessions"]
            .filter(
                scheduled_date__gte=timezone.now().date(), session_status="scheduled"
            )
            .count()
        )

        context.update(
            {
                "counselor": counselor,
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "upcoming_sessions": upcoming_sessions,
                "completion_rate": (
                    (completed_sessions / total_sessions * 100)
                    if total_sessions > 0
                    else 0
                ),
            }
        )

        return context


class CounselingReferralsView(CounselorRequiredMixin, ListView):
    """Counselor view for managing student referrals."""

    model = CounselingReferral
    template_name = "academics/counselor/referrals.html"
    context_object_name = "referrals"
    paginate_by = 15

    def get_queryset(self):
        counselor = self.request.user.teacher_profile
        return (
            CounselingReferral.objects.filter(counselor=counselor)
            .select_related("student", "referred_by")
            .order_by("-referral_date")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counselor = self.request.user.teacher_profile

        # Referral statistics
        total_referrals = context["referrals"].count()
        resolved_referrals = (
            context["referrals"].filter(referral_status="resolved").count()
        )
        pending_referrals = (
            context["referrals"].filter(referral_status="pending").count()
        )

        context.update(
            {
                "counselor": counselor,
                "total_referrals": total_referrals,
                "resolved_referrals": resolved_referrals,
                "pending_referrals": pending_referrals,
                "resolution_rate": (
                    (resolved_referrals / total_referrals * 100)
                    if total_referrals > 0
                    else 0
                ),
            }
        )

        return context


class CareerGuidanceView(CounselorRequiredMixin, ListView):
    """Counselor view for career guidance sessions."""

    model = CareerGuidance
    template_name = "academics/counselor/career_guidance.html"
    context_object_name = "guidance_sessions"
    paginate_by = 15

    def get_queryset(self):
        counselor = self.request.user.teacher_profile
        return (
            CareerGuidance.objects.filter(counselor=counselor)
            .select_related("student")
            .order_by("-session_date")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counselor = self.request.user.teacher_profile

        # Guidance statistics
        total_sessions = context["guidance_sessions"].count()
        completed_sessions = (
            context["guidance_sessions"].filter(session_status="completed").count()
        )

        context.update(
            {
                "counselor": counselor,
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "completion_rate": (
                    (completed_sessions / total_sessions * 100)
                    if total_sessions > 0
                    else 0
                ),
            }
        )

        return context


class CounselorStudentsView(CounselorRequiredMixin, ListView):
    """Counselor view for students under counseling."""

    model = Student
    template_name = "academics/counselor/students.html"
    context_object_name = "students"
    paginate_by = 20

    def get_queryset(self):
        counselor = self.request.user.teacher_profile

        # Get students who have had counseling sessions or referrals with this counselor
        students_with_sessions = CounselingSession.objects.filter(
            counselor=counselor
        ).values_list("student", flat=True)

        students_with_referrals = CounselingReferral.objects.filter(
            counselor=counselor
        ).values_list("student", flat=True)

        student_ids = set(list(students_with_sessions) + list(students_with_referrals))

        return (
            Student.objects.filter(id__in=student_ids, status="active")
            .select_related("user")
            .distinct()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counselor = self.request.user.teacher_profile

        # Add counseling information for each student
        for student in context["students"]:
            student.recent_session = (
                CounselingSession.objects.filter(counselor=counselor, student=student)
                .order_by("-scheduled_date")
                .first()
            )

            student.active_referral = CounselingReferral.objects.filter(
                counselor=counselor,
                student=student,
                referral_status__in=["pending", "in_progress"],
            ).first()

        context["counselor"] = counselor
        return context


class BehaviorRecordsView(CounselorRequiredMixin, ListView):
    """Counselor view for student behavior records."""

    model = BehaviorRecord
    template_name = "academics/counselor/behavior_records.html"
    context_object_name = "behavior_records"
    paginate_by = 15

    def get_queryset(self):
        counselor = self.request.user.teacher_profile
        current_session = AcademicSession.objects.filter(is_current=True).first()

        queryset = BehaviorRecord.objects.filter(status="active").select_related(
            "student", "reported_by"
        )

        if current_session:
            queryset = queryset.filter(incident_date__gte=current_session.start_date)

        return queryset.order_by("-incident_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counselor = self.request.user.teacher_profile

        # Behavior statistics
        total_incidents = context["behavior_records"].count()
        resolved_incidents = (
            context["behavior_records"].filter(is_resolved=True).count()
        )

        # Severity breakdown
        severity_stats = (
            context["behavior_records"]
            .values("severity")
            .annotate(count=models.Count("id"))
            .order_by("severity")
        )

        context.update(
            {
                "counselor": counselor,
                "total_incidents": total_incidents,
                "resolved_incidents": resolved_incidents,
                "resolution_rate": (
                    (resolved_incidents / total_incidents * 100)
                    if total_incidents > 0
                    else 0
                ),
                "severity_stats": list(severity_stats),
            }
        )

        return context


class AcademicWarningsView(CounselorRequiredMixin, ListView):
    """Counselor view for academic warnings."""

    model = AcademicWarning
    template_name = "academics/counselor/academic_warnings.html"
    context_object_name = "warnings"
    paginate_by = 15

    def get_queryset(self):
        counselor = self.request.user.teacher_profile
        current_session = AcademicSession.objects.filter(is_current=True).first()

        queryset = AcademicWarning.objects.filter(status="active").select_related(
            "student", "issued_by"
        )

        if current_session:
            queryset = queryset.filter(issued_date__gte=current_session.start_date)

        return queryset.order_by("-issued_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        counselor = self.request.user.teacher_profile

        # Warning statistics
        total_warnings = context["warnings"].count()
        resolved_warnings = context["warnings"].filter(is_resolved=True).count()

        # Warning level breakdown
        level_stats = (
            context["warnings"]
            .values("warning_level")
            .annotate(count=models.Count("id"))
            .order_by("warning_level")
        )

        context.update(
            {
                "counselor": counselor,
                "total_warnings": total_warnings,
                "resolved_warnings": resolved_warnings,
                "resolution_rate": (
                    (resolved_warnings / total_warnings * 100)
                    if total_warnings > 0
                    else 0
                ),
                "level_stats": list(level_stats),
            }
        )

        return context


# =============================================================================
# ACADEMIC PLANNING COMMITTEE VIEWS
# =============================================================================


class CommitteeRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a committee member."""

    def test_func(self):
        user = self.request.user
        # Check if user is a committee member
        return AcademicPlanningCommittee.objects.filter(
            models.Q(chairperson=user.teacher_profile)
            | models.Q(members=user.teacher_profile),
            is_active=True,
        ).exists()


class CommitteeDashboardView(CommitteeRequiredMixin, View):
    """Academic Planning Committee dashboard."""

    def get(self, request):
        user = request.user
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Get committees where user is a member
        committees = AcademicPlanningCommittee.objects.filter(
            models.Q(chairperson=user.teacher_profile)
            | models.Q(members=user.teacher_profile),
            is_active=True,
        ).select_related("department")

        # Upcoming meetings
        upcoming_meetings = (
            CommitteeMeeting.objects.filter(
                committee__in=committees,
                meeting_date__gte=timezone.now().date(),
                meeting_status="scheduled",
            )
            .select_related("committee")
            .order_by("meeting_date")[:5]
        )

        # Recent meetings
        recent_meetings = (
            CommitteeMeeting.objects.filter(
                committee__in=committees, meeting_date__lt=timezone.now().date()
            )
            .select_related("committee")
            .order_by("-meeting_date")[:5]
        )

        # Committee statistics
        committee_stats = self._get_committee_stats(committees, current_session)

        context = {
            "committees": committees,
            "upcoming_meetings": upcoming_meetings,
            "recent_meetings": recent_meetings,
            "committee_stats": committee_stats,
            "current_session": current_session,
        }

        return render(request, "academics/committee/dashboard.html", context)

    def _get_committee_stats(self, committees, current_session):
        """Get committee statistics."""
        if not current_session:
            return {}

        total_meetings = CommitteeMeeting.objects.filter(
            committee__in=committees, academic_session=current_session
        ).count()

        completed_meetings = CommitteeMeeting.objects.filter(
            committee__in=committees,
            academic_session=current_session,
            meeting_status="completed",
        ).count()

        return {
            "total_committees": committees.count(),
            "total_meetings": total_meetings,
            "completed_meetings": completed_meetings,
            "completion_rate": (
                (completed_meetings / total_meetings * 100) if total_meetings > 0 else 0
            ),
        }


class CommitteeMeetingsView(CommitteeRequiredMixin, ListView):
    """Committee meetings view."""

    model = CommitteeMeeting
    template_name = "academics/committee/meetings.html"
    context_object_name = "meetings"
    paginate_by = 15

    def get_queryset(self):
        user = self.request.user
        committees = AcademicPlanningCommittee.objects.filter(
            models.Q(chairperson=user.teacher_profile)
            | models.Q(members=user.teacher_profile),
            is_active=True,
        )

        return (
            CommitteeMeeting.objects.filter(committee__in=committees)
            .select_related("committee")
            .order_by("-meeting_date")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        committees = AcademicPlanningCommittee.objects.filter(
            models.Q(chairperson=user.teacher_profile)
            | models.Q(members=user.teacher_profile),
            is_active=True,
        )

        context["committees"] = committees
        return context


# =============================================================================
# GRADE LEVEL VIEWS FOR SCHOOL ADMINS
# =============================================================================


class GradeLevelListView(StaffRequiredMixin, ListView):
    """School admin view for managing grade levels."""

    model = GradeLevel
    template_name = "academics/grade_levels/grade_level_list.html"
    context_object_name = "grade_levels"
    paginate_by = 15

    def get_queryset(self):
        queryset = GradeLevel.objects.filter(status="active")

        # Filter by education stage if provided
        stage = self.request.GET.get("stage")
        if stage:
            queryset = queryset.filter(education_stage=stage)

        return queryset.order_by("education_stage", "code")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["education_stages"] = GradeLevel.EducationStage.choices
        return context


class GradeLevelCreateView(StaffRequiredMixin, CreateView):
    """Create a new grade level."""

    model = GradeLevel
    form_class = GradeLevelForm
    template_name = "academics/grade_levels/grade_level_form.html"
    success_url = reverse_lazy("academics:grade_level_list")

    def form_valid(self, form):
        messages.success(self.request, _("Grade level created successfully."))
        return super().form_valid(form)


class GradeLevelUpdateView(StaffRequiredMixin, UpdateView):
    """Update a grade level."""

    model = GradeLevel
    form_class = GradeLevelForm
    template_name = "academics/grade_levels/grade_level_form.html"
    success_url = reverse_lazy("academics:grade_level_list")

    def form_valid(self, form):
        messages.success(self.request, _("Grade level updated successfully."))
        return super().form_valid(form)


class GradeLevelDetailView(StaffRequiredMixin, DetailView):
    """Grade level detail view."""

    model = GradeLevel
    template_name = "academics/grade_levels/grade_level_detail.html"
    context_object_name = "grade_level"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get classes using this grade level
        context["classes"] = self.object.classes.filter(status="active").order_by(
            "name"
        )

        # Get enrollment count for this grade level
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            context["enrollment_count"] = Enrollment.objects.filter(
                class_enrolled__grade_level=self.object,
                academic_session=current_session,
                enrollment_status="active",
            ).count()
        else:
            context["enrollment_count"] = 0

        return context


# =============================================================================
# SUBJECT ASSIGNMENT VIEWS
# =============================================================================


class SubjectAssignmentListView(StaffRequiredMixin, ListView):
    """List all subject assignments."""

    model = SubjectAssignment
    template_name = "academics/subject_assignments/subject_assignment_list.html"
    context_object_name = "subject_assignments"
    paginate_by = 20

    def get_queryset(self):
        queryset = SubjectAssignment.objects.select_related(
            "teacher__user", "subject", "class_assigned", "academic_session"
        ).order_by("academic_session", "teacher__user__first_name", "subject__name")

        # Filter by teacher if provided
        teacher_id = self.request.GET.get("teacher")
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)

        # Filter by academic session if provided
        session_id = self.request.GET.get("session")
        if session_id:
            queryset = queryset.filter(academic_session_id=session_id)
        else:
            # Default to current session
            current_session = AcademicSession.objects.filter(is_current=True).first()
            if current_session:
                queryset = queryset.filter(academic_session=current_session)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["teachers"] = Teacher.objects.filter(status="active").select_related(
            "user"
        )
        context["sessions"] = AcademicSession.objects.all().order_by("-start_date")

        # Get filter values for form pre-population
        context["current_teacher"] = self.request.GET.get("teacher", "")
        context["current_session"] = self.request.GET.get("session", "")

        return context


class SubjectAssignmentCreateView(StaffRequiredMixin, CreateView):
    """Create a new subject assignment."""

    model = SubjectAssignment
    form_class = SubjectAssignmentForm
    template_name = "academics/subject_assignments/subject_assignment_form.html"
    success_url = reverse_lazy("academics:subject_assignment_list")

    def get_initial(self):
        """Pre-populate form with teacher from query parameter."""
        initial = super().get_initial()
        teacher_id = self.request.GET.get("teacher")
        if teacher_id:
            try:
                teacher = Teacher.objects.get(id=teacher_id)
                initial["teacher"] = teacher
            except Teacher.DoesNotExist:
                pass

        # Set current session as default
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            initial["academic_session"] = current_session

        return initial

    def form_valid(self, form):
        messages.success(self.request, _("Subject assignment created successfully."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = _("Create Subject Assignment")
        context["submit_text"] = _("Create Assignment")
        return context


class SubjectAssignmentUpdateView(StaffRequiredMixin, UpdateView):
    """Update a subject assignment."""

    model = SubjectAssignment
    form_class = SubjectAssignmentForm
    template_name = "academics/subject_assignments/subject_assignment_form.html"
    success_url = reverse_lazy("academics:subject_assignment_list")

    def form_valid(self, form):
        messages.success(self.request, _("Subject assignment updated successfully."))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = _("Update Subject Assignment")
        context["submit_text"] = _("Update Assignment")
        return context


class SubjectAssignmentDeleteView(StaffRequiredMixin, DeleteView):
    """Delete a subject assignment."""

    model = SubjectAssignment
    template_name = (
        "academics/subject_assignments/subject_assignment_confirm_delete.html"
    )
    success_url = reverse_lazy("academics:subject_assignment_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Subject assignment deleted successfully."))
        return super().delete(request, *args, **kwargs)


# =============================================================================
# CONTACT TEACHER VIEWS
# =============================================================================


class ContactTeacherView(AcademicsAccessMixin, View):
    """View for contacting teachers via email."""

    def post(self, request, pk):
        teacher = get_object_or_404(Teacher, pk=pk)

        # Check if user has permission to contact this teacher
        # Allow all authenticated users to contact teachers

        form = ContactTeacherForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data["subject"]
            message = form.cleaned_data["message"]

            # Send email using EmailService
            success, email_message, sent_email = EmailService.send_email(
                recipient_email=teacher.user.email,
                subject=f"School Contact: {subject}",
                html_content=f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2>New Message from {request.user.get_full_name()}</h2>
                    <p><strong>From:</strong> {request.user.get_full_name()} ({request.user.email})</p>
                    <p><strong>To:</strong> {teacher.user.get_full_name()}</p>
                    <p><strong>Subject:</strong> {subject}</p>
                    <hr>
                    <div style="background: #f9f9f9; padding: 15px; border-radius: 5px;">
                        <h3>Message:</h3>
                        <p style="white-space: pre-wrap;">{message}</p>
                    </div>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        This message was sent through the School Management System.
                    </p>
                </div>
                """,
                text_content=f"""
New Message from {request.user.get_full_name()}

From: {request.user.get_full_name()} ({request.user.email})
To: {teacher.user.get_full_name()}
Subject: {subject}

Message:
{message}

---
This message was sent through the School Management System.
                """,
                recipient_user=teacher.user,
                sender_user=request.user,
            )

            if success:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {"success": True, "message": "Message sent successfully!"}
                    )
                messages.success(request, "Your message has been sent successfully!")
                return redirect("academics:teacher_detail", pk=pk)
            else:
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return JsonResponse(
                        {
                            "success": False,
                            "message": f"Failed to send message: {email_message}",
                        },
                        status=500,
                    )
            messages.error(request, f"Failed to send message: {email_message}")
            return redirect("academics:teacher_detail", pk=pk)
        else:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Please correct the errors in the form.",
                        "errors": form.errors,
                    },
                    status=400,
                )
            messages.error(request, "Please correct the errors in the form.")
            return redirect("academics:teacher_detail", pk=pk)
