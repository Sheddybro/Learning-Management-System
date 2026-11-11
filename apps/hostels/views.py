# apps/hostels/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)

from apps.core.mixins import InstitutionPermissionMixin
from apps.users.utils import has_role_or_perm

from .models import (
    Hostel,
    Room,
    Bed,
    HostelAllocation,
    HostelFee,
    VisitorLog,
    MaintenanceRequest,
    InventoryItem,
)
from .forms import (
    HostelForm,
    RoomForm,
    BedForm,
    HostelAllocationForm,
    HostelFeeForm,
    VisitorLogForm,
    MaintenanceRequestForm,
    InventoryItemForm,
    HostelSearchForm,
)


# Dashboard and Overview Views
@login_required
def hostel_dashboard(request):
    """
    Dashboard view showing hostel overview and statistics.
    """
    from apps.core.middleware import get_current_institution

    current_institution = get_current_institution()

    if not current_institution:
        messages.warning(request, _("Please select an institution to continue."))
        return redirect("core:institution_select")

    hostels = Hostel.objects.filter(is_active=True, institution=current_institution)

    # Statistics
    total_hostels = hostels.count()
    total_rooms = Room.objects.filter(hostel__in=hostels).count()
    total_beds = Bed.objects.filter(room__hostel__in=hostels).count()
    total_allocations = HostelAllocation.objects.filter(
        status="active", bed__room__hostel__institution=current_institution
    ).count()

    # Occupancy statistics
    total_capacity = sum(hostel.capacity for hostel in hostels)
    total_occupancy = sum(hostel.current_occupancy for hostel in hostels)
    overall_occupancy_rate = (
        (total_occupancy / total_capacity * 100) if total_capacity > 0 else 0
    )

    # Recent activities
    recent_allocations = (
        HostelAllocation.objects.select_related("student__user", "bed__room__hostel")
        .filter(bed__room__hostel__institution=current_institution)
        .order_by("-created_at")[:5]
    )

    recent_visitors = (
        VisitorLog.objects.select_related("hostel", "visiting_student__user")
        .filter(hostel__institution=current_institution)
        .order_by("-check_in_time")[:5]
    )

    pending_maintenance = MaintenanceRequest.objects.filter(
        hostel__institution=current_institution, status__in=["pending", "in_progress"]
    ).count()

    overdue_fees = HostelFee.objects.filter(
        allocation__bed__room__hostel__institution=current_institution,
        status__in=["pending", "partial"],
        due_date__lt=timezone.now().date(),
    ).count()

    context = {
        "total_hostels": total_hostels,
        "total_rooms": total_rooms,
        "total_beds": total_beds,
        "total_allocations": total_allocations,
        "total_capacity": total_capacity,
        "total_occupancy": total_occupancy,
        "overall_occupancy_rate": round(overall_occupancy_rate, 2),
        "recent_allocations": recent_allocations,
        "recent_visitors": recent_visitors,
        "pending_maintenance": pending_maintenance,
        "overdue_fees": overdue_fees,
        "hostels": hostels,
    }

    return render(request, "hostels/dashboard/dashboard.html", context)


# Hostel Management Views
class HostelAccessMixin:
    """Mixin to check hostel-related permissions"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Check if user has hostel-related role or is staff/admin
        user_roles = request.user.user_roles.all()
        hostel_roles = ["hostel_warden", "admin", "principal", "super_admin"]

        if not any(role.role.role_type in hostel_roles for role in user_roles):
            if not request.user.is_staff:
                # Students can access hostel info but with limited permissions
                if not hasattr(request.user, "student_profile"):
                    messages.error(
                        request,
                        _("You don't have permission to access hostel resources."),
                    )
                    return redirect("users:dashboard")

        return super().dispatch(request, *args, **kwargs)


class HostelWardenRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a hostel warden, staff, or admin."""

    def test_func(self):
        user = self.request.user
        if user.is_staff:
            return True

        # Check if user has hostel warden role
        return has_role_or_perm(
            user, perm="hostels.change_hostel", role_type="hostel_warden"
        )


class HostelListView(InstitutionPermissionMixin, ListView):
    model = Hostel
    template_name = "hostels/hostels/hostel_list.html"
    context_object_name = "hostels"
    paginate_by = 10

    def get_queryset(self):
        queryset = Hostel.objects.select_related("warden", "assistant_warden")

        # Filtering
        hostel_type = self.request.GET.get("hostel_type")
        category = self.request.GET.get("category")
        is_active = self.request.GET.get("is_active")

        if hostel_type:
            queryset = queryset.filter(hostel_type=hostel_type)
        if category:
            queryset = queryset.filter(category=category)
        if is_active:
            queryset = queryset.filter(is_active=(is_active == "true"))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hostel_types"] = Hostel.HostelType.choices
        context["categories"] = Hostel.HostelCategory.choices
        return context


class HostelDetailView(LoginRequiredMixin, DetailView):
    model = Hostel
    template_name = "hostels/hostels/hostel_detail.html"
    context_object_name = "hostel"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hostel = self.get_object()

        # Room statistics
        rooms = hostel.rooms.all()
        context["total_rooms"] = rooms.count()
        context["available_rooms"] = rooms.filter(is_available=True).count()
        context["rooms_need_maintenance"] = rooms.filter(
            maintenance_required=True
        ).count()

        # Allocation statistics
        allocations = HostelAllocation.objects.filter(
            bed__room__hostel=hostel, status="active"
        )
        context["current_allocations"] = allocations.count()

        # Recent visitors
        context["recent_visitors"] = hostel.visitors.all().order_by("-check_in_time")[
            :10
        ]

        # Pending maintenance
        context["pending_maintenance"] = hostel.maintenance_requests.filter(
            status__in=["pending", "in_progress"]
        ).count()

        return context


class HostelCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Hostel
    form_class = HostelForm
    template_name = "hostels/hostels/hostel_form.html"
    permission_required = "hostels.add_hostel"
    success_url = reverse_lazy("hostels:hostel_list")

    def form_valid(self, form):
        messages.success(self.request, _("Hostel created successfully."))
        return super().form_valid(form)


class HostelUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Hostel
    form_class = HostelForm
    template_name = "hostels/hostels/hostel_form.html"
    permission_required = "hostels.change_hostel"
    success_url = reverse_lazy("hostels:hostel_list")

    def form_valid(self, form):
        messages.success(self.request, _("Hostel updated successfully."))
        return super().form_valid(form)


class HostelDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Hostel
    template_name = "hostels/hostels/hostel_confirm_delete.html"
    permission_required = "hostels.delete_hostel"
    success_url = reverse_lazy("hostels:hostel_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Hostel deleted successfully."))
        return super().delete(request, *args, **kwargs)


# Room Management Views
class RoomListView(InstitutionPermissionMixin, ListView):
    model = Room
    template_name = "hostels/rooms/room_list.html"
    context_object_name = "rooms"
    paginate_by = 15

    def get_queryset(self):
        queryset = Room.objects.select_related("hostel", "preferred_class")

        # Filter by hostel
        hostel_id = self.request.GET.get("hostel")
        if hostel_id:
            queryset = queryset.filter(hostel_id=hostel_id)

        # Filter by availability
        is_available = self.request.GET.get("is_available")
        if is_available:
            queryset = queryset.filter(is_available=(is_available == "true"))

        # Filter by maintenance status
        maintenance_required = self.request.GET.get("maintenance_required")
        if maintenance_required:
            queryset = queryset.filter(
                maintenance_required=(maintenance_required == "true")
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hostels"] = Hostel.objects.filter(is_active=True)
        context["room_types"] = Room.RoomType.choices
        return context


class RoomDetailView(LoginRequiredMixin, DetailView):
    model = Room
    template_name = "hostels/rooms/room_detail.html"
    context_object_name = "room"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room = self.get_object()

        # Current residents
        context["current_residents"] = room.get_current_residents()

        # Bed information
        context["beds"] = room.beds.all()

        # Maintenance history
        context["maintenance_history"] = room.maintenance_requests.all().order_by(
            "-requested_date"
        )[:10]

        return context


class RoomCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Room
    form_class = RoomForm
    template_name = "hostels/rooms/room_form.html"
    permission_required = "hostels.add_room"

    def get_success_url(self):
        return reverse_lazy("hostels:room_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Room created successfully."))
        return super().form_valid(form)


class RoomUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Room
    form_class = RoomForm
    template_name = "hostels/rooms/room_form.html"
    permission_required = "hostels.change_room"

    def get_success_url(self):
        return reverse_lazy("hostels:room_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Room updated successfully."))
        return super().form_valid(form)


# Bed Management Views
class BedListView(InstitutionPermissionMixin, ListView):
    model = Bed
    template_name = "hostels/beds/bed_list.html"
    context_object_name = "beds"
    paginate_by = 20

    def get_queryset(self):
        queryset = Bed.objects.select_related("room__hostel")

        # Filter by hostel
        hostel_id = self.request.GET.get("hostel")
        if hostel_id:
            queryset = queryset.filter(room__hostel_id=hostel_id)

        # Filter by room
        room_id = self.request.GET.get("room")
        if room_id:
            queryset = queryset.filter(room_id=room_id)

        # Filter by availability
        is_available = self.request.GET.get("is_available")
        if is_available:
            queryset = queryset.filter(is_available=(is_available == "true"))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hostels"] = Hostel.objects.filter(is_active=True)
        context["bed_types"] = Bed.BedType.choices
        return context


class BedCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Bed
    form_class = BedForm
    template_name = "hostels/beds/bed_form.html"
    permission_required = "hostels.add_bed"

    def get_success_url(self):
        return reverse_lazy("hostels:bed_list")

    def form_valid(self, form):
        messages.success(self.request, _("Bed created successfully."))
        return super().form_valid(form)


class BedUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Bed
    form_class = BedForm
    template_name = "hostels/beds/bed_form.html"
    permission_required = "hostels.change_bed"

    def get_success_url(self):
        return reverse_lazy("hostels:bed_list")

    def form_valid(self, form):
        messages.success(self.request, _("Bed updated successfully."))
        return super().form_valid(form)


# Hostel Allocation Views
class HostelAllocationListView(InstitutionPermissionMixin, ListView):
    model = HostelAllocation
    template_name = "hostels/allocations/allocation_list.html"
    context_object_name = "allocations"
    paginate_by = 15

    def get_queryset(self):
        queryset = HostelAllocation.objects.select_related(
            "student__user",
            "bed__room__hostel",
            "academic_session",
            "class_enrolled",
            "allocated_by",
        )

        form = HostelSearchForm(self.request.GET)
        if form.is_valid():
            # Filter by status
            status = form.cleaned_data.get("status")
            if status:
                queryset = queryset.filter(status=status)

            # Filter by hostel
            hostel = form.cleaned_data.get("hostel")
            if hostel:
                queryset = queryset.filter(bed__room__hostel=hostel)

            # Filter by academic session
            academic_session = form.cleaned_data.get("academic_session")
            if academic_session:
                queryset = queryset.filter(academic_session=academic_session)

            # Filter by class
            class_enrolled = form.cleaned_data.get("class_enrolled")
            if class_enrolled:
                queryset = queryset.filter(class_enrolled=class_enrolled)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = HostelSearchForm(self.request.GET)
        return context


class HostelAllocationCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = HostelAllocation
    form_class = HostelAllocationForm
    template_name = "hostels/allocations/allocation_form.html"
    permission_required = "hostels.add_hostelallocation"

    def get_success_url(self):
        return reverse_lazy("hostels:allocation_list")

    def form_valid(self, form):
        form.instance.allocated_by = self.request.user
        messages.success(self.request, _("Student allocated to hostel successfully."))
        return super().form_valid(form)


class HostelAllocationDetailView(LoginRequiredMixin, DetailView):
    model = HostelAllocation
    template_name = "hostels/allocations/allocation_detail.html"
    context_object_name = "allocation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        allocation = self.get_object()

        # Related fees
        context["fees"] = allocation.fees.all().order_by("-year", "-month")

        # Outstanding balance
        context["outstanding_balance"] = allocation.outstanding_balance

        # Transfer history (if any)
        context["transfer_history"] = (
            HostelAllocation.objects.filter(
                student=allocation.student, academic_session=allocation.academic_session
            )
            .exclude(pk=allocation.pk)
            .order_by("-created_at")
        )

        return context


class HostelAllocationUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = HostelAllocation
    form_class = HostelAllocationForm
    template_name = "hostels/allocations/allocation_form.html"
    permission_required = "hostels.change_hostelallocation"

    def get_success_url(self):
        return reverse_lazy("hostels:allocation_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Allocation updated successfully."))
        return super().form_valid(form)


@login_required
@permission_required("hostels.change_hostelallocation")
def transfer_allocation(request, pk):
    """
    View for transferring a student to a different bed.
    """
    allocation = get_object_or_404(HostelAllocation, pk=pk)

    if request.method == "POST":
        new_bed_id = request.POST.get("new_bed")
        notes = request.POST.get("notes", "")

        try:
            new_bed = Bed.objects.get(pk=new_bed_id, is_available=True)
            new_allocation = allocation.transfer_bed(new_bed, request.user, notes)

            messages.success(request, _("Student transferred successfully."))
            return redirect("hostels:allocation_detail", pk=new_allocation.pk)

        except Bed.DoesNotExist:
            messages.error(request, _("Selected bed is not available."))
        except ValidationError as e:
            messages.error(request, str(e))

    # Get available beds in the same hostel
    available_beds = Bed.objects.filter(
        room__hostel=allocation.bed.room.hostel, is_available=True
    ).exclude(pk=allocation.bed.pk)

    context = {
        "allocation": allocation,
        "available_beds": available_beds,
    }

    return render(request, "hostels/allocations/allocation_transfer.html", context)


@login_required
@permission_required("hostels.change_hostelallocation")
def check_out_student(request, pk):
    """
    View for checking out a student from hostel.
    """
    allocation = get_object_or_404(HostelAllocation, pk=pk)

    if request.method == "POST":
        allocation.status = HostelAllocation.AllocationStatus.COMPLETED
        allocation.actual_departure_date = timezone.now().date()
        allocation.save()

        messages.success(request, _("Student checked out successfully."))
        return redirect("hostels:allocation_list")

    context = {
        "allocation": allocation,
    }

    return render(request, "hostels/allocations/allocation_checkout.html", context)


# Hostel Fee Views
class HostelFeeListView(InstitutionPermissionMixin, ListView):
    model = HostelFee
    template_name = "hostels/fees/fee_list.html"
    context_object_name = "fees"
    paginate_by = 20

    def get_queryset(self):
        queryset = HostelFee.objects.select_related(
            "allocation__student__user", "allocation__bed__room__hostel"
        )

        form = HostelSearchForm(self.request.GET)
        if form.is_valid():
            # Filter by status
            status = form.cleaned_data.get("status")
            if status:
                queryset = queryset.filter(status=status)

            # Filter by month and year
            month = form.cleaned_data.get("month")
            if month:
                queryset = queryset.filter(month=month)

            year = form.cleaned_data.get("year")
            if year:
                queryset = queryset.filter(year=year)

            # Filter by overdue
            is_overdue = form.cleaned_data.get("is_overdue")
            if is_overdue:
                from datetime import date

                queryset = queryset.filter(
                    status__in=["pending", "partial"], due_date__lt=date.today()
                )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = HostelSearchForm(self.request.GET)
        return context


class HostelFeeDetailView(LoginRequiredMixin, DetailView):
    model = HostelFee
    template_name = "hostels/fees/fee_detail.html"
    context_object_name = "fee"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fee = self.get_object()

        # Payment history for this allocation
        context["allocation_fees"] = fee.allocation.fees.all().order_by(
            "-year", "-month"
        )

        # Similar fees for the same period
        context["similar_fees"] = (
            HostelFee.objects.filter(
                month=fee.month,
                year=fee.year,
                allocation__bed__room__hostel=fee.allocation.bed.room.hostel,
            )
            .exclude(pk=fee.pk)
            .select_related("allocation__student__user")
        )

        return context


@login_required
@permission_required("hostels.change_hostelfee")
def mark_fee_paid(request, pk):
    """
    View for marking a fee as paid.
    """
    fee = get_object_or_404(HostelFee, pk=pk)

    if request.method == "POST":
        paid_amount = request.POST.get("paid_amount")
        payment_method = request.POST.get("payment_method")
        transaction_id = request.POST.get("transaction_id")
        receipt_number = request.POST.get("receipt_number")

        try:
            paid_amount = float(paid_amount)
            fee.mark_as_paid(
                paid_amount=paid_amount,
                payment_method=payment_method,
                transaction_id=transaction_id,
                receipt_number=receipt_number,
            )

            messages.success(request, _("Fee marked as paid successfully."))
            return redirect("hostels:fee_detail", pk=fee.pk)

        except (ValueError, ValidationError) as e:
            messages.error(request, str(e))

    context = {
        "fee": fee,
    }

    return render(request, "hostels/fees/fee_mark_paid.html", context)


# Visitor Log Views
class VisitorLogListView(InstitutionPermissionMixin, ListView):
    model = VisitorLog
    template_name = "hostels/visitors/visitor_list.html"
    context_object_name = "visitors"
    paginate_by = 20

    def get_queryset(self):
        queryset = VisitorLog.objects.select_related(
            "hostel", "visiting_student__user", "authorized_by"
        ).order_by("-check_in_time")

        # Filter by hostel
        hostel_id = self.request.GET.get("hostel")
        if hostel_id:
            queryset = queryset.filter(hostel_id=hostel_id)

        # Filter by date
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")

        if date_from:
            queryset = queryset.filter(check_in_time__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(check_in_time__date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hostels"] = Hostel.objects.filter(is_active=True)
        return context


class VisitorLogDetailView(LoginRequiredMixin, DetailView):
    model = VisitorLog
    template_name = "hostels/visitors/visitor_detail.html"
    context_object_name = "visitor"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        visitor = self.get_object()

        # Other visits by the same visitor
        context["other_visits"] = (
            VisitorLog.objects.filter(
                visitor_name=visitor.visitor_name, visitor_phone=visitor.visitor_phone
            )
            .exclude(pk=visitor.pk)
            .order_by("-check_in_time")[:5]
        )

        # Recent visits to the same student
        context["student_visits"] = (
            VisitorLog.objects.filter(visiting_student=visitor.visiting_student)
            .exclude(pk=visitor.pk)
            .order_by("-check_in_time")[:5]
        )

        return context


class VisitorLogCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = VisitorLog
    form_class = VisitorLogForm
    template_name = "hostels/visitors/visitor_form.html"
    permission_required = "hostels.add_visitorlog"

    def get_success_url(self):
        return reverse_lazy("hostels:visitor_list")

    def form_valid(self, form):
        form.instance.authorized_by = self.request.user
        messages.success(self.request, _("Visitor logged successfully."))
        return super().form_valid(form)


@login_required
@permission_required("hostels.change_visitorlog")
def check_out_visitor(request, pk):
    """
    View for checking out a visitor.
    """
    visitor = get_object_or_404(VisitorLog, pk=pk)

    if request.method == "POST":
        visitor.check_out()
        messages.success(request, _("Visitor checked out successfully."))
        return redirect("hostels:visitor_list")

    context = {
        "visitor": visitor,
    }

    return render(request, "hostels/visitors/visitor_checkout.html", context)


# Maintenance Request Views
class MaintenanceRequestListView(InstitutionPermissionMixin, ListView):
    model = MaintenanceRequest
    template_name = "hostels/maintenance/maintenance_list.html"
    context_object_name = "maintenance_requests"
    paginate_by = 15

    def get_queryset(self):
        queryset = MaintenanceRequest.objects.select_related(
            "hostel", "room", "bed", "requested_by", "assigned_to"
        )

        form = HostelSearchForm(self.request.GET)
        if form.is_valid():
            # Filter by status
            status = form.cleaned_data.get("status")
            if status:
                queryset = queryset.filter(status=status)

            # Filter by priority
            priority = form.cleaned_data.get("priority")
            if priority:
                queryset = queryset.filter(priority=priority)

            # Filter by hostel
            hostel = form.cleaned_data.get("hostel")
            if hostel:
                queryset = queryset.filter(hostel=hostel)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = HostelSearchForm(self.request.GET)
        return context


class MaintenanceRequestDetailView(LoginRequiredMixin, DetailView):
    model = MaintenanceRequest
    template_name = "hostels/maintenance/maintenance_detail.html"
    context_object_name = "maintenance"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        maintenance = self.get_object()

        # Related maintenance requests for the same location
        if maintenance.room:
            context["room_maintenance"] = (
                MaintenanceRequest.objects.filter(room=maintenance.room)
                .exclude(pk=maintenance.pk)
                .order_by("-requested_date")[:5]
            )
        elif maintenance.bed:
            context["bed_maintenance"] = (
                MaintenanceRequest.objects.filter(bed=maintenance.bed)
                .exclude(pk=maintenance.pk)
                .order_by("-requested_date")[:5]
            )

        # Maintenance requests by the same requester
        context["requester_history"] = (
            MaintenanceRequest.objects.filter(requested_by=maintenance.requested_by)
            .exclude(pk=maintenance.pk)
            .order_by("-requested_date")[:5]
        )

        return context


class MaintenanceRequestCreateView(LoginRequiredMixin, CreateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = "hostels/maintenance/maintenance_form.html"

    def get_success_url(self):
        return reverse_lazy("hostels:maintenance_list")

    def form_valid(self, form):
        form.instance.requested_by = self.request.user
        messages.success(self.request, _("Maintenance request submitted successfully."))
        return super().form_valid(form)


class MaintenanceRequestUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = "hostels/maintenance/maintenance_form.html"
    permission_required = "hostels.change_maintenancerequest"

    def get_success_url(self):
        return reverse_lazy("hostels:maintenance_list")

    def form_valid(self, form):
        messages.success(self.request, _("Maintenance request updated successfully."))
        return super().form_valid(form)


@login_required
@permission_required("hostels.change_maintenancerequest")
def complete_maintenance(request, pk):
    """
    View for completing a maintenance request.
    """
    maintenance = get_object_or_404(MaintenanceRequest, pk=pk)

    if request.method == "POST":
        actual_cost = request.POST.get("actual_cost")
        notes = request.POST.get("notes", "")

        maintenance.status = MaintenanceRequest.Status.COMPLETED
        maintenance.completed_date = timezone.now()

        if actual_cost:
            maintenance.actual_cost = actual_cost

        if notes:
            maintenance.notes = notes

        maintenance.save()

        messages.success(request, _("Maintenance request completed successfully."))
        return redirect("hostels:maintenance_list")

    context = {
        "maintenance": maintenance,
    }

    return render(request, "hostels/maintenance/maintenance_complete.html", context)


# Inventory Management Views
class InventoryItemListView(InstitutionPermissionMixin, ListView):
    model = InventoryItem
    template_name = "hostels/inventory/inventory_list.html"
    context_object_name = "inventory_items"
    paginate_by = 20

    def get_queryset(self):
        queryset = InventoryItem.objects.select_related("hostel", "room")

        # Filter by hostel
        hostel_id = self.request.GET.get("hostel")
        if hostel_id:
            queryset = queryset.filter(hostel_id=hostel_id)

        # Filter by category
        category = self.request.GET.get("category")
        if category:
            queryset = queryset.filter(category=category)

        # Filter by status
        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["hostels"] = Hostel.objects.filter(is_active=True)
        context["categories"] = InventoryItem.objects.values_list(
            "category", flat=True
        ).distinct()
        context["status_choices"] = InventoryItem.ItemStatus.choices
        return context


class InventoryItemDetailView(LoginRequiredMixin, DetailView):
    model = InventoryItem
    template_name = "hostels/inventory/inventory_detail.html"
    context_object_name = "item"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()

        # Similar items in the same category
        context["similar_items"] = (
            InventoryItem.objects.filter(category=item.category, hostel=item.hostel)
            .exclude(pk=item.pk)
            .order_by("-created_at")[:5]
        )

        # Items in the same room
        if item.room:
            context["room_items"] = (
                InventoryItem.objects.filter(room=item.room)
                .exclude(pk=item.pk)
                .order_by("name")
            )

        # Maintenance history if applicable
        if hasattr(item, "maintenance_requests"):
            context["maintenance_history"] = item.maintenance_requests.all().order_by(
                "-requested_date"
            )[:5]

        return context


class InventoryItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "hostels/inventory/inventory_form.html"
    permission_required = "hostels.add_inventoryitem"

    def get_success_url(self):
        return reverse_lazy("hostels:inventory_list")

    def form_valid(self, form):
        messages.success(self.request, _("Inventory item added successfully."))
        return super().form_valid(form)


class InventoryItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = InventoryItem
    form_class = InventoryItemForm
    template_name = "hostels/inventory/inventory_form.html"
    permission_required = "hostels.change_inventoryitem"

    def get_success_url(self):
        return reverse_lazy("hostels:inventory_list")

    def form_valid(self, form):
        messages.success(self.request, _("Inventory item updated successfully."))
        return super().form_valid(form)


# AJAX Views for Dynamic Filtering
@login_required
def get_rooms_by_hostel(request):
    """
    AJAX view to get rooms for a specific hostel.
    """
    hostel_id = request.GET.get("hostel_id")
    if hostel_id:
        rooms = Room.objects.filter(hostel_id=hostel_id, is_available=True)
        room_data = [{"id": room.id, "name": str(room)} for room in rooms]
        return JsonResponse(room_data, safe=False)
    return JsonResponse([], safe=False)


@login_required
def get_beds_by_room(request):
    """
    AJAX view to get beds for a specific room.
    """
    room_id = request.GET.get("room_id")
    if room_id:
        beds = Bed.objects.filter(room_id=room_id, is_available=True)
        bed_data = [{"id": bed.id, "name": str(bed)} for bed in beds]
        return JsonResponse(bed_data, safe=False)
    return JsonResponse([], safe=False)


@login_required
def get_available_beds(request):
    """
    AJAX view to get available beds for allocation.
    """
    hostel_id = request.GET.get("hostel_id")
    room_type = request.GET.get("room_type")

    if hostel_id:
        beds = Bed.objects.filter(
            room__hostel_id=hostel_id, is_available=True, is_occupied=False
        ).select_related("room")

        # Filter by room type if specified
        if room_type:
            beds = beds.filter(room__room_type=room_type)

        bed_data = []
        for bed in beds:
            bed_data.append(
                {
                    "id": bed.id,
                    "number": bed.bed_number,
                    "room": bed.room.room_number,
                    "hostel": bed.room.hostel.name,
                    "type": bed.room.get_room_type_display(),
                    "floor": bed.room.floor,
                    "rent": str(bed.room.effective_rent),
                    "features": bed.features or "",
                }
            )

        return JsonResponse(bed_data, safe=False)
    return JsonResponse([], safe=False)


# Report Views
@login_required
@permission_required("hostels.view_hostel")
def occupancy_report(request):
    """
    View for generating hostel occupancy reports.
    """
    hostels = Hostel.objects.filter(is_active=True)

    report_data = []
    for hostel in hostels:
        occupancy_rate = hostel.occupancy_percentage
        available_beds = hostel.available_beds

        report_data.append(
            {
                "hostel": hostel,
                "total_capacity": hostel.capacity,
                "current_occupancy": hostel.current_occupancy,
                "available_beds": available_beds,
                "occupancy_rate": occupancy_rate,
                "is_full": hostel.is_full,
            }
        )

    context = {
        "report_data": report_data,
        "total_capacity": sum(h.capacity for h in hostels),
        "total_occupancy": sum(h.current_occupancy for h in hostels),
    }

    return render(request, "hostels/reports/occupancy_report.html", context)


@login_required
@permission_required("hostels.view_hostelfee")
def fee_collection_report(request):
    """
    View for generating fee collection reports.
    """
    month = request.GET.get("month", timezone.now().month)
    year = request.GET.get("year", timezone.now().year)

    fees = HostelFee.objects.filter(month=month, year=year).select_related(
        "allocation__bed__room__hostel"
    )

    total_amount = fees.aggregate(total=Sum("amount"))["total"] or 0
    total_paid = fees.aggregate(total=Sum("paid_amount"))["total"] or 0
    total_pending = total_amount - total_paid

    context = {
        "fees": fees,
        "month": month,
        "year": year,
        "total_amount": total_amount,
        "total_paid": total_paid,
        "total_pending": total_pending,
        "collection_rate": (total_paid / total_amount * 100) if total_amount > 0 else 0,
    }

    return render(request, "hostels/reports/fee_collection_report.html", context)


# API-like views for mobile app integration
@login_required
def api_hostel_list(request):
    """
    API view for mobile app to get hostel list.
    """
    hostels = Hostel.objects.filter(is_active=True).values(
        "id",
        "name",
        "code",
        "hostel_type",
        "category",
        "capacity",
        "current_occupancy",
        "available_beds",
    )
    return JsonResponse(list(hostels), safe=False)


@login_required
def api_search_students(request):
    """
    API view for searching students for allocation.
    """
    query = request.GET.get("q", "").strip()

    if len(query) < 2:
        return JsonResponse({"students": []})

    # Search students who are active and don't have current allocations
    from apps.academics.models import Student

    students = (
        Student.objects.filter(status="active", user__first_name__icontains=query)
        | Student.objects.filter(status="active", user__last_name__icontains=query)
        | Student.objects.filter(status="active", admission_number__icontains=query)
    )

    # Exclude students who already have active allocations
    students_with_allocations = HostelAllocation.objects.filter(
        status="active"
    ).values_list("student_id", flat=True)

    students = students.exclude(id__in=students_with_allocations).select_related(
        "user", "current_class"
    )[:10]

    student_data = []
    for student in students:
        student_data.append(
            {
                "id": student.id,
                "name": student.user.get_full_name(),
                "admission": student.admission_number,
                "class": str(student.current_class) if student.current_class else "N/A",
                "gender": student.get_gender_display(),
            }
        )

    return JsonResponse({"students": student_data})


@login_required
def api_student_allocation(request, student_id):
    """
    API view for mobile app to get student's current allocation.
    """
    allocation = (
        HostelAllocation.objects.filter(student_id=student_id, status="active")
        .select_related("bed__room__hostel", "academic_session")
        .first()
    )

    if allocation:
        data = {
            "hostel": allocation.bed.room.hostel.name,
            "room": allocation.bed.room.room_number,
            "bed": allocation.bed.bed_number,
            "allocation_date": allocation.allocation_date.isoformat(),
            "rent_amount": str(allocation.rent_amount),
        }
    else:
        data = {"error": "No active allocation found"}

    return JsonResponse(data)
