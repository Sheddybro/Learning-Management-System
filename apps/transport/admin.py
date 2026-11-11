# apps/transport/admin.py

from django.contrib import admin
from apps.core.admin import InstitutionModelAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.db.models import Count, Sum, Q
from django.contrib.auth.models import User

from .models import (
    Vehicle,
    Driver,
    Attendant,
    Route,
    RouteStop,
    RouteSchedule,
    TransportAllocation,
    MaintenanceRecord,
    FuelRecord,
    IncidentReport,
)


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 1
    fields = (
        "sequence",
        "name",
        "address",
        "estimated_arrival_time",
        "pickup_time",
        "drop_time",
    )
    ordering = ["sequence"]


class MaintenanceRecordInline(admin.TabularInline):
    model = MaintenanceRecord
    extra = 0
    fields = ("date", "maintenance_type", "work_done", "cost", "next_due_date")
    readonly_fields = ("date", "maintenance_type", "work_done", "cost", "next_due_date")
    can_delete = False


class FuelRecordInline(admin.TabularInline):
    model = FuelRecord
    extra = 0
    fields = (
        "date",
        "odometer_reading",
        "fuel_quantity",
        "fuel_cost",
        "fuel_efficiency_display",
    )
    readonly_fields = ("fuel_efficiency_display",)
    can_delete = False

    def fuel_efficiency_display(self, obj):
        efficiency = obj.fuel_efficiency
        if efficiency:
            return f"{efficiency:.2f} km/L"
        return _("Not available")

    fuel_efficiency_display.short_description = _("Fuel Efficiency")


@admin.register(Vehicle)
class VehicleAdmin(InstitutionModelAdmin):
    list_display = (
        "vehicle_number",
        "registration_number",
        "vehicle_type",
        "make_model_year",
        "seating_capacity",
        "available_seats_display",
        "fuel_type",
        "status_display",
    )
    list_filter = ("vehicle_type", "fuel_type", "status", "year")
    search_fields = ("vehicle_number", "registration_number", "make", "model")
    readonly_fields = (
        "available_seats_display",
        "is_insurance_expired_display",
        "is_fitness_expired_display",
        "current_mileage",
    )
    inlines = [MaintenanceRecordInline, FuelRecordInline]
    fieldsets = (
        (
            _("Basic Information"),
            {
                "fields": (
                    "vehicle_number",
                    "registration_number",
                    "vehicle_type",
                    "status",
                )
            },
        ),
        (
            _("Vehicle Details"),
            {
                "fields": (
                    "make",
                    "model",
                    "year",
                    "color",
                    "seating_capacity",
                    "fuel_type",
                )
            },
        ),
        (
            _("Legal Documents"),
            {
                "fields": (
                    "insurance_number",
                    "insurance_expiry",
                    "is_insurance_expired_display",
                    "fitness_certificate_number",
                    "fitness_expiry",
                    "is_fitness_expired_display",
                )
            },
        ),
        (
            _("Purchase Information"),
            {
                "fields": ("purchase_date", "purchase_price", "current_mileage"),
                "classes": ("collapse",),
            },
        ),
        (_("Availability"), {"fields": ("available_seats_display",)}),
        (_("Additional Information"), {"fields": ("notes",), "classes": ("collapse",)}),
    )

    def make_model_year(self, obj):
        return f"{obj.make} {obj.model} ({obj.year})"

    make_model_year.short_description = _("Vehicle Details")

    def available_seats_display(self, obj):
        available = obj.available_seats
        if available > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{}</span>',
                f"{available}/{obj.seating_capacity}",
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">{}</span>',
                f"{available}/{obj.seating_capacity}",
            )

    available_seats_display.short_description = _("Available Seats")

    def is_insurance_expired_display(self, obj):
        if obj.is_insurance_expired:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠</span> {}', _("Expired")
            )
        elif obj.insurance_expiry:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}', _("Valid")
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">?</span> {}',
                _("Not Set"),
            )

    is_insurance_expired_display.short_description = _("Insurance Status")

    def is_fitness_expired_display(self, obj):
        if obj.is_fitness_expired:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠</span> {}', _("Expired")
            )
        elif obj.fitness_expiry:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}', _("Valid")
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">?</span> {}',
                _("Not Set"),
            )

    is_fitness_expired_display.short_description = _("Fitness Status")

    def status_display(self, obj):
        status_colors = {
            "active": "green",
            "inactive": "gray",
            "maintenance": "orange",
            "out_of_service": "red",
        }
        color = status_colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display(),
        )

    status_display.short_description = _("Status")


@admin.register(Driver)
class DriverAdmin(InstitutionModelAdmin):
    list_display = (
        "employee_id",
        "user_name",
        "license_number",
        "license_type",
        "license_expiry",
        "is_license_expired_display",
        "age",
        "status_display",
    )
    list_filter = ("license_type", "status", "date_of_joining")
    search_fields = (
        "employee_id",
        "user__first_name",
        "user__last_name",
        "license_number",
    )
    readonly_fields = ("user_name", "age", "is_license_expired_display")
    fieldsets = (
        (
            _("Personal Information"),
            {"fields": ("user", "employee_id", "date_of_birth", "age")},
        ),
        (
            _("License Information"),
            {
                "fields": (
                    "license_number",
                    "license_type",
                    "license_expiry",
                    "is_license_expired_display",
                )
            },
        ),
        (_("Employment Details"), {"fields": ("date_of_joining", "salary", "status")}),
        (
            _("Contact Information"),
            {"fields": ("phone", "email", "address"), "classes": ("collapse",)},
        ),
        (
            _("Emergency Contact"),
            {
                "fields": ("emergency_contact_name", "emergency_contact_relation"),
                "classes": ("collapse",),
            },
        ),
    )

    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    user_name.short_description = _("Driver Name")

    def is_license_expired_display(self, obj):
        if obj.is_license_expired:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠</span> {}', _("Expired")
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}', _("Valid")
            )

    is_license_expired_display.short_description = _("License Status")

    def status_display(self, obj):
        status_colors = {
            "active": "green",
            "inactive": "gray",
            "suspended": "red",
            "on_leave": "orange",
        }
        color = status_colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display(),
        )

    status_display.short_description = _("Status")


@admin.register(Attendant)
class AttendantAdmin(InstitutionModelAdmin):
    list_display = (
        "employee_id",
        "user_name",
        "date_of_joining",
        "age",
        "status_display",
    )
    list_filter = ("status", "date_of_joining")
    search_fields = ("employee_id", "user__first_name", "user__last_name")
    readonly_fields = ("user_name", "age")
    fieldsets = (
        (
            _("Personal Information"),
            {"fields": ("user", "employee_id", "date_of_birth", "age")},
        ),
        (
            _("Employment Details"),
            {"fields": ("date_of_joining", "salary", "responsibilities", "status")},
        ),
        (
            _("Contact Information"),
            {"fields": ("phone", "email", "address"), "classes": ("collapse",)},
        ),
        (
            _("Emergency Contact"),
            {
                "fields": ("emergency_contact_name", "emergency_contact_relation"),
                "classes": ("collapse",),
            },
        ),
    )

    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    user_name.short_description = _("Attendant Name")

    def status_display(self, obj):
        status_colors = {
            "active": "green",
            "inactive": "gray",
            "suspended": "red",
            "on_leave": "orange",
        }
        color = status_colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_status_display(),
        )

    status_display.short_description = _("Status")


@admin.register(Route)
class RouteAdmin(InstitutionModelAdmin):
    list_display = (
        "code",
        "name",
        "start_point",
        "end_point",
        "total_distance",
        "estimated_duration",
        "current_students_count",
        "current_vehicles_count",
        "is_active_display",
    )
    list_filter = ("is_active",)
    search_fields = ("code", "name", "start_point", "end_point")
    readonly_fields = ("current_students_count", "current_vehicles_count")
    inlines = [RouteStopInline]
    fieldsets = (
        (_("Route Information"), {"fields": ("code", "name", "is_active")}),
        (
            _("Route Details"),
            {
                "fields": (
                    "start_point",
                    "end_point",
                    "total_distance",
                    "estimated_duration",
                )
            },
        ),
        (
            _("Statistics"),
            {"fields": ("current_students_count", "current_vehicles_count")},
        ),
        (_("Description"), {"fields": ("description",), "classes": ("collapse",)}),
    )

    def is_active_display(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Active"),
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗</span> {}',
                _("Inactive"),
            )

    is_active_display.short_description = _("Active")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _student_count=Count(
                    "student_allocations",
                    filter=Q(
                        student_allocations__status="active",
                        student_allocations__academic_session__is_current=True,
                    ),
                ),
                _vehicle_count=Count(
                    "route_schedules",
                    filter=Q(
                        route_schedules__status="active",
                        route_schedules__academic_session__is_current=True,
                    ),
                    distinct=True,
                ),
            )
        )

    def current_students_count(self, obj):
        return obj._student_count

    current_students_count.short_description = _("Current Students")
    current_students_count.admin_order_field = "_student_count"

    def current_vehicles_count(self, obj):
        return obj._vehicle_count

    current_vehicles_count.short_description = _("Current Vehicles")
    current_vehicles_count.admin_order_field = "_vehicle_count"


@admin.register(RouteStop)
class RouteStopAdmin(InstitutionModelAdmin):
    list_display = (
        "route",
        "sequence",
        "name",
        "estimated_arrival_time",
        "pickup_time",
        "drop_time",
    )
    list_filter = ("route",)
    search_fields = ("name", "route__code", "route__name", "address")
    ordering = ("route", "sequence")
    fieldsets = (
        (_("Stop Information"), {"fields": ("route", "sequence", "name")}),
        (_("Location Details"), {"fields": ("address", "latitude", "longitude")}),
        (
            _("Timing Information"),
            {"fields": ("estimated_arrival_time", "pickup_time", "drop_time")},
        ),
    )


class TransportAllocationInline(admin.TabularInline):
    model = TransportAllocation
    extra = 0
    fields = (
        "student",
        "pickup_stop",
        "drop_stop",
        "allocation_type",
        "is_active_allocation_display",
    )
    readonly_fields = ("is_active_allocation_display",)
    can_delete = False

    def is_active_allocation_display(self, obj):
        if obj.is_active_allocation:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span>', _("Active")
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗</span>', _("Inactive")
            )

    is_active_allocation_display.short_description = _("Active")


@admin.register(RouteSchedule)
class RouteScheduleAdmin(InstitutionModelAdmin):
    list_display = (
        "route_code",
        "vehicle_number",
        "driver_name",
        "academic_session",
        "morning_start_time",
        "current_students_count",
        "is_operational_today_display",
    )
    list_filter = ("academic_session", "route", "status")
    search_fields = (
        "route__code",
        "route__name",
        "vehicle__vehicle_number",
        "driver__user__first_name",
    )
    readonly_fields = ("current_students_count", "is_operational_today_display")
    inlines = [TransportAllocationInline]
    fieldsets = (
        (
            _("Schedule Information"),
            {
                "fields": (
                    "route",
                    "vehicle",
                    "driver",
                    "attendant",
                    "academic_session",
                    "status",
                )
            },
        ),
        (
            _("Timing Information"),
            {
                "fields": (
                    "morning_start_time",
                    "morning_end_time",
                    "evening_start_time",
                    "evening_end_time",
                    "days_of_week",
                )
            },
        ),
        (
            _("Statistics"),
            {"fields": ("current_students_count", "is_operational_today_display")},
        ),
    )

    def route_code(self, obj):
        return obj.route.code

    route_code.short_description = _("Route Code")

    def vehicle_number(self, obj):
        return obj.vehicle.vehicle_number

    vehicle_number.short_description = _("Vehicle")

    def driver_name(self, obj):
        return obj.driver.user.get_full_name()

    driver_name.short_description = _("Driver")

    def is_operational_today_display(self, obj):
        if obj.is_operational_today:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Operational"),
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗</span> {}',
                _("Not Operational"),
            )

    is_operational_today_display.short_description = _("Today Status")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _student_count=Count(
                    "student_allocations",
                    filter=Q(student_allocations__status="active"),
                )
            )
        )

    def current_students_count(self, obj):
        return obj._student_count

    current_students_count.short_description = _("Current Students")
    current_students_count.admin_order_field = "_student_count"


@admin.register(TransportAllocation)
class TransportAllocationAdmin(InstitutionModelAdmin):
    list_display = (
        "student",
        "route_schedule_display",
        "pickup_stop",
        "drop_stop",
        "allocation_type",
        "start_date",
        "end_date",
        "is_active_allocation_display",
        "monthly_fee",
    )
    list_filter = ("allocation_type", "route_schedule__route", "status")
    search_fields = (
        "student__first_name",
        "student__last_name",
        "route_schedule__route__code",
        "pickup_stop__name",
        "drop_stop__name",
    )
    readonly_fields = ("is_active_allocation_display",)
    fieldsets = (
        (
            _("Allocation Information"),
            {"fields": ("student", "route_schedule", "allocation_type", "status")},
        ),
        (_("Stop Information"), {"fields": ("pickup_stop", "drop_stop")}),
        (
            _("Date Information"),
            {"fields": ("start_date", "end_date", "is_active_allocation_display")},
        ),
        (_("Financial Information"), {"fields": ("monthly_fee",)}),
        (_("Additional Information"), {"fields": ("notes",), "classes": ("collapse",)}),
    )

    def route_schedule_display(self, obj):
        return f"{obj.route_schedule.route.code} - {obj.route_schedule.vehicle.vehicle_number}"

    route_schedule_display.short_description = _("Route Schedule")

    def is_active_allocation_display(self, obj):
        if obj.is_active_allocation:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Active"),
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗</span> {}',
                _("Inactive"),
            )

    is_active_allocation_display.short_description = _("Active Status")


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(InstitutionModelAdmin):
    list_display = (
        "vehicle",
        "maintenance_type",
        "date",
        "odometer_reading",
        "cost",
        "next_due_date",
        "is_overdue_display",
    )
    list_filter = ("maintenance_type", "date", "vehicle__vehicle_type")
    search_fields = (
        "vehicle__vehicle_number",
        "description",
        "work_done",
        "invoice_number",
    )
    readonly_fields = ("is_overdue_display",)
    fieldsets = (
        (
            _("Maintenance Information"),
            {"fields": ("vehicle", "maintenance_type", "date", "odometer_reading")},
        ),
        (_("Work Details"), {"fields": ("description", "work_done", "parts_replaced")}),
        (
            _("Financial Information"),
            {"fields": ("cost", "service_center", "invoice_number")},
        ),
        (
            _("Next Maintenance"),
            {"fields": ("next_due_odometer", "next_due_date", "is_overdue_display")},
        ),
    )

    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠</span> {}', _("Overdue")
            )
        elif obj.next_due_date:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Scheduled"),
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">?</span> {}',
                _("Not Set"),
            )

    is_overdue_display.short_description = _("Next Maintenance Status")


@admin.register(FuelRecord)
class FuelRecordAdmin(InstitutionModelAdmin):
    list_display = (
        "vehicle",
        "date",
        "odometer_reading",
        "fuel_quantity",
        "fuel_cost",
        "fuel_efficiency_display",
        "fuel_station",
    )
    list_filter = ("date", "vehicle")
    search_fields = ("vehicle__vehicle_number", "fuel_station", "invoice_number")
    readonly_fields = ("fuel_efficiency_display",)
    fieldsets = (
        (_("Fuel Information"), {"fields": ("vehicle", "date", "odometer_reading")}),
        (
            _("Fuel Details"),
            {"fields": ("fuel_quantity", "fuel_cost", "fuel_efficiency_display")},
        ),
        (
            _("Station Information"),
            {"fields": ("fuel_station", "invoice_number"), "classes": ("collapse",)},
        ),
        (_("Additional Information"), {"fields": ("notes",), "classes": ("collapse",)}),
    )

    def fuel_efficiency_display(self, obj):
        efficiency = obj.fuel_efficiency
        if efficiency:
            return f"{efficiency:.2f} km/L"
        return _("Not available")

    fuel_efficiency_display.short_description = _("Fuel Efficiency")


@admin.register(IncidentReport)
class IncidentReportAdmin(InstitutionModelAdmin):
    list_display = (
        "incident_type",
        "severity_display",
        "route_schedule",
        "date",
        "time",
        "reported_by_name",
        "follow_up_required_display",
    )
    list_filter = ("incident_type", "severity", "date", "follow_up_required")
    search_fields = (
        "route_schedule__route__code",
        "location",
        "description",
        "reported_by__first_name",
        "reported_by__last_name",
    )
    readonly_fields = ("reported_by_name",)
    filter_horizontal = ("students_affected",)
    fieldsets = (
        (
            _("Incident Information"),
            {"fields": ("route_schedule", "incident_type", "severity")},
        ),
        (_("Time and Location"), {"fields": ("date", "time", "location")}),
        (_("Details"), {"fields": ("description", "action_taken")}),
        (_("Reporting"), {"fields": ("reported_by", "students_affected")}),
        (
            _("Follow-up"),
            {
                "fields": ("follow_up_required", "follow_up_notes"),
                "classes": ("collapse",),
            },
        ),
    )

    def severity_display(self, obj):
        severity_colors = {
            "low": "green",
            "medium": "orange",
            "high": "red",
            "critical": "darkred",
        }
        color = severity_colors.get(obj.severity, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_severity_display(),
        )

    severity_display.short_description = _("Severity")

    def reported_by_name(self, obj):
        return obj.reported_by.get_full_name() or obj.reported_by.username

    reported_by_name.short_description = _("Reported By")

    def follow_up_required_display(self, obj):
        if obj.follow_up_required:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⚠</span> {}',
                _("Required"),
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Completed"),
            )

    follow_up_required_display.short_description = _("Follow-up")


# Custom admin site header and title for transport app
admin.site.site_header = _("Transport Management System")
admin.site.site_title = _("Transport Admin")
admin.site.index_title = _("Transport Administration")
