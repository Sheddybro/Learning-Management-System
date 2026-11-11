from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.views.generic.edit import FormView
from django.db.models import Q, Count, Avg
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.core.mixins import InstitutionPermissionMixin

from .models import (
    ActivityCategory,
    Activity,
    ActivityEnrollment,
    ActivityStaffAssignment,
    SportsTeam,
    Club,
    Competition,
    Equipment,
    ActivityBudget,
    ActivityAttendance,
    ActivityAchievement,
)
from .forms import (
    ActivityForm,
    ActivityEnrollmentForm,
    StudentActivityEnrollmentForm,
    ActivityStaffAssignmentForm,
    SportsTeamForm,
    ClubForm,
    CompetitionForm,
    EquipmentForm,
    ActivityBudgetForm,
    ActivityAttendanceForm,
    ActivityAttendanceBulkForm,
    ActivityAchievementForm,
    ActivitySearchForm,
)


class ActivityCoordinatorRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is an activity coordinator or admin"""

    def test_func(self):
        user = self.request.user
        # Teachers are not allowed to create activities, even if they coordinate them
        if hasattr(user, "teacher_profile"):
            return False
        return (
            user.is_staff
            or user.is_superuser
            or Activity.objects.filter(coordinator=user).exists()
        )


class ActivityListView(InstitutionPermissionMixin, ListView):
    model = Activity
    template_name = "activities/activity_list.html"
    context_object_name = "activities"
    paginate_by = 12

    def get_queryset(self):
        queryset = Activity.objects.select_related(
            "category", "coordinator", "academic_session"
        ).prefetch_related("enrollments")

        # Apply search and filters
        search_form = ActivitySearchForm(self.request.GET)
        if search_form.is_valid():
            search = search_form.cleaned_data.get("search")
            category = search_form.cleaned_data.get("category")
            activity_type = search_form.cleaned_data.get("activity_type")
            status = search_form.cleaned_data.get("status")
            start_date_from = search_form.cleaned_data.get("start_date_from")
            start_date_to = search_form.cleaned_data.get("start_date_to")
            fee_max = search_form.cleaned_data.get("fee_max")

            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                    | Q(venue__icontains=search)
                )

            if category:
                queryset = queryset.filter(category=category)

            if activity_type:
                queryset = queryset.filter(activity_type=activity_type)

            if status:
                queryset = queryset.filter(status=status)

            if start_date_from:
                queryset = queryset.filter(start_date__gte=start_date_from)

            if start_date_to:
                queryset = queryset.filter(start_date__lte=start_date_to)

            if fee_max is not None:
                queryset = queryset.filter(fee_amount__lte=fee_max)

        # Order by start date
        return queryset.order_by("-start_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = ActivitySearchForm(self.request.GET)
        context["categories"] = ActivityCategory.objects.filter(is_active=True)

        # Add enrollment status for each activity if user is a student
        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile
            enrolled_activity_ids = set(
                ActivityEnrollment.objects.filter(
                    student=student, status__in=["active", "pending"]
                ).values_list("activity_id", flat=True)
            )
            for activity in context["activities"]:
                activity.is_enrolled = activity.id in enrolled_activity_ids

        return context


class ActivityDetailView(InstitutionPermissionMixin, DetailView):
    model = Activity
    template_name = "activities/activity_detail.html"
    context_object_name = "activity"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self.object

        # Check if user is enrolled
        if hasattr(self.request.user, "student_profile"):
            context["enrollment"] = ActivityEnrollment.objects.filter(
                student=self.request.user.student_profile, activity=activity
            ).first()

        # Get staff assignments
        context["staff_assignments"] = activity.staff_assignments.select_related(
            "staff_member"
        )

        # Get related competitions
        context["competitions"] = activity.competitions.filter(is_active=True)

        # Get equipment assigned to this activity
        context["equipment"] = activity.equipment.all()

        return context


class ActivityCreateView(
    LoginRequiredMixin, ActivityCoordinatorRequiredMixin, CreateView
):
    model = Activity
    form_class = ActivityForm
    template_name = "activities/activity_form.html"
    success_url = reverse_lazy("activities:activity_list")

    def form_valid(self, form):
        messages.success(self.request, _("Activity created successfully."))
        return super().form_valid(form)


class ActivityUpdateView(
    LoginRequiredMixin, ActivityCoordinatorRequiredMixin, UpdateView
):
    model = Activity
    form_class = ActivityForm
    template_name = "activities/activity_form.html"

    def get_success_url(self):
        return reverse("activities:activity_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Activity updated successfully."))
        return super().form_valid(form)


class ActivityDeleteView(
    LoginRequiredMixin, ActivityCoordinatorRequiredMixin, DeleteView
):
    model = Activity
    template_name = "activities/activity_confirm_delete.html"
    success_url = reverse_lazy("activities:activity_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Activity deleted successfully."))
        return super().delete(request, *args, **kwargs)


@login_required
def activity_enroll(request, pk):
    """View for students to enroll in activities"""
    activity = get_object_or_404(Activity, pk=pk)

    # Check if user is a student
    if not hasattr(request.user, "student_profile"):
        messages.error(request, _("Only students can enroll in activities."))
        return redirect("activities:activity_detail", pk=pk)

    student = request.user.student_profile

    # Check if already enrolled
    existing_enrollment = ActivityEnrollment.objects.filter(
        student=student, activity=activity
    ).first()

    if existing_enrollment:
        if existing_enrollment.status == "cancelled":
            existing_enrollment.status = "pending"
            existing_enrollment.save()
            messages.success(
                request, _("Your enrollment request has been reactivated.")
            )
        else:
            messages.info(request, _("You are already enrolled in this activity."))
        return redirect("activities:activity_detail", pk=pk)

    if request.method == "POST":
        form = StudentActivityEnrollmentForm(request.POST)
        if form.is_valid():
            enrollment = form.save(commit=False)
            enrollment.student = student
            enrollment.activity = activity
            enrollment.save()
            messages.success(request, _("Successfully enrolled in the activity."))
            return redirect("activities:my_activities")
    else:
        form = StudentActivityEnrollmentForm()

    return render(
        request, "activities/activity_enroll.html", {"activity": activity, "form": form}
    )


@login_required
def activity_unenroll(request, pk):
    """View for students to unenroll from activities"""
    activity = get_object_or_404(Activity, pk=pk)

    if not hasattr(request.user, "student_profile"):
        messages.error(request, _("Only students can unenroll from activities."))
        return redirect("activities:activity_detail", pk=pk)

    enrollment = get_object_or_404(
        ActivityEnrollment,
        student=request.user.student_profile,
        activity=activity,
        status__in=["active", "pending"],
    )

    if request.method == "POST":
        enrollment.status = "cancelled"
        enrollment.save()
        messages.success(request, _("Successfully unenrolled from the activity."))
        return redirect("activities:my_activities")

    return render(
        request,
        "activities/activity_unenroll.html",
        {"activity": activity, "enrollment": enrollment},
    )


class MyActivitiesView(InstitutionPermissionMixin, ListView):
    """View for students to see their enrolled activities"""

    model = ActivityEnrollment
    template_name = "activities/my_activities.html"
    context_object_name = "enrollments"
    paginate_by = 10

    def get_queryset(self):
        if not hasattr(self.request.user, "student_profile"):
            return ActivityEnrollment.objects.none()

        return (
            ActivityEnrollment.objects.filter(student=self.request.user.student_profile)
            .select_related("activity__category")
            .order_by("-enrollment_date")
        )


class ActivityEnrollmentListView(InstitutionPermissionMixin, ListView):
    """View for coordinators to manage activity enrollments"""

    model = ActivityEnrollment
    template_name = "activities/enrollment_list.html"
    context_object_name = "enrollments"
    paginate_by = 20

    def get_queryset(self):
        activity_id = self.request.GET.get("activity")
        status = self.request.GET.get("status")

        queryset = ActivityEnrollment.objects.select_related(
            "student__user", "activity__category"
        )

        if activity_id:
            queryset = queryset.filter(activity_id=activity_id)

        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("-enrollment_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activities"] = Activity.objects.filter(
            coordinator=self.request.user
        ).order_by("title")
        return context


@login_required
def update_enrollment_status(request, pk):
    """AJAX view to update enrollment status"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"})

    enrollment = get_object_or_404(ActivityEnrollment, pk=pk)

    # Check permissions
    if not (request.user.is_staff or enrollment.activity.coordinator == request.user):
        return JsonResponse({"success": False, "error": "Permission denied"})

    new_status = request.POST.get("status")
    if new_status not in dict(ActivityEnrollment.EnrollmentStatus.choices):
        return JsonResponse({"success": False, "error": "Invalid status"})

    enrollment.status = new_status
    enrollment.save()

    return JsonResponse(
        {
            "success": True,
            "status": enrollment.get_status_display(),
            "status_class": enrollment.status,
        }
    )


class ActivityAttendanceView(
    LoginRequiredMixin, ActivityCoordinatorRequiredMixin, FormView
):
    """View for marking attendance"""

    template_name = "activities/activity_attendance.html"
    form_class = ActivityAttendanceBulkForm

    def dispatch(self, request, *args, **kwargs):
        self.activity = get_object_or_404(Activity, pk=self.kwargs["pk"])

        # Check if user can manage this activity
        if not (request.user.is_staff or self.activity.coordinator == request.user):
            messages.error(
                request, _("You do not have permission to manage this activity.")
            )
            return redirect("activities:activity_detail", pk=self.activity.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["activity"] = self.activity
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activity"] = self.activity

        # Get enrollments for this activity
        enrollments = (
            ActivityEnrollment.objects.filter(activity=self.activity, status="active")
            .select_related("student__user")
            .order_by("student__user__last_name")
        )

        # Get existing attendance for today if any
        session_date = self.request.GET.get("date", timezone.now().date())
        existing_attendance = ActivityAttendance.objects.filter(
            enrollment__activity=self.activity, session_date=session_date
        ).select_related("enrollment__student__user")

        attendance_dict = {att.enrollment_id: att for att in existing_attendance}

        # Combine enrollments with attendance
        attendance_data = []
        for enrollment in enrollments:
            attendance_record = attendance_dict.get(enrollment.id)
            attendance_data.append(
                {
                    "enrollment": enrollment,
                    "attendance": attendance_record,
                    "is_present": (
                        attendance_record.is_present if attendance_record else False
                    ),
                }
            )

        context["attendance_data"] = attendance_data
        context["session_date"] = session_date
        return context

    def form_valid(self, form):
        session_date = form.cleaned_data["session_date"]
        activity = form.cleaned_data["activity"]

        # Process attendance data from POST
        for key, value in self.request.POST.items():
            if key.startswith("present_"):
                enrollment_id = key.split("_")[1]
                is_present = value == "on"

                enrollment = get_object_or_404(
                    ActivityEnrollment, id=enrollment_id, activity=activity
                )

                attendance, created = ActivityAttendance.objects.get_or_create(
                    enrollment=enrollment,
                    session_date=session_date,
                    defaults={"is_present": is_present},
                )

                if not created:
                    attendance.is_present = is_present
                    attendance.save()

        messages.success(self.request, _("Attendance updated successfully."))
        return redirect("activities:activity_attendance", pk=activity.pk)


class EquipmentListView(InstitutionPermissionMixin, ListView):
    model = Equipment
    template_name = "activities/equipment_list.html"
    context_object_name = "equipment_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = Equipment.objects.all()

        # Filter by type, condition, availability
        equipment_type = self.request.GET.get("type")
        condition = self.request.GET.get("condition")
        available_only = self.request.GET.get("available")

        if equipment_type:
            queryset = queryset.filter(equipment_type=equipment_type)

        if condition:
            queryset = queryset.filter(condition=condition)

        if available_only:
            queryset = queryset.filter(quantity_available__gt=0)

        return queryset.order_by("equipment_type", "name")


class EquipmentCreateView(
    LoginRequiredMixin, ActivityCoordinatorRequiredMixin, CreateView
):
    model = Equipment
    form_class = EquipmentForm
    template_name = "activities/equipment_form.html"
    success_url = reverse_lazy("activities:equipment_list")

    def form_valid(self, form):
        messages.success(self.request, _("Equipment added successfully."))
        return super().form_valid(form)


class EquipmentUpdateView(
    LoginRequiredMixin, ActivityCoordinatorRequiredMixin, UpdateView
):
    model = Equipment
    form_class = EquipmentForm
    template_name = "activities/equipment_form.html"

    def get_success_url(self):
        return reverse("activities:equipment_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Equipment updated successfully."))
        return super().form_valid(form)


class ActivityBudgetListView(InstitutionPermissionMixin, ListView):
    model = ActivityBudget
    template_name = "activities/budget_list.html"
    context_object_name = "budgets"
    paginate_by = 20

    def get_queryset(self):
        queryset = ActivityBudget.objects.select_related("activity", "approved_by")

        activity_id = self.request.GET.get("activity")
        budget_type = self.request.GET.get("type")

        if activity_id:
            queryset = queryset.filter(activity_id=activity_id)

        if budget_type:
            queryset = queryset.filter(budget_type=budget_type)

        return queryset.order_by("-planned_date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Calculate totals
        budgets = context["budgets"]
        total_revenue = sum(b.amount for b in budgets if b.budget_type == "revenue")
        total_expense = sum(b.amount for b in budgets if b.budget_type == "expense")
        net_amount = total_revenue - total_expense

        context.update(
            {
                "total_revenue": total_revenue,
                "total_expense": total_expense,
                "net_amount": net_amount,
                "activities": Activity.objects.filter(coordinator=self.request.user),
            }
        )

        return context


class CompetitionListView(InstitutionPermissionMixin, ListView):
    model = Competition
    template_name = "activities/competition_list.html"
    context_object_name = "competitions"
    paginate_by = 10

    def get_queryset(self):
        return (
            Competition.objects.filter(is_active=True)
            .select_related("activity__category")
            .order_by("-start_date")
        )


class CompetitionDetailView(InstitutionPermissionMixin, DetailView):
    model = Competition
    template_name = "activities/competition_detail.html"
    context_object_name = "competition"


class CompetitionCreateView(
    LoginRequiredMixin, ActivityCoordinatorRequiredMixin, CreateView
):
    model = Competition
    form_class = CompetitionForm
    template_name = "activities/competition_form.html"
    success_url = reverse_lazy("activities:competition_list")

    def form_valid(self, form):
        messages.success(self.request, _("Competition created successfully."))
        return super().form_valid(form)


# AJAX views for dynamic content
def get_activity_enrollments(request, activity_id):
    """AJAX view to get enrollment data for an activity"""
    from apps.core.middleware import get_current_institution

    current_institution = get_current_institution()
    if not current_institution:
        return JsonResponse({"error": "No institution context"}, status=403)

    enrollments = (
        ActivityEnrollment.objects.filter(
            activity_id=activity_id, activity__institution=current_institution
        )
        .select_related("student__user")
        .order_by("student__user__last_name")
    )

    data = {
        "enrollments": [
            {
                "id": e.id,
                "student_name": str(e.student),
                "status": e.get_status_display(),
                "status_value": e.status,
                "enrollment_date": e.enrollment_date.strftime("%Y-%m-%d"),
                "payment_status": e.payment_status,
            }
            for e in enrollments
        ]
    }

    return JsonResponse(data)


def get_activity_stats(request, activity_id):
    """AJAX view to get activity statistics"""
    from apps.core.middleware import get_current_institution

    current_institution = get_current_institution()
    if not current_institution:
        return JsonResponse({"error": "No institution context"}, status=403)

    activity = get_object_or_404(
        Activity, id=activity_id, institution=current_institution
    )

    enrollments = ActivityEnrollment.objects.filter(activity=activity)
    total_enrolled = enrollments.count()
    active_enrolled = enrollments.filter(status="active").count()
    pending_enrolled = enrollments.filter(status="pending").count()

    # Attendance stats
    attendance_records = ActivityAttendance.objects.filter(
        enrollment__activity=activity, is_present=True
    )
    total_sessions = attendance_records.count()
    avg_participation = (
        attendance_records.aggregate(avg_rating=Avg("participation_rating"))[
            "avg_rating"
        ]
        or 0
    )

    data = {
        "total_enrolled": total_enrolled,
        "active_enrolled": active_enrolled,
        "pending_enrolled": pending_enrolled,
        "available_spots": activity.available_spots,
        "is_full": activity.is_full,
        "total_sessions": total_sessions,
        "avg_participation": round(avg_participation, 1) if avg_participation else 0,
    }

    return JsonResponse(data)
