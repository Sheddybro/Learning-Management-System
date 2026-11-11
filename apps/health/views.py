from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
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
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _

from apps.core.mixins import InstitutionPermissionMixin

from .models import (
    HealthRecord,
    MedicalAppointment,
    Medication,
    HealthScreening,
    EmergencyContact,
)
from .forms import (
    HealthRecordForm,
    MedicalAppointmentForm,
    MedicationForm,
    HealthScreeningForm,
    EmergencyContactForm,
    HealthRecordSearchForm,
    MedicalAppointmentSearchForm,
    MedicationSearchForm,
    HealthScreeningSearchForm,
)


# =============================================================================
# MIXINS AND BASE CLASSES
# =============================================================================


class HealthAccessMixin(LoginRequiredMixin):
    """Base mixin for health app access control."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Check if user has health-related role
        user_roles = request.user.user_roles.all()
        health_roles = [
            "student",
            "teacher",
            "admin",
            "principal",
            "super_admin",
            "nurse",
            "health_staff",
        ]

        if not any(role.role.role_type in health_roles for role in user_roles):
            if not request.user.is_staff:
                messages.error(
                    request, _("You don't have permission to access health services.")
                )
                return redirect("users:dashboard")

        return super().dispatch(request, *args, **kwargs)


class NurseRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a nurse or health staff."""

    def test_func(self):
        user = self.request.user
        if user.is_staff:
            return True

        # Check if user has nurse or health staff role
        user_roles = user.user_roles.all()
        health_staff_roles = [
            "nurse",
            "health_staff",
            "admin",
            "principal",
            "super_admin",
        ]
        return any(role.role.role_type in health_staff_roles for role in user_roles)


class StudentRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a student."""

    def test_func(self):
        return hasattr(self.request.user, "student_profile")


# =============================================================================
# DASHBOARD VIEWS
# =============================================================================


class HealthDashboardView(HealthAccessMixin, View):
    """Health dashboard with comprehensive health overview."""

    def get(self, request):
        context = {}
        user = request.user

        # Role-specific context
        if hasattr(user, "student_profile"):
            context.update(self._get_student_context(user))
        elif self._is_health_staff(user):
            context.update(self._get_health_staff_context(user))
        else:
            context.update(self._get_general_context(user))

        return render(request, "health/dashboard/dashboard.html", context)

    def _is_health_staff(self, user):
        """Check if user is health staff."""
        if user.is_staff:
            return True
        user_roles = user.user_roles.all()
        health_staff_roles = [
            "nurse",
            "health_staff",
            "admin",
            "principal",
            "super_admin",
        ]
        return any(role.role.role_type in health_staff_roles for role in user_roles)

    def _get_student_context(self, user):
        """Get context for student health dashboard."""
        student = user.student_profile

        # Health record
        health_record = HealthRecord.objects.filter(student=student).first()

        # Recent appointments
        recent_appointments = MedicalAppointment.objects.filter(
            student=student
        ).order_by("-appointment_date")[:5]

        # Current medications
        current_medications = Medication.objects.filter(
            student=student, is_active=True
        ).order_by("start_date")

        # Upcoming screenings
        upcoming_screenings = HealthScreening.objects.filter(
            student=student,
            follow_up_required=True,
            follow_up_date__gte=timezone.now().date(),
        ).order_by("follow_up_date")[:3]

        return {
            "student": student,
            "health_record": health_record,
            "recent_appointments": recent_appointments,
            "current_medications": current_medications,
            "upcoming_screenings": upcoming_screenings,
            "emergency_contacts": EmergencyContact.objects.filter(
                student=student, is_active=True
            ),
        }

    def _get_health_staff_context(self, user):
        """Get context for health staff dashboard."""
        # Today's appointments
        today = timezone.now().date()
        today_appointments = (
            MedicalAppointment.objects.filter(appointment_date=today)
            .select_related("student")
            .order_by("appointment_time")
        )

        # Pending medications
        pending_medications = (
            Medication.objects.filter(
                administration_status="pending",
                start_date__lte=today,
                end_date__gte=today,
            )
            .select_related("student")
            .order_by("start_date")[:10]
        )

        # Overdue screenings
        overdue_screenings = (
            HealthScreening.objects.filter(
                follow_up_required=True,
                follow_up_date__lt=today,
                is_follow_up_overdue=True,
            )
            .select_related("student")
            .order_by("follow_up_date")[:10]
        )

        # Health statistics
        health_stats = self._get_health_statistics()

        return {
            "today_appointments": today_appointments,
            "pending_medications": pending_medications,
            "overdue_screenings": overdue_screenings,
            "health_stats": health_stats,
        }

    def _get_general_context(self, user):
        """Get context for general staff dashboard."""
        # Basic health overview
        total_students = HealthRecord.objects.count()
        total_appointments = MedicalAppointment.objects.filter(
            appointment_date__gte=timezone.now().date()
        ).count()
        active_medications = Medication.objects.filter(is_active=True).count()

        return {
            "total_students": total_students,
            "total_appointments": total_appointments,
            "active_medications": active_medications,
        }

    def _get_health_statistics(self):
        """Get comprehensive health statistics."""
        today = timezone.now().date()

        # Appointment statistics
        total_appointments = MedicalAppointment.objects.count()
        today_appointments = MedicalAppointment.objects.filter(
            appointment_date=today
        ).count()
        completed_appointments = MedicalAppointment.objects.filter(
            appointment_status="completed"
        ).count()

        # Medication statistics
        total_medications = Medication.objects.count()
        active_medications = Medication.objects.filter(is_active=True).count()
        pending_administrations = Medication.objects.filter(
            administration_status="pending"
        ).count()

        # Screening statistics
        total_screenings = HealthScreening.objects.count()
        pending_followups = HealthScreening.objects.filter(
            follow_up_required=True, follow_up_date__gte=today
        ).count()
        overdue_followups = HealthScreening.objects.filter(
            is_follow_up_overdue=True
        ).count()

        # Health record statistics
        total_health_records = HealthRecord.objects.count()
        students_with_insurance = HealthRecord.objects.filter(
            has_insurance=True
        ).count()

        return {
            "total_appointments": total_appointments,
            "today_appointments": today_appointments,
            "completed_appointments": completed_appointments,
            "appointment_completion_rate": (
                (completed_appointments / total_appointments * 100)
                if total_appointments > 0
                else 0
            ),
            "total_medications": total_medications,
            "active_medications": active_medications,
            "pending_administrations": pending_administrations,
            "total_screenings": total_screenings,
            "pending_followups": pending_followups,
            "overdue_followups": overdue_followups,
            "total_health_records": total_health_records,
            "students_with_insurance": students_with_insurance,
            "insurance_coverage_rate": (
                (students_with_insurance / total_health_records * 100)
                if total_health_records > 0
                else 0
            ),
        }


# =============================================================================
# HEALTH RECORD VIEWS
# =============================================================================


class HealthRecordListView(InstitutionPermissionMixin, ListView):
    """List all health records with search and filtering."""

    model = HealthRecord
    template_name = "health/records/record_list.html"
    context_object_name = "health_records"
    paginate_by = 20

    def get_queryset(self):
        queryset = HealthRecord.objects.select_related("student__user")

        # Apply search filters
        form = HealthRecordSearchForm(self.request.GET)
        if form.is_valid():
            student_name = form.cleaned_data.get("student_name")
            student_id = form.cleaned_data.get("student_id")
            blood_group = form.cleaned_data.get("blood_group")
            health_status = form.cleaned_data.get("health_status")
            has_insurance = form.cleaned_data.get("has_insurance")

            if student_name:
                queryset = queryset.filter(
                    Q(student__user__first_name__icontains=student_name)
                    | Q(student__user__last_name__icontains=student_name)
                )

            if student_id:
                queryset = queryset.filter(student__student_id__icontains=student_id)

            if blood_group:
                queryset = queryset.filter(blood_group=blood_group)

            if health_status:
                queryset = queryset.filter(current_health_status=health_status)

            if has_insurance is not None:
                queryset = queryset.filter(has_insurance=has_insurance)

        return queryset.order_by(
            "student__user__last_name", "student__user__first_name"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = HealthRecordSearchForm(self.request.GET)
        return context


class HealthRecordDetailView(InstitutionPermissionMixin, DetailView):
    """Health record detail view."""

    model = HealthRecord
    template_name = "health/records/record_detail.html"
    context_object_name = "health_record"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        health_record = self.object

        # Related data
        context["recent_appointments"] = MedicalAppointment.objects.filter(
            student=health_record.student
        ).order_by("-appointment_date")[:5]

        context["current_medications"] = Medication.objects.filter(
            student=health_record.student, is_active=True
        ).order_by("start_date")

        context["recent_screenings"] = HealthScreening.objects.filter(
            student=health_record.student
        ).order_by("-screening_date")[:5]

        context["emergency_contacts"] = EmergencyContact.objects.filter(
            student=health_record.student, is_active=True
        )

        return context


class HealthRecordCreateView(NurseRequiredMixin, CreateView):
    """Create a new health record."""

    model = HealthRecord
    form_class = HealthRecordForm
    template_name = "health/records/record_form.html"
    success_url = reverse_lazy("health:record_list")

    def form_valid(self, form):
        messages.success(self.request, _("Health record created successfully."))
        return super().form_valid(form)


class HealthRecordUpdateView(NurseRequiredMixin, UpdateView):
    """Update a health record."""

    model = HealthRecord
    form_class = HealthRecordForm
    template_name = "health/records/record_form.html"
    success_url = reverse_lazy("health:record_list")

    def form_valid(self, form):
        messages.success(self.request, _("Health record updated successfully."))
        return super().form_valid(form)


# =============================================================================
# MEDICAL APPOINTMENT VIEWS
# =============================================================================


class MedicalAppointmentListView(InstitutionPermissionMixin, ListView):
    """List all medical appointments with search and filtering."""

    model = MedicalAppointment
    template_name = "health/appointments/appointment_list.html"
    context_object_name = "appointments"
    paginate_by = 20

    def get_queryset(self):
        queryset = MedicalAppointment.objects.select_related("student__user")

        # Apply search filters
        form = MedicalAppointmentSearchForm(self.request.GET)
        if form.is_valid():
            student_name = form.cleaned_data.get("student_name")
            appointment_type = form.cleaned_data.get("appointment_type")
            appointment_status = form.cleaned_data.get("appointment_status")
            date_from = form.cleaned_data.get("date_from")
            date_to = form.cleaned_data.get("date_to")
            healthcare_provider = form.cleaned_data.get("healthcare_provider")

            if student_name:
                queryset = queryset.filter(
                    Q(student__user__first_name__icontains=student_name)
                    | Q(student__user__last_name__icontains=student_name)
                )

            if appointment_type:
                queryset = queryset.filter(appointment_type=appointment_type)

            if appointment_status:
                queryset = queryset.filter(appointment_status=appointment_status)

            if date_from:
                queryset = queryset.filter(appointment_date__gte=date_from)

            if date_to:
                queryset = queryset.filter(appointment_date__lte=date_to)

            if healthcare_provider:
                queryset = queryset.filter(
                    healthcare_provider__icontains=healthcare_provider
                )

        return queryset.order_by("-appointment_date", "-appointment_time")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = MedicalAppointmentSearchForm(self.request.GET)
        return context


class MedicalAppointmentDetailView(InstitutionPermissionMixin, DetailView):
    """Medical appointment detail view."""

    model = MedicalAppointment
    template_name = "health/appointments/appointment_detail.html"
    context_object_name = "appointment"


class MedicalAppointmentCreateView(NurseRequiredMixin, CreateView):
    """Create a new medical appointment."""

    model = MedicalAppointment
    form_class = MedicalAppointmentForm
    template_name = "health/appointments/appointment_form.html"
    success_url = reverse_lazy("health:appointment_list")

    def form_valid(self, form):
        messages.success(self.request, _("Medical appointment created successfully."))
        return super().form_valid(form)


class MedicalAppointmentUpdateView(NurseRequiredMixin, UpdateView):
    """Update a medical appointment."""

    model = MedicalAppointment
    form_class = MedicalAppointmentForm
    template_name = "health/appointments/appointment_form.html"
    success_url = reverse_lazy("health:appointment_list")

    def form_valid(self, form):
        messages.success(self.request, _("Medical appointment updated successfully."))
        return super().form_valid(form)


# =============================================================================
# MEDICATION VIEWS
# =============================================================================


class MedicationListView(InstitutionPermissionMixin, ListView):
    """List all medications with search and filtering."""

    model = Medication
    template_name = "health/medications/medication_list.html"
    context_object_name = "medications"
    paginate_by = 20

    def get_queryset(self):
        queryset = Medication.objects.select_related("student__user", "administered_by")

        # Apply search filters
        form = MedicationSearchForm(self.request.GET)
        if form.is_valid():
            student_name = form.cleaned_data.get("student_name")
            medication_name = form.cleaned_data.get("medication_name")
            medication_type = form.cleaned_data.get("medication_type")
            administration_status = form.cleaned_data.get("administration_status")
            is_active = form.cleaned_data.get("is_active")

            if student_name:
                queryset = queryset.filter(
                    Q(student__user__first_name__icontains=student_name)
                    | Q(student__user__last_name__icontains=student_name)
                )

            if medication_name:
                queryset = queryset.filter(medication_name__icontains=medication_name)

            if medication_type:
                queryset = queryset.filter(medication_type=medication_type)

            if administration_status:
                queryset = queryset.filter(administration_status=administration_status)

            if is_active is not None:
                queryset = queryset.filter(is_active=is_active)

        return queryset.order_by("-start_date", "student__user__last_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = MedicationSearchForm(self.request.GET)
        return context


class MedicationDetailView(InstitutionPermissionMixin, DetailView):
    """Medication detail view."""

    model = Medication
    template_name = "health/medications/medication_detail.html"
    context_object_name = "medication"


class MedicationCreateView(NurseRequiredMixin, CreateView):
    """Create a new medication record."""

    model = Medication
    form_class = MedicationForm
    template_name = "health/medications/medication_form.html"
    success_url = reverse_lazy("health:medication_list")

    def form_valid(self, form):
        messages.success(self.request, _("Medication record created successfully."))
        return super().form_valid(form)


class MedicationUpdateView(NurseRequiredMixin, UpdateView):
    """Update a medication record."""

    model = Medication
    form_class = MedicationForm
    template_name = "health/medications/medication_form.html"
    success_url = reverse_lazy("health:medication_list")

    def form_valid(self, form):
        messages.success(self.request, _("Medication record updated successfully."))
        return super().form_valid(form)


# =============================================================================
# HEALTH SCREENING VIEWS
# =============================================================================


class HealthScreeningListView(InstitutionPermissionMixin, ListView):
    """List all health screenings with search and filtering."""

    model = HealthScreening
    template_name = "health/screenings/screening_list.html"
    context_object_name = "screenings"
    paginate_by = 20

    def get_queryset(self):
        queryset = HealthScreening.objects.select_related(
            "student__user", "conducted_by"
        )

        # Apply search filters
        form = HealthScreeningSearchForm(self.request.GET)
        if form.is_valid():
            student_name = form.cleaned_data.get("student_name")
            screening_type = form.cleaned_data.get("screening_type")
            screening_result = form.cleaned_data.get("screening_result")
            date_from = form.cleaned_data.get("date_from")
            date_to = form.cleaned_data.get("date_to")
            follow_up_required = form.cleaned_data.get("follow_up_required")

            if student_name:
                queryset = queryset.filter(
                    Q(student__user__first_name__icontains=student_name)
                    | Q(student__user__last_name__icontains=student_name)
                )

            if screening_type:
                queryset = queryset.filter(screening_type=screening_type)

            if screening_result:
                queryset = queryset.filter(screening_result=screening_result)

            if date_from:
                queryset = queryset.filter(screening_date__gte=date_from)

            if date_to:
                queryset = queryset.filter(screening_date__lte=date_to)

            if follow_up_required is not None:
                queryset = queryset.filter(follow_up_required=follow_up_required)

        return queryset.order_by("-screening_date", "student__user__last_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = HealthScreeningSearchForm(self.request.GET)
        return context


class HealthScreeningDetailView(InstitutionPermissionMixin, DetailView):
    """Health screening detail view."""

    model = HealthScreening
    template_name = "health/screenings/screening_detail.html"
    context_object_name = "screening"


class HealthScreeningCreateView(NurseRequiredMixin, CreateView):
    """Create a new health screening."""

    model = HealthScreening
    form_class = HealthScreeningForm
    template_name = "health/screenings/screening_form.html"
    success_url = reverse_lazy("health:screening_list")

    def form_valid(self, form):
        messages.success(self.request, _("Health screening created successfully."))
        return super().form_valid(form)


class HealthScreeningUpdateView(NurseRequiredMixin, UpdateView):
    """Update a health screening."""

    model = HealthScreening
    form_class = HealthScreeningForm
    template_name = "health/screenings/screening_form.html"
    success_url = reverse_lazy("health:screening_list")

    def form_valid(self, form):
        messages.success(self.request, _("Health screening updated successfully."))
        return super().form_valid(form)


# =============================================================================
# EMERGENCY CONTACT VIEWS
# =============================================================================


class EmergencyContactListView(InstitutionPermissionMixin, ListView):
    """List all emergency contacts."""

    model = EmergencyContact
    template_name = "health/contacts/contact_list.html"
    context_object_name = "contacts"
    paginate_by = 20

    def get_queryset(self):
        queryset = EmergencyContact.objects.select_related("student__user")

        # Filter by student if provided
        student_id = self.request.GET.get("student")
        if student_id:
            queryset = queryset.filter(student_id=student_id)

        # Filter by priority if provided
        priority = self.request.GET.get("priority")
        if priority:
            queryset = queryset.filter(priority=priority)

        return queryset.order_by("student__user__last_name", "priority")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.academics.models import Student

        context["students"] = Student.objects.filter(status="active").order_by(
            "user__last_name"
        )
        return context


class EmergencyContactDetailView(InstitutionPermissionMixin, DetailView):
    """Emergency contact detail view."""

    model = EmergencyContact
    template_name = "health/contacts/contact_detail.html"
    context_object_name = "contact"


class EmergencyContactCreateView(NurseRequiredMixin, CreateView):
    """Create a new emergency contact."""

    model = EmergencyContact
    form_class = EmergencyContactForm
    template_name = "health/contacts/contact_form.html"
    success_url = reverse_lazy("health:contact_list")

    def form_valid(self, form):
        messages.success(self.request, _("Emergency contact created successfully."))
        return super().form_valid(form)


class EmergencyContactUpdateView(NurseRequiredMixin, UpdateView):
    """Update an emergency contact."""

    model = EmergencyContact
    form_class = EmergencyContactForm
    template_name = "health/contacts/contact_form.html"
    success_url = reverse_lazy("health:contact_list")

    def form_valid(self, form):
        messages.success(self.request, _("Emergency contact updated successfully."))
        return super().form_valid(form)


# =============================================================================
# STUDENT HEALTH VIEWS
# =============================================================================


class StudentHealthView(StudentRequiredMixin, View):
    """Student's personal health view."""

    def get(self, request):
        student = request.user.student_profile

        # Health record
        health_record = HealthRecord.objects.filter(student=student).first()

        # Recent appointments
        recent_appointments = MedicalAppointment.objects.filter(
            student=student
        ).order_by("-appointment_date")[:10]

        # Current medications
        current_medications = Medication.objects.filter(
            student=student, is_active=True
        ).order_by("start_date")

        # Health screenings
        health_screenings = HealthScreening.objects.filter(student=student).order_by(
            "-screening_date"
        )[:10]

        # Emergency contacts
        emergency_contacts = EmergencyContact.objects.filter(
            student=student, is_active=True
        )

        context = {
            "student": student,
            "health_record": health_record,
            "recent_appointments": recent_appointments,
            "current_medications": current_medications,
            "health_screenings": health_screenings,
            "emergency_contacts": emergency_contacts,
        }

        return render(request, "health/students/health_dashboard.html", context)


# =============================================================================
# API AND AJAX VIEWS
# =============================================================================


class GetStudentHealthRecordView(HealthAccessMixin, View):
    """AJAX view to get student health record."""

    def get(self, request):
        student_id = request.GET.get("student_id")

        if not student_id:
            return JsonResponse({"error": "Student ID required"}, status=400)

        try:
            health_record = HealthRecord.objects.get(student_id=student_id)
            data = {
                "blood_group": health_record.blood_group,
                "height_cm": health_record.height_cm,
                "weight_kg": health_record.weight_kg,
                "bmi": health_record.bmi,
                "allergies": health_record.allergies,
                "chronic_conditions": health_record.chronic_conditions,
                "current_health_status": health_record.current_health_status,
                "last_checkup_date": (
                    health_record.last_checkup_date.strftime("%Y-%m-%d")
                    if health_record.last_checkup_date
                    else None
                ),
            }
            return JsonResponse(data)
        except HealthRecord.DoesNotExist:
            return JsonResponse({"error": "Health record not found"}, status=404)


class UpdateMedicationStatusView(NurseRequiredMixin, View):
    """AJAX view to update medication administration status."""

    def post(self, request):
        import json

        try:
            data = json.loads(request.body)
            medication_id = data.get("medication_id")
            status = data.get("status")
            notes = data.get("notes", "")

            if not medication_id or not status:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Medication ID and status are required",
                    },
                    status=400,
                )

            medication = Medication.objects.get(id=medication_id)
            medication.administration_status = status
            medication.administration_notes = notes
            medication.administered_by = request.user
            medication.administration_date = timezone.now().date()
            medication.administration_time = timezone.now().time()
            medication.save()

            return JsonResponse(
                {"success": True, "message": f"Medication status updated to {status}"}
            )

        except Medication.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "Medication not found"}, status=404
            )
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)


class HealthReportsView(NurseRequiredMixin, View):
    """Health reports and analytics."""

    def get(self, request):
        # Health statistics
        health_stats = self._get_health_statistics()

        # Appointment trends
        appointment_trends = self._get_appointment_trends()

        # Medication usage
        medication_stats = self._get_medication_statistics()

        # Screening results
        screening_stats = self._get_screening_statistics()

        context = {
            "health_stats": health_stats,
            "appointment_trends": appointment_trends,
            "medication_stats": medication_stats,
            "screening_stats": screening_stats,
        }

        return render(request, "health/reports/health_reports.html", context)

    def _get_health_statistics(self):
        """Get overall health statistics."""
        total_students = HealthRecord.objects.count()
        students_with_allergies = HealthRecord.objects.exclude(allergies="").count()
        students_with_chronic_conditions = HealthRecord.objects.exclude(
            chronic_conditions=""
        ).count()
        students_with_insurance = HealthRecord.objects.filter(
            has_insurance=True
        ).count()

        return {
            "total_students": total_students,
            "students_with_allergies": students_with_allergies,
            "students_with_chronic_conditions": students_with_chronic_conditions,
            "students_with_insurance": students_with_insurance,
            "insurance_coverage_rate": (
                (students_with_insurance / total_students * 100)
                if total_students > 0
                else 0
            ),
        }

    def _get_appointment_trends(self):
        """Get appointment trends over time."""
        from django.db.models.functions import TruncMonth

        trends = (
            MedicalAppointment.objects.annotate(month=TruncMonth("appointment_date"))
            .values("month")
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=Q(appointment_status="completed")),
            )
            .order_by("month")[:12]
        )

        return list(trends)

    def _get_medication_statistics(self):
        """Get medication usage statistics."""
        total_medications = Medication.objects.count()
        active_medications = Medication.objects.filter(is_active=True).count()
        administered_today = Medication.objects.filter(
            administration_date=timezone.now().date(),
            administration_status="administered",
        ).count()

        # Most common medications
        common_medications = (
            Medication.objects.values("medication_name")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        return {
            "total_medications": total_medications,
            "active_medications": active_medications,
            "administered_today": administered_today,
            "common_medications": list(common_medications),
        }

    def _get_screening_statistics(self):
        """Get screening statistics."""
        total_screenings = HealthScreening.objects.count()
        normal_results = HealthScreening.objects.filter(
            screening_result="normal"
        ).count()
        abnormal_results = HealthScreening.objects.filter(
            screening_result="abnormal"
        ).count()
        needs_attention = HealthScreening.objects.filter(
            screening_result="needs_attention"
        ).count()
        pending_followups = HealthScreening.objects.filter(
            follow_up_required=True
        ).count()

        # Screening types breakdown
        screening_types = (
            HealthScreening.objects.values("screening_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return {
            "total_screenings": total_screenings,
            "normal_results": normal_results,
            "abnormal_results": abnormal_results,
            "needs_attention": needs_attention,
            "pending_followups": pending_followups,
            "screening_types": list(screening_types),
        }
