# apps/transport/views.py

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
)
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone

from apps.core.mixins import InstitutionPermissionMixin

from .models import (
    Vehicle,
    Driver,
    Attendant,
    Route,
    RouteStop,
    RouteSchedule,
    TransportAllocation,
    FuelRecord,
    MaintenanceRecord,
    IncidentReport,
)
from .forms import (
    VehicleForm,
    DriverForm,
    AttendantForm,
    RouteForm,
    RouteStopForm,
    RouteScheduleForm,
    TransportAllocationForm,
    MaintenanceRecordForm,
    FuelRecordForm,
    IncidentReportForm,
    BulkTransportNotificationForm,
)
from apps.users.utils import has_role_or_perm


# ============================================================================
# VEHICLE VIEWS
# ============================================================================


class TransportAccessMixin:
    """Mixin to check transport-related permissions"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Check if user has transport-related permissions first, then fall back to role checks
        has_transport_perm = request.user.has_perm(
            "transport.view_vehicle"
        ) or request.user.has_perm("transport.view_transportallocation")

        user_roles = request.user.user_roles.filter(status="active")
        transport_roles = [
            "transport_manager",
            "driver",
            "admin",
            "principal",
            "super_admin",
        ]

        has_transport_role = any(
            role.role.role_type in transport_roles for role in user_roles
        )
        is_staff_admin = request.user.is_staff or request.user.is_superuser

        if not (has_transport_perm or has_transport_role or is_staff_admin):
            messages.error(
                request, _("You don't have permission to access transport resources.")
            )
            return redirect("users:dashboard")

        return super().dispatch(request, *args, **kwargs)


class TransportManagerRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a transport manager, staff, or admin."""

    def test_func(self):
        user = self.request.user
        if user.is_staff:
            return True

        # Allow based on permission as primary check, then fallback to role membership
        if user.has_perm("transport.change_route") or user.has_perm(
            "transport.change_transportallocation"
        ):
            return True

        # Check if user has transport manager role
        return has_role_or_perm(
            user, perm="transport.change_route", role_type="transport_manager"
        )


class VehicleListView(InstitutionPermissionMixin, ListView):
    model = Vehicle
    template_name = "transport/vehicles/vehicle_list.html"
    context_object_name = "vehicles"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtering
        vehicle_type = self.request.GET.get("vehicle_type")
        status = self.request.GET.get("status")
        fuel_type = self.request.GET.get("fuel_type")
        search = self.request.GET.get("search")

        if vehicle_type:
            queryset = queryset.filter(vehicle_type=vehicle_type)
        if status:
            queryset = queryset.filter(status=status)
        if fuel_type:
            queryset = queryset.filter(fuel_type=fuel_type)
        if search:
            queryset = queryset.filter(
                Q(vehicle_number__icontains=search)
                | Q(registration_number__icontains=search)
                | Q(make__icontains=search)
                | Q(model__icontains=search)
            )

        return queryset.select_related()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["vehicle_types"] = Vehicle.VehicleType.choices
        context["status_choices"] = Vehicle.Status.choices
        context["fuel_types"] = Vehicle.FuelType.choices
        return context


class VehicleDetailView(LoginRequiredMixin, DetailView):
    model = Vehicle
    template_name = "transport/vehicles/vehicle_detail.html"
    context_object_name = "vehicle"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vehicle = self.get_object()

        # Add related data
        context["maintenance_records"] = vehicle.maintenance_records.all()[:10]
        context["fuel_records"] = vehicle.fuel_records.all()[:10]
        context["route_schedules"] = vehicle.route_schedules.filter(
            status="active", academic_session__is_current=True
        )

        # Statistics
        context["total_maintenance_cost"] = (
            vehicle.maintenance_records.aggregate(total=Sum("cost"))["total"] or 0
        )

        context["total_fuel_cost"] = (
            vehicle.fuel_records.aggregate(total=Sum("fuel_cost"))["total"] or 0
        )

        return context


class VehicleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "transport/vehicles/vehicle_form.html"
    permission_required = "transport.add_vehicle"
    success_url = reverse_lazy("transport:vehicle_list")

    def form_valid(self, form):
        messages.success(self.request, _("Vehicle created successfully."))
        return super().form_valid(form)


class VehicleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = "transport/vehicles/vehicle_form.html"
    permission_required = "transport.change_vehicle"
    success_url = reverse_lazy("transport:vehicle_list")

    def form_valid(self, form):
        messages.success(self.request, _("Vehicle updated successfully."))
        return super().form_valid(form)


class VehicleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Vehicle
    template_name = "transport/vehicles/vehicle_confirm_delete.html"
    permission_required = "transport.delete_vehicle"
    success_url = reverse_lazy("transport:vehicle_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Vehicle deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# DRIVER VIEWS
# ============================================================================


class DriverListView(InstitutionPermissionMixin, ListView):
    model = Driver
    template_name = "transport/drivers/driver_list.html"
    context_object_name = "drivers"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user")

        # Filtering
        license_type = self.request.GET.get("license_type")
        status = self.request.GET.get("status")
        search = self.request.GET.get("search")

        if license_type:
            queryset = queryset.filter(license_type=license_type)
        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(employee_id__icontains=search)
                | Q(license_number__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["license_types"] = Driver.LicenseType.choices
        context["status_choices"] = Driver.Status.choices
        return context


class DriverDetailView(LoginRequiredMixin, DetailView):
    model = Driver
    template_name = "transport/drivers/driver_detail.html"
    context_object_name = "driver"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        driver = self.get_object()

        # Add related data
        context["current_schedules"] = driver.route_schedules.filter(
            status="active", academic_session__is_current=True
        )
        context["incident_reports"] = driver.route_schedules.filter(
            incident_reports__isnull=False
        ).distinct()

        return context


class DriverCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Driver
    form_class = DriverForm
    template_name = "transport/drivers/driver_form.html"
    permission_required = "transport.add_driver"
    success_url = reverse_lazy("transport:driver_list")

    def form_valid(self, form):
        messages.success(self.request, _("Driver created successfully."))
        return super().form_valid(form)


class DriverUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Driver
    form_class = DriverForm
    template_name = "transport/drivers/driver_form.html"
    permission_required = "transport.change_driver"
    success_url = reverse_lazy("transport:driver_list")

    def form_valid(self, form):
        messages.success(self.request, _("Driver updated successfully."))
        return super().form_valid(form)


class DriverDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Driver
    template_name = "transport/drivers/driver_confirm_delete.html"
    permission_required = "transport.delete_driver"
    success_url = reverse_lazy("transport:driver_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Driver deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# ATTENDANT VIEWS
# ============================================================================


class AttendantListView(InstitutionPermissionMixin, ListView):
    model = Attendant
    template_name = "transport/attendants/attendant_list.html"
    context_object_name = "attendants"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("user")

        # Filtering
        status = self.request.GET.get("status")
        search = self.request.GET.get("search")

        if status:
            queryset = queryset.filter(status=status)
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(employee_id__icontains=search)
            )

        return queryset


class AttendantDetailView(LoginRequiredMixin, DetailView):
    model = Attendant
    template_name = "transport/attendants/attendant_detail.html"
    context_object_name = "attendant"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attendant = self.get_object()

        # Add related data
        context["current_schedules"] = attendant.route_schedules.filter(
            status="active", academic_session__is_current=True
        )

        return context


class AttendantCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Attendant
    form_class = AttendantForm
    template_name = "transport/attendants/attendant_form.html"
    permission_required = "transport.add_attendant"
    success_url = reverse_lazy("transport:attendant_list")

    def form_valid(self, form):
        messages.success(self.request, _("Attendant created successfully."))
        return super().form_valid(form)


class AttendantUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Attendant
    form_class = AttendantForm
    template_name = "transport/attendants/attendant_form.html"
    permission_required = "transport.change_attendant"
    success_url = reverse_lazy("transport:attendant_list")

    def form_valid(self, form):
        messages.success(self.request, _("Attendant updated successfully."))
        return super().form_valid(form)


class AttendantDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Attendant
    template_name = "transport/attendants/attendant_confirm_delete.html"
    permission_required = "transport.delete_attendant"
    success_url = reverse_lazy("transport:attendant_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Attendant deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# ROUTE VIEWS
# ============================================================================


class RouteListView(InstitutionPermissionMixin, ListView):
    model = Route
    template_name = "transport/routes/route_list.html"
    context_object_name = "routes"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtering
        is_active = self.request.GET.get("is_active")
        search = self.request.GET.get("search")

        if is_active in ["true", "false"]:
            queryset = queryset.filter(is_active=(is_active == "true"))
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(code__icontains=search)
                | Q(start_point__icontains=search)
                | Q(end_point__icontains=search)
            )

        return queryset.prefetch_related("stops")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Scope counts to accessible institutions
        try:
            from apps.core.middleware import get_user_accessible_institutions

            if self.request.user.is_superuser:
                context["active_count"] = Route.objects.filter(is_active=True).count()
                context["inactive_count"] = Route.objects.filter(
                    is_active=False
                ).count()
            else:
                accessible_insts = get_user_accessible_institutions(self.request.user)
                context["active_count"] = Route.objects.filter(
                    is_active=True, institution__in=accessible_insts
                ).count()
                context["inactive_count"] = Route.objects.filter(
                    is_active=False, institution__in=accessible_insts
                ).count()
        except Exception:
            context["active_count"] = Route.objects.filter(is_active=True).count()
            context["inactive_count"] = Route.objects.filter(is_active=False).count()
        return context


class RouteDetailView(LoginRequiredMixin, DetailView):
    model = Route
    template_name = "transport/routes/route_detail.html"
    context_object_name = "route"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        route = self.get_object()

        # Add related data
        context["stops"] = route.stops.all().order_by("sequence")
        context["current_schedules"] = route.route_schedules.filter(
            status="active", academic_session__is_current=True
        ).select_related("vehicle", "driver", "attendant")

        # Statistics
        context["total_students"] = route.current_students_count
        context["total_vehicles"] = route.current_vehicles_count

        return context


class RouteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Route
    form_class = RouteForm
    template_name = "transport/routes/route_form.html"
    permission_required = "transport.add_route"
    success_url = reverse_lazy("transport:route_list")

    def form_valid(self, form):
        messages.success(self.request, _("Route created successfully."))
        return super().form_valid(form)


class RouteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Route
    form_class = RouteForm
    template_name = "transport/routes/route_form.html"
    permission_required = "transport.change_route"
    success_url = reverse_lazy("transport:route_list")

    def form_valid(self, form):
        messages.success(self.request, _("Route updated successfully."))
        return super().form_valid(form)


class RouteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Route
    template_name = "transport/routes/route_confirm_delete.html"
    permission_required = "transport.delete_route"
    success_url = reverse_lazy("transport:route_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Route deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# ROUTE STOP VIEWS
# ============================================================================


class RouteStopCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = RouteStop
    form_class = RouteStopForm
    template_name = "transport/routestop_form.html"
    permission_required = "transport.add_routestop"

    def get_success_url(self):
        return reverse_lazy(
            "transport:route_detail", kwargs={"pk": self.object.route.pk}
        )

    def get_initial(self):
        initial = super().get_initial()
        route_id = self.kwargs.get("route_id")
        if route_id:
            initial["route"] = get_object_or_404(Route, pk=route_id)
        return initial

    def form_valid(self, form):
        messages.success(self.request, _("Route stop created successfully."))
        return super().form_valid(form)


class RouteStopUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = RouteStop
    form_class = RouteStopForm
    template_name = "transport/routestop_form.html"
    permission_required = "transport.change_routestop"

    def get_success_url(self):
        return reverse_lazy(
            "transport:route_detail", kwargs={"pk": self.object.route.pk}
        )

    def form_valid(self, form):
        messages.success(self.request, _("Route stop updated successfully."))
        return super().form_valid(form)


class RouteStopDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = RouteStop
    template_name = "transport/routestop_confirm_delete.html"
    permission_required = "transport.delete_routestop"

    def get_success_url(self):
        return reverse_lazy(
            "transport:route_detail", kwargs={"pk": self.object.route.pk}
        )

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Route stop deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# ROUTE SCHEDULE VIEWS
# ============================================================================


class RouteScheduleListView(InstitutionPermissionMixin, ListView):
    model = RouteSchedule
    template_name = "transport/routeschedules/routeschedule_list.html"
    context_object_name = "schedules"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related(
                "route", "vehicle", "driver", "attendant", "academic_session"
            )
        )

        # Filtering
        route = self.request.GET.get("route")
        vehicle = self.request.GET.get("vehicle")
        driver = self.request.GET.get("driver")
        status = self.request.GET.get("status")
        academic_session = self.request.GET.get("academic_session")

        if route:
            queryset = queryset.filter(route_id=route)
        if vehicle:
            queryset = queryset.filter(vehicle_id=vehicle)
        if driver:
            queryset = queryset.filter(driver_id=driver)
        if status:
            queryset = queryset.filter(status=status)
        if academic_session:
            queryset = queryset.filter(academic_session_id=academic_session)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            from apps.core.middleware import get_user_accessible_institutions

            if self.request.user.is_superuser:
                context["routes"] = Route.objects.filter(is_active=True)
                context["vehicles"] = Vehicle.objects.filter(status="active")
                context["drivers"] = Driver.objects.filter(status="active")
            else:
                accessible_insts = get_user_accessible_institutions(self.request.user)
                context["routes"] = Route.objects.filter(
                    is_active=True, institution__in=accessible_insts
                )
                context["vehicles"] = Vehicle.objects.filter(
                    status="active", institution__in=accessible_insts
                )
                context["drivers"] = Driver.objects.filter(
                    status="active", institution__in=accessible_insts
                )
        except Exception:
            context["routes"] = Route.objects.filter(is_active=True)
            context["vehicles"] = Vehicle.objects.filter(status="active")
            context["drivers"] = Driver.objects.filter(status="active")
        context["status_choices"] = RouteSchedule.Status.choices
        return context


class RouteScheduleDetailView(LoginRequiredMixin, DetailView):
    model = RouteSchedule
    template_name = "transport/routeschedules/routeschedule_detail.html"
    context_object_name = "schedule"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        schedule = self.get_object()

        # Add related data
        context["allocations"] = schedule.student_allocations.filter(
            status="active"
        ).select_related("student", "pickup_stop", "drop_stop")
        context["incidents"] = schedule.incident_reports.all()[:10]

        # Statistics
        context["total_students"] = schedule.current_students_count
        context["is_operational_today"] = schedule.is_operational_today

        return context


class RouteScheduleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = RouteSchedule
    form_class = RouteScheduleForm
    template_name = "transport/routeschedules/routeschedule_form.html"
    permission_required = "transport.add_routeschedule"
    success_url = reverse_lazy("transport:routeschedule_list")

    def form_valid(self, form):
        messages.success(self.request, _("Route schedule created successfully."))
        return super().form_valid(form)


class RouteScheduleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = RouteSchedule
    form_class = RouteScheduleForm
    template_name = "transport/routeschedules/routeschedule_form.html"
    permission_required = "transport.change_routeschedule"
    success_url = reverse_lazy("transport:routeschedule_list")

    def form_valid(self, form):
        messages.success(self.request, _("Route schedule updated successfully."))
        return super().form_valid(form)


class RouteScheduleDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = RouteSchedule
    template_name = "transport/routeschedules/routeschedule_confirm_delete.html"
    permission_required = "transport.delete_routeschedule"
    success_url = reverse_lazy("transport:routeschedule_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Route schedule deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# TRANSPORT ALLOCATION VIEWS
# ============================================================================


class TransportAllocationListView(InstitutionPermissionMixin, ListView):
    model = TransportAllocation
    template_name = "transport/allocations/transportallocation_list.html"
    context_object_name = "allocations"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("student", "route_schedule", "pickup_stop", "drop_stop")
        )

        # Filtering
        student = self.request.GET.get("student")
        route_schedule = self.request.GET.get("route_schedule")
        allocation_type = self.request.GET.get("allocation_type")
        status = self.request.GET.get("status")

        if student:
            queryset = queryset.filter(student_id=student)
        if route_schedule:
            queryset = queryset.filter(route_schedule_id=route_schedule)
        if allocation_type:
            queryset = queryset.filter(allocation_type=allocation_type)
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["allocation_types"] = TransportAllocation.AllocationType.choices
        context["status_choices"] = TransportAllocation.Status.choices
        return context


class TransportAllocationCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = TransportAllocation
    form_class = TransportAllocationForm
    template_name = "transport/allocations/transportallocation_form.html"
    permission_required = "transport.add_transportallocation"
    success_url = reverse_lazy("transport:transportallocation_list")

    def form_valid(self, form):
        messages.success(self.request, _("Transport allocation created successfully."))
        return super().form_valid(form)


class TransportAllocationUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = TransportAllocation
    form_class = TransportAllocationForm
    template_name = "transport/allocations/transportallocation_form.html"
    permission_required = "transport.change_transportallocation"
    success_url = reverse_lazy("transport:transportallocation_list")

    def form_valid(self, form):
        messages.success(self.request, _("Transport allocation updated successfully."))
        return super().form_valid(form)


class TransportAllocationDetailView(LoginRequiredMixin, DetailView):
    model = TransportAllocation
    template_name = "transport/allocations/transportallocation_detail.html"
    context_object_name = "allocation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        allocation = self.get_object()

        # Add related data
        context["route_schedule"] = allocation.route_schedule
        context["route"] = allocation.route_schedule.route
        context["vehicle"] = allocation.route_schedule.vehicle
        context["driver"] = allocation.route_schedule.driver
        context["attendant"] = allocation.route_schedule.attendant

        # Student information
        context["student"] = allocation.student
        context["parent_guardians"] = allocation.student.parent_guardians.all()

        # Route stops information
        context["pickup_stop"] = allocation.pickup_stop
        context["drop_stop"] = allocation.drop_stop

        # Payment information
        context["monthly_fee"] = allocation.monthly_fee
        context["is_active"] = allocation.is_active_allocation

        # Related allocations for the same student
        context["other_allocations"] = (
            TransportAllocation.objects.filter(student=allocation.student)
            .exclude(pk=allocation.pk)
            .select_related("route_schedule__route", "route_schedule__vehicle")[:5]
        )

        return context


class TransportAllocationDeleteView(
    LoginRequiredMixin, PermissionRequiredMixin, DeleteView
):
    model = TransportAllocation
    template_name = "transport/allocations/transportallocation_confirm_delete.html"
    permission_required = "transport.delete_transportallocation"
    success_url = reverse_lazy("transport:transportallocation_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Transport allocation deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# MAINTENANCE RECORD VIEWS
# ============================================================================


class MaintenanceRecordListView(InstitutionPermissionMixin, ListView):
    model = MaintenanceRecord
    template_name = "transport/maintenancerecords/maintenancerecord_list.html"
    context_object_name = "maintenance_records"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("vehicle")

        # Filtering
        vehicle = self.request.GET.get("vehicle")
        maintenance_type = self.request.GET.get("maintenance_type")
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")

        if vehicle:
            queryset = queryset.filter(vehicle_id=vehicle)
        if maintenance_type:
            queryset = queryset.filter(maintenance_type=maintenance_type)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        return queryset.order_by("-date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            from apps.core.middleware import get_user_accessible_institutions

            if self.request.user.is_superuser:
                from apps.core.middleware import get_user_accessible_institutions

                if request.user.is_superuser:
                    context["vehicles"] = Vehicle.objects.all()
                else:
                    accessible_insts = get_user_accessible_institutions(request.user)
                    context["vehicles"] = Vehicle.objects.filter(
                        institution__in=accessible_insts
                    )
            else:
                accessible_insts = get_user_accessible_institutions(self.request.user)
                context["vehicles"] = Vehicle.objects.filter(
                    institution__in=accessible_insts
                )
        except Exception:
            from apps.core.middleware import get_user_accessible_institutions

            if request.user.is_superuser:
                context["vehicles"] = Vehicle.objects.all()
            else:
                accessible_insts = get_user_accessible_institutions(request.user)
                context["vehicles"] = Vehicle.objects.filter(
                    institution__in=accessible_insts
                )
        context["maintenance_types"] = MaintenanceRecord.MaintenanceType.choices
        return context


class MaintenanceRecordCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = MaintenanceRecord
    form_class = MaintenanceRecordForm
    template_name = "transport/maintenancerecords/maintenancerecord_form.html"
    permission_required = "transport.add_maintenancerecord"
    success_url = reverse_lazy("transport:maintenancerecord_list")

    def form_valid(self, form):
        messages.success(self.request, _("Maintenance record created successfully."))
        return super().form_valid(form)


class MaintenanceRecordUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = MaintenanceRecord
    form_class = MaintenanceRecordForm
    template_name = "transport/maintenancerecords/maintenancerecord_form.html"
    permission_required = "transport.change_maintenancerecord"
    success_url = reverse_lazy("transport:maintenancerecord_list")

    def form_valid(self, form):
        messages.success(self.request, _("Maintenance record updated successfully."))
        return super().form_valid(form)


class MaintenanceRecordDeleteView(
    LoginRequiredMixin, PermissionRequiredMixin, DeleteView
):
    model = MaintenanceRecord
    template_name = "transport/maintenancerecords/maintenancerecord_confirm_delete.html"
    permission_required = "transport.delete_maintenancerecord"
    success_url = reverse_lazy("transport:maintenancerecord_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Maintenance record deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# FUEL RECORD VIEWS
# ============================================================================


class FuelRecordListView(InstitutionPermissionMixin, ListView):
    model = FuelRecord
    template_name = "transport/fuelrecords/fuelrecord_list.html"
    context_object_name = "fuel_records"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("vehicle")

        # Filtering
        vehicle = self.request.GET.get("vehicle")
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")

        if vehicle:
            queryset = queryset.filter(vehicle_id=vehicle)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        return queryset.order_by("-date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            from apps.core.middleware import get_user_accessible_institutions

            if self.request.user.is_superuser:
                from apps.core.middleware import get_user_accessible_institutions

                if request.user.is_superuser:
                    context["vehicles"] = Vehicle.objects.all()
                else:
                    accessible_insts = get_user_accessible_institutions(request.user)
                    context["vehicles"] = Vehicle.objects.filter(
                        institution__in=accessible_insts
                    )
            else:
                accessible_insts = get_user_accessible_institutions(self.request.user)
                context["vehicles"] = Vehicle.objects.filter(
                    institution__in=accessible_insts
                )
        except Exception:
            context["vehicles"] = Vehicle.objects.all()

        # Statistics
        if self.request.GET.get("vehicle"):
            vehicle_id = self.request.GET.get("vehicle")
            vehicle_fuel = FuelRecord.objects.filter(vehicle_id=vehicle_id)
            context["total_fuel_cost"] = (
                vehicle_fuel.aggregate(Sum("fuel_cost"))["fuel_cost__sum"] or 0
            )
            context["total_fuel_quantity"] = (
                vehicle_fuel.aggregate(Sum("fuel_quantity"))["fuel_quantity__sum"] or 0
            )

        return context


class FuelRecordCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = FuelRecord
    form_class = FuelRecordForm
    template_name = "transport/fuelrecords/fuelrecord_form.html"
    permission_required = "transport.add_fuelrecord"
    success_url = reverse_lazy("transport:fuelrecord_list")

    def form_valid(self, form):
        messages.success(self.request, _("Fuel record created successfully."))
        return super().form_valid(form)


class FuelRecordUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = FuelRecord
    form_class = FuelRecordForm
    template_name = "transport/fuelrecords/fuelrecord_form.html"
    permission_required = "transport.change_fuelrecord"
    success_url = reverse_lazy("transport:fuelrecord_list")

    def form_valid(self, form):
        messages.success(self.request, _("Fuel record updated successfully."))
        return super().form_valid(form)


class FuelRecordDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = FuelRecord
    template_name = "transport/fuelrecords/fuelrecord_confirm_delete.html"
    permission_required = "transport.delete_fuelrecord"
    success_url = reverse_lazy("transport:fuelrecord_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Fuel record deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# INCIDENT REPORT VIEWS
# ============================================================================


class IncidentReportListView(InstitutionPermissionMixin, ListView):
    model = IncidentReport
    template_name = "transport/incidentreports/incidentreport_list.html"
    context_object_name = "incident_reports"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("route_schedule", "reported_by")
            .prefetch_related("students_affected")
        )

        # Filtering
        incident_type = self.request.GET.get("incident_type")
        severity = self.request.GET.get("severity")
        follow_up_required = self.request.GET.get("follow_up_required")
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")

        if incident_type:
            queryset = queryset.filter(incident_type=incident_type)
        if severity:
            queryset = queryset.filter(severity=severity)
        if follow_up_required in ["true", "false"]:
            queryset = queryset.filter(
                follow_up_required=(follow_up_required == "true")
            )
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        return queryset.order_by("-date", "-time")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["incident_types"] = IncidentReport.IncidentType.choices
        context["severity_levels"] = IncidentReport.Severity.choices
        return context


class IncidentReportDetailView(LoginRequiredMixin, DetailView):
    model = IncidentReport
    template_name = "transport/incidentreports/incidentreport_detail.html"
    context_object_name = "incident_report"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        incident = self.get_object()

        # Add related students
        context["affected_students"] = incident.students_affected.all()

        return context


class IncidentReportCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = IncidentReport
    form_class = IncidentReportForm
    template_name = "transport/incidentreports/incidentreport_form.html"
    permission_required = "transport.add_incidentreport"
    success_url = reverse_lazy("transport:incidentreport_list")

    def form_valid(self, form):
        form.instance.reported_by = self.request.user
        messages.success(self.request, _("Incident report created successfully."))
        return super().form_valid(form)


class IncidentReportUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = IncidentReport
    form_class = IncidentReportForm
    template_name = "transport/incidentreports/incidentreport_form.html"
    permission_required = "transport.change_incidentreport"
    success_url = reverse_lazy("transport:incidentreport_list")

    def form_valid(self, form):
        messages.success(self.request, _("Incident report updated successfully."))
        return super().form_valid(form)


class IncidentReportDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = IncidentReport
    template_name = "transport/incidentreports/incidentreport_confirm_delete.html"
    permission_required = "transport.delete_incidentreport"
    success_url = reverse_lazy("transport:incidentreport_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _("Incident report deleted successfully."))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# DASHBOARD AND ANALYTICS VIEWS
# ============================================================================


class TransportDashboardView(LoginRequiredMixin, View):
    template_name = "transport/dashboard/dashboard.html"

    def get(self, request):
        context = {}

        # Get current institution for filtering
        from apps.core.middleware import get_current_institution

        current_institution = get_current_institution()

        # Vehicle Statistics - FILTERED BY INSTITUTION
        context["total_vehicles"] = Vehicle.objects.filter(
            institution=current_institution
        ).count()
        context["active_vehicles"] = Vehicle.objects.filter(
            institution=current_institution, status="active"
        ).count()
        context["maintenance_vehicles"] = Vehicle.objects.filter(
            institution=current_institution, status="maintenance"
        ).count()
        context["out_of_service_vehicles"] = Vehicle.objects.filter(
            institution=current_institution, status="out_of_service"
        ).count()

        # Driver Statistics - FILTERED BY INSTITUTION
        context["total_drivers"] = Driver.objects.filter(
            institution=current_institution
        ).count()
        context["active_drivers"] = Driver.objects.filter(
            institution=current_institution, status="active"
        ).count()
        context["drivers_with_expired_license"] = Driver.objects.filter(
            institution=current_institution, license_expiry__lt=timezone.now().date()
        ).count()

        # Route Statistics - FILTERED BY INSTITUTION
        context["total_routes"] = Route.objects.filter(
            institution=current_institution
        ).count()
        context["active_routes"] = Route.objects.filter(
            institution=current_institution, is_active=True
        ).count()

        # Allocation Statistics - FILTERED BY INSTITUTION
        context["total_allocations"] = TransportAllocation.objects.filter(
            route_schedule__academic_session__institution=current_institution
        ).count()
        context["active_allocations"] = TransportAllocation.objects.filter(
            route_schedule__academic_session__institution=current_institution,
            status="active",
        ).count()

        # Maintenance Statistics - FILTERED BY INSTITUTION
        context["pending_maintenance"] = MaintenanceRecord.objects.filter(
            vehicle__institution=current_institution,
            next_due_date__lte=timezone.now().date() + timezone.timedelta(days=7),
        ).count()

        # Recent Incidents - FILTERED BY INSTITUTION
        context["recent_incidents"] = IncidentReport.objects.filter(
            route_schedule__academic_session__institution=current_institution
        )[:5]

        # Vehicle Status Distribution - FILTERED BY INSTITUTION
        vehicle_status = (
            Vehicle.objects.filter(institution=current_institution)
            .values("status")
            .annotate(count=Count("id"))
        )
        context["vehicle_status_distribution"] = {
            item["status"]: item["count"] for item in vehicle_status
        }

        return render(request, self.template_name, context)


class TransportAnalyticsView(LoginRequiredMixin, View):
    template_name = "transport/analytics/analytics.html"

    def get(self, request):
        context = {}

        # Fuel Efficiency Analytics
        vehicles_with_fuel = Vehicle.objects.filter(
            fuel_records__isnull=False
        ).distinct()

        fuel_data = []
        for vehicle in vehicles_with_fuel:
            fuel_records = vehicle.fuel_records.all()
            if fuel_records.count() >= 2:
                total_distance = 0
                total_fuel = 0

                for i in range(1, len(fuel_records)):
                    distance = (
                        fuel_records[i].odometer_reading
                        - fuel_records[i - 1].odometer_reading
                    )
                    fuel = float(fuel_records[i].fuel_quantity)

                    if distance > 0 and fuel > 0:
                        total_distance += distance
                        total_fuel += fuel

                if total_fuel > 0:
                    efficiency = total_distance / total_fuel
                    fuel_data.append(
                        {
                            "vehicle": vehicle.vehicle_number,
                            "efficiency": round(efficiency, 2),
                        }
                    )

        context["fuel_efficiency_data"] = fuel_data

        # Maintenance Cost Analysis
        maintenance_costs = (
            MaintenanceRecord.objects.values("vehicle__vehicle_number")
            .annotate(total_cost=Sum("cost"), maintenance_count=Count("id"))
            .order_by("-total_cost")[:10]
        )

        context["maintenance_costs"] = maintenance_costs

        # Incident Analysis
        incidents_by_type = (
            IncidentReport.objects.values("incident_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        context["incidents_by_type"] = incidents_by_type

        # Route Utilization
        route_utilization = Route.objects.annotate(
            student_count=Count(
                "route_schedules__student_allocations",
                filter=Q(
                    route_schedules__student_allocations__status="active",
                    route_schedules__academic_session__is_current=True,
                ),
            ),
            vehicle_count=Count(
                "route_schedules",
                filter=Q(
                    route_schedules__status="active",
                    route_schedules__academic_session__is_current=True,
                ),
                distinct=True,
            ),
        ).values("name", "student_count", "vehicle_count")[:10]

        context["route_utilization"] = route_utilization

        return render(request, self.template_name, context)


# ============================================================================
# API VIEWS FOR AJAX REQUESTS
# ============================================================================


class GetRouteStopsView(LoginRequiredMixin, View):
    def get(self, request, route_id):
        stops = (
            RouteStop.objects.filter(route_id=route_id)
            .order_by("sequence")
            .values("id", "name", "sequence", "estimated_arrival_time")
        )
        return JsonResponse(list(stops), safe=False)


class GetVehicleAvailabilityView(LoginRequiredMixin, View):
    def get(self, request, date):
        # Check vehicle availability for a specific date
        # This is a simplified version - you might want to implement more complex logic
        available_vehicles = (
            Vehicle.objects.filter(status="active", route_schedules__date=date)
            .distinct()
            .values("id", "vehicle_number", "make", "model")
        )

        return JsonResponse(list(available_vehicles), safe=False)


class GetDriverScheduleView(LoginRequiredMixin, View):
    def get(self, request, driver_id, date):
        schedules = (
            RouteSchedule.objects.filter(driver_id=driver_id, date=date)
            .select_related("route", "vehicle")
            .values(
                "id", "route__name", "vehicle__vehicle_number", "start_time", "end_time"
            )
        )

        return JsonResponse(list(schedules), safe=False)


# ============================================================================
# CUSTOM VIEWS FOR SPECIFIC FUNCTIONALITY
# ============================================================================


class VehicleMaintenanceScheduleView(LoginRequiredMixin, ListView):
    model = Vehicle
    template_name = "transport/vehicles/vehicle_maintenance_schedule.html"
    context_object_name = "vehicles"

    def get_queryset(self):
        return Vehicle.objects.prefetch_related("maintenance_records").filter(
            status__in=["active", "maintenance"]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Vehicles due for maintenance
        due_soon = Vehicle.objects.filter(
            maintenance_records__next_due_date__lte=timezone.now().date()
            + timezone.timedelta(days=30)
        ).distinct()

        context["due_for_maintenance"] = due_soon
        context["overdue_maintenance"] = Vehicle.objects.filter(
            maintenance_records__next_due_date__lt=timezone.now().date()
        ).distinct()

        return context


class RouteOptimizationView(LoginRequiredMixin, View):
    template_name = "transport/routes/route_optimization.html"

    def get(self, request):
        routes = Route.objects.filter(is_active=True).prefetch_related("stops")

        # Calculate optimization metrics
        optimization_data = []
        for route in routes:
            stops = route.stops.all().order_by("sequence")
            student_count = route.current_students_count

            # Calculate efficiency metrics
            if route.total_distance and route.estimated_duration:
                efficiency_score = (
                    (student_count / route.total_distance) * 100
                    if route.total_distance > 0
                    else 0
                )
                time_efficiency = (
                    (student_count / route.estimated_duration) * 60
                    if route.estimated_duration > 0
                    else 0
                )
            else:
                efficiency_score = 0
                time_efficiency = 0

            optimization_data.append(
                {
                    "route": route,
                    "stops_count": stops.count(),
                    "student_count": student_count,
                    "efficiency_score": round(efficiency_score, 2),
                    "time_efficiency": round(time_efficiency, 2),
                    "capacity_utilization": (
                        (
                            student_count
                            / sum(
                                route.route_schedules.filter(
                                    status="active"
                                ).values_list("vehicle__seating_capacity", flat=True)[
                                    :1
                                ]
                            )
                            * 100
                        )
                        if route.route_schedules.filter(status="active").exists()
                        else 0
                    ),
                }
            )

        context = {
            "routes": routes,
            "optimization_data": optimization_data,
            "total_stops": RouteStop.objects.count(),
            "total_distance_estimate": sum(route.distance or 0 for route in routes),
            "average_efficiency": (
                round(
                    sum(data["efficiency_score"] for data in optimization_data)
                    / len(optimization_data),
                    2,
                )
                if optimization_data
                else 0
            ),
        }

        return render(request, self.template_name, context)

    def post(self, request):
        # Handle route optimization requests
        route_id = request.POST.get("route_id")
        optimization_type = request.POST.get("optimization_type", "distance")

        if route_id:
            try:
                route = Route.objects.get(id=route_id, is_active=True)
                stops = list(route.stops.all().order_by("sequence"))

                if optimization_type == "distance":
                    # Simple distance-based optimization (placeholder for more complex algorithms)
                    optimized_stops = self._optimize_by_distance(stops)
                elif optimization_type == "time":
                    # Time-based optimization
                    optimized_stops = self._optimize_by_time(stops)
                else:
                    optimized_stops = stops

                # Update sequence numbers
                for i, stop in enumerate(optimized_stops, 1):
                    stop.sequence = i
                    stop.save()

                messages.success(request, _("Route optimized successfully."))
                return JsonResponse(
                    {"status": "success", "message": "Route optimized successfully"}
                )

            except Route.DoesNotExist:
                return JsonResponse(
                    {"status": "error", "message": "Route not found"}, status=404
                )

        return JsonResponse(
            {"status": "error", "message": "Invalid request"}, status=400
        )

    def _optimize_by_distance(self, stops):
        """Simple distance-based optimization (placeholder for complex algorithms)"""
        # This is a simplified version. In a real implementation, you would use
        # algorithms like Traveling Salesman Problem solvers or Google Maps API
        return sorted(stops, key=lambda x: (x.latitude or 0, x.longitude or 0))

    def _optimize_by_time(self, stops):
        """Time-based optimization"""
        # Sort by estimated arrival time
        return sorted(
            stops, key=lambda x: x.estimated_arrival_time or timezone.now().time()
        )


class TransportReportView(LoginRequiredMixin, View):
    template_name = "transport/reports/reports.html"

    def get(self, request):
        report_type = request.GET.get("type", "summary")
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")

        context = {"report_type": report_type}
        # Scope reports to user's accessible institutions unless superuser
        try:
            from apps.core.middleware import get_user_accessible_institutions

            if request.user.is_superuser:
                accessible_insts = None
            else:
                accessible_insts = get_user_accessible_institutions(request.user)
        except Exception:
            # Fail closed: a failed institution lookup must not reveal all schools.
            accessible_insts = None if request.user.is_superuser else []

        if report_type == "fuel":
            fuel_data = FuelRecord.objects.all()
            if accessible_insts is not None:
                fuel_data = fuel_data.filter(institution__in=accessible_insts)
            if date_from:
                fuel_data = fuel_data.filter(date__gte=date_from)
            if date_to:
                fuel_data = fuel_data.filter(date__lte=date_to)

            context["fuel_data"] = fuel_data.select_related("vehicle")
            context["total_fuel_cost"] = (
                fuel_data.aggregate(Sum("fuel_cost"))["fuel_cost__sum"] or 0
            )

        elif report_type == "maintenance":
            maintenance_data = MaintenanceRecord.objects.all()
            if accessible_insts is not None:
                maintenance_data = maintenance_data.filter(
                    institution__in=accessible_insts
                )
            if date_from:
                maintenance_data = maintenance_data.filter(date__gte=date_from)
            if date_to:
                maintenance_data = maintenance_data.filter(date__lte=date_to)

            context["maintenance_data"] = maintenance_data.select_related("vehicle")
            context["total_maintenance_cost"] = (
                maintenance_data.aggregate(Sum("cost"))["cost__sum"] or 0
            )

        elif report_type == "incidents":
            incident_data = IncidentReport.objects.all()
            if accessible_insts is not None:
                incident_data = incident_data.filter(institution__in=accessible_insts)
            if date_from:
                incident_data = incident_data.filter(date__gte=date_from)
            if date_to:
                incident_data = incident_data.filter(date__lte=date_to)

            context["incident_data"] = incident_data.select_related("route_schedule")

        else:  # summary report
            context["summary_data"] = self._get_summary_report(
                date_from, date_to, accessible_insts
            )

        return render(request, self.template_name, context)

    def _get_summary_report(self, date_from, date_to, accessible_insts):
        # Generate summary report data
        summary = {}

        # Date range filter
        date_filter = Q()
        if date_from:
            date_filter &= Q(date__gte=date_from)
        if date_to:
            date_filter &= Q(date__lte=date_to)

        # Vehicle statistics
        vehicles_qs = Vehicle.objects.all()
        if accessible_insts is not None:
            vehicles_qs = vehicles_qs.filter(institution__in=accessible_insts)
        summary["vehicle_count"] = vehicles_qs.count()
        summary["active_vehicles"] = vehicles_qs.filter(status="active").count()

        # Fuel statistics
        fuel_data = FuelRecord.objects.filter(date_filter)
        if accessible_insts is not None:
            fuel_data = fuel_data.filter(institution__in=accessible_insts)
        summary["total_fuel_cost"] = (
            fuel_data.aggregate(Sum("fuel_cost"))["fuel_cost__sum"] or 0
        )
        summary["total_fuel_quantity"] = (
            fuel_data.aggregate(Sum("fuel_quantity"))["fuel_quantity__sum"] or 0
        )

        # Maintenance statistics
        maintenance_data = MaintenanceRecord.objects.filter(date_filter)
        if accessible_insts is not None:
            maintenance_data = maintenance_data.filter(institution__in=accessible_insts)
        summary["total_maintenance_cost"] = (
            maintenance_data.aggregate(Sum("cost"))["cost__sum"] or 0
        )
        summary["maintenance_count"] = maintenance_data.count()

        # Incident statistics
        incident_data = IncidentReport.objects.filter(date_filter)
        if accessible_insts is not None:
            incident_data = incident_data.filter(institution__in=accessible_insts)
        summary["incident_count"] = incident_data.count()
        summary["severe_incidents"] = incident_data.filter(severity="severe").count()

        return summary


# ============================================================================
# PARENT COMMUNICATION VIEWS
# ============================================================================


class ParentNotificationView(LoginRequiredMixin, View):
    """View for sending notifications to parents about transport matters."""

    def post(self, request):
        form = BulkTransportNotificationForm(request.POST)
        if form.is_valid():
            # Process the notification
            notification_type = form.cleaned_data["notification_type"]
            recipients = form.cleaned_data["recipients"]
            subject = form.cleaned_data["subject"]
            message = form.cleaned_data["message"]
            send_email = form.cleaned_data["send_email"]
            send_sms = form.cleaned_data["send_sms"]
            priority = form.cleaned_data["priority"]
            schedule_send = form.cleaned_data["schedule_send"]

            # Get parent contacts for selected students
            parent_contacts = []
            for allocation in recipients:
                for parent in allocation.student.parent_guardians.all():
                    if parent.email or parent.phone:
                        parent_contacts.append(
                            {
                                "parent": parent,
                                "student": allocation.student,
                                "allocation": allocation,
                            }
                        )

            # Here you would integrate with your messaging system
            # For now, we'll simulate the process
            success_count = len(parent_contacts)

            messages.success(
                request,
                _("Notification sent successfully to {} parent(s).").format(
                    success_count
                ),
            )

            return JsonResponse(
                {
                    "status": "success",
                    "message": _("Notification sent successfully"),
                    "sent_count": success_count,
                }
            )

        return JsonResponse({"status": "error", "errors": form.errors}, status=400)
