# apps/hostels/admin.py

from django.contrib import admin
from apps.core.admin import InstitutionModelAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError

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

User = get_user_model()


class RoomInline(admin.TabularInline):
    model = Room
    extra = 1
    fields = ["room_number", "floor", "room_type", "capacity", "is_available"]
    readonly_fields = ["current_occupancy"]


class BedInline(admin.TabularInline):
    model = Bed
    extra = 2
    fields = ["bed_number", "bed_type", "is_available", "features"]
    readonly_fields = ["is_occupied"]


class HostelAdmin(InstitutionModelAdmin):
    list_display = [
        "name",
        "code",
        "hostel_type",
        "category",
        "total_rooms",
        "capacity",
        "current_occupancy",
        "available_beds",
        "occupancy_percentage",
        "is_full",
        "warden",
        "is_active",
        "status",
    ]
    list_filter = ["hostel_type", "category", "is_active", "status"]
    search_fields = ["name", "code", "warden__first_name", "warden__last_name"]
    list_editable = ["is_active"]
    readonly_fields = [
        "current_occupancy",
        "available_beds",
        "occupancy_percentage",
        "is_full",
        "created_at",
        "updated_at",
    ]
    inlines = [RoomInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("name", "code", "hostel_type", "category")},
        ),
        (
            _("Capacity & Structure"),
            {
                "fields": (
                    "total_floors",
                    "total_rooms",
                    "capacity",
                    "current_occupancy",
                    "available_beds",
                )
            },
        ),
        (_("Staff"), {"fields": ("warden", "assistant_warden")}),
        (_("Financial"), {"fields": ("monthly_rent", "security_deposit")}),
        (_("Facilities & Rules"), {"fields": ("amenities", "rules", "description")}),
        (_("Access Control"), {"fields": ("allowed_classes",)}),
        (
            _("Address & Contact"),
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "postal_code",
                    "country",
                    "phone",
                    "mobile",
                    "email",
                )
            },
        ),
        (
            _("Status"),
            {"fields": ("is_active", "status", "occupancy_percentage", "is_full")},
        ),
    )

    def available_beds(self, obj):
        return obj.available_beds

    available_beds.short_description = _("Available Beds")

    def occupancy_percentage(self, obj):
        return f"{obj.occupancy_percentage}%"

    occupancy_percentage.short_description = _("Occupancy %")

    def is_full(self, obj):
        return obj.is_full

    is_full.boolean = True
    is_full.short_description = _("Full")

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("warden", "assistant_warden")
        )


class RoomAdmin(InstitutionModelAdmin):
    list_display = [
        "room_number",
        "hostel",
        "floor",
        "room_type",
        "capacity",
        "current_occupancy",
        "available_beds",
        "effective_rent",
        "is_available",
        "maintenance_required",
        "is_full",
        "status",
    ]
    list_filter = [
        "hostel",
        "floor",
        "room_type",
        "is_available",
        "maintenance_required",
        "status",
    ]
    search_fields = ["room_number", "hostel__name", "preferred_class__name"]
    list_editable = ["is_available"]
    readonly_fields = [
        "current_occupancy",
        "available_beds",
        "effective_rent",
        "is_full",
        "created_at",
        "updated_at",
    ]
    inlines = [BedInline]

    fieldsets = (
        (
            _("Room Information"),
            {"fields": ("hostel", "room_number", "floor", "room_type")},
        ),
        (
            _("Capacity"),
            {"fields": ("capacity", "current_occupancy", "available_beds", "is_full")},
        ),
        (_("Financial"), {"fields": ("rent", "effective_rent")}),
        (_("Facilities"), {"fields": ("amenities",)}),
        (_("Academic Preference"), {"fields": ("preferred_class",)}),
        (_("Maintenance"), {"fields": ("maintenance_required", "maintenance_notes")}),
        (_("Status"), {"fields": ("is_available", "status")}),
    )

    def available_beds(self, obj):
        return obj.available_beds

    available_beds.short_description = _("Available Beds")

    def effective_rent(self, obj):
        return obj.effective_rent

    effective_rent.short_description = _("Monthly Rent")

    def is_full(self, obj):
        return obj.is_full

    is_full.boolean = True
    is_full.short_description = _("Full")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("hostel", "preferred_class")


class HostelAllocationInline(admin.TabularInline):
    model = HostelAllocation
    extra = 0
    fields = ["student", "academic_session", "allocation_date", "status"]
    readonly_fields = ["student", "academic_session", "allocation_date"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class BedAdmin(InstitutionModelAdmin):
    list_display = [
        "bed_number",
        "room",
        "bed_type",
        "is_available",
        "is_occupied",
        "requires_maintenance",
        "last_maintenance_date",
        "status",
    ]
    list_filter = ["room__hostel", "bed_type", "is_available", "status"]
    search_fields = ["bed_number", "room__room_number", "room__hostel__name"]
    list_editable = ["is_available"]
    readonly_fields = [
        "is_occupied",
        "requires_maintenance",
        "created_at",
        "updated_at",
    ]
    inlines = [HostelAllocationInline]

    fieldsets = (
        (_("Bed Information"), {"fields": ("room", "bed_number", "bed_type")}),
        (
            _("Features & Maintenance"),
            {"fields": ("features", "last_maintenance_date", "next_maintenance_date")},
        ),
        (
            _("Status"),
            {
                "fields": (
                    "is_available",
                    "is_occupied",
                    "requires_maintenance",
                    "status",
                )
            },
        ),
    )

    def is_occupied(self, obj):
        return obj.is_occupied

    is_occupied.boolean = True
    is_occupied.short_description = _("Occupied")

    def requires_maintenance(self, obj):
        return obj.requires_maintenance

    requires_maintenance.boolean = True
    requires_maintenance.short_description = _("Needs Maintenance")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("room", "room__hostel")


class HostelFeeInline(admin.TabularInline):
    model = HostelFee
    extra = 0
    fields = ["month", "year", "amount", "paid_amount", "status", "due_date"]
    readonly_fields = ["month", "year", "amount", "due_date"]
    can_delete = False


class HostelAllocationAdmin(InstitutionModelAdmin):
    list_display = [
        "student",
        "bed",
        "academic_session",
        "class_enrolled",
        "allocation_date",
        "status",
        "is_current",
        "duration_days",
        "rent_amount",
        "outstanding_balance",
    ]
    list_filter = ["academic_session", "status", "class_enrolled", "allocation_date"]
    search_fields = [
        "student__user__first_name",
        "student__user__last_name",
        "student__admission_number",
        "bed__room__hostel__name",
    ]
    readonly_fields = [
        "duration_days",
        "is_current",
        "outstanding_balance",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "allocation_date"
    inlines = [HostelFeeInline]

    fieldsets = (
        (
            _("Allocation Information"),
            {"fields": ("student", "bed", "academic_session")},
        ),
        (_("Academic Context"), {"fields": ("class_enrolled",)}),
        (
            _("Dates"),
            {
                "fields": (
                    "allocation_date",
                    "expected_departure_date",
                    "actual_departure_date",
                )
            },
        ),
        (
            _("Financial"),
            {"fields": ("rent_amount", "security_deposit_paid", "deposit_refunded")},
        ),
        (
            _("Student Information"),
            {
                "fields": (
                    "special_requirements",
                    "emergency_contact",
                    "medical_information",
                )
            },
        ),
        (_("Administration"), {"fields": ("allocated_by", "notes")}),
        (
            _("Calculated Fields"),
            {"fields": ("duration_days", "is_current", "outstanding_balance")},
        ),
        (_("Status"), {"fields": ("status",)}),
    )

    def is_current(self, obj):
        return obj.is_current

    is_current.boolean = True
    is_current.short_description = _("Current")

    def outstanding_balance(self, obj):
        return obj.outstanding_balance

    outstanding_balance.short_description = _("Outstanding Balance")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "student__user",
                "bed__room__hostel",
                "academic_session",
                "class_enrolled",
                "allocated_by",
                "emergency_contact",
            )
        )

    def save_model(self, request, obj, form, change):
        if not obj.allocated_by_id:
            obj.allocated_by = request.user
        super().save_model(request, obj, form, change)


class HostelFeeAdmin(InstitutionModelAdmin):
    list_display = [
        "allocation",
        "month",
        "year",
        "amount",
        "paid_amount",
        "total_payable",
        "balance_amount",
        "status",
        "due_date",
        "is_overdue",
        "paid_date",
    ]
    list_filter = ["month", "year", "status", "due_date", "paid_date"]
    search_fields = [
        "allocation__student__user__first_name",
        "allocation__student__user__last_name",
        "allocation__bed__room__hostel__name",
        "receipt_number",
        "transaction_id",
    ]
    readonly_fields = [
        "total_payable",
        "balance_amount",
        "is_overdue",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "due_date"

    fieldsets = (
        (_("Fee Information"), {"fields": ("allocation", "month", "year", "due_date")}),
        (_("Amounts"), {"fields": ("amount", "late_fee", "discount")}),
        (
            _("Payment"),
            {
                "fields": (
                    "paid_amount",
                    "paid_date",
                    "payment_method",
                    "transaction_id",
                    "receipt_number",
                )
            },
        ),
        (
            _("Calculated Fields"),
            {"fields": ("total_payable", "balance_amount", "is_overdue")},
        ),
        (_("Notes"), {"fields": ("notes",)}),
        (_("Status"), {"fields": ("status",)}),
    )

    def total_payable(self, obj):
        return obj.total_payable

    total_payable.short_description = _("Total Payable")

    def balance_amount(self, obj):
        return obj.balance_amount

    balance_amount.short_description = _("Balance")

    def is_overdue(self, obj):
        return obj.is_overdue

    is_overdue.boolean = True
    is_overdue.short_description = _("Overdue")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "allocation__student__user", "allocation__bed__room__hostel"
            )
        )


class VisitorLogAdmin(InstitutionModelAdmin):
    list_display = [
        "visitor_name",
        "hostel",
        "visiting_student",
        "purpose",
        "check_in_time",
        "check_out_time",
        "is_checked_out",
        "duration_minutes",
        "is_parent_guardian",
        "authorized_by",
        "status",
    ]
    list_filter = ["hostel", "purpose", "is_parent_guardian", "check_in_time", "status"]
    search_fields = [
        "visitor_name",
        "visitor_phone",
        "visiting_student__user__first_name",
        "visiting_student__user__last_name",
        "authorized_by__first_name",
    ]
    readonly_fields = ["duration_minutes", "is_checked_out", "created_at", "updated_at"]
    date_hierarchy = "check_in_time"

    fieldsets = (
        (
            _("Visitor Information"),
            {
                "fields": (
                    "visitor_name",
                    "visitor_phone",
                    "visitor_id_type",
                    "visitor_id_number",
                )
            },
        ),
        (_("Visit Details"), {"fields": ("hostel", "visiting_student", "purpose")}),
        (_("Relationship"), {"fields": ("is_parent_guardian", "parent_guardian")}),
        (_("Timing"), {"fields": ("check_in_time", "check_out_time")}),
        (
            _("Security"),
            {
                "fields": (
                    "items_carried",
                    "authorized_by",
                    "photo_id_verified",
                    "allowed_items_only",
                )
            },
        ),
        (_("Calculated Fields"), {"fields": ("duration_minutes", "is_checked_out")}),
        (_("Notes"), {"fields": ("notes",)}),
        (_("Status"), {"fields": ("status",)}),
    )

    def is_checked_out(self, obj):
        return obj.is_checked_out

    is_checked_out.boolean = True
    is_checked_out.short_description = _("Checked Out")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "hostel", "visiting_student__user", "authorized_by", "parent_guardian"
            )
        )


class MaintenanceRequestAdmin(InstitutionModelAdmin):
    list_display = [
        "title",
        "hostel",
        "room",
        "requested_by",
        "priority",
        "status",
        "assigned_to",
        "requested_date",
        "is_overdue",
        "estimated_cost",
        "actual_cost",
        "completed_date",
    ]
    list_filter = [
        "hostel",
        "priority",
        "status",
        "assigned_to",
        "requested_date",
        "completed_date",
    ]
    search_fields = [
        "title",
        "hostel__name",
        "room__room_number",
        "requested_by__first_name",
        "requested_by__last_name",
    ]
    readonly_fields = [
        "requested_date",
        "is_overdue",
        "resolution_time",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "requested_date"

    fieldsets = (
        (_("Request Information"), {"fields": ("hostel", "room", "bed", "title")}),
        (_("Details"), {"fields": ("description", "priority")}),
        (_("Assignment"), {"fields": ("assigned_to", "status")}),
        (_("Financial"), {"fields": ("estimated_cost", "actual_cost")}),
        (_("Scheduling"), {"fields": ("scheduled_date", "completed_date")}),
        (_("Calculated Fields"), {"fields": ("is_overdue", "resolution_time")}),
        (_("Notes"), {"fields": ("notes",)}),
        (_("Requester"), {"fields": ("requested_by",)}),
        (_("Status"), {"fields": ("status",)}),
    )

    def is_overdue(self, obj):
        return obj.is_overdue

    is_overdue.boolean = True
    is_overdue.short_description = _("Overdue")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("hostel", "room", "bed", "requested_by", "assigned_to")
        )

    def save_model(self, request, obj, form, change):
        if not obj.requested_by_id:
            obj.requested_by = request.user
        super().save_model(request, obj, form, change)


class InventoryItemAdmin(InstitutionModelAdmin):
    list_display = [
        "name",
        "hostel",
        "room",
        "category",
        "quantity",
        "condition",
        "status",
        "purchase_date",
        "purchase_cost",
        "is_warranty_valid",
        "age_years",
    ]
    list_filter = ["hostel", "category", "condition", "status", "purchase_date"]
    search_fields = [
        "name",
        "serial_number",
        "hostel__name",
        "room__room_number",
        "category",
    ]
    readonly_fields = ["is_warranty_valid", "age_years", "created_at", "updated_at"]

    fieldsets = (
        (_("Item Information"), {"fields": ("hostel", "room", "name", "category")}),
        (_("Identification"), {"fields": ("serial_number", "quantity")}),
        (_("Condition & Status"), {"fields": ("condition", "status")}),
        (
            _("Purchase Details"),
            {"fields": ("purchase_date", "purchase_cost", "warranty_expiry")},
        ),
        (_("Calculated Fields"), {"fields": ("is_warranty_valid", "age_years")}),
        (_("Description"), {"fields": ("description", "notes")}),
        (_("Status"), {"fields": ("status",)}),
    )

    def is_warranty_valid(self, obj):
        return obj.is_warranty_valid

    is_warranty_valid.boolean = True
    is_warranty_valid.short_description = _("Warranty Valid")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("hostel", "room")


# Custom filters
class OverdueFeeFilter(admin.SimpleListFilter):
    title = _("overdue fees")
    parameter_name = "is_overdue"

    def lookups(self, request, model_admin):
        return (
            ("overdue", _("Overdue")),
            ("paid", _("Paid")),
            ("pending", _("Pending")),
        )

    def queryset(self, request, queryset):
        from datetime import date

        today = date.today()
        if self.value() == "overdue":
            return queryset.filter(
                status__in=["pending", "partial"], due_date__lt=today
            )
        elif self.value() == "paid":
            return queryset.filter(status="paid")
        elif self.value() == "pending":
            return queryset.filter(status__in=["pending", "partial"])
        return queryset


class CurrentAllocationFilter(admin.SimpleListFilter):
    title = _("current allocations")
    parameter_name = "is_current"

    def lookups(self, request, model_admin):
        return (
            ("current", _("Current")),
            ("past", _("Past")),
        )

    def queryset(self, request, queryset):
        if self.value() == "current":
            return queryset.filter(status="active", actual_departure_date__isnull=True)
        elif self.value() == "past":
            return queryset.exclude(status="active")
        return queryset


# Add custom filters
HostelFeeAdmin.list_filter.append(OverdueFeeFilter)
HostelAllocationAdmin.list_filter.append(CurrentAllocationFilter)


# Custom admin actions
def allocate_selected_beds(modeladmin, request, queryset):
    # This would open a custom allocation form
    modeladmin.message_user(
        request, _("Bed allocation feature would be implemented here.")
    )


allocate_selected_beds.short_description = _("Allocate selected beds")


def mark_selected_fees_paid(modeladmin, request, queryset):
    from datetime import date

    updated = queryset.filter(status__in=["pending", "partial"]).update(
        status="paid",
        paid_amount=models.F("amount") + models.F("late_fee") - models.F("discount"),
        paid_date=date.today(),
    )
    modeladmin.message_user(
        request, _("Successfully marked %d fees as paid.") % updated
    )


mark_selected_fees_paid.short_description = _("Mark selected fees as paid")


def check_out_selected_visitors(modeladmin, request, queryset):
    updated = queryset.filter(check_out_time__isnull=True).update(
        check_out_time=timezone.now()
    )
    modeladmin.message_user(
        request, _("Successfully checked out %d visitors.") % updated
    )


check_out_selected_visitors.short_description = _("Check out selected visitors")


def complete_selected_maintenance(modeladmin, request, queryset):
    updated = queryset.filter(status__in=["pending", "in_progress"]).update(
        status="completed", completed_date=timezone.now()
    )
    modeladmin.message_user(
        request, _("Successfully completed %d maintenance requests.") % updated
    )


complete_selected_maintenance.short_description = _("Complete selected maintenance")


def transfer_students(modeladmin, request, queryset):
    # This would open a custom transfer form
    modeladmin.message_user(
        request, _("Student transfer feature would be implemented here.")
    )


transfer_students.short_description = _("Transfer selected students")


# Add custom actions to models
BedAdmin.actions = [allocate_selected_beds]
HostelFeeAdmin.actions = [mark_selected_fees_paid]
VisitorLogAdmin.actions = [check_out_selected_visitors]
MaintenanceRequestAdmin.actions = [complete_selected_maintenance]
HostelAllocationAdmin.actions = [transfer_students]


# Custom admin site configuration
class HostelAdminSite(admin.AdminSite):
    site_header = _("Hostel Management System")
    site_title = _("Hostel Admin")
    index_title = _("Hostel Administration")


# NOTE: Custom HostelAdminSite removed. Models are registered with the
# default admin site via the @admin.register decorators above.


# Export functionality
class ExportMixin:
    def export_to_csv(self, request, queryset):
        # Placeholder for CSV export functionality
        self.message_user(request, _("Export feature would be implemented here."))

    export_to_csv.short_description = _("Export selected to CSV")


# Add export to relevant admins
HostelAllocationAdmin.actions = list(HostelAllocationAdmin.actions) + ["export_to_csv"]
HostelFeeAdmin.actions = list(HostelFeeAdmin.actions) + ["export_to_csv"]
VisitorLogAdmin.actions = list(VisitorLogAdmin.actions) + ["export_to_csv"]
