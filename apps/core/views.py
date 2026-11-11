from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.views import View
from django.utils import timezone
import json
from django.db import IntegrityError, transaction

from .models import SystemConfig, Institution, InstitutionConfig
from .forms import (
    SystemConfigForm,
    SystemConfigBulkUpdateForm,
    InstitutionForm,
    InstitutionConfigForm,
    InstitutionConfigOverrideForm,
)
from .mixins import MultiInstitutionMixin, InstitutionPermissionMixin


class SystemConfigListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for System Configurations with filtering and search.
    """

    model = SystemConfig
    template_name = "core/config/list.html"
    context_object_name = "configs"
    paginate_by = 20
    permission_required = "core.view_systemconfig"

    def get_queryset(self):
        from apps.core.middleware import get_user_accessible_institutions

        if self.request.user.is_superuser:
            queryset = SystemConfig.objects.all()
        else:
            accessible_insts = get_user_accessible_institutions(self.request.user)
            queryset = SystemConfig.objects.filter(institution__in=accessible_insts)

        # Apply filters
        config_type = self.request.GET.get("config_type")
        status = self.request.GET.get("status")
        is_public = self.request.GET.get("is_public")
        search = self.request.GET.get("search")

        if config_type and config_type != "all":
            queryset = queryset.filter(config_type=config_type)

        if status and status != "all":
            queryset = queryset.filter(status=status)

        if is_public and is_public != "all":
            queryset = queryset.filter(is_public=is_public == "true")

        if search:
            queryset = queryset.filter(
                Q(key__icontains=search)
                | Q(description__icontains=search)
                | Q(value__icontains=search)
            )

        return queryset.order_by("config_type", "key")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter options
        context["config_types"] = SystemConfig.ConfigType.choices
        context["status_choices"] = SystemConfig.Status.choices

        # Add current filter values
        context["current_filters"] = {
            "config_type": self.request.GET.get("config_type", ""),
            "status": self.request.GET.get("status", ""),
            "is_public": self.request.GET.get("is_public", ""),
            "search": self.request.GET.get("search", ""),
        }

        # Add statistics
        from apps.core.middleware import get_user_accessible_institutions

        if self.request.user.is_superuser:
            context["total_configs"] = SystemConfig.objects.count()
            context["active_configs"] = SystemConfig.objects.filter(
                status="active"
            ).count()
        else:
            accessible_insts = get_user_accessible_institutions(self.request.user)
            context["total_configs"] = SystemConfig.objects.filter(
                institution__in=accessible_insts
            ).count()
            context["active_configs"] = SystemConfig.objects.filter(
                institution__in=accessible_insts, status="active"
            ).count()

        return context


class SystemConfigCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Create view for System Configuration.
    """

    model = SystemConfig
    form_class = SystemConfigForm
    template_name = "core/config/form.html"
    permission_required = "core.add_systemconfig"

    def get_success_url(self):
        messages.success(self.request, _("System configuration created successfully!"))
        return reverse_lazy("core:config_list")

    def form_valid(self, form):
        # Set created_by if the model had such a field
        return super().form_valid(form)


class SystemConfigUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Update view for System Configuration.
    """

    model = SystemConfig
    form_class = SystemConfigForm
    template_name = "core/config/form.html"
    permission_required = "core.change_systemconfig"

    def get_success_url(self):
        messages.success(self.request, _("System configuration updated successfully!"))
        return reverse_lazy("core:config_list")


class SystemConfigDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detail view for System Configuration.
    """

    model = SystemConfig
    template_name = "core/config/detail.html"
    context_object_name = "config"
    permission_required = "core.view_systemconfig"


class SystemConfigDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Delete view for System Configuration.
    """

    model = SystemConfig
    template_name = "core/config/confirm_delete.html"
    permission_required = "core.delete_systemconfig"

    def get_success_url(self):
        messages.success(self.request, _("System configuration deleted successfully!"))
        return reverse_lazy("core:config_list")


class SystemConfigBulkUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Bulk update view for multiple System Configurations.
    """

    permission_required = "core.change_systemconfig"

    def get(self, request, *args, **kwargs):
        config_ids = request.GET.getlist("config_ids")
        if not config_ids:
            messages.error(request, _("No configurations selected for bulk update."))
            return redirect("core:config_list")

        configs = SystemConfig.objects.filter(id__in=config_ids)
        form = SystemConfigBulkUpdateForm(configs=configs)

        context = {
            "form": form,
            "configs": configs,
            "page_title": _("Bulk Update Configurations"),
        }

        return render(request, "core/config/bulk_update.html", context)

    def post(self, request, *args, **kwargs):
        config_ids = request.POST.getlist("config_ids")
        configs = SystemConfig.objects.filter(id__in=config_ids)
        form = SystemConfigBulkUpdateForm(request.POST, configs=configs)

        if form.is_valid():
            updated_count = 0
            for config in configs:
                field_name = f"config_{config.id}"
                if field_name in form.cleaned_data:
                    new_value = form.cleaned_data[field_name]
                    if new_value != config.value:
                        config.value = new_value
                        config.save()
                        updated_count += 1

            messages.success(
                request, _(f"Successfully updated {updated_count} configuration(s).")
            )
            return redirect("core:config_list")
        else:
            context = {
                "form": form,
                "configs": configs,
                "page_title": _("Bulk Update Configurations"),
            }
            return render(request, "core/config/bulk_update.html", context)


class SystemConfigDashboardView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Dashboard view showing configuration statistics and categories.
    """

    permission_required = "core.view_systemconfig"

    def get(self, request, *args, **kwargs):
        # Get configuration statistics by type
        config_stats = {}
        for config_type, display_name in SystemConfig.ConfigType.choices:
            count = SystemConfig.objects.filter(config_type=config_type).count()
            active_count = SystemConfig.objects.filter(
                config_type=config_type, status="active"
            ).count()
            config_stats[config_type] = {
                "total": count,
                "active": active_count,
                "inactive": count - active_count,
                "display_name": display_name,
            }

        # Recent changes (last 10)
        from apps.core.middleware import get_user_accessible_institutions

        if request.user.is_superuser:
            recent_configs = SystemConfig.objects.order_by("-updated_at")[:10]
            public_configs = SystemConfig.objects.filter(is_public=True).count()
            private_configs = SystemConfig.objects.filter(is_public=False).count()
        else:
            accessible_insts = get_user_accessible_institutions(request.user)
            recent_configs = SystemConfig.objects.filter(
                institution__in=accessible_insts
            ).order_by("-updated_at")[:10]
            public_configs = SystemConfig.objects.filter(
                institution__in=accessible_insts, is_public=True
            ).count()
            private_configs = SystemConfig.objects.filter(
                institution__in=accessible_insts, is_public=False
            ).count()

        context = {
            "config_stats": config_stats,
            "recent_configs": recent_configs,
            "public_configs": public_configs,
            "private_configs": private_configs,
            "total_configs": SystemConfig.objects.count(),
            "page_title": _("Configuration Dashboard"),
        }

        return render(request, "core/config/dashboard.html", context)


def get_config_value(request, config_key):
    """
    API endpoint to get a configuration value by key.
    """
    try:
        config = SystemConfig.objects.get(key=config_key, status="active")
        return JsonResponse(
            {
                "key": config.key,
                "value": config.value,
                "config_type": config.config_type,
                "description": config.description,
            }
        )
    except SystemConfig.DoesNotExist:
        return JsonResponse({"error": "Configuration not found"}, status=404)


def validate_config_value(request):
    """
    API endpoint to validate configuration value format.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    value = request.POST.get("value", "")
    config_type = request.POST.get("config_type", "")

    try:
        # Basic JSON validation
        if value.strip().startswith(("{", "[", '"')):
            json.loads(value)
            is_valid = True
            error_message = ""
        else:
            # Try to parse as simple values
            import ast

            ast.literal_eval(value)
            is_valid = True
            error_message = ""
    except (json.JSONDecodeError, ValueError, SyntaxError) as e:
        is_valid = False
        error_message = str(e)

    return JsonResponse(
        {
            "is_valid": is_valid,
            "error_message": error_message,
        }
    )


def export_configs(request):
    """
    Export system configurations to JSON format.
    """
    configs = SystemConfig.objects.all().values(
        "key",
        "value",
        "config_type",
        "description",
        "is_public",
        "is_encrypted",
        "status",
    )

    data = {
        "exported_at": (
            request.user.get_full_name() if request.user.is_authenticated else "System"
        ),
        "configurations": list(configs),
    }

    response = JsonResponse(data, safe=False)
    response["Content-Disposition"] = 'attachment; filename="system_configs.json"'
    return response


def import_configs(request):
    """
    Import system configurations from JSON file.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if "config_file" not in request.FILES:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    config_file = request.FILES["config_file"]

    try:
        data = json.load(config_file)
        configs_data = data.get("configurations", [])

        imported_count = 0
        updated_count = 0

        for config_data in configs_data:
            key = config_data.get("key")
            if not key:
                continue

            config, created = SystemConfig.objects.get_or_create(
                key=key, defaults=config_data
            )

            if created:
                imported_count += 1
            else:
                # Update existing config fields
                updated = False
                for field, value in config_data.items():
                    if field in [
                        "value",
                        "config_type",
                        "description",
                        "is_public",
                        "is_encrypted",
                        "status",
                    ]:
                        if getattr(config, field) != value:
                            setattr(config, field, value)
                            updated = True
                if updated:
                    config.save()
                    updated_count += 1

        return JsonResponse({"imported": imported_count, "updated": updated_count})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


class InstitutionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for Institution.
    """

    model = Institution
    template_name = "core/institutions/list.html"
    context_object_name = "institutions"
    paginate_by = 20
    permission_required = "core.view_institution"

    def get_queryset(self):
        queryset = Institution.objects.all()
        # Apply simple ordering
        return queryset.order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add filter options
        context["institution_types"] = Institution.InstitutionType.choices
        context["ownership_types"] = Institution.OwnershipType.choices
        context["status_choices"] = Institution.Status.choices

        # Add current filter values
        context["current_filters"] = {
            "institution_type": self.request.GET.get("institution_type", ""),
            "ownership_type": self.request.GET.get("ownership_type", ""),
            "status": self.request.GET.get("status", ""),
            "is_active": self.request.GET.get("is_active", ""),
            "search": self.request.GET.get("search", ""),
        }

        # Add statistics
        context["total_institutions"] = Institution.objects.count()
        context["active_institutions"] = Institution.objects.filter(
            is_active=True
        ).count()

        return context


class InstitutionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Create view for Institution.
    """

    model = Institution
    form_class = InstitutionForm
    template_name = "core/institutions/form.html"
    permission_required = "core.add_institution"

    def get_success_url(self):
        messages.success(self.request, _("Institution created successfully!"))
        return reverse_lazy("core:institution_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class InstitutionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Update view for Institution.
    """

    model = Institution
    form_class = InstitutionForm
    template_name = "core/institutions/form.html"
    permission_required = "core.change_institution"

    def get_success_url(self):
        messages.success(self.request, _("Institution updated successfully!"))
        return reverse_lazy("core:institution_list")


class InstitutionDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detail view for Institution.
    """

    model = Institution
    template_name = "core/institutions/detail.html"
    context_object_name = "institution"
    permission_required = "core.view_institution"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        institution = self.object

        # Add institution statistics
        context["student_count"] = institution.current_student_count
        context["staff_count"] = institution.current_staff_count
        context["utilization_rate"] = institution.utilization_rate

        # Add configuration overrides
        context["config_overrides"] = InstitutionConfig.objects.filter(
            institution=institution, is_active=True
        ).select_related("system_config")

        return context


class InstitutionDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Delete view for Institution.
    """

    model = Institution
    template_name = "core/institutions/confirm_delete.html"
    permission_required = "core.delete_institution"

    def get_success_url(self):
        messages.success(self.request, _("Institution deleted successfully!"))
        return reverse_lazy("core:institution_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            with transaction.atomic():
                response = super().delete(request, *args, **kwargs)
            return response
        except IntegrityError as e:
            messages.error(
                request,
                _(
                    "Cannot delete institution because related records exist. Remove dependent records first or archive the institution."
                ),
            )
            return redirect(
                request.META.get("HTTP_REFERER", reverse_lazy("core:institution_list"))
            )


class InstitutionConfigOverrideView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    View for managing institution-specific configuration overrides.
    """

    permission_required = "core.change_institution"

    def get(self, request, institution_id, *args, **kwargs):
        institution = get_object_or_404(Institution, id=institution_id)
        form = InstitutionConfigOverrideForm(institution=institution)

        context = {
            "institution": institution,
            "form": form,
            "page_title": _("Configuration Overrides"),
        }

        return render(request, "core/institutions/config_overrides.html", context)

    def post(self, request, institution_id, *args, **kwargs):
        institution = get_object_or_404(Institution, id=institution_id)
        form = InstitutionConfigOverrideForm(request.POST, institution=institution)

        if form.is_valid():
            updated_count = 0
            created_count = 0

            for field_name, value in form.cleaned_data:
                if field_name.startswith("config_") and value:
                    config_id = field_name.replace("config_", "")
                    try:
                        system_config = SystemConfig.objects.get(id=config_id)

                        # Check if override already exists
                        institution_config, created = (
                            InstitutionConfig.objects.get_or_create(
                                institution=institution,
                                system_config=system_config,
                                defaults={"override_value": value, "is_active": True},
                            )
                        )

                        if not created:
                            # Update existing override
                            if institution_config.override_value != value:
                                institution_config.override_value = value
                                institution_config.save()
                                updated_count += 1
                        else:
                            created_count += 1

                    except SystemConfig.DoesNotExist:
                        continue

            messages.success(
                request,
                _(
                    f"Successfully created {created_count} and updated {updated_count} configuration override(s)."
                ),
            )
            return redirect("core:institution_detail", pk=institution_id)
        else:
            context = {
                "institution": institution,
                "form": form,
                "page_title": _("Configuration Overrides"),
            }
            return render(request, "core/institutions/config_overrides.html", context)


class InstitutionSwitcherView(LoginRequiredMixin, View):
    """
    View for switching between institutions (for users with access to multiple institutions).
    """

    template_name = "core/institution_switcher.html"

    def get(self, request, *args, **kwargs):
        from .middleware import (
            get_user_accessible_institutions,
            get_current_institution,
        )

        user = request.user

        # Check if user can switch institutions
        if user.is_superuser:
            institutions = Institution.objects.filter(is_active=True)
        else:
            institutions = get_user_accessible_institutions(user)

        # Calculate totals for statistics
        total_students = sum(
            institution.current_student_count for institution in institutions
        )
        total_staff = sum(
            institution.current_staff_count for institution in institutions
        )

        context = {
            "institutions": institutions,
            "current_institution": get_current_institution(),
            "can_switch_institutions": user.is_superuser or institutions.count() > 1,
            "total_students": total_students,
            "total_staff": total_staff,
            "page_title": _("Select Institution"),
        }

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        institution_id = request.POST.get("institution")

        if institution_id:
            try:
                from .middleware import user_can_access_institution

                institution = Institution.objects.get(id=institution_id, is_active=True)

                # Check permission
                if user_can_access_institution(request.user, institution):
                    # Set in session
                    request.session["current_institution_id"] = str(institution.id)
                    request.session.modified = True

                    messages.success(request, _("Institution switched successfully."))
                    return redirect("users:dashboard")
                else:
                    messages.error(
                        request,
                        _("You don't have permission to access this institution."),
                    )

            except Institution.DoesNotExist:
                messages.error(request, _("Selected institution not found."))

        return redirect("core:institution_select")


class SuperAdminDashboardView(
    MultiInstitutionMixin, LoginRequiredMixin, PermissionRequiredMixin, View
):
    """
    Super Administrator dashboard showing system-wide metrics and institution overview.
    """

    permission_required = "core.view_institution"  # Could be more specific

    def get(self, request, *args, **kwargs):
        # Institution statistics
        total_institutions = Institution.objects.count()
        active_institutions = Institution.objects.filter(is_active=True).count()
        inactive_institutions = total_institutions - active_institutions

        # System-wide user statistics
        from apps.users.models import User

        total_users = User.objects.filter(is_active=True).count()

        # Configuration statistics
        total_configs = SystemConfig.objects.count()
        active_configs = SystemConfig.objects.filter(status="active").count()

        # Academic overview statistics (aggregated across all institutions)
        academic_stats = self._get_academic_overview_stats()

        # Recent institution changes
        recent_institutions = Institution.objects.order_by("-updated_at")[:5]

        # System health indicators
        from apps.analytics.models import KPIMeasurement, KPI

        system_kpis = KPI.objects.filter(category="system", status="active")[:6]
        kpi_data = {}
        for kpi in system_kpis:
            latest_measurement = (
                KPIMeasurement.objects.filter(kpi=kpi).order_by("-measured_at").first()
            )
            if latest_measurement:
                kpi_data[kpi.id] = latest_measurement

        # Recent audit logs
        from apps.audit.models import AuditLog

        recent_audits = AuditLog.objects.order_by("-timestamp")[:10]

        context = {
            "total_institutions": total_institutions,
            "active_institutions": active_institutions,
            "inactive_institutions": inactive_institutions,
            "total_users": total_users,
            "total_configs": total_configs,
            "active_configs": active_configs,
            "academic_stats": academic_stats,
            "recent_institutions": recent_institutions,
            "system_kpis": system_kpis,
            "kpi_data": kpi_data,
            "recent_audits": recent_audits,
            "page_title": _("Super Administrator Dashboard"),
        }

        return render(request, "core/dashboard/super_admin.html", context)

    def _get_academic_overview_stats(self):
        """Get aggregated academic statistics across all institutions."""
        from apps.academics.models import (
            Student,
            Teacher,
            Class,
            Department,
            AcademicSession,
            Enrollment,
        )

        try:
            return {
                "total_students": Student.objects.filter(status="active").count(),
                "total_teachers": Teacher.objects.filter(status="active").count(),
                "total_classes": Class.objects.filter(status="active").count(),
                "total_departments": Department.objects.filter(status="active").count(),
                "total_sessions": AcademicSession.objects.filter(
                    status="active"
                ).count(),
                "total_enrollments": Enrollment.objects.filter(status="active").count(),
            }
        except Exception:
            # Fallback if tables don't exist yet or there are issues
            return {
                "total_students": 0,
                "total_teachers": 0,
                "total_classes": 0,
                "total_departments": 0,
                "total_sessions": 0,
                "total_enrollments": 0,
            }


class SchoolAdminDashboardView(InstitutionPermissionMixin, LoginRequiredMixin, View):
    """
    School Administrator dashboard showing school-specific metrics and operations overview.
    """

    def get(self, request, *args, **kwargs):
        user = request.user

        # Check if user has school admin role or institution-level permission
        is_school_admin = (
            user.has_perm("core.change_institution")
            or user.user_roles.filter(
                role__role_type__in=["admin", "principal", "school_admin"]
            ).exists()
        )

        if not is_school_admin and not user.is_staff:
            messages.error(
                request,
                _(
                    "You don't have permission to access the school administrator dashboard."
                ),
            )
            return redirect("users:dashboard")

        # Check if user is a principal for role-specific content
        from apps.users.utils import has_role_or_perm

        is_principal = has_role_or_perm(
            user, perm="core.change_institution", role_type="principal"
        )

        # Get current institution
        from .middleware import get_current_institution

        current_institution = get_current_institution()

        # Get current academic session
        from apps.academics.models import AcademicSession

        current_session = AcademicSession.objects.filter(is_current=True).first()

        # School Statistics - FILTERED BY INSTITUTION
        total_students = 0
        total_teachers = 0
        total_classes = 0
        total_subjects = 0

        if current_session:
            from apps.academics.models import Student, Teacher, Class, Subject

            total_students = Student.objects.filter(
                institution=current_institution, status="active"
            ).count()
            total_teachers = Teacher.objects.filter(
                institution=current_institution, status="active"
            ).count()
            total_classes = Class.objects.filter(
                institution=current_institution, status="active"
            ).count()
            total_subjects = Subject.objects.filter(
                institution=current_institution, status="active"
            ).count()

        # Financial Overview - FILTERED BY INSTITUTION
        from apps.finance.models import Invoice, Payment, Expense

        total_revenue = 0
        total_expenses = 0
        pending_payments = 0

        if current_session:
            # Calculate total revenue from paid invoices
            paid_invoices = Invoice.objects.filter(
                academic_session=current_session,
                student__institution=current_institution,
                status="paid",
            )
            total_revenue = sum(invoice.amount_paid for invoice in paid_invoices)

            # Calculate total expenses (filter by expense date range within current session)
            expenses = Expense.objects.filter(
                expense_date__range=(
                    current_session.start_date,
                    current_session.end_date,
                ),
                institution=current_institution,
                status="active",
            )
            total_expenses = sum(expense.amount for expense in expenses)

            # Calculate pending payments
            pending_invoices = Invoice.objects.filter(
                academic_session=current_session,
                student__institution=current_institution,
                status__in=["issued", "partial"],
            )
            pending_payments = sum(invoice.balance_due for invoice in pending_invoices)

        # Attendance Overview
        attendance_rate = 0
        if current_session:
            from apps.attendance.models import AttendanceSummary

            # Get average attendance for current month
            current_month = timezone.now().month
            current_year = timezone.now().year

            monthly_summaries = AttendanceSummary.objects.filter(
                academic_session=current_session, month=current_month, year=current_year
            )

            if monthly_summaries.exists():
                total_percentage = sum(
                    summary.attendance_percentage for summary in monthly_summaries
                )
                attendance_rate = round(total_percentage / monthly_summaries.count(), 1)

        # Recent Applications - FILTERED BY INSTITUTION
        from apps.users.models import StudentApplication, StaffApplication

        pending_student_applications = StudentApplication.objects.filter(
            application_status__in=["pending", "under_review"],
            institution=current_institution,
        ).order_by("-application_date")[:5]

        pending_staff_applications = StaffApplication.objects.filter(
            application_status__in=["pending", "under_review"],
            institution=current_institution,
        ).order_by("-application_date")[:5]

        # Recent Announcements - FILTERED BY INSTITUTION
        from apps.communication.models import Announcement

        recent_announcements = Announcement.objects.filter(
            is_published=True, status="active", institution=current_institution
        ).order_by("-published_at")[:5]

        # System Health
        from apps.analytics.models import KPIMeasurement, KPI

        school_kpis = KPI.objects.filter(
            category__in=["academic", "financial", "operational"], status="active"
        )[:8]

        kpi_data = {}
        for kpi in school_kpis:
            latest_measurement = (
                KPIMeasurement.objects.filter(kpi=kpi).order_by("-measured_at").first()
            )
            if latest_measurement:
                kpi_data[kpi.id] = latest_measurement

        # Principal-specific data
        principal_stats = {}
        if is_principal:
            # Academic performance metrics
            from apps.assessment.models import Result

            if current_session:
                # Average class performance
                results = Result.objects.filter(
                    academic_session=current_session, exam_type__is_final=True
                )
                if results.exists():
                    avg_percentage = results.aggregate(avg=models.Avg("percentage"))[
                        "avg"
                    ]
                    principal_stats["avg_class_performance"] = round(
                        avg_percentage or 0, 1
                    )

                # Students at risk (below 50%)
                at_risk_count = results.filter(percentage__lt=50).count()
                principal_stats["students_at_risk"] = at_risk_count

            # Behavior incidents this month
            from apps.academics.models import BehaviorRecord

            current_month = timezone.now().replace(day=1)
            next_month = (current_month + timezone.timedelta(days=32)).replace(day=1)
            monthly_incidents = BehaviorRecord.objects.filter(
                incident_date__gte=current_month, incident_date__lt=next_month
            ).count()
            principal_stats["monthly_behavior_incidents"] = monthly_incidents

            # Academic warnings
            from apps.academic.models import AcademicWarning

            active_warnings = AcademicWarning.objects.filter(is_resolved=False).count()
            principal_stats["active_academic_warnings"] = active_warnings

        # Quick Actions Data
        quick_stats = {
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_classes": total_classes,
            "total_subjects": total_subjects,
            "attendance_rate": attendance_rate,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "pending_payments": pending_payments,
            "pending_student_apps": pending_student_applications.count(),
            "pending_staff_apps": pending_staff_applications.count(),
        }

        context = {
            "current_session": current_session,
            "quick_stats": quick_stats,
            "pending_student_applications": pending_student_applications,
            "pending_staff_applications": pending_staff_applications,
            "recent_announcements": recent_announcements,
            "school_kpis": school_kpis,
            "kpi_data": kpi_data,
            "is_principal": is_principal,
            "principal_stats": principal_stats,
            "page_title": (
                _("Principal Dashboard")
                if is_principal
                else _("School Administrator Dashboard")
            ),
        }

        # Use different template for principal
        template_name = (
            "principal/principal_dashboard.html"
            if is_principal
            else "core/dashboard/school_admin.html"
        )
        return render(request, template_name, context)


class PrincipalPerformanceMonitoringView(LoginRequiredMixin, View):
    """
    Principal view for monitoring academic performance across the school.
    """

    def get(self, request, *args, **kwargs):
        user = request.user

        # Check if user is a principal
        if (
            not has_role_or_perm(
                user, perm="core.change_institution", role_type="principal"
            )
            and not user.is_staff
        ):
            messages.error(request, _("You don't have permission to access this page."))
            return redirect("users:dashboard")

        from apps.academics.models import AcademicSession, Class, Student
        from apps.assessment.models import Result, Exam
        from apps.analytics.models import KPIMeasurement, KPI

        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Performance data
        performance_data = {
            "grade_distribution": {},
            "subject_performance": {},
            "class_performance": [],
            "trends": [],
        }

        if current_session:
            # Grade distribution
            results = Result.objects.filter(
                academic_session=current_session, exam_type__is_final=True
            ).select_related("grade")

            grade_counts = {}
            for result in results:
                grade_name = result.grade.grade if result.grade else "No Grade"
                grade_counts[grade_name] = grade_counts.get(grade_name, 0) + 1

            performance_data["grade_distribution"] = grade_counts

            # Subject-wise performance
            from django.db.models import Avg

            subject_performance = (
                Result.objects.filter(academic_session=current_session)
                .values("result__subject__name")
                .annotate(avg_percentage=Avg("percentage"))
                .order_by("-avg_percentage")
            )

            performance_data["subject_performance"] = list(subject_performance)

            # Class performance
            class_performance = (
                Result.objects.filter(
                    academic_session=current_session, exam_type__is_final=True
                )
                .values("academic_class__name")
                .annotate(
                    avg_percentage=Avg("percentage"),
                    student_count=models.Count("student", distinct=True),
                )
                .order_by("-avg_percentage")
            )

            performance_data["class_performance"] = list(class_performance)

        # Academic KPIs
        academic_kpis = KPI.objects.filter(category="academic", status="active")[:10]

        kpi_data = {}
        for kpi in academic_kpis:
            latest_measurement = (
                KPIMeasurement.objects.filter(kpi=kpi).order_by("-measured_at").first()
            )
            if latest_measurement:
                kpi_data[kpi.id] = latest_measurement

        context = {
            "current_session": current_session,
            "performance_data": performance_data,
            "academic_kpis": academic_kpis,
            "kpi_data": kpi_data,
            "page_title": _("Academic Performance Monitoring"),
        }

        return render(
            request, "principal/principal_performance_monitoring.html", context
        )


class PrincipalTeacherManagementView(LoginRequiredMixin, View):
    """
    Principal view for managing and monitoring teachers.
    """

    def get(self, request, *args, **kwargs):
        user = request.user

        # Check if user is a principal
        if (
            not has_role_or_perm(
                user, perm="core.change_institution", role_type="principal"
            )
            and not user.is_staff
        ):
            messages.error(request, _("You don't have permission to access this page."))
            return redirect("users:dashboard")

        from apps.academics.models import (
            AcademicSession,
            Teacher,
            SubjectAssignment,
            Class,
        )
        from apps.assessment.models import Mark

        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Teacher data
        teachers_data = []

        if current_session:
            teachers = Teacher.objects.filter(status="active")

            for teacher in teachers:
                # Get teacher's assignments
                assignments = SubjectAssignment.objects.filter(
                    teacher=teacher, academic_session=current_session
                ).select_related("subject", "class_assigned")

                # Calculate workload (total periods per week)
                total_periods = sum(
                    assignment.periods_per_week for assignment in assignments
                )

                # Get classes taught
                classes_taught = assignments.values_list(
                    "class_assigned__name", flat=True
                ).distinct()

                # Performance metrics (average student performance in teacher's classes)
                teacher_marks = Mark.objects.filter(
                    exam__academic_class__subject_assignments__teacher=teacher,
                    exam__academic_session=current_session,
                ).aggregate(avg_percentage=models.Avg("percentage"))

                avg_performance = teacher_marks["avg_percentage"] or 0

                teachers_data.append(
                    {
                        "teacher": teacher,
                        "assignments": assignments,
                        "total_periods": total_periods,
                        "classes_count": len(classes_taught),
                        "classes_list": list(classes_taught),
                        "avg_student_performance": round(avg_performance, 1),
                        "subjects": assignments.values_list(
                            "subject__name", flat=True
                        ).distinct(),
                    }
                )

        context = {
            "current_session": current_session,
            "teachers_data": teachers_data,
            "page_title": _("Teacher Management & Performance"),
        }

        return render(request, "principal/principal_teacher_management.html", context)


class PrincipalStudentWelfareView(LoginRequiredMixin, View):
    """
    Principal view for monitoring student welfare and behavior.
    """

    def get(self, request, *args, **kwargs):
        user = request.user

        # Check if user is a principal
        if (
            not has_role_or_perm(
                user, perm="core.change_institution", role_type="principal"
            )
            and not user.is_staff
        ):
            messages.error(request, _("You don't have permission to access this page."))
            return redirect("users:dashboard")

        from apps.academics.models import (
            AcademicSession,
            BehaviorRecord,
            AcademicWarning,
            Student,
        )
        from apps.attendance.models import AttendanceSummary

        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Behavior and welfare data
        welfare_data = {
            "recent_incidents": [],
            "active_warnings": [],
            "attendance_issues": [],
            "behavior_trends": {},
        }

        if current_session:
            # Recent behavior incidents (last 30 days)
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            recent_incidents = (
                BehaviorRecord.objects.filter(incident_date__gte=thirty_days_ago)
                .select_related("student", "reported_by")
                .order_by("-incident_date")[:20]
            )

            welfare_data["recent_incidents"] = recent_incidents

            # Active academic warnings
            active_warnings = (
                AcademicWarning.objects.filter(is_resolved=False)
                .select_related("student", "issued_by")
                .order_by("issued_date")[:20]
            )

            welfare_data["active_warnings"] = active_warnings

            # Students with attendance issues (< 75% this month)
            current_month = timezone.now().month
            current_year = timezone.now().year

            attendance_issues = (
                AttendanceSummary.objects.filter(
                    academic_session=current_session,
                    month=current_month,
                    year=current_year,
                    attendance_percentage__lt=75,
                )
                .select_related("student")
                .order_by("attendance_percentage")[:20]
            )

            welfare_data["attendance_issues"] = attendance_issues

            # Behavior trends by category (last 6 months)
            six_months_ago = timezone.now() - timezone.timedelta(days=180)
            behavior_trends = (
                BehaviorRecord.objects.filter(incident_date__gte=six_months_ago)
                .values("incident_category")
                .annotate(count=models.Count("id"))
                .order_by("-count")
            )

            welfare_data["behavior_trends"] = {
                item["incident_category"]: item["count"] for item in behavior_trends
            }

        context = {
            "current_session": current_session,
            "welfare_data": welfare_data,
            "page_title": _("Student Welfare & Behavior Management"),
        }

        return render(request, "principal/principal_student_welfare.html", context)


class PrincipalCurriculumPlanningView(LoginRequiredMixin, View):
    """
    Principal view for curriculum planning and academic oversight.
    """

    def get(self, request, *args, **kwargs):
        user = request.user

        # Check if user is a principal
        if (
            not has_role_or_perm(
                user, perm="core.change_institution", role_type="principal"
            )
            and not user.is_staff
        ):
            messages.error(request, _("You don't have permission to access this page."))
            return redirect("users:dashboard")

        from apps.academics.models import AcademicSession, Subject, Class, Timetable
        from apps.assessment.models import GradingSystem, Exam

        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Curriculum data
        curriculum_data = {
            "subject_enrollment": {},
            "grading_effectiveness": {},
            "timetable_utilization": {},
            "exam_schedule": [],
        }

        if current_session:
            # Subject enrollment statistics
            from django.db.models import Count

            subject_enrollment = (
                Subject.objects.filter(
                    subject_assignments__academic_session=current_session
                )
                .annotate(
                    class_count=Count(
                        "subject_assignments__class_assigned", distinct=True
                    ),
                    teacher_count=Count("subject_assignments__teacher", distinct=True),
                )
                .values("name", "class_count", "teacher_count")
            )

            curriculum_data["subject_enrollment"] = list(subject_enrollment)

            # Grading system analysis
            grading_systems = GradingSystem.objects.filter(is_active=True)
            grading_stats = {}

            for system in grading_systems:
                results_count = Exam.objects.filter(
                    exam_type__grading_system=system, academic_session=current_session
                ).count()
                grading_stats[system.name] = results_count

            curriculum_data["grading_effectiveness"] = grading_stats

            # Timetable utilization
            total_slots = Timetable.objects.filter(
                academic_session=current_session
            ).count()

            used_slots = (
                Timetable.objects.filter(academic_session=current_session)
                .exclude(subject__isnull=True)
                .count()
            )

            utilization_rate = (
                (used_slots / total_slots * 100) if total_slots > 0 else 0
            )
            curriculum_data["timetable_utilization"] = {
                "total_slots": total_slots,
                "used_slots": used_slots,
                "utilization_rate": round(utilization_rate, 1),
            }

            # Upcoming exams
            upcoming_exams = Exam.objects.filter(
                academic_session=current_session, exam_date__gte=timezone.now().date()
            ).order_by("exam_date", "start_time")[:10]

            curriculum_data["exam_schedule"] = upcoming_exams

        context = {
            "current_session": current_session,
            "curriculum_data": curriculum_data,
            "page_title": _("Curriculum & Academic Planning"),
        }

        return render(request, "principal/principal_curriculum_planning.html", context)


class PrincipalCommunicationView(LoginRequiredMixin, View):
    """
    Principal view for stakeholder communication and messaging.
    """

    def get(self, request, *args, **kwargs):
        user = request.user

        # Check if user is a principal
        if (
            not has_role_or_perm(
                user, perm="core.change_institution", role_type="principal"
            )
            and not user.is_staff
        ):
            messages.error(request, _("You don't have permission to access this page."))
            return redirect("users:dashboard")

        from apps.communication.models import Announcement, Message
        from apps.users.models import User

        # Communication data
        communication_data = {
            "recent_announcements": [],
            "message_threads": [],
            "feedback_summary": {},
        }

        # Recent principal announcements
        principal_announcements = Announcement.objects.filter(
            author=user, is_published=True
        ).order_by("-published_at")[:10]

        communication_data["recent_announcements"] = principal_announcements

        # Recent message threads
        recent_messages = Message.objects.filter(sender=user).order_by("-created_at")[
            :10
        ]

        communication_data["message_threads"] = recent_messages

        # Feedback summary (simplified - would need proper feedback model)
        communication_data["feedback_summary"] = {
            "total_responses": 0,
            "positive_feedback": 0,
            "needs_attention": 0,
        }

        context = {
            "communication_data": communication_data,
            "page_title": _("Stakeholder Communication"),
        }

        return render(request, "principal/principal_communication.html", context)


class SuperAdminEntityView(
    MultiInstitutionMixin, LoginRequiredMixin, PermissionRequiredMixin, View
):
    """
    Super Administrator view for comprehensive entity management across institutions.
    Displays teachers, students, classes, departments, sessions, and enrollments
    with institution-based filtering. Now includes "All Institutions" option for cross-institution views.
    """

    permission_required = "core.view_institution"  # Could be more specific

    def get(self, request, *args, **kwargs):
        user = request.user

        # Check if user is super admin or has institution-level view permission
        if not (
            user.is_superuser
            or user.has_perm("core.view_institution")
            or user.user_roles.filter(role__role_type="super_admin").exists()
        ):
            messages.error(
                request,
                _(
                    "You don't have permission to access the super admin entity management."
                ),
            )
            return redirect("users:dashboard")

        from apps.academics.models import (
            AcademicSession,
            Department,
            Class,
            Student,
            Teacher,
            Enrollment,
        )
        from apps.users.models import User, Role
        from django.db.models import Count, Avg

        # Get institution filter from request, allow 'all' for cross-institution view
        institution_filter = request.GET.get("institution", "all")  # Default to 'all'
        selected_institution = None
        view_all_institutions = institution_filter == "all"

        # Get accessible institutions for this user
        if user.is_superuser:
            accessible_institutions = Institution.objects.filter(is_active=True)
        else:
            # Get institutions the user has access to
            try:
                from .middleware import get_user_accessible_institutions

                accessible_institutions = get_user_accessible_institutions(user)
            except ImportError:
                # Fallback if middleware not available
                accessible_institutions = Institution.objects.filter(
                    is_active=True, users=user
                )

        institutions = accessible_institutions.order_by("name")

        # Handle institution selection or "all institutions" view
        if not view_all_institutions:
            if not institution_filter or institution_filter == "all":
                # If no specific institution selected and not explicitly 'all', default to first institution
                if institutions.exists():
                    selected_institution = institutions.first()
                    institution_filter = str(selected_institution.id)
                else:
                    messages.error(request, _("No accessible institutions found."))
                    return redirect("users:dashboard")
            else:
                try:
                    selected_institution = institutions.get(
                        id=institution_filter, is_active=True
                    )
                except Institution.DoesNotExist:
                    # If selected institution not found, fall back to "all institutions" view
                    view_all_institutions = True
                    institution_filter = "all"
                    messages.info(
                        request,
                        _(
                            "Selected institution not found. Showing data from all institutions."
                        ),
                    )

        # Filter querysets based on selection
        if view_all_institutions:
            # Cross-institution view - no institution filtering
            student_qs = Student.objects.filter(status="active")
            teacher_qs = Teacher.objects.filter(status="active")
            class_qs = Class.objects.filter(status="active")
            department_qs = Department.objects.filter(status="active")
            session_qs = AcademicSession.objects.filter(status="active")
            enrollment_qs = Enrollment.objects.filter(status="active")
        else:
            # Single institution view
            student_qs = Student.objects.filter(
                institution=selected_institution, status="active"
            )
            teacher_qs = Teacher.objects.filter(
                institution=selected_institution, status="active"
            )
            class_qs = Class.objects.filter(
                institution=selected_institution, status="active"
            )
            department_qs = Department.objects.filter(
                institution=selected_institution, status="active"
            )
            session_qs = AcademicSession.objects.filter(
                institution=selected_institution, status="active"
            )
            enrollment_qs = Enrollment.objects.filter(
                institution=selected_institution, status="active"
            )

        # Apply additional filters if present
        search_query = request.GET.get("search", "")

        # Students
        students = student_qs.filter(status="active").select_related("user")
        if search_query:
            students = students.filter(
                Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(student_id__icontains=search_query)
                | Q(admission_number__icontains=search_query)
            )
        students = students.order_by("user__last_name", "user__first_name")[
            :50
        ]  # Limit for performance

        # Teachers
        teachers = teacher_qs.filter(status="active").select_related(
            "user", "department"
        )
        if search_query:
            teachers = teachers.filter(
                Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(teacher_id__icontains=search_query)
                | Q(employee_id__icontains=search_query)
            )
        teachers = teachers.order_by("user__last_name", "user__first_name")[:50]

        # Classes
        classes = class_qs.filter(status="active").select_related(
            "grade_level", "class_teacher", "academic_session"
        )
        if search_query:
            classes = classes.filter(
                Q(name__icontains=search_query) | Q(code__icontains=search_query)
            )
        classes = classes.order_by("grade_level__name", "name")[:50]

        # Departments
        departments = department_qs.filter(status="active")
        if search_query:
            departments = departments.filter(
                Q(name__icontains=search_query) | Q(code__icontains=search_query)
            )
        departments = departments.order_by("name")[:50]

        # Sessions
        sessions = session_qs.filter(status="active")
        if search_query:
            sessions = sessions.filter(name__icontains=search_query)
        sessions = sessions.order_by("-start_date")[:50]

        # Enrollments
        enrollments = enrollment_qs.filter(status="active").select_related(
            "student__user", "class_enrolled", "academic_session"
        )
        if search_query:
            enrollments = enrollments.filter(
                Q(student__user__first_name__icontains=search_query)
                | Q(student__user__last_name__icontains=search_query)
                | Q(class_enrolled__name__icontains=search_query)
            )
        enrollments = enrollments.order_by("class_enrolled__name", "roll_number")[:100]

        # Fetch data for all entities - Users & Applications
        users_list = User.objects.filter(is_active=True).select_related("profile")
        student_applications = []
        staff_applications = []

        try:
            from apps.users.models import StudentApplication, StaffApplication

            if view_all_institutions:
                student_applications = StudentApplication.objects.filter(
                    status="active"
                )[:50]
                staff_applications = StaffApplication.objects.filter(status="active")[
                    :50
                ]
            else:
                student_applications = StudentApplication.objects.filter(
                    institution=selected_institution, status="active"
                )[:50]
                staff_applications = StaffApplication.objects.filter(
                    institution=selected_institution, status="active"
                )[:50]
        except ImportError:
            pass

        # Finance entities
        invoices = []
        payments = []
        expenses = []

        try:
            if view_all_institutions:
                from apps.finance.models import Invoice, Payment, Expense

                invoices = Invoice.objects.filter(is_deleted=False)[:50]
                payments = Payment.objects.filter(is_deleted=False)[:50]
                expenses = Expense.objects.filter(is_deleted=False)[:50]
            else:
                from apps.finance.models import Invoice, Payment, Expense

                invoices = Invoice.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
                payments = Payment.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
                expenses = Expense.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
        except ImportError:
            pass

        # Library entities
        books = []
        authors = []
        borrow_records = []
        reservations = []

        try:
            if view_all_institutions:
                from apps.library.models import (
                    Book,
                    BookAuthor,
                    BookBorrowRecord,
                    BookReservation,
                )

                books = Book.objects.filter(is_deleted=False)[:50]
                authors = BookAuthor.objects.filter(is_deleted=False)[:50]
                borrow_records = BookBorrowRecord.objects.filter(is_deleted=False)[:50]
                reservations = BookReservation.objects.filter(is_deleted=False)[:50]
            else:
                from apps.library.models import (
                    Book,
                    BookAuthor,
                    BookBorrowRecord,
                    BookReservation,
                )

                books = Book.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
                authors = BookAuthor.objects.filter(is_deleted=False)[
                    :50
                ]  # Authors cross-institution
                borrow_records = BookBorrowRecord.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
                reservations = BookReservation.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
        except ImportError:
            pass

        # Transport entities
        vehicles = []
        drivers = []
        routes = []
        allocations = []

        try:
            if view_all_institutions:
                from apps.transport.models import (
                    Vehicle,
                    Driver,
                    Route,
                    TransportAllocation,
                )

                vehicles = Vehicle.objects.filter(is_deleted=False)[:50]
                drivers = Driver.objects.filter(is_deleted=False)[:50]
                routes = Route.objects.filter(is_deleted=False)[:50]
                allocations = TransportAllocation.objects.filter(is_deleted=False)[:50]
            else:
                from apps.transport.models import (
                    Vehicle,
                    Driver,
                    Route,
                    TransportAllocation,
                )

                vehicles = Vehicle.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
                drivers = Driver.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
                routes = Route.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
                allocations = TransportAllocation.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
        except ImportError:
            pass

        # Activities
        activities = []
        try:
            if view_all_institutions:
                from apps.activities.models import Activity

                activities = Activity.objects.filter(is_deleted=False)[:50]
            else:
                from apps.activities.models import Activity

                activities = Activity.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
        except ImportError:
            pass

        # Communication
        announcements = []
        try:
            if view_all_institutions:
                from apps.communication.models import Announcement

                announcements = Announcement.objects.filter(
                    is_published=True, is_deleted=False
                )[:50]
            else:
                from apps.communication.models import Announcement

                announcements = Announcement.objects.filter(
                    institution=selected_institution,
                    is_published=True,
                    is_deleted=False,
                )[:50]
        except ImportError:
            pass

        # Audit
        audit_logs = []
        try:
            if view_all_institutions:
                from apps.audit.models import AuditLog

                audit_logs = AuditLog.objects.all().order_by("-timestamp")[:50]
            else:
                from apps.audit.models import AuditLog

                audit_logs = AuditLog.objects.filter(
                    institution=selected_institution
                ).order_by("-timestamp")[:50]
        except ImportError:
            pass

        # Assessment
        exams = []
        assignments = []

        try:
            if view_all_institutions:
                from apps.assessment.models import Exam, Assignment

                exams = Exam.objects.filter(is_deleted=False)[:50]
                assignments = Assignment.objects.filter(is_deleted=False)[:50]
            else:
                from apps.assessment.models import Exam, Assignment

                exams = Exam.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
                assignments = Assignment.objects.filter(
                    institution=selected_institution, is_deleted=False
                )[:50]
        except ImportError:
            pass

        # Apply search filters to new entities
        if search_query:
            if users_list and search_query:
                users_list = users_list.filter(
                    Q(first_name__icontains=search_query)
                    | Q(last_name__icontains=search_query)
                    | Q(email__icontains=search_query)
                    | Q(profile__phone__icontains=search_query)
                )[:50]

            # Finance entities
            if invoices and search_query:
                invoices = invoices.filter(
                    Q(invoice_number__icontains=search_query)
                    | Q(description__icontains=search_query)
                    | Q(student__user__first_name__icontains=search_query)
                    | Q(student__user__last_name__icontains=search_query)
                    | Q(student__student_id__icontains=search_query)
                )[:50]

            if payments and search_query:
                payments = payments.filter(
                    Q(payment_number__icontains=search_query)
                    | Q(reference_number__icontains=search_query)
                    | Q(description__icontains=search_query)
                    | Q(student__user__first_name__icontains=search_query)
                    | Q(student__user__last_name__icontains=search_query)
                    | Q(student__student_id__icontains=search_query)
                )[:50]

            if expenses and search_query:
                expenses = expenses.filter(
                    Q(description__icontains=search_query)
                    | Q(category__icontains=search_query)
                    | Q(vendor__icontains=search_query)
                )[:50]

            # Library entities
            if books and search_query:
                books = books.filter(
                    Q(title__icontains=search_query)
                    | Q(isbn__icontains=search_query)
                    | Q(authors__first_name__icontains=search_query)
                    | Q(authors__last_name__icontains=search_query)
                    | Q(publisher__icontains=search_query)
                )[:50]

            if authors and search_query:
                authors = authors.filter(
                    Q(first_name__icontains=search_query)
                    | Q(last_name__icontains=search_query)
                    | Q(email__icontains=search_query)
                )[:50]

            if borrow_records and search_query:
                borrow_records = borrow_records.filter(
                    Q(student__user__first_name__icontains=search_query)
                    | Q(student__user__last_name__icontains=search_query)
                    | Q(student__student_id__icontains=search_query)
                    | Q(book__title__icontains=search_query)
                    | Q(book__isbn__icontains=search_query)
                )[:50]

            if reservations and search_query:
                reservations = reservations.filter(
                    Q(student__user__first_name__icontains=search_query)
                    | Q(student__user__last_name__icontains=search_query)
                    | Q(student__student_id__icontains=search_query)
                    | Q(book__title__icontains=search_query)
                    | Q(book__isbn__icontains=search_query)
                )[:50]

            # Transport entities
            if vehicles and search_query:
                vehicles = vehicles.filter(
                    Q(license_plate__icontains=search_query)
                    | Q(make__icontains=search_query)
                    | Q(model__icontains=search_query)
                    | Q(vehicle_type__icontains=search_query)
                )[:50]

            if drivers and search_query:
                drivers = drivers.filter(
                    Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(employee_id__icontains=search_query)
                    | Q(license_number__icontains=search_query)
                )[:50]

            if routes and search_query:
                routes = routes.filter(
                    Q(name__icontains=search_query)
                    | Q(code__icontains=search_query)
                    | Q(description__icontains=search_query)
                )[:50]

            if allocations and search_query:
                allocations = allocations.filter(
                    Q(student__user__first_name__icontains=search_query)
                    | Q(student__user__last_name__icontains=search_query)
                    | Q(student__student_id__icontains=search_query)
                    | Q(vehicle__license_plate__icontains=search_query)
                    | Q(route__name__icontains=search_query)
                )[:50]

            # Activities
            if activities and search_query:
                activities = activities.filter(
                    Q(name__icontains=search_query)
                    | Q(description__icontains=search_query)
                    | Q(activity_type__icontains=search_query)
                )[:50]

            # Communication
            if announcements and search_query:
                announcements = announcements.filter(
                    Q(title__icontains=search_query)
                    | Q(content__icontains=search_query)
                    | Q(author__first_name__icontains=search_query)
                    | Q(author__last_name__icontains=search_query)
                )[:50]

            # Audit
            if audit_logs and search_query:
                audit_logs = audit_logs.filter(
                    Q(action__icontains=search_query)
                    | Q(description__icontains=search_query)
                    | Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                )[:50]

            # Assessment
            if exams and search_query:
                exams = exams.filter(
                    Q(name__icontains=search_query)
                    | Q(code__icontains=search_query)
                    | Q(description__icontains=search_query)
                    | Q(subject__name__icontains=search_query)
                    | Q(exam_type__name__icontains=search_query)
                )[:50]

            if assignments and search_query:
                assignments = assignments.filter(
                    Q(title__icontains=search_query)
                    | Q(description__icontains=search_query)
                    | Q(subject__name__icontains=search_query)
                    | Q(teacher__user__first_name__icontains=search_query)
                    | Q(teacher__user__last_name__icontains=search_query)
                )[:50]

            # Applications
            if student_applications and search_query:
                student_applications = student_applications.filter(
                    Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(phone__icontains=search_query)
                    | Q(application_number__icontains=search_query)
                )[:50]

            if staff_applications and search_query:
                staff_applications = staff_applications.filter(
                    Q(user__first_name__icontains=search_query)
                    | Q(user__last_name__icontains=search_query)
                    | Q(user__email__icontains=search_query)
                    | Q(phone__icontains=search_query)
                    | Q(application_number__icontains=search_query)
                )[:50]

        # Get entity counts for all entities
        entity_counts = self._get_entity_counts(
            view_all_institutions, selected_institution
        )

        # Add cross-institution aggregate statistics if viewing all institutions
        aggregate_stats = {}
        if view_all_institutions:
            aggregate_stats = {
                "total_institutions": institutions.count(),
                "institution_breakdown": {},
                "top_performing_institutions": [],
            }

            # Get breakdown by institution
            inst_stats = []
            for institution in institutions:
                inst_students = Student.objects.filter(
                    institution=institution, status="active"
                ).count()
                inst_teachers = Teacher.objects.filter(
                    institution=institution, status="active"
                ).count()
                inst_classes = Class.objects.filter(
                    institution=institution, status="active"
                ).count()

                inst_stats.append(
                    {
                        "institution": institution,
                        "students": inst_students,
                        "teachers": inst_teachers,
                        "classes": inst_classes,
                        "student_teacher_ratio": (
                            round(inst_students / inst_teachers, 1)
                            if inst_teachers > 0
                            else 0
                        ),
                        "class_utilization": (
                            round((inst_students / (inst_classes * 30)) * 100, 1)
                            if inst_classes > 0
                            else 0
                        ),
                    }
                )

            # Sort by student count for top performers
            aggregate_stats["institution_breakdown"] = sorted(
                inst_stats, key=lambda x: x["students"], reverse=True
            )
            aggregate_stats["top_performing_institutions"] = inst_stats[
                :5
            ]  # Top 5 by student count

            # Overall system statistics
            aggregate_stats["system_totals"] = {
                "total_students": sum(inst["students"] for inst in inst_stats),
                "total_teachers": sum(inst["teachers"] for inst in inst_stats),
                "total_classes": sum(inst["classes"] for inst in inst_stats),
                "avg_students_per_institution": (
                    round(
                        sum(inst["students"] for inst in inst_stats) / len(inst_stats),
                        1,
                    )
                    if inst_stats
                    else 0
                ),
                "avg_teachers_per_institution": (
                    round(
                        sum(inst["teachers"] for inst in inst_stats) / len(inst_stats),
                        1,
                    )
                    if inst_stats
                    else 0
                ),
                "avg_classes_per_institution": (
                    round(
                        sum(inst["classes"] for inst in inst_stats) / len(inst_stats), 1
                    )
                    if inst_stats
                    else 0
                ),
            }

        context = {
            "selected_institution": selected_institution,
            "institutions": institutions,
            "institution_filter": institution_filter,
            "search_query": search_query,
            "view_all_institutions": view_all_institutions,
            # Existing Academic Data
            "students": students,
            "teachers": teachers,
            "classes": classes,
            "departments": departments,
            "sessions": sessions,
            "enrollments": enrollments,
            # Users & Applications
            "users_list": users_list,
            "student_applications": student_applications,
            "staff_applications": staff_applications,
            # Finance
            "invoices": invoices,
            "payments": payments,
            "expenses": expenses,
            # Library
            "books": books,
            "authors": authors,
            "borrow_records": borrow_records,
            "reservations": reservations,
            # Transport
            "vehicles": vehicles,
            "drivers": drivers,
            "routes": routes,
            "allocations": allocations,
            # Activities
            "activities": activities,
            # Communication
            "announcements": announcements,
            # Audit
            "audit_logs": audit_logs,
            # Assessment
            "exams": exams,
            "assignments": assignments,
            # Counts
            "entity_counts": entity_counts,
            "aggregate_stats": aggregate_stats,
            "page_title": _("Super Admin Entity Management"),
        }

        return render(request, "core/dashboard/super_admin_entities.html", context)

    def _get_entity_counts(self, view_all_institutions, selected_institution):
        """Helper method to get counts for all system entities."""
        from apps.users.models import User

        # Academic entities
        student_count = 0
        teacher_count = 0
        class_count = 0
        department_count = 0
        session_count = 0
        enrollment_count = 0

        try:
            from apps.academics.models import (
                Student,
                Teacher,
                Class,
                Department,
                AcademicSession,
                Enrollment,
            )

            if view_all_institutions:
                student_count = Student.objects.filter(status="active").count()
                teacher_count = Teacher.objects.filter(status="active").count()
                class_count = Class.objects.filter(status="active").count()
                department_count = Department.objects.filter(status="active").count()
                session_count = AcademicSession.objects.filter(status="active").count()
                enrollment_count = Enrollment.objects.filter(status="active").count()
            else:
                student_count = Student.objects.filter(
                    institution=selected_institution, status="active"
                ).count()
                teacher_count = Teacher.objects.filter(
                    institution=selected_institution, status="active"
                ).count()
                class_count = Class.objects.filter(
                    institution=selected_institution, status="active"
                ).count()
                department_count = Department.objects.filter(
                    institution=selected_institution, status="active"
                ).count()
                session_count = AcademicSession.objects.filter(
                    institution=selected_institution, status="active"
                ).count()
                enrollment_count = Enrollment.objects.filter(
                    institution=selected_institution, status="active"
                ).count()
        except ImportError:
            pass

        # Users and Applications
        user_count = User.objects.filter(is_active=True).count()
        student_app_count = 0
        staff_app_count = 0

        try:
            from apps.users.models import StudentApplication, StaffApplication

            if view_all_institutions:
                student_app_count = StudentApplication.objects.filter(
                    status="active"
                ).count()
                staff_app_count = StaffApplication.objects.filter(
                    status="active"
                ).count()
            else:
                student_app_count = StudentApplication.objects.filter(
                    institution=selected_institution, status="active"
                ).count()
                staff_app_count = StaffApplication.objects.filter(
                    institution=selected_institution, status="active"
                ).count()
        except ImportError:
            pass

        # Finance entities
        invoice_count = 0
        payment_count = 0
        expense_count = 0

        try:
            from apps.finance.models import Invoice, Payment, Expense

            if view_all_institutions:
                invoice_count = Invoice.objects.filter(is_deleted=False).count()
                payment_count = Payment.objects.filter(is_deleted=False).count()
                expense_count = Expense.objects.filter(is_deleted=False).count()
            else:
                invoice_count = Invoice.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
                payment_count = Payment.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
                expense_count = Expense.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
        except ImportError:
            pass

        # Library entities
        book_count = 0
        author_count = 0
        borrow_count = 0
        reservation_count = 0

        try:
            from apps.library.models import (
                Book,
                BookAuthor,
                BookBorrowRecord,
                BookReservation,
            )

            if view_all_institutions:
                book_count = Book.objects.filter(is_deleted=False).count()
                author_count = BookAuthor.objects.filter(is_deleted=False).count()
                borrow_count = BookBorrowRecord.objects.filter(is_deleted=False).count()
                reservation_count = BookReservation.objects.filter(
                    is_deleted=False
                ).count()
            else:
                book_count = Book.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
                author_count = BookAuthor.objects.filter(
                    is_deleted=False
                ).count()  # Cross-institution
                borrow_count = BookBorrowRecord.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
                reservation_count = BookReservation.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
        except ImportError:
            pass

        # Transport entities
        vehicle_count = 0
        driver_count = 0
        route_count = 0
        allocation_count = 0

        try:
            from apps.transport.models import (
                Vehicle,
                Driver,
                Route,
                TransportAllocation,
            )

            if view_all_institutions:
                vehicle_count = Vehicle.objects.filter(is_deleted=False).count()
                driver_count = Driver.objects.filter(is_deleted=False).count()
                route_count = Route.objects.filter(is_deleted=False).count()
                allocation_count = TransportAllocation.objects.filter(
                    is_deleted=False
                ).count()
            else:
                vehicle_count = Vehicle.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
                driver_count = Driver.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
                route_count = Route.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
                allocation_count = TransportAllocation.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
        except ImportError:
            pass

        # Activities
        activity_count = 0
        try:
            from apps.activities.models import Activity

            if view_all_institutions:
                activity_count = Activity.objects.filter(is_deleted=False).count()
            else:
                activity_count = Activity.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
        except ImportError:
            pass

        # Communication
        announcement_count = 0
        try:
            from apps.communication.models import Announcement

            if view_all_institutions:
                announcement_count = Announcement.objects.filter(
                    is_published=True, status="active"
                ).count()
            else:
                announcement_count = Announcement.objects.filter(
                    institution=selected_institution, is_published=True, status="active"
                ).count()
        except ImportError:
            pass

        # Audit
        audit_count = 0
        try:
            from apps.audit.models import AuditLog

            if view_all_institutions:
                audit_count = AuditLog.objects.all().count()
            else:
                audit_count = AuditLog.objects.filter(
                    institution=selected_institution
                ).count()
        except ImportError:
            pass

        # Assessment
        exam_count = 0
        assignment_count = 0

        try:
            from apps.assessment.models import Exam, Assignment

            if view_all_institutions:
                exam_count = Exam.objects.filter(is_deleted=False).count()
                assignment_count = Assignment.objects.filter(is_deleted=False).count()
            else:
                exam_count = Exam.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
                assignment_count = Assignment.objects.filter(
                    institution=selected_institution, is_deleted=False
                ).count()
        except ImportError:
            pass

        # Return comprehensive counts
        return {
            "students": student_count,
            "teachers": teacher_count,
            "classes": class_count,
            "departments": department_count,
            "sessions": session_count,
            "enrollments": enrollment_count,
            "users": user_count,
            "student_applications": student_app_count,
            "staff_applications": staff_app_count,
            "invoices": invoice_count,
            "payments": payment_count,
            "expenses": expense_count,
            "books": book_count,
            "authors": author_count,
            "borrow_records": borrow_count,
            "reservations": reservation_count,
            "vehicles": vehicle_count,
            "drivers": driver_count,
            "routes": route_count,
            "transport_allocations": allocation_count,
            "activities": activity_count,
            "announcements": announcement_count,
            "audit_logs": audit_count,
            "exams": exam_count,
            "assignments": assignment_count,
        }


# API endpoints for institutions


def get_institution_config_value(request, institution_code, config_key):
    """
    API endpoint to get configuration value for a specific institution.
    """
    try:
        institution = Institution.objects.get(code=institution_code, is_active=True)
        config = SystemConfig.objects.get(key=config_key, status="active")

        effective_value = config.get_value_for_institution(institution)

        return JsonResponse(
            {
                "institution": institution.code,
                "key": config.key,
                "value": effective_value,
                "config_type": config.config_type,
                "description": config.description,
            }
        )
    except (Institution.DoesNotExist, SystemConfig.DoesNotExist):
        return JsonResponse(
            {"error": "Institution or configuration not found"}, status=404
        )


def institution_statistics_api(request):
    """
    API endpoint for institution statistics.
    """
    institutions = Institution.objects.filter(is_active=True)

    data = {"total_institutions": institutions.count(), "institutions": []}

    for institution in institutions:
        data["institutions"].append(
            {
                "id": str(institution.id),
                "code": institution.code,
                "name": institution.name,
                "student_count": institution.current_student_count,
                "staff_count": institution.current_staff_count,
                "utilization_rate": institution.utilization_rate,
                "status": institution.status,
            }
        )

    return JsonResponse(data)


def ui_config_demo(request):
    """
    Demo view to showcase the UI configuration system.
    """
    return render(request, "base/ui_config_demo.html")


class UIConfigManagementView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Dedicated UI configuration management interface for superusers and admins.
    Provides theme management, color schemes, typography, and layout options.
    """

    permission_required = "core.change_systemconfig"

    def get(self, request, *args, **kwargs):
        # Only superusers can access UI config management
        if not request.user.is_superuser:
            messages.error(
                request, _("You don't have permission to manage UI configurations.")
            )
            return redirect("users:dashboard")

        # Get all UI configurations
        ui_configs = SystemConfig.objects.filter(
            config_type="ui", status="active"
        ).order_by("key")

        # Group configs by category
        config_categories = {
            "colors": [],
            "typography": [],
            "spacing": [],
            "layout": [],
            "features": [],
        }

        for config in ui_configs:
            if "color" in config.key.lower():
                config_categories["colors"].append(config)
            elif any(
                word in config.key.lower()
                for word in ["font", "weight", "line", "size"]
            ):
                config_categories["typography"].append(config)
            elif any(
                word in config.key.lower()
                for word in ["border", "shadow", "spacing", "radius"]
            ):
                config_categories["spacing"].append(config)
            elif any(
                word in config.key.lower()
                for word in ["header", "sidebar", "container", "width"]
            ):
                config_categories["layout"].append(config)
            else:
                config_categories["features"].append(config)

        # Get theme presets
        theme_presets = self.get_theme_presets()

        context = {
            "config_categories": config_categories,
            "theme_presets": theme_presets,
            "page_title": _("UI Configuration Management"),
        }

        return render(request, "core/config/ui_management.html", context)

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(
                request, _("You don't have permission to manage UI configurations.")
            )
            return redirect("users:dashboard")

        action = request.POST.get("action")

        if action == "update_configs":
            return self.update_configs(request)
        elif action == "apply_preset":
            return self.apply_theme_preset(request)
        elif action == "reset_defaults":
            return self.reset_to_defaults(request)

        messages.error(request, _("Invalid action."))
        return redirect("core:ui_config_management")

    def update_configs(self, request):
        """Update multiple UI configurations at once."""
        updated_count = 0

        for key, value in request.POST.items():
            if key.startswith("config_"):
                config_key = key.replace("config_", "")
                try:
                    config = SystemConfig.objects.get(
                        key=config_key, config_type="ui", status="active"
                    )

                    # Validate and clean the value based on config type
                    if config.key.startswith("ui_") and "color" in config.key:
                        # Validate color values
                        if not self.is_valid_color(value):
                            messages.warning(
                                request,
                                _("Invalid color value for {}: {}").format(
                                    config.key, value
                                ),
                            )
                            continue
                    elif (
                        "size" in config.key
                        or "width" in config.key
                        or "height" in config.key
                    ):
                        # Validate numeric values
                        try:
                            if value.endswith(("px", "rem", "em", "%")):
                                float(value[:-2])
                            elif value.replace(".", "").isdigit():
                                float(value)
                            else:
                                raise ValueError
                        except (ValueError, IndexError):
                            messages.warning(
                                request,
                                _("Invalid numeric value for {}: {}").format(
                                    config.key, value
                                ),
                            )
                            continue

                    config.value = value
                    config.save()
                    updated_count += 1

                except SystemConfig.DoesNotExist:
                    continue

        if updated_count > 0:
            messages.success(
                request,
                _("Successfully updated {} UI configuration(s).").format(updated_count),
            )
        else:
            messages.info(request, _("No configurations were updated."))

        return redirect("core:ui_config_management")

    def apply_theme_preset(self, request):
        """Apply a predefined theme preset."""
        preset_name = request.POST.get("preset_name")

        if not preset_name:
            messages.error(request, _("No preset selected."))
            return redirect("core:ui_config_management")

        presets = self.get_theme_presets()
        if preset_name not in presets:
            messages.error(request, _("Invalid preset selected."))
            return redirect("core:ui_config_management")

        preset_configs = presets[preset_name]
        updated_count = 0

        for config_key, value in preset_configs.items():
            try:
                config = SystemConfig.objects.get(
                    key=config_key, config_type="ui", status="active"
                )
                config.value = value
                config.save()
                updated_count += 1
            except SystemConfig.DoesNotExist:
                continue

        messages.success(
            request,
            _(
                "Successfully applied '{}' theme preset ({} configurations updated)."
            ).format(preset_name, updated_count),
        )

        return redirect("core:ui_config_management")

    def reset_to_defaults(self, request):
        """Reset UI configurations to default values."""
        # Re-run the seed command to reset defaults
        from .management.commands.seed_ui_configs import Command

        command = Command()
        command.handle()

        messages.success(request, _("UI configurations have been reset to defaults."))
        return redirect("core:ui_config_management")

    def get_theme_presets(self):
        """Get predefined theme presets."""
        return {
            "Modern Blue": {
                "ui_primary_color": "#0d6efd",
                "ui_secondary_color": "#6c757d",
                "ui_success_color": "#198754",
                "ui_danger_color": "#dc3545",
                "ui_warning_color": "#ffc107",
                "ui_info_color": "#0dcaf0",
                "ui_accent_color": "#6610f2",
                "ui_font_family_primary": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                "ui_font_family_secondary": "'Poppins', sans-serif",
                "ui_border_radius": "0.5rem",
                "ui_enable_rounded_corners": True,
                "ui_enable_shadows": True,
                "ui_enable_animations": True,
            },
            "Classic Professional": {
                "ui_primary_color": "#2c3e50",
                "ui_secondary_color": "#7f8c8d",
                "ui_success_color": "#27ae60",
                "ui_danger_color": "#e74c3c",
                "ui_warning_color": "#f39c12",
                "ui_info_color": "#3498db",
                "ui_accent_color": "#9b59b6",
                "ui_font_family_primary": "'Times New Roman', serif",
                "ui_font_family_secondary": "'Georgia', serif",
                "ui_border_radius": "0.25rem",
                "ui_enable_rounded_corners": False,
                "ui_enable_shadows": True,
                "ui_enable_animations": False,
            },
            "Bright & Energetic": {
                "ui_primary_color": "#ff6b35",
                "ui_secondary_color": "#f7931e",
                "ui_success_color": "#00a896",
                "ui_danger_color": "#d7263d",
                "ui_warning_color": "#ffd23f",
                "ui_info_color": "#1e96fc",
                "ui_accent_color": "#a23b72",
                "ui_font_family_primary": "'Montserrat', sans-serif",
                "ui_font_family_secondary": "'Oswald', sans-serif",
                "ui_border_radius": "0.75rem",
                "ui_enable_rounded_corners": True,
                "ui_enable_shadows": True,
                "ui_enable_animations": True,
            },
            "Minimal Dark": {
                "ui_primary_color": "#ffffff",
                "ui_secondary_color": "#cccccc",
                "ui_success_color": "#4ade80",
                "ui_danger_color": "#f87171",
                "ui_warning_color": "#fbbf24",
                "ui_info_color": "#60a5fa",
                "ui_accent_color": "#c084fc",
                "ui_font_family_primary": "'Roboto', sans-serif",
                "ui_font_family_secondary": "'Open Sans', sans-serif",
                "ui_border_radius": "0.125rem",
                "ui_enable_rounded_corners": False,
                "ui_enable_shadows": False,
                "ui_enable_animations": True,
            },
        }

    def is_valid_color(self, color_value):
        """Validate color values (hex, rgb, rgba, named colors)."""
        import re

        # Hex colors
        if re.match(
            r"^#[0-9a-fA-F]{3}$|^#[0-9a-fA-F]{6}$|^#[0-9a-fA-F]{8}$", color_value
        ):
            return True

        # RGB/RGBA
        if re.match(r"^rgb(a)?\([^)]+\)$", color_value):
            return True

        # HSL/HSLA
        if re.match(r"^hsl(a)?\([^)]+\)$", color_value):
            return True

        # Named colors (basic validation - just check it's not empty and no special chars)
        if re.match(r"^[a-zA-Z]+$", color_value):
            return True

        return False


class GlobalSearchView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Global search view that searches across multiple models based on user query and filter.
    Results are filtered based on user's permissions and roles.
    """

    template_name = "core/search/results.html"
    permission_required = "core.view_institution"  # Basic permission to access search

    def has_permission(self):
        """
        Override to allow search based on user roles.
        Any authenticated user can search, but results are filtered by permissions.
        """
        return self.request.user.is_authenticated

    def get_accessible_students(self):
        """
        Get queryset of students the current user can access.
        """
        user = self.request.user

        # Super admin can see all students
        if (
            user.is_superuser
            or user.has_perm("core.view_institution")
            or user.user_roles.filter(role__role_type="super_admin").exists()
        ):
            from apps.academics.models import Student

            return Student.objects.all()

        # Admin can see students in their accessible institutions
        if user.user_roles.filter(
            role__role_type__in=["admin", "principal", "school_admin"]
        ).exists():
            from apps.academics.models import Student

            try:
                from .middleware import get_user_accessible_institutions

                accessible_institutions = get_user_accessible_institutions(user)
                return Student.objects.filter(institution__in=accessible_institutions)
            except ImportError:
                # Fallback - return all students (shouldn't happen in production)
                return Student.objects.all()

        # Teachers can see students in their classes
        if (
            user.has_perm("academics.view_class")
            or user.user_roles.filter(role__role_type="teacher").exists()
        ):
            from apps.academics.models import Student, SubjectAssignment

            # Get classes where teacher is assigned subjects
            teacher_assignments = SubjectAssignment.objects.filter(
                teacher__user=user, status="active"
            ).values_list("class_assigned", flat=True)
            return Student.objects.filter(
                enrollments__class_enrolled__in=teacher_assignments,
                enrollments__status="active",
            ).distinct()

        # Parents can see only their children
        if user.has_perm("academics.view_student") or has_role_or_perm(
            user, perm="academics.view_student", role_type="parent"
        ):
            from apps.users.models import ParentStudentRelationship
            from apps.academics.models import Student

            # Get students linked to this parent
            parent_students = ParentStudentRelationship.objects.filter(
                parent=user, status="active"
            ).values_list("student", flat=True)
            return Student.objects.filter(user__in=parent_students)

        # Students can see only themselves
        if (
            user.has_perm("academics.view_enrollment")
            or user.user_roles.filter(role__role_type="student").exists()
        ):
            from apps.academics.models import Student

            return Student.objects.filter(user=user)

        # Default: no students accessible
        from apps.academics.models import Student

        return Student.objects.none()

    def get_accessible_teachers(self):
        """
        Get queryset of teachers the current user can access.
        Only admin-level users (super_admin, admin, principal) can see teachers.
        """
        user = self.request.user
        from apps.academics.models import Teacher

        # Only super admin, admin, and principal can see teachers
        if (
            user.is_superuser
            or user.has_perm("core.view_institution")
            or user.user_roles.filter(
                role__role_type__in=["super_admin", "admin", "principal"]
            ).exists()
        ):
            return Teacher.objects.all()

        # Other staff members cannot see teachers
        return Teacher.objects.none()

    def get_accessible_classes(self):
        """
        Get queryset of classes the current user can access.
        """
        user = self.request.user
        from apps.academics.models import Class

        # Super admin can see all classes
        if (
            user.is_superuser
            or user.has_perm("core.view_institution")
            or user.user_roles.filter(role__role_type="super_admin").exists()
        ):
            return Class.objects.all()

        # Admin/principal can see classes in their accessible institutions
        if (
            user.has_perm("academics.change_class")
            or user.user_roles.filter(
                role__role_type__in=["admin", "principal"]
            ).exists()
        ):
            try:
                from .middleware import get_user_accessible_institutions

                accessible_institutions = get_user_accessible_institutions(user)
                return Class.objects.filter(institution__in=accessible_institutions)
            except ImportError:
                return Class.objects.all()

        # Teachers can see their assigned classes
        if (
            user.has_perm("academics.view_class")
            or user.user_roles.filter(role__role_type="teacher").exists()
        ):
            from apps.academics.models import SubjectAssignment

            teacher_assignments = SubjectAssignment.objects.filter(
                teacher__user=user, status="active"
            ).values_list("class_assigned", flat=True)
            return Class.objects.filter(id__in=teacher_assignments)

        # Students can see their enrolled classes
        if (
            user.has_perm("academics.view_enrollment")
            or user.user_roles.filter(role__role_type="student").exists()
        ):
            from apps.academics.models import Enrollment

            student_class_ids = Enrollment.objects.filter(
                student__user=user, status="active"
            ).values_list("class_enrolled", flat=True)
            return Class.objects.filter(id__in=student_class_ids)

        # Parents can see their children's classes
        if user.has_perm("academics.view_student") or has_role_or_perm(
            user, perm="academics.view_student", role_type="parent"
        ):
            from apps.users.models import ParentStudentRelationship
            from apps.academics.models import Enrollment

            # Get classes where parent's children are enrolled
            parent_students = ParentStudentRelationship.objects.filter(
                parent=user, status="active"
            ).values_list("student", flat=True)
            class_ids = Enrollment.objects.filter(
                student__in=parent_students, status="active"
            ).values_list("class_enrolled", flat=True)
            return Class.objects.filter(id__in=class_ids)

        # Default: no classes accessible
        return Class.objects.none()

    def get_accessible_subjects(self):
        """
        Get queryset of subjects the current user can access.
        """
        user = self.request.user
        from apps.academics.models import Subject

        # Super admin can see all subjects
        if (
            user.is_superuser
            or user.has_perm("core.view_institution")
            or user.user_roles.filter(role__role_type="super_admin").exists()
        ):
            return Subject.objects.all()

        # Admin/principal can see subjects in their accessible institutions
        if (
            user.has_perm("academics.change_subject")
            or user.user_roles.filter(
                role__role_type__in=["admin", "principal"]
            ).exists()
        ):
            try:
                from .middleware import get_user_accessible_institutions

                accessible_institutions = get_user_accessible_institutions(user)
                return Subject.objects.filter(institution__in=accessible_institutions)
            except ImportError:
                return Subject.objects.all()

        # Teachers can see subjects they're assigned to
        if (
            user.has_perm("academics.view_subject")
            or user.user_roles.filter(role__role_type="teacher").exists()
        ):
            from apps.academics.models import SubjectAssignment

            subject_ids = SubjectAssignment.objects.filter(
                teacher__user=user, status="active"
            ).values_list("subject", flat=True)
            return Subject.objects.filter(id__in=subject_ids)

        # Students/parents can see subjects from their classes
        accessible_classes = self.get_accessible_classes()
        subject_ids = []
        from apps.academics.models import SubjectAssignment, Enrollment
        from apps.users.utils import has_role_or_perm

        # For students: get subjects from enrolled classes
        if user.has_perm("academics.view_enrollment") or has_role_or_perm(
            user, perm="academics.view_enrollment", role_type="student"
        ):
            enrollments = Enrollment.objects.filter(student__user=user, status="active")
            for enrollment in enrollments:
                assignments = SubjectAssignment.objects.filter(
                    class_assigned=enrollment.class_enrolled, status="active"
                ).values_list("subject", flat=True)
                subject_ids.extend(assignments)

        # For parents: get subjects from children's classes
        elif user.has_perm("academics.view_student") or has_role_or_perm(
            user, perm="academics.view_student", role_type="parent"
        ):
            from apps.users.models import ParentStudentRelationship

            parent_students = ParentStudentRelationship.objects.filter(
                parent=user, status="active"
            ).values_list("student", flat=True)
            enrollments = Enrollment.objects.filter(
                student__in=parent_students, status="active"
            )
            for enrollment in enrollments:
                assignments = SubjectAssignment.objects.filter(
                    class_assigned=enrollment.class_enrolled, status="active"
                ).values_list("subject", flat=True)
                subject_ids.extend(assignments)

        if subject_ids:
            return Subject.objects.filter(id__in=set(subject_ids))

        return Subject.objects.none()

    def get_accessible_exams(self):
        """
        Get queryset of exams the current user can access.
        """
        from apps.assessment.models import Exam

        accessible_classes = self.get_accessible_classes()

        # Limit exams to accessible classes
        return Exam.objects.filter(academic_class__in=accessible_classes)

    def get_accessible_assignments(self):
        """
        Get queryset of assignments the current user can access.
        """
        from apps.assessment.models import Assignment

        # Students can only see assignments for their classes
        user = self.request.user
        accessible_classes = self.get_accessible_classes()

        return Assignment.objects.filter(academic_class__in=accessible_classes)

    def get_accessible_invoices(self):
        """
        Get queryset of invoices the current user can access.
        """
        from apps.finance.models import Invoice

        user = self.request.user

        # Parents can see invoices for their children
        if has_role_or_perm(user, perm="academics.view_student", role_type="parent"):
            from apps.users.models import ParentStudentRelationship

            parent_students = ParentStudentRelationship.objects.filter(
                parent=user, status="active"
            ).values_list("student", flat=True)
            return Invoice.objects.filter(student__in=parent_students)

        # Students can see their own invoices
        if has_role_or_perm(
            user, perm="academics.view_enrollment", role_type="student"
        ):
            return Invoice.objects.filter(student__user=user)

        # Staff and admins can see invoices for students they can access
        accessible_students = self.get_accessible_students()
        return Invoice.objects.filter(student__in=accessible_students)

    def get_accessible_payments(self):
        """
        Get queryset of payments the current user can access.
        """
        from apps.finance.models import Payment

        user = self.request.user

        # Parents can see payments for their children
        if has_role_or_perm(user, perm="academics.view_student", role_type="parent"):
            from apps.users.models import ParentStudentRelationship

            parent_students = ParentStudentRelationship.objects.filter(
                parent=user, status="active"
            ).values_list("student", flat=True)
            return Payment.objects.filter(student__in=parent_students)

        # Students can see their own payments
        if has_role_or_perm(
            user, perm="academics.view_enrollment", role_type="student"
        ):
            return Payment.objects.filter(student__user=user)

        # Staff and admins can see payments for students they can access
        accessible_students = self.get_accessible_students()
        return Payment.objects.filter(student__in=accessible_students)

    def get_accessible_documents(self):
        """
        Get queryset of documents the current user can access.
        """
        # All authenticated users can search documents (library access)
        try:
            from apps.library.models import Book, BookCopy

            # Scope documents to user's accessible institutions
            try:
                from apps.core.middleware import get_user_accessible_institutions

                if self.request.user.is_superuser:
                    return Book.objects.all()
                accessible_insts = get_user_accessible_institutions(self.request.user)
                return Book.objects.filter(institution__in=accessible_insts)
            except Exception:
                return Book.objects.none()
        except ImportError:
            return []

    def get(self, request):
        query = request.GET.get("q", "").strip()
        filter_type = request.GET.get("filter", "all")

        results = {
            "students": [],
            "teachers": [],
            "classes": [],
            "subjects": [],
            "exams": [],
            "assignments": [],
            "invoices": [],
            "payments": [],
            "documents": [],
        }

        if query:
            if filter_type in ["all", "students"]:
                results["students"] = self.search_students(query)
            if filter_type in ["all", "teachers"]:
                results["teachers"] = self.search_teachers(query)
            if filter_type in ["all", "classes"]:
                results["classes"] = self.search_classes(query)
            if filter_type in ["all", "subjects"]:
                results["subjects"] = self.search_subjects(query)
            if filter_type in ["all", "exams"]:
                results["exams"] = self.search_exams(query)
            if filter_type in ["all", "assignments"]:
                results["assignments"] = self.search_assignments(query)
            if filter_type in ["all", "invoices"]:
                results["invoices"] = self.search_invoices(query)
            if filter_type in ["all", "payments"]:
                results["payments"] = self.search_payments(query)
            if filter_type in ["all", "documents"]:
                results["documents"] = self.search_documents(query)

        context = {
            "query": query,
            "filter_type": filter_type,
            "results": results,
            "total_results": sum(len(res) for res in results.values()),
            "page_title": _("Search Results"),
        }

        return render(request, self.template_name, context)

    def search_students(self, query):
        """Search for students across comprehensive fields including parent emails."""
        accessible_students = self.get_accessible_students()

        return (
            accessible_students.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__email__icontains=query)
                | Q(user__mobile__icontains=query)
                |
                # Student profile fields
                Q(student_id__icontains=query)
                | Q(admission_number__icontains=query)
                | Q(place_of_birth__icontains=query)
                | Q(blood_group__icontains=query)
                | Q(nationality__icontains=query)
                | Q(religion__icontains=query)
                | Q(student_type__icontains=query)
                | Q(previous_school__icontains=query)
                |
                # Parent/Guardian fields - THIS IS KEY FOR YOUR REQUEST!
                Q(father_name__icontains=query)
                | Q(father_email__icontains=query)
                | Q(father_phone__icontains=query)
                | Q(mother_name__icontains=query)
                | Q(mother_email__icontains=query)
                | Q(mother_phone__icontains=query)
                | Q(guardian_name__icontains=query)
                | Q(guardian_email__icontains=query)
                | Q(guardian_phone__icontains=query)
                |
                # Address fields (from AddressModel)
                Q(address_line_1__icontains=query)
                | Q(address_line_2__icontains=query)
                | Q(city__icontains=query)
                | Q(state__icontains=query)
                | Q(postal_code__icontains=query)
                | Q(country__icontains=query)
                |
                # User profile fields (from profile)
                Q(user__profile__phone__icontains=query)
                | Q(user__profile__emergency_contact__icontains=query)
                | Q(user__profile__emergency_phone__icontains=query)
            )
            .distinct()
            .select_related("user__profile")[:20]
        )

    def search_teachers(self, query):
        """Search for teachers/staff across relevant fields."""
        accessible_teachers = self.get_accessible_teachers()

        # Filter the accessible teachers by the search query
        return (
            accessible_teachers.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__email__icontains=query)
                | Q(employee_id__icontains=query)
                | Q(user__profile__phone__icontains=query)
            )
            .distinct()
            .select_related("user__profile")[:10]
        )

    def search_classes(self, query):
        """Search for classes across relevant fields."""
        accessible_classes = self.get_accessible_classes()

        return (
            accessible_classes.filter(
                Q(name__icontains=query) | Q(code__icontains=query)
            )
            .distinct()
            .select_related("academic_session", "class_teacher")[:10]
        )

    def search_subjects(self, query):
        """Search for subjects across relevant fields."""
        accessible_subjects = self.get_accessible_subjects()

        return (
            accessible_subjects.filter(
                Q(name__icontains=query)
                | Q(code__icontains=query)
                | Q(description__icontains=query)
            )
            .distinct()
            .select_related("department")[:10]
        )

    def search_exams(self, query):
        """Search for exams across relevant fields."""
        accessible_exams = self.get_accessible_exams()

        return (
            accessible_exams.filter(
                Q(name__icontains=query)
                | Q(code__icontains=query)
                | Q(subject__name__icontains=query)
            )
            .distinct()
            .select_related("exam_type", "subject", "academic_class")[:10]
        )

    def search_assignments(self, query):
        """Search for assignments across relevant fields."""
        accessible_assignments = self.get_accessible_assignments()

        return (
            accessible_assignments.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(subject__name__icontains=query)
            )
            .distinct()
            .select_related("subject", "teacher", "academic_class")[:10]
        )

    def search_invoices(self, query):
        """Search for invoices across relevant fields."""
        accessible_invoices = self.get_accessible_invoices()

        return (
            accessible_invoices.filter(
                Q(invoice_number__icontains=query)
                | Q(student__user__first_name__icontains=query)
                | Q(student__user__last_name__icontains=query)
                | Q(student__student_id__icontains=query)
            )
            .distinct()
            .select_related("student__user")[:10]
        )

    def search_payments(self, query):
        """Search for payments across relevant fields."""
        accessible_payments = self.get_accessible_payments()

        return (
            accessible_payments.filter(
                Q(payment_number__icontains=query)
                | Q(reference_number__icontains=query)
                | Q(student__user__first_name__icontains=query)
                | Q(student__user__last_name__icontains=query)
                | Q(student__student_id__icontains=query)
            )
            .distinct()
            .select_related("student__user", "invoice")[:10]
        )

    def search_documents(self, query):
        """Search for documents/books across relevant fields."""
        try:
            from apps.library.models import Book, BookCopy

            # Search books
            books = Book.objects.filter(
                Q(title__icontains=query)
                | Q(isbn__icontains=query)
                | Q(authors__first_name__icontains=query)
                | Q(authors__last_name__icontains=query)
            ).distinct()[:10]

            # Search book copies for barcodes
            book_copies = BookCopy.objects.filter(
                Q(barcode__icontains=query)
            ).select_related("book")[:10]

            # Combine and deduplicate
            documents = []
            seen_books = set()

            for book in books:
                if book.id not in seen_books:
                    documents.append(
                        {
                            "type": "book",
                            "object": book,
                            "url": reverse(
                                "library:book_detail", kwargs={"pk": book.pk}
                            ),
                        }
                    )
                    seen_books.add(book.id)

            for copy in book_copies:
                if copy.book.id not in seen_books:
                    documents.append(
                        {
                            "type": "book_copy",
                            "object": copy,
                            "url": reverse(
                                "library:book_detail", kwargs={"pk": copy.book.pk}
                            ),
                        }
                    )
                    seen_books.add(copy.book.id)

            return documents[:10]

        except ImportError:
            # Library app not available
            return []
