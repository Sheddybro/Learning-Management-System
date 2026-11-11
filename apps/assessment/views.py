# apps/assessment/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Max, Min, Count, Sum
from django.utils import timezone
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from .models import (
    ExamType,
    GradingSystem,
    Grade,
    Exam,
    ExamAttendance,
    Mark,
    Assignment,
    Result,
    ResultSubject,
    ReportCard,
    AssessmentRule,
    QuestionBank,
    Question,
    QuestionOption,
    ExamQuestion,
    StudentAnswer,
    QuizAttempt,
    QuizProgress,
    CourseGrade,
    AIGenerationLog,
    TakenCourse,
)
from .forms import QuestionBankForm, QuestionForm, ExamCompositionForm, ExamForm
from .ai_generator import generate_questions_with_ai
from apps.academics.models import Student, Teacher, Class, Subject, AcademicSession
from apps.users.models import User
from apps.core.mixins import (
    StudentRequiredMixin,
    TeacherRequiredMixin,
    AdminOrTeacherRequiredMixin,
)


# =============================================================================
# PERMISSION DECORATORS AND MIXINS
# =============================================================================


def is_teacher(user):
    """Check if user is a teacher."""
    return hasattr(user, "teacher_profile")


def is_student(user):
    """Check if user is a student."""
    return hasattr(user, "student_profile")


def is_admin_or_teacher(user):
    """Check if user is admin or teacher."""
    return user.is_staff or hasattr(user, "teacher_profile")


# =============================================================================
# EXAM VIEWS
# =============================================================================


class ExamListView(LoginRequiredMixin, ListView):
    """List all exams with filtering options."""

    model = Exam
    template_name = "assessment/exams/exam_list.html"
    context_object_name = "exams"
    paginate_by = 20

    def get_queryset(self):
        queryset = Exam.objects.select_related(
            "exam_type", "academic_class", "subject"
        ).filter(is_published=True)

        # Filter by class if provided
        class_id = self.request.GET.get("class_id")
        if class_id:
            queryset = queryset.filter(academic_class_id=class_id)

        # Filter by subject if provided
        subject_id = self.request.GET.get("subject_id")
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        # Filter by exam type if provided
        exam_type_id = self.request.GET.get("exam_type_id")
        if exam_type_id:
            queryset = queryset.filter(exam_type_id=exam_type_id)

        # For students, show only their class exams
        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile
            current_class = student.current_class
            if current_class:
                queryset = queryset.filter(academic_class=current_class)

        # For teachers, show only exams they're involved in
        elif hasattr(self.request.user, "teacher_profile"):
            teacher = self.request.user.teacher_profile
            # Get classes taught by this teacher
            taught_classes = Class.objects.filter(
                subject_assignments__teacher=teacher,
                subject_assignments__academic_session__is_current=True,
            )
            queryset = queryset.filter(academic_class__in=taught_classes)

        return queryset.order_by("-exam_date", "-start_time")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["exam_types"] = ExamType.objects.filter(status="active")
        context["classes"] = Class.objects.filter(academic_session__is_current=True)
        context["subjects"] = Subject.objects.filter(is_active=True)
        return context


class ExamDetailView(LoginRequiredMixin, DetailView):
    """Display exam details."""

    model = Exam
    template_name = "assessment/exams/exam_detail.html"
    context_object_name = "exam"

    def get_queryset(self):
        queryset = Exam.objects.select_related("exam_type", "academic_class", "subject")

        # Filter based on user role
        user = self.request.user
        if hasattr(user, "student_profile"):
            # Students can only see exams for their class
            queryset = queryset.filter(
                academic_class=user.student_profile.current_class
            )
        elif hasattr(user, "teacher_profile"):
            # Teachers can only see exams for classes they teach
            taught_classes = Class.objects.filter(
                subject_assignments__teacher=user.teacher_profile,
                subject_assignments__academic_session__is_current=True,
            ).distinct()
            queryset = queryset.filter(academic_class__in=taught_classes)
        else:
            # Admins can see all exams
            pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add attendance status for students
        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile
            attendance = ExamAttendance.objects.filter(
                exam=self.object, student=student
            ).first()
            context["attendance"] = attendance

        # Add marks if available and published (only for authorized users)
        if self.object.is_published:
            marks_queryset = Mark.objects.filter(exam=self.object).select_related(
                "student__user"
            )

            # Filter marks based on user role
            user = self.request.user
            if hasattr(user, "student_profile"):
                # Students can only see their own marks
                marks_queryset = marks_queryset.filter(student=user.student_profile)
            elif hasattr(user, "teacher_profile"):
                # Teachers can see marks for their class
                marks_queryset = marks_queryset.filter(
                    exam__academic_class__in=Class.objects.filter(
                        subject_assignments__teacher=user.teacher_profile,
                        subject_assignments__academic_session__is_current=True,
                    ).distinct()
                )

            context["marks"] = marks_queryset

        return context


class ExamCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    """Create a new exam."""

    model = Exam
    form_class = ExamForm
    template_name = "assessment/exams/exam_form.html"

    def get_success_url(self):
        return reverse_lazy("assessment:exam_detail", kwargs={"pk": self.object.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        """Set initial values for the form."""
        initial = super().get_initial()

        # Set default exam type if available
        default_exam_type = ExamType.objects.filter(
            status="active", is_final=False
        ).first()

        if default_exam_type:
            initial["exam_type"] = default_exam_type

        # Set default total marks
        initial["total_marks"] = 100
        initial["passing_marks"] = 40

        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add exam types for template if needed
        context["exam_types"] = ExamType.objects.filter(status="active")

        # Add teacher's classes and subjects
        teacher = self.request.user.teacher_profile
        context["teacher_classes"] = Class.objects.filter(
            subject_assignments__teacher=teacher,
            subject_assignments__academic_session__is_current=True,
        ).distinct()

        return context

    def form_valid(self, form):
        # Set the exam as unpublished by default
        form.instance.is_published = False

        # Add success message
        messages.success(
            self.request, "Exam created successfully! You can now add questions to it."
        )

        response = super().form_valid(form)

        # Redirect to exam composition after creation
        return redirect("assessment:compose_exam", exam_id=self.object.pk)

    def form_invalid(self, form):
        """Handle invalid form submission."""
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class ExamUpdateView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    """Update an existing exam."""

    model = Exam
    form_class = ExamForm
    template_name = "assessment/exams/exam_form.html"
    success_url = reverse_lazy("assessment:exam_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        if form.instance.is_published and not form.instance.published_at:
            form.instance.published_at = timezone.now()
        messages.success(self.request, "Exam updated successfully!")
        return super().form_valid(form)


@login_required
@user_passes_test(is_teacher)
def exam_attendance(request, exam_id):
    """Manage exam attendance for students."""
    exam = get_object_or_404(Exam, id=exam_id)

    if request.method == "POST":
        # Check if this is a bulk save operation (JSON data)
        attendance_data_json = request.POST.get("attendance_data")
        if attendance_data_json:
            # Handle bulk save from JavaScript
            try:
                attendance_data = json.loads(attendance_data_json)
                is_final = request.POST.get("is_final") == "true"

                created_count = 0
                updated_count = 0

                for student_id, data in attendance_data.items():
                    student = get_object_or_404(Student, id=int(student_id))
                    attendance, created = ExamAttendance.objects.update_or_create(
                        exam=exam,
                        student=student,
                        defaults={
                            "is_present": data.get("is_present", False),
                            "late_minutes": data.get("late_minutes", 0),
                            "remarks": data.get("remarks", ""),
                        },
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                # Additional processing if finalized
                if is_final and not exam.is_locked_for_editing:
                    exam.save()  # Could add locking logic here

                return JsonResponse(
                    {
                        "success": True,
                        "created": created_count,
                        "updated": updated_count,
                        "message": f'Attendance {"finalized" if is_final else "saved"} successfully!',
                    }
                )

            except (json.JSONDecodeError, ValueError) as e:
                return JsonResponse(
                    {"success": False, "error": "Invalid attendance data format"},
                    status=400,
                )

        # Legacy: Handle individual student updates (for backward compatibility)
        student_id = request.POST.get("student_id")
        if student_id:
            is_present = request.POST.get("is_present") == "true"
            late_minutes = int(request.POST.get("late_minutes", 0))
            remarks = request.POST.get("remarks", "")

            student = get_object_or_404(Student, id=student_id)

            attendance, created = ExamAttendance.objects.update_or_create(
                exam=exam,
                student=student,
                defaults={
                    "is_present": is_present,
                    "late_minutes": late_minutes,
                    "remarks": remarks,
                },
            )

            return JsonResponse({"success": True, "created": created})
        else:
            return JsonResponse(
                {"success": False, "error": "No valid data provided"}, status=400
            )

    # GET request - show attendance page
    students = exam.academic_class.enrollments.filter(
        enrollment_status="active"
    ).select_related("student__user")

    attendance_records = {
        record.student_id: record for record in ExamAttendance.objects.filter(exam=exam)
    }

    context = {
        "exam": exam,
        "students": students,
        "attendance_records": attendance_records,
    }
    return render(request, "assessment/exams/exam_attendance.html", context)


# =============================================================================
# MARK MANAGEMENT VIEWS
# =============================================================================


@login_required
@user_passes_test(is_teacher)
def enter_marks(request, exam_id):
    """Enter marks for an exam."""
    exam = get_object_or_404(Exam, id=exam_id)

    if request.method == "POST":
        marks_data = json.loads(request.POST.get("marks_data", "{}"))

        for student_id, mark_data in marks_data.items():
            student = get_object_or_404(Student, id=student_id)
            marks_obtained = mark_data.get("marks_obtained")
            is_absent = mark_data.get("is_absent", False)
            grace_marks = mark_data.get("grace_marks", 0)
            remarks = mark_data.get("remarks", "")

            mark, created = Mark.objects.update_or_create(
                exam=exam,
                student=student,
                defaults={
                    "marks_obtained": marks_obtained if not is_absent else 0,
                    "is_absent": is_absent,
                    "grace_marks": grace_marks,
                    "remarks": remarks,
                    "entered_by": request.user.teacher_profile,
                },
            )

        messages.success(request, "Marks entered successfully!")
        return JsonResponse({"success": True})

    # GET request - show marks entry page
    students = exam.academic_class.enrollments.filter(
        enrollment_status="active"
    ).select_related("student__user")

    existing_marks = {mark.student_id: mark for mark in Mark.objects.filter(exam=exam)}

    context = {"exam": exam, "students": students, "existing_marks": existing_marks}
    return render(request, "assessment/exams/enter_marks.html", context)


@login_required
@user_passes_test(is_teacher)
def grading_overview(request):
    """Show grading overview for teachers - list of exams they can enter marks for."""
    teacher = request.user.teacher_profile

    # Get classes taught by this teacher
    taught_classes = Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session__is_current=True,
    ).distinct()

    # Get exams for these classes
    exams = (
        Exam.objects.filter(academic_class__in=taught_classes)
        .select_related("exam_type", "academic_class", "subject")
        .order_by("-exam_date", "-start_time")
    )

    # Add mark entry status for each exam
    exam_data = []
    completed_exams = 0
    in_progress_exams = 0
    total_marks_entered = 0

    for exam in exams:
        marks_entered = Mark.objects.filter(exam=exam).count()
        total_students = exam.academic_class.enrollments.filter(
            enrollment_status="active"
        ).count()
        completion_percentage = (
            (marks_entered / total_students * 100) if total_students > 0 else 0
        )

        exam_data.append(
            {
                "exam": exam,
                "marks_entered": marks_entered,
                "total_students": total_students,
                "completion_percentage": completion_percentage,
            }
        )

        # Aggregate statistics for summary cards
        total_marks_entered += marks_entered
        if completion_percentage == 100:
            completed_exams += 1
        elif completion_percentage < 100:
            in_progress_exams += 1

    context = {
        "exam_data": exam_data,
        "taught_classes": taught_classes,
        "completed_exams": completed_exams,
        "in_progress_exams": in_progress_exams,
        "total_marks_entered": total_marks_entered,
    }

    return render(request, "assessment/grading_overview.html", context)


class StudentMarksView(LoginRequiredMixin, StudentRequiredMixin, ListView):
    """View for students to see their marks."""

    template_name = "assessment/results/student_marks.html"
    context_object_name = "marks"
    paginate_by = 20

    def get_queryset(self):
        student = self.request.user.student_profile
        return (
            Mark.objects.filter(student=student)
            .select_related("exam", "exam__subject", "exam__academic_class")
            .order_by("-exam__exam_date")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.request.user.student_profile

        # Add summary statistics
        marks = self.get_queryset()
        if marks:
            context["total_exams"] = marks.count()
            context["average_percentage"] = marks.aggregate(avg=Avg("percentage"))[
                "avg"
            ]
            context["highest_percentage"] = marks.aggregate(max=Max("percentage"))[
                "max"
            ]

        return context


# =============================================================================
# ASSIGNMENT VIEWS
# =============================================================================


class AssignmentListView(LoginRequiredMixin, ListView):
    """List assignments with filtering."""

    model = Assignment
    template_name = "assessment/assignments/assignment_list.html"
    context_object_name = "assignments"
    paginate_by = 15

    def get_queryset(self):
        # Get assignment templates (not student submissions)
        queryset = Assignment.objects.filter(
            student__isnull=True, is_published=True
        ).select_related("subject", "teacher__user", "academic_class")

        # Apply filters
        subject_id = self.request.GET.get("subject_id")
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)

        assignment_type = self.request.GET.get("assignment_type")
        if assignment_type:
            queryset = queryset.filter(assignment_type=assignment_type)

        status = self.request.GET.get("status")
        if status == "active":
            queryset = queryset.filter(due_date__gte=timezone.now())
        elif status == "overdue":
            queryset = queryset.filter(due_date__lt=timezone.now())

        # For students, show only assignments for their class
        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile
            current_class = student.current_class
            if current_class:
                queryset = queryset.filter(
                    Q(academic_class=current_class) | Q(class_assigned=current_class)
                )

        # For teachers, show only their assignments
        elif hasattr(self.request.user, "teacher_profile"):
            teacher = self.request.user.teacher_profile
            queryset = queryset.filter(teacher=teacher)

        return queryset.order_by("-due_date", "display_order")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["subjects"] = Subject.objects.filter(is_active=True)
        context["assignment_types"] = Assignment.AssignmentType.choices

        # Add submission status for students
        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile
            submissions = {
                sub.title: sub
                for sub in Assignment.objects.filter(
                    student=student, title__in=[a.title for a in context["assignments"]]
                )
            }
            context["submissions"] = submissions

        return context


class AssignmentDetailView(LoginRequiredMixin, DetailView):
    """Display assignment details."""

    model = Assignment
    template_name = "assessment/assignments/assignment_detail.html"
    context_object_name = "assignment"

    def get_queryset(self):
        queryset = Assignment.objects.select_related(
            "subject", "teacher__user", "academic_class"
        )

        # Filter based on user role
        user = self.request.user
        if hasattr(user, "student_profile"):
            # Students can only see assignments for their class or assigned to them
            queryset = queryset.filter(
                Q(academic_class=user.student_profile.current_class)
                | Q(class_assigned=user.student_profile.current_class)
                | Q(student=user.student_profile)
            )
        elif hasattr(user, "teacher_profile"):
            # Teachers can only see their own assignments
            queryset = queryset.filter(teacher=user.teacher_profile)
        else:
            # Admins can see all assignments
            pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # For students, show their submission if exists
        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile
            submission = (
                Assignment.objects.filter(
                    student=student,
                    title=self.object.title,
                    subject=self.object.subject,
                )
                .order_by("-submission_attempt")
                .first()
            )
            context["submission"] = submission

        # For teachers, show submission statistics
        elif hasattr(self.request.user, "teacher_profile"):
            submissions = Assignment.objects.filter(
                student__isnull=False,
                title=self.object.title,
                subject=self.object.subject,
            ).select_related("student__user")
            context["submissions"] = submissions
            context["submission_count"] = submissions.count()
            context["graded_count"] = submissions.filter(
                submission_status=Assignment.SubmissionStatus.GRADED
            ).count()

        return context


class AssignmentCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    """Create a new assignment."""

    model = Assignment
    template_name = "assessment/assignments/assignment_form.html"
    fields = [
        "title",
        "assignment_type",
        "subject",
        "academic_class",
        "class_assigned",
        "description",
        "instructions",
        "total_marks",
        "passing_marks",
        "weightage",
        "due_date",
        "allow_late_submissions",
        "late_submission_penalty",
        "max_submission_attempts",
        "max_file_size",
        "attachment",
        "tags",
    ]
    success_url = reverse_lazy("assessment:assignment_list")

    def form_valid(self, form):
        form.instance.teacher = self.request.user.teacher_profile
        form.instance.academic_session = self.get_current_academic_session()
        form.instance.is_published = True
        messages.success(self.request, "Assignment created successfully!")
        return super().form_valid(form)

    def get_current_academic_session(self):
        """Get current academic session."""
        from apps.academics.models import AcademicSession

        return AcademicSession.objects.filter(is_current=True).first()

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Limit to classes taught by the teacher
        teacher = self.request.user.teacher_profile
        form.fields["academic_class"].queryset = Class.objects.filter(
            subject_assignments__teacher=teacher,
            subject_assignments__academic_session__is_current=True,
        ).distinct()
        form.fields["class_assigned"].queryset = form.fields["academic_class"].queryset
        return form


class AssignmentSubmissionView(LoginRequiredMixin, StudentRequiredMixin, CreateView):
    """Submit an assignment."""

    model = Assignment
    template_name = "assessment/assignments/assignment_submission.html"
    fields = ["submission_text", "submission_attachment"]

    def get_success_url(self):
        return reverse_lazy(
            "assessment:assignment_detail", kwargs={"pk": self.kwargs["assignment_id"]}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assignment"] = get_object_or_404(
            Assignment, id=self.kwargs["assignment_id"], student__isnull=True
        )

        # Check for existing submissions
        student = self.request.user.student_profile
        existing_submissions = Assignment.objects.filter(
            student=student,
            title=context["assignment"].title,
            subject=context["assignment"].subject,
        ).order_by("-submission_attempt")

        context["existing_submissions"] = existing_submissions
        context["latest_submission"] = existing_submissions.first()

        return context

    def form_valid(self, form):
        assignment_template = get_object_or_404(
            Assignment, id=self.kwargs["assignment_id"], student__isnull=True
        )
        student = self.request.user.student_profile

        # Check if student can submit
        latest_submission = (
            Assignment.objects.filter(
                student=student,
                title=assignment_template.title,
                subject=assignment_template.subject,
            )
            .order_by("-submission_attempt")
            .first()
        )

        if latest_submission:
            if not latest_submission.can_resubmit:
                messages.error(self.request, "Maximum submission attempts reached.")
                return self.form_invalid(form)
            submission_attempt = latest_submission.submission_attempt + 1
            original_submission = (
                latest_submission.original_submission or latest_submission
            )
        else:
            submission_attempt = 1
            original_submission = None

        # Create submission
        submission = form.save(commit=False)
        submission.title = assignment_template.title
        submission.assignment_type = assignment_template.assignment_type
        submission.description = assignment_template.description
        submission.instructions = assignment_template.instructions
        submission.subject = assignment_template.subject
        submission.academic_class = assignment_template.academic_class
        submission.class_assigned = assignment_template.class_assigned
        submission.teacher = assignment_template.teacher
        submission.academic_session = assignment_template.academic_session
        submission.total_marks = assignment_template.total_marks
        submission.passing_marks = assignment_template.passing_marks
        submission.weightage = assignment_template.weightage
        submission.grading_criteria = assignment_template.grading_criteria
        submission.publish_date = assignment_template.publish_date
        submission.due_date = assignment_template.due_date
        submission.allow_late_submissions = assignment_template.allow_late_submissions
        submission.late_submission_penalty = assignment_template.late_submission_penalty
        submission.max_submission_attempts = assignment_template.max_submission_attempts
        submission.max_file_size = assignment_template.max_file_size

        submission.student = student
        submission.submission_attempt = submission_attempt
        submission.original_submission = original_submission
        submission.submission_date = timezone.now()
        submission.submission_status = Assignment.SubmissionStatus.SUBMITTED

        submission.save()
        messages.success(self.request, "Assignment submitted successfully!")
        return redirect(self.get_success_url())


@login_required
@user_passes_test(is_teacher)
def grade_assignment(request, submission_id):
    """Grade a student's assignment submission."""
    submission = get_object_or_404(Assignment, id=submission_id, student__isnull=False)

    if request.method == "POST":
        marks_obtained = request.POST.get("marks_obtained")
        feedback = request.POST.get("feedback", "")
        rubric_scores = request.POST.get("rubric_scores")

        if marks_obtained:
            submission.marks_obtained = marks_obtained
            submission.feedback = feedback
            submission.graded_by = request.user.teacher_profile
            submission.graded_date = timezone.now()
            submission.graded_at = timezone.now()
            submission.submission_status = Assignment.SubmissionStatus.GRADED

            if rubric_scores:
                submission.rubric_scores = json.loads(rubric_scores)

            submission.save()
            messages.success(request, "Assignment graded successfully!")

        return redirect(
            "assessment:assignment_detail",
            pk=(
                submission.original_submission.id
                if submission.original_submission
                else submission.id
            ),
        )

    context = {
        "submission": submission,
        "assignment_template": (
            submission.original_submission
            if submission.original_submission
            else submission
        ),
    }
    return render(request, "assessment/assignments/grade_assignment.html", context)


# =============================================================================
# RESULT AND REPORT CARD VIEWS
# =============================================================================


class ResultListView(LoginRequiredMixin, ListView):
    """List results for students or teachers."""

    template_name = "assessment/results/result_list.html"
    context_object_name = "results"
    paginate_by = 20

    def get_queryset(self):
        if hasattr(self.request.user, "student_profile"):
            # Student view - show their results
            student = self.request.user.student_profile
            return Result.objects.filter(student=student).select_related(
                "academic_class", "exam_type", "grade"
            )

        elif hasattr(self.request.user, "teacher_profile"):
            # Teacher view - show results for their classes
            teacher = self.request.user.teacher_profile
            taught_classes = Class.objects.filter(
                subject_assignments__teacher=teacher,
                subject_assignments__academic_session__is_current=True,
            )
            return Result.objects.filter(
                academic_class__in=taught_classes
            ).select_related("student__user", "academic_class", "exam_type", "grade")

        return Result.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter options for teachers
        if hasattr(self.request.user, "teacher_profile"):
            context["classes"] = Class.objects.filter(academic_session__is_current=True)
            context["exam_types"] = ExamType.objects.filter(status="active")

        return context


class ResultDetailView(LoginRequiredMixin, DetailView):
    """Display detailed result information."""

    model = Result
    template_name = "assessment/results/result_detail.html"
    context_object_name = "result"

    def get_queryset(self):
        queryset = Result.objects.select_related(
            "student__user", "academic_class", "exam_type", "grade"
        ).prefetch_related("subject_marks__subject")

        # Filter based on user role
        user = self.request.user
        if hasattr(user, "student_profile"):
            # Students can only see their own results
            queryset = queryset.filter(student=user.student_profile)
        elif hasattr(user, "teacher_profile"):
            # Teachers can only see results for classes they teach
            taught_classes = Class.objects.filter(
                subject_assignments__teacher=user.teacher_profile,
                subject_assignments__academic_session__is_current=True,
            ).distinct()
            queryset = queryset.filter(academic_class__in=taught_classes)
        else:
            # Admins can see all results
            pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add subject marks
        context["subject_marks"] = self.object.subject_marks.select_related(
            "subject", "grade"
        )

        return context


class ReportCardListView(LoginRequiredMixin, ListView):
    """List report cards."""

    template_name = "assessment/results/reportcard_list.html"
    context_object_name = "report_cards"
    paginate_by = 15

    def get_queryset(self):
        if hasattr(self.request.user, "student_profile"):
            # Student view
            student = self.request.user.student_profile
            return ReportCard.objects.filter(
                student=student, is_approved=True
            ).select_related("academic_class", "exam_type", "result")

        elif hasattr(self.request.user, "teacher_profile"):
            # Teacher view
            teacher = self.request.user.teacher_profile
            taught_classes = Class.objects.filter(
                subject_assignments__teacher=teacher,
                subject_assignments__academic_session__is_current=True,
            )
            return ReportCard.objects.filter(
                academic_class__in=taught_classes
            ).select_related("student__user", "academic_class", "exam_type", "result")

        return ReportCard.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add statistics for teachers
        if hasattr(self.request.user, "teacher_profile"):
            report_cards = self.get_queryset()
            context["total_report_cards"] = report_cards.count()
            context["approved_count"] = report_cards.filter(is_approved=True).count()
            context["pending_approval"] = report_cards.filter(is_approved=False).count()

        return context


class ReportCardDetailView(LoginRequiredMixin, DetailView):
    """Display report card details."""

    model = ReportCard
    template_name = "assessment/results/reportcard_detail.html"
    context_object_name = "report_card"

    def get_queryset(self):
        return ReportCard.objects.select_related(
            "student__user", "academic_class", "exam_type", "result"
        ).prefetch_related("result__subject_marks__subject")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Check permissions
        user = self.request.user
        report_card = self.object

        if (
            hasattr(user, "student_profile")
            and report_card.student != user.student_profile
        ):
            messages.error(
                self.request, "You do not have permission to view this report card."
            )
            return redirect("assessment:reportcard_list")

        return context


@login_required
@user_passes_test(is_teacher)
def generate_report_card(request, result_id):
    """Generate a report card for a result."""
    result = get_object_or_404(Result, id=result_id)

    # Check if report card already exists
    report_card, created = ReportCard.objects.get_or_create(
        student=result.student,
        academic_class=result.academic_class,
        exam_type=result.exam_type,
        defaults={
            "result": result,
            "generated_by": request.user.teacher_profile,
            "is_approved": False,
        },
    )

    if created:
        messages.success(request, "Report card generated successfully!")
    else:
        messages.info(request, "Report card already exists.")

    return redirect("assessment:reportcard_detail", pk=report_card.id)


@login_required
@user_passes_test(is_teacher)
def approve_report_card(request, reportcard_id):
    """Approve a report card."""
    report_card = get_object_or_404(ReportCard, id=reportcard_id)

    if request.method == "POST":
        report_card.is_approved = True
        report_card.approved_by = request.user.teacher_profile
        report_card.approved_at = timezone.now()
        report_card.save()

        messages.success(request, "Report card approved successfully!")

    return redirect("assessment:reportcard_detail", pk=reportcard_id)


# =============================================================================
# DASHBOARD AND ANALYTICS VIEWS
# =============================================================================


@login_required
def assessment_dashboard(request):
    """Assessment dashboard for students and teachers."""
    context = {}

    if hasattr(request.user, "student_profile"):
        # Student dashboard
        student = request.user.student_profile
        context["recent_assignments"] = Assignment.objects.filter(
            Q(academic_class=student.current_class)
            | Q(class_assigned=student.current_class),
            student__isnull=True,
            is_published=True,
        ).select_related("subject")[:5]

        context["upcoming_exams"] = Exam.objects.filter(
            academic_class=student.current_class,
            exam_date__gte=timezone.now().date(),
            is_published=True,
        ).select_related("subject")[:5]

        context["recent_marks"] = Mark.objects.filter(student=student).select_related(
            "exam", "exam__subject"
        )[:10]

        # Performance summary
        marks = Mark.objects.filter(student=student)
        if marks.exists():
            context["average_percentage"] = marks.aggregate(avg=Avg("percentage"))[
                "avg"
            ]
            context["total_exams"] = marks.count()
            context["passed_exams"] = marks.filter(
                marks_obtained__gte=models.F("exam__passing_marks")
            ).count()

    elif hasattr(request.user, "teacher_profile"):
        # Teacher dashboard
        teacher = request.user.teacher_profile
        taught_classes = Class.objects.filter(
            subject_assignments__teacher=teacher,
            subject_assignments__academic_session__is_current=True,
        )

        context["recent_assignments"] = Assignment.objects.filter(
            teacher=teacher, student__isnull=True
        ).select_related("subject", "academic_class")[:5]

        context["upcoming_exams"] = Exam.objects.filter(
            academic_class__in=taught_classes, exam_date__gte=timezone.now().date()
        ).select_related("subject", "academic_class")[:5]

        context["pending_grading"] = Assignment.objects.filter(
            teacher=teacher,
            student__isnull=False,
            submission_status=Assignment.SubmissionStatus.SUBMITTED,
        ).count()

        # Class performance summary
        class_performance = []
        for class_obj in taught_classes:
            marks = Mark.objects.filter(
                exam__academic_class=class_obj,
                exam__subject__in=class_obj.subject_assignments.filter(
                    teacher=teacher
                ).values("subject"),
            )
            if marks.exists():
                avg_percentage = marks.aggregate(avg=Avg("percentage"))["avg"]
                class_performance.append(
                    {
                        "class": class_obj,
                        "average_percentage": avg_percentage,
                        "total_students": class_obj.current_student_count,
                    }
                )

        context["class_performance"] = class_performance

    return render(request, "assessment/dashboard/dashboard.html", context)


@login_required
@user_passes_test(is_admin_or_teacher)
def assessment_analytics(request):
    """Advanced analytics for assessment data."""
    context = {}

    # Get filter parameters
    class_id = request.GET.get("class_id")
    subject_id = request.GET.get("subject_id")
    exam_type_id = request.GET.get("exam_type_id")

    # Base querysets
    marks_qs = Mark.objects.select_related("exam", "student__user")
    assignments_qs = Assignment.objects.filter(student__isnull=False)

    # Apply filters
    if class_id:
        marks_qs = marks_qs.filter(exam__academic_class_id=class_id)
        assignments_qs = assignments_qs.filter(
            Q(academic_class_id=class_id) | Q(class_assigned_id=class_id)
        )

    if subject_id:
        marks_qs = marks_qs.filter(exam__subject_id=subject_id)
        assignments_qs = assignments_qs.filter(subject_id=subject_id)

    if exam_type_id:
        marks_qs = marks_qs.filter(exam__exam_type_id=exam_type_id)

    # Performance statistics
    if marks_qs.exists():
        context["marks_stats"] = marks_qs.aggregate(
            avg_percentage=Avg("percentage"),
            max_percentage=Max("percentage"),
            min_percentage=Min("percentage"),
            total_entries=Count("id"),
        )

        # Grade distribution
        context["grade_distribution"] = marks_qs.values(
            "exam__academic_class__name"
        ).annotate(
            avg_percentage=Avg("percentage"),
            student_count=Count("student", distinct=True),
        )

    # Assignment statistics
    if assignments_qs.exists():
        context["assignment_stats"] = assignments_qs.aggregate(
            total_submissions=Count("id"),
            avg_marks=Avg("marks_obtained"),
            submission_rate=Count("id")
            * 100
            / assignments_qs.values("student").distinct().count(),
        )

    # Filter options
    context["classes"] = Class.objects.filter(academic_session__is_current=True)
    context["subjects"] = Subject.objects.filter(is_active=True)
    context["exam_types"] = ExamType.objects.filter(status="active")

    return render(request, "assessment/dashboard/analytics.html", context)


# =============================================================================
# API VIEWS FOR AJAX CALLS
# =============================================================================


@login_required
@require_http_methods(["GET"])
def get_class_subjects(request, class_id):
    """Get subjects for a specific class (AJAX)."""
    subjects = (
        Subject.objects.filter(
            subject_assignments__class_assigned_id=class_id,
            subject_assignments__academic_session__is_current=True,
        )
        .distinct()
        .values("id", "name")
    )

    return JsonResponse(list(subjects), safe=False)


@login_required
@require_http_methods(["GET"])
def get_student_progress(request, student_id):
    """Get student progress data (AJAX)."""
    student = get_object_or_404(Student, id=student_id)

    # Check permissions
    if hasattr(request.user, "teacher_profile") or (
        hasattr(request.user, "student_profile")
        and request.user.student_profile == student
    ):

        marks = Mark.objects.filter(student=student).select_related("exam__subject")
        assignments = Assignment.objects.filter(student=student).select_related(
            "subject"
        )

        progress_data = {
            "subject_performance": [],
            "assignment_completion": {
                "total": assignments.count(),
                "graded": assignments.filter(submission_status="graded").count(),
                "pending": assignments.filter(submission_status="submitted").count(),
            },
        }

        # Subject-wise performance
        for subject in Subject.objects.filter(exams__marks__student=student).distinct():
            subject_marks = marks.filter(exam__subject=subject)
            if subject_marks.exists():
                avg_percentage = subject_marks.aggregate(avg=Avg("percentage"))["avg"]
                progress_data["subject_performance"].append(
                    {
                        "subject": subject.name,
                        "average_percentage": avg_percentage,
                        "exam_count": subject_marks.count(),
                    }
                )

        return JsonResponse(progress_data)

    return JsonResponse({"error": "Permission denied"}, status=403)


# =============================================================================
# QUESTION BANK AND QUESTION MANAGEMENT VIEWS
# =============================================================================


class QuestionBankListView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    """List question banks for teachers."""

    model = QuestionBank
    template_name = "assessment/questions/question_bank_list.html"
    context_object_name = "question_banks"
    paginate_by = 20

    def get_queryset(self):
        teacher = self.request.user.teacher_profile

        # Get classes taught by this teacher
        taught_classes = Class.objects.filter(
            subject_assignments__teacher=teacher,
            subject_assignments__academic_session__is_current=True,
        ).distinct()

        return (
            QuestionBank.objects.filter(academic_class__in=taught_classes)
            .select_related("subject", "academic_class")
            .order_by("-created_at")
        )


class QuestionBankCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    """Create a new question bank."""

    model = QuestionBank
    form_class = QuestionBankForm
    template_name = "assessment/questions/question_bank_form.html"
    success_url = reverse_lazy("assessment:question_bank_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["teacher"] = self.request.user.teacher_profile
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user.teacher_profile
        messages.success(self.request, "Question bank created successfully!")
        return super().form_valid(form)


class QuestionBankDeleteView(LoginRequiredMixin, TeacherRequiredMixin, DeleteView):
    """Delete a question bank."""

    model = QuestionBank
    template_name = "assessment/questions/question_bank_confirm_delete.html"
    success_url = reverse_lazy("assessment:quiz_bank_list")

    def get_queryset(self):
        """Only allow teachers to delete question banks they created or for classes they teach."""
        teacher = self.request.user.teacher_profile
        taught_classes = Class.objects.filter(
            subject_assignments__teacher=teacher,
            subject_assignments__academic_session__is_current=True,
        ).distinct()
        return QuestionBank.objects.filter(
            Q(created_by=teacher) | Q(academic_class__in=taught_classes)
        )

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Question bank deleted successfully!")
        return super().delete(request, *args, **kwargs)


class QuestionListView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    """List questions with filtering."""

    model = Question
    template_name = "assessment/questions/question_list.html"
    context_object_name = "questions"
    paginate_by = 20

    def get_queryset(self):
        queryset = Question.objects.select_related(
            "question_bank__subject", "question_bank__academic_class"
        )

        # Filter by question bank if provided
        question_bank_id = self.request.GET.get("question_bank_id")
        if question_bank_id:
            queryset = queryset.filter(question_bank_id=question_bank_id)

        # Filter by question type
        question_type = self.request.GET.get("question_type")
        if question_type:
            queryset = queryset.filter(question_type=question_type)

        # Filter by difficulty
        difficulty = self.request.GET.get("difficulty")
        if difficulty:
            queryset = queryset.filter(difficulty_level=difficulty)

        # Only show questions from question banks accessible to the teacher
        teacher = self.request.user.teacher_profile
        taught_classes = Class.objects.filter(
            subject_assignments__teacher=teacher,
            subject_assignments__academic_session__is_current=True,
        ).distinct()

        queryset = queryset.filter(question_bank__academic_class__in=taught_classes)

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["question_banks"] = QuestionBank.objects.filter(
            academic_class__in=Class.objects.filter(
                subject_assignments__teacher=self.request.user.teacher_profile,
                subject_assignments__academic_session__is_current=True,
            ).distinct()
        )
        context["question_types"] = Question.QuestionType.choices
        context["difficulty_levels"] = [
            ("easy", "Easy"),
            ("medium", "Medium"),
            ("hard", "Hard"),
            ("expert", "Expert"),
        ]
        return context


class QuestionCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    """Create a new question."""

    model = Question
    form_class = QuestionForm
    template_name = "assessment/questions/question_form.html"
    success_url = reverse_lazy("assessment:question_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["teacher"] = self.request.user.teacher_profile
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)

        # Handle options for multiple choice and true/false questions
        question = self.object
        if question.question_type in ["multiple_choice", "true_false"]:
            options_data = self.request.POST.getlist("option_text")
            correct_options = self.request.POST.getlist("is_correct")

            for i, option_text in enumerate(options_data):
                if option_text.strip():  # Only create non-empty options
                    QuestionOption.objects.create(
                        question=question,
                        option_text=option_text.strip(),
                        is_correct=str(i) in correct_options,
                        order=i,
                    )

        messages.success(self.request, "Question created successfully!")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["max_options"] = (
            6 if self.request.POST.get("question_type") == "multiple_choice" else 2
        )
        return context


@login_required
@user_passes_test(is_teacher)
def compose_exam(request, exam_id):
    """Compose an exam by selecting questions from question banks."""
    exam = get_object_or_404(Exam, id=exam_id)
    teacher = request.user.teacher_profile

    # Check if teacher has access to this exam
    if not Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__subject=exam.subject,
        subject_assignments__academic_session__is_current=True,
    ).exists():
        messages.error(request, "You do not have permission to modify this exam.")
        return redirect("assessment:exam_list")

    if request.method == "POST":
        form = ExamCompositionForm(request.POST, exam=exam)
        if form.is_valid():
            question_bank = form.cleaned_data["question_bank"]
            num_mc = form.cleaned_data["num_multiple_choice"]
            num_tf = form.cleaned_data["num_true_false"]
            num_sa = form.cleaned_data["num_short_answer"]
            num_essay = form.cleaned_data["num_essay"]
            marks_mc = form.cleaned_data["marks_per_multiple_choice"]
            marks_tf = form.cleaned_data["marks_per_true_false"]
            randomize = form.cleaned_data["randomize_order"]

            # Get questions from the selected question bank
            mc_questions = list(
                Question.objects.filter(
                    question_bank=question_bank,
                    question_type="multiple_choice",
                    is_active=True,
                )
            )
            tf_questions = list(
                Question.objects.filter(
                    question_bank=question_bank,
                    question_type="true_false",
                    is_active=True,
                )
            )
            sa_questions = list(
                Question.objects.filter(
                    question_bank=question_bank,
                    question_type="short_answer",
                    is_active=True,
                )
            )
            essay_questions = list(
                Question.objects.filter(
                    question_bank=question_bank, question_type="essay", is_active=True
                )
            )

            if randomize:
                import random

                random.shuffle(mc_questions)
                random.shuffle(tf_questions)
                random.shuffle(sa_questions)
                random.shuffle(essay_questions)

            # Select the required number of questions
            selected_questions = []
            order = 0

            # Add multiple choice questions
            for q in mc_questions[:num_mc]:
                selected_questions.append((q, marks_mc, order))
                order += 1

            # Add true/false questions
            for q in tf_questions[:num_tf]:
                selected_questions.append((q, marks_tf, order))
                order += 1

            # Add short answer questions (assume 5 marks each if not specified)
            for q in sa_questions[:num_sa]:
                selected_questions.append((q, 5.0, order))
                order += 1

            # Add essay questions (assume 10 marks each if not specified)
            for q in essay_questions[:num_essay]:
                selected_questions.append((q, 10.0, order))
                order += 1

            # Create ExamQuestion instances
            for question, marks, order_num in selected_questions:
                ExamQuestion.objects.create(
                    exam=exam, question=question, marks=marks, order=order_num
                )

            # Update exam total marks
            total_marks = sum(marks for _, marks, _ in selected_questions)
            exam.total_marks = total_marks
            exam.save()

            messages.success(
                request,
                f"Exam composed successfully with {len(selected_questions)} questions!",
            )
            return redirect("assessment:exam_detail", pk=exam.id)
    else:
        form = ExamCompositionForm(exam=exam)

    context = {
        "exam": exam,
        "form": form,
        "existing_questions": ExamQuestion.objects.filter(exam=exam).select_related(
            "question"
        ),
    }
    return render(request, "assessment/exams/exam_compose.html", context)


# =============================================================================
# STUDENT EXAM TAKING VIEWS
# =============================================================================


@login_required
@user_passes_test(is_student)
def take_exam(request, exam_id):
    """Allow students to take an exam."""
    exam = get_object_or_404(Exam, id=exam_id, is_published=True)
    student = request.user.student_profile

    # Check if student belongs to the exam class
    if student.current_class != exam.academic_class:
        messages.error(request, "You are not enrolled in this class.")
        return redirect("assessment:exam_list")

    # Check if exam is currently active
    now = timezone.now()
    exam_start = timezone.make_aware(datetime.combine(exam.exam_date, exam.start_time))
    exam_end = timezone.make_aware(datetime.combine(exam.exam_date, exam.end_time))

    if now < exam_start:
        messages.error(request, "Exam has not started yet.")
        return redirect("assessment:exam_list")
    elif now > exam_end:
        messages.error(request, "Exam has already ended.")
        return redirect("assessment:exam_list")

    # Check attendance
    attendance = ExamAttendance.objects.filter(
        exam=exam, student=student, is_present=True
    ).exists()
    if not attendance:
        messages.error(request, "You are not marked as present for this exam.")
        return redirect("assessment:exam_list")

    # Get exam questions
    exam_questions = (
        ExamQuestion.objects.filter(exam=exam)
        .select_related("question")
        .order_by("order")
    )

    if not exam_questions.exists():
        messages.error(request, "No questions available for this exam.")
        return redirect("assessment:exam_list")

    if request.method == "POST":
        # Process submitted answers
        for eq in exam_questions:
            answer_text = request.POST.get(f"answer_{eq.id}", "")
            selected_options = request.POST.getlist(f"options_{eq.id}")

            # Create or update student answer
            StudentAnswer.objects.update_or_create(
                exam_question=eq,
                student=student,
                defaults={
                    "answer_text": answer_text,
                    "selected_options": selected_options if selected_options else None,
                    "submitted_at": timezone.now(),
                },
            )

        messages.success(request, "Exam submitted successfully!")
        return redirect("assessment:exam_list")

    # GET request - show exam
    existing_answers = {
        sa.exam_question_id: sa
        for sa in StudentAnswer.objects.filter(
            exam_question__exam=exam, student=student
        )
    }

    context = {
        "exam": exam,
        "exam_questions": exam_questions,
        "existing_answers": existing_answers,
        "time_remaining": int((exam_end - now).total_seconds()),
    }
    return render(request, "assessment/exams/take_exam.html", context)


@login_required
@user_passes_test(is_teacher)
def grade_exam_answers(request, exam_id):
    """Grade subjective answers in an exam."""
    exam = get_object_or_404(Exam, id=exam_id)
    teacher = request.user.teacher_profile

    # Check permissions
    if not Class.objects.filter(
        subject_assignments__teacher=teacher, subject_assignments__subject=exam.subject
    ).exists():
        messages.error(request, "You do not have permission to grade this exam.")
        return redirect("assessment:exam_list")

    if request.method == "POST":
        answer_id = request.POST.get("answer_id")
        marks = request.POST.get("marks_obtained")

        if answer_id and marks:
            answer = get_object_or_404(
                StudentAnswer, id=answer_id, exam_question__exam=exam
            )
            answer.marks_obtained = marks
            answer.is_graded = True
            answer.save()

            messages.success(request, "Answer graded successfully!")

        return redirect("assessment:grade_exam_answers", exam_id=exam.id)

    # Get all student answers for subjective questions
    subjective_questions = ExamQuestion.objects.filter(
        exam=exam, question__question_type__in=["short_answer", "essay"]
    ).values_list("id", flat=True)

    student_answers = (
        StudentAnswer.objects.filter(exam_question_id__in=subjective_questions)
        .select_related("exam_question__question", "student__user")
        .order_by("student__user__first_name", "exam_question__order")
    )

    context = {
        "exam": exam,
        "student_answers": student_answers,
        "total_to_grade": student_answers.filter(is_graded=False).count(),
    }
    return render(request, "assessment/exams/grade_exam_answers.html", context)


@login_required
@user_passes_test(is_teacher)
def auto_calculate_marks(request, exam_id):
    """Automatically calculate marks for an exam based on question-based answers."""
    exam = get_object_or_404(Exam, id=exam_id)

    # Calculate marks for each student
    students = exam.academic_class.enrollments.filter(
        enrollment_status="active"
    ).values_list("student", flat=True)

    calculated_marks = []
    for student_id in students:
        student = Student.objects.get(id=student_id)

        # Sum up marks from all answered questions
        total_marks = (
            StudentAnswer.objects.filter(
                exam_question__exam=exam, student=student, is_graded=True
            ).aggregate(total=Sum("marks_obtained"))["total"]
            or 0
        )

        # Create or update mark record
        mark, created = Mark.objects.update_or_create(
            exam=exam,
            student=student,
            defaults={
                "marks_obtained": total_marks,
                "entered_by": request.user.teacher_profile,
            },
        )

        calculated_marks.append(
            {"student": student, "marks": total_marks, "created": created}
        )

    messages.success(request, f"Marks calculated for {len(calculated_marks)} students!")
    return redirect("assessment:exam_detail", pk=exam.id)


# =============================================================================
# AI QUESTION GENERATION VIEWS
# =============================================================================


@login_required
@user_passes_test(is_teacher)
def generate_ai_questions(request, question_bank_id):
    """Generate questions using AI for a question bank."""
    question_bank = get_object_or_404(QuestionBank, id=question_bank_id)
    teacher = request.user.teacher_profile

    # Check permissions - teacher must teach this class
    if not Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__subject=question_bank.subject,
        subject_assignments__academic_session__is_current=True,
    ).exists():
        messages.error(
            request, "You do not have permission to modify this question bank."
        )
        return redirect("assessment:question_bank_list")

    if request.method == "POST":
        topic = request.POST.get("topic", "").strip()
        count = int(request.POST.get("count", 5))
        difficulty = request.POST.get("difficulty", "medium")
        question_types = request.POST.getlist("question_types")

        if not topic:
            messages.error(request, "Please provide a topic for question generation.")
            return redirect(request.path)

        if not question_types:
            question_types = ["multiple_choice"]

        try:
            # Generate questions using AI
            created_questions, generation_log = generate_questions_with_ai(
                topic=topic,
                question_bank=question_bank,
                teacher=teacher,
                count=min(count, 10),  # Limit to 10 questions max
                difficulty=difficulty,
                question_types=question_types,
            )

            if created_questions:
                messages.success(
                    request,
                    f"Successfully generated {len(created_questions)} questions using AI!",
                )
            else:
                messages.warning(
                    request,
                    "AI generation completed but no valid questions were created.",
                )

        except Exception as e:
            logger.error(f"AI question generation failed: {str(e)}")
            messages.error(request, f"AI question generation failed: {str(e)}")

        return redirect("assessment:question_list")

    # GET request - show generation form
    context = {
        "question_bank": question_bank,
        "question_types": [
            ("multiple_choice", "Multiple Choice"),
            ("true_false", "True/False"),
            ("short_answer", "Short Answer"),
        ],
        "difficulty_levels": [
            ("easy", "Easy"),
            ("medium", "Medium"),
            ("hard", "Hard"),
            ("expert", "Expert"),
        ],
    }
    return render(request, "assessment/questions/ai_generate.html", context)


@login_required
@user_passes_test(is_teacher)
def ai_generation_history(request):
    """View AI generation history for teachers."""
    teacher = request.user.teacher_profile

    # Get generation logs for this teacher
    generation_logs = (
        AIGenerationLog.objects.filter(user=teacher)
        .select_related("question_bank")
        .order_by("-generated_at")
    )

    context = {
        "generation_logs": generation_logs,
        "total_generations": generation_logs.count(),
        "successful_generations": generation_logs.filter(success=True).count(),
        "total_questions_generated": generation_logs.filter(success=True).aggregate(
            total=Sum("question_count")
        )["total"]
        or 0,
    }

    return render(request, "assessment/questions/ai_history.html", context)


# =============================================================================
# QUIZ MARKING AND GRADING VIEWS (Enhanced from Clue System)
# =============================================================================


@login_required
@user_passes_test(is_teacher)
def quiz_marking_list(request):
    """List quiz attempts that need manual grading (enhanced from clue system)."""
    teacher = request.user.teacher_profile

    # Get classes taught by this teacher
    taught_classes = Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session__is_current=True,
    ).distinct()

    # Get quiz attempts for question banks in taught classes that need grading
    quiz_attempts = (
        QuizAttempt.objects.filter(
            question_bank__academic_class__in=taught_classes,
            complete=True,
            question_bank__exam_paper=True,  # Only show attempts for exam papers
        )
        .select_related("student__user", "question_bank")
        .order_by("-end_time")
    )

    # Filter attempts that have essay/short answer questions needing grading
    attempts_needing_grading = []
    for attempt in quiz_attempts:
        # Check if this attempt has questions that need manual grading
        questions = attempt.get_questions_with_answers()
        needs_grading = False
        for question in questions:
            if question.question_type in ["essay", "short_answer"]:
                # Check if this specific answer needs grading
                user_answer = question.user_answer
                if user_answer and not user_answer.get("is_graded", False):
                    needs_grading = True
                    break
        if needs_grading:
            attempts_needing_grading.append(attempt)

    context = {
        "attempts_needing_grading": attempts_needing_grading,
        "total_attempts": len(attempts_needing_grading),
    }
    return render(request, "assessment/quizzes/quiz_marking_list.html", context)


@login_required
@user_passes_test(is_teacher)
def quiz_marking_detail(request, attempt_id):
    """Detailed view for grading a specific quiz attempt (enhanced from clue system)."""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)

    # Check permissions
    teacher = request.user.teacher_profile
    if not Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__subject=attempt.question_bank.subject,
        subject_assignments__academic_session__is_current=True,
    ).exists():
        messages.error(
            request, "You do not have permission to grade this quiz attempt."
        )
        return redirect("assessment:quiz_marking_list")

    if request.method == "POST":
        question_id = request.POST.get("question_id")
        marks = request.POST.get("marks")

        if question_id and marks:
            try:
                marks = float(marks)
                question = Question.objects.get(id=int(question_id))

                # Update the user answer with grading info
                user_answers = json.loads(attempt.user_answers)
                if str(question.id) in user_answers:
                    user_answers[str(question.id)]["marks_obtained"] = marks
                    user_answers[str(question.id)]["is_graded"] = True
                    user_answers[str(question.id)]["graded_by"] = request.user.id
                    user_answers[str(question.id)][
                        "graded_at"
                    ] = timezone.now().isoformat()

                    # Update current score if this is an essay/short answer question
                    if question.question_type in ["essay", "short_answer"]:
                        attempt.current_score += marks
                        attempt.save()

                    attempt.user_answers = json.dumps(user_answers)
                    attempt.save()

                    messages.success(
                        request, f"Question graded successfully with {marks} marks."
                    )
                else:
                    messages.error(request, "Question answer not found.")

            except (ValueError, Question.DoesNotExist) as e:
                messages.error(request, "Invalid question or marks value.")

        return redirect("assessment:quiz_marking_detail", attempt_id=attempt.id)

    # Get questions with user answers for display
    questions_with_answers = attempt.get_questions_with_answers()

    context = {
        "attempt": attempt,
        "questions_with_answers": questions_with_answers,
    }
    return render(request, "assessment/quizzes/quiz_marking_detail.html", context)


@login_required
@user_passes_test(is_teacher)
def quiz_attempt_list(request):
    """List all quiz attempts for teachers to review (sitting list from clue system)."""
    teacher = request.user.teacher_profile

    # Get classes taught by this teacher
    taught_classes = Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session__is_current=True,
    ).distinct()

    # Get all quiz attempts for question banks in taught classes
    quiz_attempts = (
        QuizAttempt.objects.filter(question_bank__academic_class__in=taught_classes)
        .select_related("student__user", "question_bank")
        .order_by("-end_time")
    )

    # Filter by question bank if provided
    question_bank_id = request.GET.get("question_bank_id")
    if question_bank_id:
        quiz_attempts = quiz_attempts.filter(question_bank_id=question_bank_id)

    # Filter by student if provided
    student_id = request.GET.get("student_id")
    if student_id:
        quiz_attempts = quiz_attempts.filter(student_id=student_id)

    # Filter by status
    status = request.GET.get("status")
    if status == "complete":
        quiz_attempts = quiz_attempts.filter(complete=True)
    elif status == "in_progress":
        quiz_attempts = quiz_attempts.filter(complete=False)

    # Get question banks for filter dropdown
    question_banks = QuestionBank.objects.filter(
        academic_class__in=taught_classes, bank_type="quiz"
    ).select_related("subject", "academic_class")

    context = {
        "quiz_attempts": quiz_attempts,
        "question_banks": question_banks,
        "total_attempts": quiz_attempts.count(),
        "completed_attempts": quiz_attempts.filter(complete=True).count(),
        "in_progress_attempts": quiz_attempts.filter(complete=False).count(),
    }
    return render(request, "assessment/quizzes/quiz_attempt_list.html", context)


# =============================================================================
# QUIZ MARKING VIEWS (Enhanced from Clue System)
# =============================================================================


@login_required
@user_passes_test(is_teacher)
def quiz_marking_list(request):
    """List quiz attempts that need manual grading (enhanced from clue system)."""
    teacher = request.user.teacher_profile

    # Get classes taught by this teacher
    taught_classes = Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session__is_current=True,
    ).distinct()

    # Get quiz attempts for question banks in taught classes that need grading
    quiz_attempts = (
        QuizAttempt.objects.filter(
            question_bank__academic_class__in=taught_classes,
            complete=True,
            question_bank__exam_paper=True,  # Only show attempts for exam papers
        )
        .select_related("student__user", "question_bank")
        .order_by("-end_time")
    )

    # Filter attempts that have essay/short answer questions needing grading
    attempts_needing_grading = []
    for attempt in quiz_attempts:
        # Check if this attempt has questions that need manual grading
        questions_with_answers = attempt.get_questions_with_answers()
        needs_grading = False
        for question in questions_with_answers:
            if question.question_type in ["essay", "short_answer"]:
                # Check if this specific answer needs grading
                user_answer = question.user_answer
                if user_answer and not user_answer.get("is_graded", False):
                    needs_grading = True
                    break
        if needs_grading:
            attempts_needing_grading.append(attempt)

    context = {
        "attempts_needing_grading": attempts_needing_grading,
        "total_attempts": len(attempts_needing_grading),
    }
    return render(request, "assessment/quizzes/quiz_marking_list.html", context)


@login_required
@user_passes_test(is_teacher)
def quiz_marking_detail(request, attempt_id):
    """Detailed view for grading a specific quiz attempt (enhanced from clue system)."""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)

    # Check permissions
    teacher = request.user.teacher_profile
    if not Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__subject=attempt.question_bank.subject,
        subject_assignments__academic_session__is_current=True,
    ).exists():
        messages.error(
            request, "You do not have permission to grade this quiz attempt."
        )
        return redirect("assessment:quiz_marking_list")

    if request.method == "POST":
        question_id = request.POST.get("question_id")
        marks = request.POST.get("marks")

        if question_id and marks:
            try:
                marks = float(marks)
                question = Question.objects.get(id=int(question_id))

                # Update the user answer with grading info
                user_answers = (
                    json.loads(attempt.user_answers) if attempt.user_answers else {}
                )
                if str(question.id) in user_answers:
                    user_answers[str(question.id)]["marks_obtained"] = marks
                    user_answers[str(question.id)]["is_graded"] = True
                    user_answers[str(question.id)]["graded_by"] = request.user.id
                    user_answers[str(question.id)][
                        "graded_at"
                    ] = timezone.now().isoformat()

                    # Update current score if this is an essay/short answer question
                    if question.question_type in ["essay", "short_answer"]:
                        attempt.current_score += marks
                        attempt.save()

                    attempt.user_answers = json.dumps(user_answers)
                    attempt.save()

                    messages.success(
                        request, f"Question graded successfully with {marks} marks."
                    )
                else:
                    messages.error(request, "Question answer not found.")

            except (ValueError, Question.DoesNotExist) as e:
                messages.error(request, "Invalid question or marks value.")

        return redirect("assessment:quiz_marking_detail", attempt_id=attempt.id)

    # Get questions with user answers for display
    questions_with_answers = attempt.get_questions_with_answers()

    context = {
        "attempt": attempt,
        "questions_with_answers": questions_with_answers,
    }
    return render(request, "assessment/quizzes/quiz_marking_detail.html", context)


# =============================================================================
# QUIZ MARKING VIEWS (Enhanced from Clue System)
# =============================================================================


@login_required
@user_passes_test(is_teacher)
def quiz_marking_list(request):
    """List quiz attempts that need manual grading (enhanced from clue system)."""
    teacher = request.user.teacher_profile

    # Get classes taught by this teacher
    taught_classes = Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session__is_current=True,
    ).distinct()

    # Get quiz attempts for question banks in taught classes that need grading
    quiz_attempts = (
        QuizAttempt.objects.filter(
            question_bank__academic_class__in=taught_classes,
            complete=True,
            question_bank__exam_paper=True,  # Only show attempts for exam papers
        )
        .select_related("student__user", "question_bank")
        .order_by("-end_time")
    )

    # Filter attempts that have essay/short answer questions needing grading
    attempts_needing_grading = []
    for attempt in quiz_attempts:
        # Check if this attempt has questions that need manual grading
        questions_with_answers = attempt.get_questions_with_answers()
        needs_grading = False
        for question in questions_with_answers:
            if question.question_type in ["essay", "short_answer"]:
                # Check if this specific answer needs grading
                user_answer = question.user_answer
                if user_answer and not user_answer.get("is_graded", False):
                    needs_grading = True
                    break
        if needs_grading:
            attempts_needing_grading.append(attempt)

    context = {
        "attempts_needing_grading": attempts_needing_grading,
        "total_attempts": len(attempts_needing_grading),
    }
    return render(request, "assessment/quizzes/quiz_marking_list.html", context)


@login_required
@user_passes_test(is_teacher)
def quiz_marking_detail(request, attempt_id):
    """Detailed view for grading a specific quiz attempt (enhanced from clue system)."""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)

    # Check permissions
    teacher = request.user.teacher_profile
    if not Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__subject=attempt.question_bank.subject,
        subject_assignments__academic_session__is_current=True,
    ).exists():
        messages.error(
            request, "You do not have permission to grade this quiz attempt."
        )
        return redirect("assessment:quiz_marking_list")

    if request.method == "POST":
        question_id = request.POST.get("question_id")
        marks = request.POST.get("marks")

        if question_id and marks:
            try:
                marks = float(marks)
                question = Question.objects.get(id=int(question_id))

                # Update the user answer with grading info
                user_answers = (
                    json.loads(attempt.user_answers) if attempt.user_answers else {}
                )
                if str(question.id) in user_answers:
                    user_answers[str(question.id)]["marks_obtained"] = marks
                    user_answers[str(question.id)]["is_graded"] = True
                    user_answers[str(question.id)]["graded_by"] = request.user.id
                    user_answers[str(question.id)][
                        "graded_at"
                    ] = timezone.now().isoformat()

                    # Update current score if this is an essay/short answer question
                    if question.question_type in ["essay", "short_answer"]:
                        attempt.current_score += marks
                        attempt.save()

                    attempt.user_answers = json.dumps(user_answers)
                    attempt.save()

                    messages.success(
                        request, f"Question graded successfully with {marks} marks."
                    )
                else:
                    messages.error(request, "Question answer not found.")

            except (ValueError, Question.DoesNotExist) as e:
                messages.error(request, "Invalid question or marks value.")

        return redirect("assessment:quiz_marking_detail", attempt_id=attempt.id)

    # Get questions with user answers for display
    questions_with_answers = attempt.get_questions_with_answers()

    context = {
        "attempt": attempt,
        "questions_with_answers": questions_with_answers,
    }
    return render(request, "assessment/quizzes/quiz_marking_detail.html", context)


@login_required
def course_registration_pdf_view(request, course_id):
    """
    Generate PDF course registration form (from clue system).
    """
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
    from reportlab.lib.units import inch, cm
    import os

    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    if not current_session:
        messages.error(request, "No active academic session found.")
        return redirect("assessment:grade_results")

    # Verify teacher teaches this course
    course = get_object_or_404(Subject, id=course_id)
    if not Subject.objects.filter(
        id=course_id,
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session=current_session,
    ).exists():
        messages.error(
            request,
            "You are not authorized to generate registration forms for this course.",
        )
        return redirect("assessment:grade_results")

    # Get students enrolled in this course
    taken_courses = TakenCourse.objects.filter(
        course=course, academic_session=current_session
    ).select_related("student__user")

    if not taken_courses.exists():
        messages.warning(request, "No students enrolled in this course.")
        return redirect("assessment:grade_results")

    # Create filename
    fname = f"{request.user.username}_{course.code}_registration_form.pdf"
    fname = fname.replace("/", "-")

    # Create PDF directory if it doesn't exist
    pdf_dir = os.path.join(settings.MEDIA_ROOT, "registration_forms")
    os.makedirs(pdf_dir, exist_ok=True)
    flocation = os.path.join(pdf_dir, fname)

    # Create PDF document
    doc = SimpleDocTemplate(
        flocation,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm,
    )

    styles = getSampleStyleSheet()

    Story = []

    # Header
    header_style = ParagraphStyle(
        name="Header",
        fontSize=14,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=20,
    )

    institution_name = getattr(settings, "INSTITUTION_NAME", "School Management System")
    Story.append(Paragraph(institution_name.upper(), header_style))

    department_name = getattr(settings, "DEPARTMENT_NAME", "Academic Department")
    dept_style = ParagraphStyle(
        name="Dept", fontSize=12, alignment=TA_CENTER, spaceAfter=30
    )
    Story.append(Paragraph(department_name.upper(), dept_style))

    # Title
    title_style = ParagraphStyle(
        name="Title",
        fontSize=12,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=30,
    )
    Story.append(Paragraph("STUDENT COURSE REGISTRATION FORM", title_style))

    # Student information
    student = (
        taken_courses.first().student
    )  # Get first student (assuming one student per request)

    info_data = [
        [
            f"Registration Number: {student.user.username.upper()}",
            f"Level: {getattr(student, 'level', 'N/A')}",
        ],
        [
            f"Name: {student.user.get_full_name().upper()}",
            f"Session: {current_session.session}",
        ],
    ]

    info_table = Table(info_data, colWidths=[8 * cm, 6 * cm])
    info_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    Story.append(info_table)
    Story.append(Spacer(1, 1 * cm))

    # Course registration table
    course_data = [
        ["S/No", "Course Code", "Course Title", "Credit Hours", "Lecturer Signature"],
        ["1", course.code.upper(), course.name, getattr(course, "credit_hours", 1), ""],
    ]

    course_table = Table(
        course_data, colWidths=[1 * cm, 3 * cm, 8 * cm, 2 * cm, 4 * cm]
    )
    course_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
            ]
        )
    )
    Story.append(course_table)
    Story.append(Spacer(1, 2 * cm))

    # Certification text
    cert_style = ParagraphStyle(
        name="Cert", fontSize=9, alignment=TA_JUSTIFY, spaceAfter=30
    )

    cert_text = f"""
    CERTIFICATION OF REGISTRATION: I certify that {student.user.get_full_name().upper()} has been duly registered for the course shown above in the {department_name} and that the course and credit hours registered are as approved by the department administration.
    """

    Story.append(Paragraph(cert_text, cert_style))

    # Signatures
    signature_data = [
        [
            "Student Signature:",
            "_______________________________",
            "Date:",
            "________________",
        ],
        [
            "Lecturer Signature:",
            "_______________________________",
            "Date:",
            "________________",
        ],
        [
            "Department Head:",
            "_______________________________",
            "Date:",
            "________________",
        ],
    ]

    signature_table = Table(signature_data, colWidths=[3 * cm, 6 * cm, 2 * cm, 5 * cm])
    signature_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ]
        )
    )
    Story.append(signature_table)

    # Build PDF
    try:
        doc.build(Story)

        # Return file for download
        with open(flocation, "rb") as pdf_file:
            response = HttpResponse(pdf_file.read(), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{fname}"'
            return response

    except Exception as e:
        messages.error(request, f"Error generating PDF: {str(e)}")
        return redirect("assessment:grade_results")


@login_required
def quiz_bank_detail(request, quiz_bank_id):
    """Show quiz bank details and allow starting quiz (enhanced from clue system)."""
    quiz_bank = get_object_or_404(QuestionBank, id=quiz_bank_id, bank_type="quiz")

    # Check permissions
    if hasattr(request.user, "student_profile"):
        student = request.user.student_profile
        if quiz_bank.academic_class != student.current_class:
            messages.error(request, "You do not have access to this quiz.")
            return redirect("assessment:quiz_bank_list")
    else:
        messages.error(request, "Only students can access quizzes.")
        return redirect("users:dashboard")

    # Check if student has already completed this quiz (single attempt)
    if quiz_bank.single_attempt:
        existing_attempt = QuizAttempt.objects.filter(
            student=request.user.student_profile, question_bank=quiz_bank, complete=True
        ).exists()
        if existing_attempt:
            messages.info(request, "You have already completed this quiz.")
            return redirect("assessment:student_progress")

    # Get quiz statistics
    total_attempts = QuizAttempt.objects.filter(question_bank=quiz_bank).count()
    completed_attempts = QuizAttempt.objects.filter(
        question_bank=quiz_bank, complete=True
    ).count()

    # Calculate average score
    avg_score = 0
    if completed_attempts > 0:
        avg_score = (
            QuizAttempt.objects.filter(
                question_bank=quiz_bank, complete=True
            ).aggregate(avg=Avg("current_score"))["avg"]
            or 0
        )

    context = {
        "quiz_bank": quiz_bank,
        "total_attempts": total_attempts,
        "completed_attempts": completed_attempts,
        "avg_score": avg_score,
        "question_count": quiz_bank.questions.filter(is_active=True).count(),
    }
    return render(request, "assessment/quizzes/quiz_bank_detail.html", context)


@login_required
def take_quiz(request, quiz_bank_id):
    """Enhanced quiz taking view similar to clue system."""
    quiz_bank = get_object_or_404(QuestionBank, id=quiz_bank_id, bank_type="quiz")

    # Check permissions
    if hasattr(request.user, "student_profile"):
        student = request.user.student_profile
        if quiz_bank.academic_class != student.current_class:
            messages.error(request, "You do not have access to this quiz.")
            return redirect("assessment:quiz_bank_list")
    else:
        messages.error(request, "Only students can take quizzes.")
        return redirect("assessment:quiz_bank_list")

    # Check single attempt rule
    if quiz_bank.single_attempt:
        existing_attempt = QuizAttempt.objects.filter(
            student=request.user.student_profile, question_bank=quiz_bank, complete=True
        ).exists()
        if existing_attempt:
            messages.error(request, "You have already completed this quiz.")
            return redirect("assessment:quiz_bank_detail", quiz_bank_id=quiz_bank.id)

    # Get or create quiz attempt
    attempt, created = QuizAttempt.objects.get_or_create(
        student=request.user.student_profile,
        question_bank=quiz_bank,
        defaults={
            "question_order": "",
            "question_list": "",
            "user_answers": {},
            "current_score": 0,
            "max_score": 0,
        },
    )

    # Initialize questions if this is a new attempt
    if created:
        questions = list(quiz_bank.questions.filter(is_active=True))
        if quiz_bank.random_order:
            import random

            random.shuffle(questions)

        question_ids = [str(q.id) for q in questions]
        attempt.question_order = ",".join(question_ids) + ","
        attempt.question_list = attempt.question_order
        attempt.max_score = len(questions)
        attempt.save()

    # Get current question
    current_question = attempt.get_first_question()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "answer":
            # Process answer
            question_id = request.POST.get("question_id")
            answer_data = {}

            if current_question.question_type == "multiple_choice":
                selected_options = request.POST.getlist("selected_options")
                answer_data = {"selected_options": selected_options}
                # Auto-grade multiple choice
                if selected_options:
                    correct_options = set(
                        current_question.get_correct_options().values_list(
                            "id", flat=True
                        )
                    )
                    selected_set = set(int(opt) for opt in selected_options)
                    if correct_options == selected_set:
                        attempt.add_to_score(1)
            elif current_question.question_type == "true_false":
                selected_options = request.POST.getlist("selected_options")
                answer_data = {"selected_options": selected_options}
                # Auto-grade true/false
                if selected_options:
                    correct_options = set(
                        current_question.get_correct_options().values_list(
                            "id", flat=True
                        )
                    )
                    selected_set = set(int(opt) for opt in selected_options)
                    if correct_options == selected_set:
                        attempt.add_to_score(1)
            else:
                # Essay or short answer - store for manual grading
                answer_text = request.POST.get("answer_text", "")
                answer_data = {"answer_text": answer_text}

            # Store answer
            attempt.add_user_answer(current_question, answer_data)

            # Move to next question
            attempt.remove_first_question()

            # Check if quiz is complete
            next_question = attempt.get_first_question()
            if not next_question:
                # Quiz completed
                attempt.mark_complete()

                # Update progress
                progress, _ = QuizProgress.objects.get_or_create(
                    student=request.user.student_profile
                )
                progress.update_score(
                    quiz_bank, attempt.current_score, attempt.max_score
                )

                # Update course grade if applicable (enhanced from clue system)
                try:
                    from apps.academics.models import AcademicSession

                    current_session = AcademicSession.objects.filter(
                        is_current=True
                    ).first()
                    if current_session:
                        # Update CourseGrade
                        course_grade, _ = CourseGrade.objects.get_or_create(
                            student=request.user.student_profile,
                            subject=quiz_bank.subject,
                            academic_session=current_session,
                        )
                        course_grade.update_quiz_score(attempt.get_percent_correct)

                        # Update TakenCourse (from clue system integration)
                        taken_course, _ = TakenCourse.objects.get_or_create(
                            student=request.user.student_profile,
                            course=quiz_bank.subject,
                            academic_session=current_session,
                        )
                        taken_course.update_quiz_score(attempt.get_percent_correct)

                except Exception as e:
                    # Log error but don't fail quiz completion
                    pass

                messages.success(
                    request, f"Quiz completed! Score: {attempt.get_percent_correct}%"
                )
                return redirect("assessment:quiz_result", attempt_id=attempt.id)

            current_question = next_question

        elif action == "finish":
            # Force finish quiz
            attempt.mark_complete()

            # Update progress
            progress, _ = QuizProgress.objects.get_or_create(
                student=request.user.student_profile
            )
            progress.update_score(quiz_bank, attempt.current_score, attempt.max_score)

            messages.success(
                request, f"Quiz completed! Score: {attempt.get_percent_correct}%"
            )
            return redirect("assessment:quiz_result", attempt_id=attempt.id)

    context = {
        "quiz_bank": quiz_bank,
        "attempt": attempt,
        "current_question": current_question,
        "progress_percentage": attempt.progress_percentage,
        "show_answers": quiz_bank.answers_at_end and attempt.complete,
    }

    if current_question:
        if current_question.question_type in ["multiple_choice", "true_false"]:
            context["options"] = current_question.options.all().order_by("order")

    return render(request, "assessment/quizzes/take_quiz.html", context)


@login_required
def quiz_result(request, attempt_id):
    """Show quiz results."""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)

    # Check permissions
    if hasattr(request.user, "student_profile"):
        if attempt.student != request.user.student_profile:
            messages.error(request, "You do not have permission to view this result.")
            return redirect("assessment:quiz_bank_list")
    elif hasattr(request.user, "teacher_profile"):
        teacher = request.user.teacher_profile
        if not Class.objects.filter(
            subject_assignments__teacher=teacher,
            subject_assignments__subject=attempt.question_bank.subject,
            subject_assignments__academic_session__is_current=True,
        ).exists():
            messages.error(request, "You do not have permission to view this result.")
            return redirect("assessment:quiz_bank_list")

    context = {
        "attempt": attempt,
        "questions_with_answers": attempt.get_questions_with_answers(),
        "show_answers": True,
    }
    return render(request, "assessment/quizzes/quiz_result.html", context)


@login_required
def student_progress(request):
    """Show student quiz progress."""
    if not hasattr(request.user, "student_profile"):
        messages.error(request, "Only students can view progress.")
        return redirect("assessment:quiz_bank_list")

    student = request.user.student_profile
    progress, _ = QuizProgress.objects.get_or_create(student=student)

    context = {
        "progress": progress,
        "category_scores": progress.list_category_scores(),
        "recent_attempts": progress.show_attempts()[:10],
    }
    return render(request, "assessment/quizzes/student_progress.html", context)


# =============================================================================
# QUIZ MARKING AND GRADING VIEWS (Enhanced from Clue System)
# =============================================================================


@login_required
@user_passes_test(is_teacher)
def quiz_marking_list(request):
    """List quiz attempts that need manual grading (enhanced from clue system)."""
    teacher = request.user.teacher_profile

    # Get classes taught by this teacher
    taught_classes = Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session__is_current=True,
    ).distinct()

    # Get quiz attempts for question banks in taught classes that need grading
    quiz_attempts = (
        QuizAttempt.objects.filter(
            question_bank__academic_class__in=taught_classes,
            complete=True,
            question_bank__exam_paper=True,  # Only show attempts for exam papers
        )
        .select_related("student__user", "question_bank")
        .order_by("-end_time")
    )

    # Filter attempts that have essay/short answer questions needing grading
    attempts_needing_grading = []
    for attempt in quiz_attempts:
        # Check if this attempt has questions that need manual grading
        questions = attempt.get_questions_with_answers()
        needs_grading = False
        for question in questions:
            if question.question_type in ["essay", "short_answer"]:
                # Check if this specific answer needs grading
                user_answer = question.user_answer
                if user_answer and not user_answer.get("is_graded", False):
                    needs_grading = True
                    break
        if needs_grading:
            attempts_needing_grading.append(attempt)

    context = {
        "attempts_needing_grading": attempts_needing_grading,
        "total_attempts": len(attempts_needing_grading),
    }
    return render(request, "assessment/quizzes/quiz_marking_list.html", context)


@login_required
@user_passes_test(is_teacher)
def quiz_marking_detail(request, attempt_id):
    """Detailed view for grading a specific quiz attempt (enhanced from clue system)."""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)

    # Check permissions
    teacher = request.user.teacher_profile
    if not Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__subject=attempt.question_bank.subject,
        subject_assignments__academic_session__is_current=True,
    ).exists():
        messages.error(
            request, "You do not have permission to grade this quiz attempt."
        )
        return redirect("assessment:quiz_marking_list")

    if request.method == "POST":
        question_id = request.POST.get("question_id")
        marks = request.POST.get("marks")

        if question_id and marks:
            try:
                marks = float(marks)
                question = Question.objects.get(id=int(question_id))

                # Update the user answer with grading info
                user_answers = attempt.user_answers.copy()
                if str(question.id) in user_answers:
                    user_answers[str(question.id)]["marks_obtained"] = marks
                    user_answers[str(question.id)]["is_graded"] = True
                    user_answers[str(question.id)]["graded_by"] = request.user.id
                    user_answers[str(question.id)][
                        "graded_at"
                    ] = timezone.now().isoformat()

                    # Update current score if this is an essay/short answer question
                    if question.question_type in ["essay", "short_answer"]:
                        attempt.current_score += marks
                        attempt.save()

                    attempt.user_answers = user_answers
                    attempt.save()

                    messages.success(
                        request, f"Question graded successfully with {marks} marks."
                    )
                else:
                    messages.error(request, "Question answer not found.")

            except (ValueError, Question.DoesNotExist) as e:
                messages.error(request, "Invalid question or marks value.")

        return redirect("assessment:quiz_marking_detail", attempt_id=attempt.id)

    # Get questions with user answers for display
    questions_with_answers = attempt.get_questions_with_answers()

    context = {
        "attempt": attempt,
        "questions_with_answers": questions_with_answers,
    }
    return render(request, "assessment/quizzes/quiz_marking_detail.html", context)


@login_required
@user_passes_test(is_teacher)
def quiz_attempt_list(request):
    """List all quiz attempts for teachers to review (sitting list from clue system)."""
    teacher = request.user.teacher_profile

    # Get classes taught by this teacher
    taught_classes = Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session__is_current=True,
    ).distinct()

    # Get all quiz attempts for question banks in taught classes
    quiz_attempts = (
        QuizAttempt.objects.filter(question_bank__academic_class__in=taught_classes)
        .select_related("student__user", "question_bank")
        .order_by("-end_time")
    )

    # Filter by question bank if provided
    question_bank_id = request.GET.get("question_bank_id")
    if question_bank_id:
        quiz_attempts = quiz_attempts.filter(question_bank_id=question_bank_id)

    # Filter by student if provided
    student_id = request.GET.get("student_id")
    if student_id:
        quiz_attempts = quiz_attempts.filter(student_id=student_id)

    # Filter by status
    status = request.GET.get("status")
    if status == "complete":
        quiz_attempts = quiz_attempts.filter(complete=True)
    elif status == "in_progress":
        quiz_attempts = quiz_attempts.filter(complete=False)

    # Get question banks for filter dropdown
    question_banks = QuestionBank.objects.filter(
        academic_class__in=taught_classes, bank_type="quiz"
    ).select_related("subject", "academic_class")

    context = {
        "quiz_attempts": quiz_attempts,
        "question_banks": question_banks,
        "total_attempts": quiz_attempts.count(),
        "completed_attempts": quiz_attempts.filter(complete=True).count(),
        "in_progress_attempts": quiz_attempts.filter(complete=False).count(),
    }
    return render(request, "assessment/quizzes/quiz_attempt_list.html", context)


# =============================================================================
# BULK SCORE ENTRY VIEWS (from Clue System)
# =============================================================================


@login_required
@user_passes_test(is_teacher)
def add_score(request):
    """
    Shows a page where a lecturer will select a course allocated
    to him for score entry. Similar to clue system's add_score view.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()
    current_semester = getattr(current_session, "current_semester", None)

    if not current_session or not current_semester:
        messages.error(request, "No active semester found.")
        return render(request, "assessment/scores/add_score.html")

    # Get courses taught by this teacher in current semester
    courses = Subject.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session=current_session,
        subject_assignments__semester=current_semester,
    ).distinct()

    context = {
        "current_session": current_session,
        "current_semester": current_semester,
        "courses": courses,
    }
    return render(request, "assessment/scores/add_score.html", context)


@login_required
@user_passes_test(is_teacher)
def add_score_for(request, course_id):
    """
    Shows a page where a lecturer will add comprehensive course scores for students.
    Enhanced version of clue system's add_score_for view with TakenCourse model.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()
    current_semester = getattr(current_session, "current_semester", None)

    if not current_session or not current_semester:
        messages.error(request, "No active semester found.")
        return redirect("assessment:add_score")

    # Verify teacher teaches this course
    course = get_object_or_404(Subject, id=course_id)
    if not Subject.objects.filter(
        id=course_id,
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session=current_session,
        subject_assignments__semester=current_semester,
    ).exists():
        messages.error(
            request, "You are not authorized to enter scores for this course."
        )
        return redirect("assessment:add_score")

    if request.method == "GET":
        # Get all students enrolled in classes where this course is taught
        taught_classes = Class.objects.filter(
            subject_assignments__teacher=teacher,
            subject_assignments__subject=course,
            subject_assignments__academic_session=current_session,
            subject_assignments__semester=current_semester,
        ).distinct()

        students = (
            Student.objects.filter(
                enrollments__academic_class__in=taught_classes,
                enrollments__enrollment_status="active",
                enrollments__academic_session=current_session,
            )
            .distinct()
            .select_related("user")
        )

        # Get existing TakenCourse records for this course/session
        existing_scores = {
            tc.student_id: tc
            for tc in TakenCourse.objects.filter(
                course=course, academic_session=current_session, student__in=students
            )
        }

        context = {
            "title": "Submit Course Scores",
            "courses": [course],  # For template compatibility
            "course": course,
            "students": students,
            "existing_scores": existing_scores,
            "current_session": current_session,
            "current_semester": current_semester,
        }
        return render(request, "assessment/scores/add_score_for.html", context)

    if request.method == "POST":
        # Process bulk score submission
        data = request.POST.copy()
        data.pop("csrfmiddlewaretoken", None)  # remove csrf_token

        # Get all student IDs from form
        student_ids = []
        for key in data.keys():
            if key.startswith("assignment_"):
                student_id = key.split("_")[1]
                if student_id not in student_ids:
                    student_ids.append(student_id)

        # Process each student's scores
        for student_id in student_ids:
            student = get_object_or_404(Student, id=student_id)

            # Extract scores from form data
            assignment_score = data.get(f"assignment_{student_id}", "0").strip()
            mid_exam_score = data.get(f"mid_exam_{student_id}", "0").strip()
            quiz_score = data.get(f"quiz_{student_id}", "0").strip()
            attendance_score = data.get(f"attendance_{student_id}", "0").strip()
            final_exam_score = data.get(f"final_exam_{student_id}", "0").strip()

            # Convert to decimal, defaulting to 0 if empty
            try:
                assignment = (
                    Decimal(assignment_score) if assignment_score else Decimal("0.00")
                )
                mid_exam = (
                    Decimal(mid_exam_score) if mid_exam_score else Decimal("0.00")
                )
                quiz = Decimal(quiz_score) if quiz_score else Decimal("0.00")
                attendance = (
                    Decimal(attendance_score) if attendance_score else Decimal("0.00")
                )
                final_exam = (
                    Decimal(final_exam_score) if final_exam_score else Decimal("0.00")
                )
            except (ValueError, TypeError):
                messages.error(
                    request,
                    f"Invalid score format for student {student.user.get_full_name()}",
                )
                continue

            # Create or update TakenCourse record
            taken_course, created = TakenCourse.objects.update_or_create(
                student=student,
                course=course,
                academic_session=current_session,
                defaults={
                    "assignment": assignment,
                    "mid_exam": mid_exam,
                    "quiz": quiz,
                    "attendance": attendance,
                    "final_exam": final_exam,
                },
            )

            # Calculate GPA and CGPA
            gpa = taken_course.calculate_gpa()
            cgpa = taken_course.calculate_cgpa()

        messages.success(request, "Successfully recorded course scores!")
        return redirect("assessment:add_score_for", course_id=course_id)


# =============================================================================
# ADDITIONAL VIEWS FROM CLUE SYSTEM INTEGRATION
# =============================================================================


@login_required
@user_passes_test(is_teacher)
def assessment_results(request):
    """
    View for displaying assessment results similar to clue system's results view.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    if not current_session:
        messages.error(request, "No active academic session found.")
        return render(request, "assessment/results/assessment_results.html")

    # Get classes taught by this teacher
    taught_classes = Class.objects.filter(
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session=current_session,
    ).distinct()

    # Get results for these classes
    results = (
        Result.objects.filter(
            academic_class__in=taught_classes, session=current_session.session
        )
        .select_related("student__user", "academic_class")
        .order_by("-gpa")
    )

    context = {
        "results": results,
        "current_session": current_session,
        "taught_classes": taught_classes,
    }
    return render(request, "assessment/results/assessment_results.html", context)


@login_required
@user_passes_test(is_teacher)
def grade_results(request):
    """
    View for displaying grade results similar to clue system's grade results view.
    """
    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    if not current_session:
        messages.error(request, "No active academic session found.")
        return render(request, "assessment/results/grade_results.html")

    # Get taken courses for subjects taught by this teacher
    taken_courses = (
        TakenCourse.objects.filter(
            course__subject_assignments__teacher=teacher,
            course__subject_assignments__academic_session=current_session,
            academic_session=current_session,
        )
        .select_related("student__user", "course")
        .order_by("student__user__last_name")
    )

    # Group by grade for summary
    grade_summary = {}
    for tc in taken_courses:
        grade = tc.grade
        if grade not in grade_summary:
            grade_summary[grade] = {"count": 0, "students": []}
        grade_summary[grade]["count"] += 1
        grade_summary[grade]["students"].append(tc.student)

    context = {
        "taken_courses": taken_courses,
        "grade_summary": grade_summary,
        "current_session": current_session,
        "grade_choices": GRADE_CHOICES,
    }
    return render(request, "assessment/results/grade_results.html", context)


# =============================================================================
# PDF RESULT SHEET GENERATION (Enhanced from Clue System)
# =============================================================================


@login_required
@user_passes_test(is_teacher)
def result_sheet_pdf_view(request, course_id):
    """
    Generate PDF result sheet for a course (enhanced from clue system's implementation).
    """
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER, TA_RIGHT
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    import os

    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    if not current_session:
        messages.error(request, "No active academic session found.")
        return redirect("assessment:grade_results")

    # Verify teacher teaches this course
    course = get_object_or_404(Subject, id=course_id)
    if not Subject.objects.filter(
        id=course_id,
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session=current_session,
    ).exists():
        messages.error(
            request, "You are not authorized to view results for this course."
        )
        return redirect("assessment:grade_results")

    # Get taken courses for this course
    taken_courses = (
        TakenCourse.objects.filter(course=course, academic_session=current_session)
        .select_related("student__user")
        .order_by("student__user__last_name")
    )

    if not taken_courses.exists():
        messages.warning(request, "No results found for this course.")
        return redirect("assessment:grade_results")

    # Calculate statistics
    no_of_pass = taken_courses.filter(comment="PASS").count()
    no_of_fail = taken_courses.filter(comment="FAIL").count()

    # Create filename
    fname = f"{current_session.session}_{course.code}_result_sheet.pdf"
    fname = fname.replace("/", "-")

    # Create PDF directory if it doesn't exist
    pdf_dir = os.path.join(settings.MEDIA_ROOT, "result_sheets")
    os.makedirs(pdf_dir, exist_ok=True)
    flocation = os.path.join(pdf_dir, fname)

    # Create PDF document
    doc = SimpleDocTemplate(
        flocation,
        pagesize=A4,
        rightMargin=1 * cm,
        leftMargin=1 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm,
    )

    # Styles
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(name="ParagraphTitle", fontSize=11, fontName="Helvetica-Bold")
    )

    Story = []

    # Header section
    header_style = ParagraphStyle(
        name="Header",
        fontSize=14,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=20,
    )

    # Institution header
    institution_name = getattr(settings, "INSTITUTION_NAME", "School Management System")
    department_name = getattr(settings, "DEPARTMENT_NAME", "Academic Department")

    Story.append(Paragraph(institution_name.upper(), header_style))
    Story.append(Paragraph(department_name.upper(), styles["Normal"]))
    Story.append(Spacer(1, 0.5 * cm))

    # Title
    title = f"{current_session.session} Session - {course.name} ({course.code})"
    Story.append(Paragraph(title, header_style))
    Story.append(Paragraph("Result Sheet", header_style))
    Story.append(Spacer(1, 0.5 * cm))

    # Course and lecturer info
    info_style = ParagraphStyle(
        name="Info", fontSize=10, alignment=TA_LEFT, spaceAfter=10
    )

    Story.append(Paragraph(f"<b>Course Code:</b> {course.code}", info_style))
    Story.append(Paragraph(f"<b>Course Title:</b> {course.name}", info_style))
    Story.append(
        Paragraph(f"<b>Lecturer:</b> {request.user.get_full_name()}", info_style)
    )
    Story.append(Paragraph(f"<b>Session:</b> {current_session.session}", info_style))
    Story.append(
        Paragraph(f"<b>Total Students:</b> {taken_courses.count()}", info_style)
    )
    Story.append(Spacer(1, 0.5 * cm))

    # Results table
    table_data = [
        [
            "S/N",
            "Student ID",
            "Full Name",
            "Assignment",
            "Mid Exam",
            "Quiz",
            "Attendance",
            "Final Exam",
            "Total",
            "Grade",
            "Comment",
        ]
    ]

    for i, tc in enumerate(taken_courses, 1):
        row = [
            str(i),
            tc.student.user.username.upper(),
            tc.student.user.get_full_name().title(),
            f"{tc.assignment:.1f}",
            f"{tc.mid_exam:.1f}",
            f"{tc.quiz:.1f}",
            f"{tc.attendance:.1f}",
            f"{tc.final_exam:.1f}",
            f"{tc.total:.1f}",
            tc.grade,
            tc.comment,
        ]
        table_data.append(row)

    # Table style
    table_style = TableStyle(
        [
            # Header styling
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            # Data styling
            ("ALIGN", (0, 1), (0, -1), "CENTER"),
            ("ALIGN", (1, 1), (1, -1), "LEFT"),
            ("ALIGN", (2, 1), (2, -1), "LEFT"),
            ("ALIGN", (3, 1), (-2, -1), "CENTER"),
            ("FONTNAME", (3, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            # Grid lines
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("BOX", (0, 0), (-1, -1), 1, colors.black),
            # Alternate row colors
            ("BACKGROUND", (0, 1), (-1, 1), colors.lightgrey),
            ("BACKGROUND", (0, 3), (-1, 3), colors.lightgrey),
            ("BACKGROUND", (0, 5), (-1, 5), colors.lightgrey),
        ]
    )

    # Column widths
    col_widths = [
        0.8 * cm,
        2.5 * cm,
        4 * cm,
        2 * cm,
        2 * cm,
        1.5 * cm,
        2 * cm,
        2 * cm,
        2 * cm,
        1.5 * cm,
        2 * cm,
    ]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(table_style)
    Story.append(table)
    Story.append(Spacer(1, 1 * cm))

    # Summary section
    summary_style = ParagraphStyle(
        name="Summary", fontSize=10, alignment=TA_LEFT, spaceAfter=5
    )

    Story.append(Paragraph("<b>Summary:</b>", summary_style))
    Story.append(Paragraph(f"Total Students: {taken_courses.count()}", summary_style))
    Story.append(Paragraph(f"Passed: {no_of_pass}", summary_style))
    Story.append(Paragraph(f"Failed: {no_of_fail}", summary_style))
    Story.append(Paragraph(".1f", summary_style))

    # Signature section
    Story.append(Spacer(1, 2 * cm))

    signature_table_data = [
        ["Prepared by:", "Approved by:", "Date:"],
        [request.user.get_full_name(), "", timezone.now().strftime("%B %d, %Y")],
        ["Course Lecturer", "Department Head", ""],
    ]

    signature_table = Table(signature_table_data, colWidths=[5 * cm, 5 * cm, 4 * cm])
    signature_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 20),
                ("TOPPADDING", (0, 1), (-1, 1), 30),
            ]
        )
    )

    Story.append(signature_table)

    # Build PDF
    try:
        doc.build(Story)

        # Create file URL for download
        file_url = os.path.join(settings.MEDIA_URL, "result_sheets", fname)

        # Return file for download
        with open(flocation, "rb") as pdf_file:
            response = HttpResponse(pdf_file.read(), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{fname}"'
            return response

    except Exception as e:
        messages.error(request, f"Error generating PDF: {str(e)}")
        return redirect("assessment:grade_results")


@login_required
def quiz_bank_list(request):
    """List quiz banks for students, teachers, administrators, and principals (enhanced from clue system)."""
    is_teacher = hasattr(request.user, "teacher_profile")
    is_admin_or_principal = request.user.user_roles.filter(
        role__role_type__in=["super_admin", "admin", "principal", "school_admin"],
        status="active",
    ).exists()

    if is_teacher or is_admin_or_principal:
        # Teacher/Admin/Principal view - show quiz banks they can manage
        if is_teacher:
            teacher = request.user.teacher_profile
            # Get classes taught by this teacher
            taught_classes = Class.objects.filter(
                subject_assignments__teacher=teacher,
                subject_assignments__academic_session__is_current=True,
            ).distinct()
        else:
            # Admin/Principal can see all classes
            taught_classes = Class.objects.filter(
                academic_session__is_current=True
            ).distinct()

        # Get quiz banks for these classes
        quiz_banks = (
            QuestionBank.objects.filter(
                bank_type="quiz", academic_class__in=taught_classes
            )
            .select_related("subject", "academic_class")
            .order_by("-created_at")
        )

        # Apply filters
        class_id = request.GET.get("class_id")
        if class_id:
            quiz_banks = quiz_banks.filter(academic_class_id=class_id)

        subject_id = request.GET.get("subject_id")
        if subject_id:
            quiz_banks = quiz_banks.filter(subject_id=subject_id)

        status = request.GET.get("status")
        if status == "draft":
            quiz_banks = quiz_banks.filter(draft=True)
        elif status == "published":
            quiz_banks = quiz_banks.filter(draft=False)

        # Build quiz data for teachers
        quiz_data = []
        for quiz_bank in quiz_banks:
            # Get statistics
            total_attempts = QuizAttempt.objects.filter(question_bank=quiz_bank).count()
            completed_attempts = QuizAttempt.objects.filter(
                question_bank=quiz_bank, complete=True
            ).count()

            # Calculate average score
            avg_score = 0
            if completed_attempts > 0:
                avg_score = (
                    QuizAttempt.objects.filter(
                        question_bank=quiz_bank, complete=True
                    ).aggregate(avg=Avg("current_score"))["avg"]
                    or 0
                )

            quiz_data.append(
                {
                    "question_bank": quiz_bank,
                    "question_count": quiz_bank.questions.filter(
                        is_active=True
                    ).count(),
                    "total_attempts": total_attempts,
                    "completed_attempts": completed_attempts,
                    "avg_score": avg_score,
                    "can_attempt": True,  # Teachers can always attempt/manage
                }
            )

        context = {
            "is_teacher": True,
            "quiz_data": quiz_data,
            "taught_classes": taught_classes,
            "subjects": Subject.objects.filter(is_active=True),
        }

    else:
        # Student view - show available quiz banks
        if not hasattr(request.user, "student_profile"):
            messages.error(request, "Only students can access this page.")
            return redirect("users:dashboard")

        student = request.user.student_profile

        # Get quiz banks for student's class that aren't drafts
        quiz_banks = (
            QuestionBank.objects.filter(
                bank_type="quiz", academic_class=student.current_class, draft=False
            )
            .select_related("subject", "academic_class")
            .order_by("-created_at")
        )

        # Apply filters
        subject_id = request.GET.get("subject_id")
        if subject_id:
            quiz_banks = quiz_banks.filter(subject_id=subject_id)

        category = request.GET.get("category")
        if category:
            quiz_banks = quiz_banks.filter(category=category)

        # Build quiz data for students
        quiz_data = []
        for quiz_bank in quiz_banks:
            # Get student's attempts
            student_attempts = QuizAttempt.objects.filter(
                student=student, question_bank=quiz_bank
            )
            completed_attempts = student_attempts.filter(complete=True).count()
            best_score = 0
            if completed_attempts > 0:
                best_score = max(
                    attempt.get_percent_correct
                    for attempt in student_attempts.filter(complete=True)
                )

            # Check if student can attempt this quiz
            can_attempt = True
            if quiz_bank.single_attempt and completed_attempts > 0:
                can_attempt = False

            quiz_data.append(
                {
                    "question_bank": quiz_bank,
                    "question_count": quiz_bank.questions.filter(
                        is_active=True
                    ).count(),
                    "completed_attempts": completed_attempts,
                    "best_score": best_score,
                    "can_attempt": can_attempt,
                }
            )

        # Get available categories
        categories = QuestionBank.QUIZ_CATEGORIES

        context = {
            "is_teacher": False,
            "quiz_data": quiz_data,
            "subjects": Subject.objects.filter(is_active=True),
            "categories": categories,
        }

    return render(request, "assessment/quizzes/quiz_bank_list.html", context)


@login_required
def quiz_bank_detail(request, quiz_bank_id):
    """Show quiz bank details and allow starting quiz (enhanced from clue system)."""
    quiz_bank = get_object_or_404(QuestionBank, id=quiz_bank_id, bank_type="quiz")

    # Check permissions
    if hasattr(request.user, "student_profile"):
        student = request.user.student_profile
        if quiz_bank.academic_class != student.current_class:
            messages.error(request, "You do not have access to this quiz.")
            return redirect("assessment:quiz_bank_list")
    else:
        messages.error(request, "Only students can access quizzes.")
        return redirect("assessment:quiz_bank_list")

    # Check if student has already completed this quiz (single attempt)
    if quiz_bank.single_attempt:
        existing_attempt = QuizAttempt.objects.filter(
            student=request.user.student_profile, question_bank=quiz_bank, complete=True
        ).exists()
        if existing_attempt:
            messages.info(
                request,
                "You have already completed this quiz. You cannot attempt it again.",
            )
            return redirect("assessment:student_progress")

    # Get quiz statistics
    total_attempts = QuizAttempt.objects.filter(question_bank=quiz_bank).count()
    completed_attempts = QuizAttempt.objects.filter(
        question_bank=quiz_bank, complete=True
    ).count()

    # Calculate average score
    avg_score = 0
    if completed_attempts > 0:
        avg_score = (
            QuizAttempt.objects.filter(
                question_bank=quiz_bank, complete=True
            ).aggregate(avg=Avg("current_score"))["avg"]
            or 0
        )

    # Get student's attempts
    student_attempts = QuizAttempt.objects.filter(
        student=request.user.student_profile, question_bank=quiz_bank
    ).order_by("-start_time")

    context = {
        "quiz_bank": quiz_bank,
        "total_attempts": total_attempts,
        "completed_attempts": completed_attempts,
        "avg_score": avg_score,
        "question_count": quiz_bank.questions.filter(is_active=True).count(),
        "student_attempts": student_attempts,
        "can_attempt": not (
            quiz_bank.single_attempt and student_attempts.filter(complete=True).exists()
        ),
    }
    return render(request, "assessment/quizzes/quiz_bank_detail.html", context)


@login_required
def quiz_result(request, attempt_id):
    """Show quiz results."""
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)

    # Check permissions
    if hasattr(request.user, "student_profile"):
        if attempt.student != request.user.student_profile:
            messages.error(request, "You do not have permission to view this result.")
            return redirect("assessment:quiz_bank_list")
    elif hasattr(request.user, "teacher_profile"):
        teacher = request.user.teacher_profile
        if not Class.objects.filter(
            subject_assignments__teacher=teacher,
            subject_assignments__subject=attempt.question_bank.subject,
            subject_assignments__academic_session__is_current=True,
        ).exists():
            messages.error(request, "You do not have permission to view this result.")
            return redirect("assessment:quiz_bank_list")

    context = {
        "attempt": attempt,
        "questions_with_answers": attempt.get_questions_with_answers(),
        "show_answers": True,
    }
    return render(request, "assessment/quizzes/quiz_result.html", context)


@login_required
def student_progress(request):
    """Show student quiz progress."""
    if not hasattr(request.user, "student_profile"):
        messages.error(request, "Only students can view progress.")
        return redirect("assessment:quiz_bank_list")

    student = request.user.student_profile
    progress, _ = QuizProgress.objects.get_or_create(student=student)

    context = {
        "progress": progress,
        "category_scores": progress.list_category_scores(),
        "recent_attempts": progress.show_attempts()[:10],
    }
    return render(request, "assessment/quizzes/student_progress.html", context)


@login_required
@user_passes_test(is_teacher)
def course_registration_pdf_view(request, course_id):
    """
    Generate PDF course registration form (from clue system).
    """
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
    from reportlab.lib.units import inch, cm
    import os

    teacher = request.user.teacher_profile
    current_session = AcademicSession.objects.filter(is_current=True).first()

    if not current_session:
        messages.error(request, "No active academic session found.")
        return redirect("assessment:grade_results")

    # Verify teacher teaches this course
    course = get_object_or_404(Subject, id=course_id)
    if not Subject.objects.filter(
        id=course_id,
        subject_assignments__teacher=teacher,
        subject_assignments__academic_session=current_session,
    ).exists():
        messages.error(
            request,
            "You are not authorized to generate registration forms for this course.",
        )
        return redirect("assessment:grade_results")

    # Get students enrolled in this course
    taken_courses = TakenCourse.objects.filter(
        course=course, academic_session=current_session
    ).select_related("student__user")

    if not taken_courses.exists():
        messages.warning(request, "No students enrolled in this course.")
        return redirect("assessment:grade_results")

    # Create filename
    fname = f"{request.user.username}_{course.code}_registration_form.pdf"
    fname = fname.replace("/", "-")

    # Create PDF directory if it doesn't exist
    pdf_dir = os.path.join(settings.MEDIA_ROOT, "registration_forms")
    os.makedirs(pdf_dir, exist_ok=True)
    flocation = os.path.join(pdf_dir, fname)

    # Create PDF document
    doc = SimpleDocTemplate(
        flocation,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm,
    )

    styles = getSampleStyleSheet()

    Story = []

    # Header
    header_style = ParagraphStyle(
        name="Header",
        fontSize=14,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=20,
    )

    institution_name = getattr(settings, "INSTITUTION_NAME", "School Management System")
    Story.append(Paragraph(institution_name.upper(), header_style))

    department_name = getattr(settings, "DEPARTMENT_NAME", "Academic Department")
    dept_style = ParagraphStyle(
        name="Dept", fontSize=12, alignment=TA_CENTER, spaceAfter=30
    )
    Story.append(Paragraph(department_name.upper(), dept_style))

    # Title
    title_style = ParagraphStyle(
        name="Title",
        fontSize=12,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=30,
    )
    Story.append(Paragraph("STUDENT COURSE REGISTRATION FORM", title_style))

    # Student information
    student = (
        taken_courses.first().student
    )  # Get first student (assuming one student per request)

    info_data = [
        [
            f"Registration Number: {student.user.username.upper()}",
            f"Level: {getattr(student, 'level', 'N/A')}",
        ],
        [
            f"Name: {student.user.get_full_name().upper()}",
            f"Session: {current_session.session}",
        ],
    ]

    info_table = Table(info_data, colWidths=[8 * cm, 6 * cm])
    info_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    Story.append(info_table)
    Story.append(Spacer(1, 1 * cm))

    # Course registration table
    course_data = [
        ["S/No", "Course Code", "Course Title", "Credit Hours", "Lecturer Signature"],
        ["1", course.code.upper(), course.name, getattr(course, "credit_hours", 1), ""],
    ]

    course_table = Table(
        course_data, colWidths=[1 * cm, 3 * cm, 8 * cm, 2 * cm, 4 * cm]
    )
    course_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
            ]
        )
    )
    Story.append(course_table)
    Story.append(Spacer(1, 2 * cm))

    # Certification text
    cert_style = ParagraphStyle(
        name="Cert", fontSize=9, alignment=TA_JUSTIFY, spaceAfter=30
    )

    cert_text = f"""
    CERTIFICATION OF REGISTRATION: I certify that {student.user.get_full_name().upper()} has been duly registered for the course shown above in the {department_name} and that the course and credit hours registered are as approved by the department administration.
    """

    Story.append(Paragraph(cert_text, cert_style))

    # Signatures
    signature_data = [
        [
            "Student Signature:",
            "_______________________________",
            "Date:",
            "________________",
        ],
        [
            "Lecturer Signature:",
            "_______________________________",
            "Date:",
            "________________",
        ],
        [
            "Department Head:",
            "_______________________________",
            "Date:",
            "________________",
        ],
    ]

    signature_table = Table(signature_data, colWidths=[3 * cm, 6 * cm, 2 * cm, 5 * cm])
    signature_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ]
        )
    )
    Story.append(signature_table)

    # Build PDF
    try:
        doc.build(Story)

        # Return file for download
        with open(flocation, "rb") as pdf_file:
            response = HttpResponse(pdf_file.read(), content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{fname}"'
            return response

    except Exception as e:
        messages.error(request, f"Error generating PDF: {str(e)}")
        return redirect("assessment:grade_results")
