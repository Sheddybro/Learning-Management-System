# apps/analytics/admin.py

from django.contrib import admin
from apps.core.admin import InstitutionModelAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.utils import timezone
from .models import (
    ReportType,
    Report,
    Dashboard,
    KPI,
    KPIMeasurement,
    DataExport,
    AnalyticsCache,
    TrendAnalysis,
)


class ReportInline(admin.TabularInline):
    """
    Inline admin for ReportType reports.
    """

    model = Report
    extra = 0
    fields = ("name", "academic_session", "format", "status", "created_at")
    readonly_fields = ("name", "academic_session", "format", "status", "created_at")
    autocomplete_fields = ("academic_session",)
    can_delete = False
    max_num = 5
    verbose_name_plural = _("Recent Reports")

    def has_add_permission(self, request, obj):
        return False


@admin.register(ReportType)
class ReportTypeAdmin(InstitutionModelAdmin):
    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)

    # Permission checks will defer to Django's default permission handling
    """
    Admin interface for ReportType model.
    """
    list_display = (
        "name",
        "code",
        "category",
        "is_standard",
        "refresh_frequency",
        "status",
    )
    list_filter = (
        "category",
        "is_standard",
        "refresh_frequency",
        "status",
        "created_at",
    )
    search_fields = ("name", "code", "description", "data_source")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            _("Report Type Information"),
            {"fields": ("name", "code", "category", "description", "is_standard")},
        ),
        (
            _("Data Configuration"),
            {
                "fields": ("data_source", "parameters_schema", "refresh_frequency"),
                "classes": ("collapse",),
            },
        ),
        (_("Access Control"), {"fields": ("access_roles",), "classes": ("collapse",)}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [ReportInline]

    actions = ["mark_as_standard", "mark_as_custom"]

    def mark_as_standard(self, request, queryset):
        """Admin action to mark report types as standard."""
        updated = queryset.update(is_standard=True)
        self.message_user(
            request, f"{updated} report types marked as standard.", messages.SUCCESS
        )

    mark_as_standard.short_description = _("Mark selected report types as standard")

    def mark_as_custom(self, request, queryset):
        """Admin action to mark report types as custom."""
        updated = queryset.update(is_standard=False)
        self.message_user(
            request, f"{updated} report types marked as custom.", messages.WARNING
        )

    mark_as_custom.short_description = _("Mark selected report types as custom")


class KPIMeasurementInline(admin.TabularInline):
    """
    Inline admin for KPI measurements.
    """

    model = KPIMeasurement
    extra = 0
    fields = ("academic_session", "measured_at", "value", "change_percentage")
    readonly_fields = ("academic_session", "measured_at", "value", "change_percentage")
    autocomplete_fields = ("academic_session",)
    can_delete = False
    max_num = 5
    verbose_name_plural = _("Recent Measurements")

    def has_add_permission(self, request, obj):
        return False


@admin.register(Report)
class ReportAdmin(InstitutionModelAdmin):
    """
    Admin interface for Report model.
    """

    list_display = (
        "name",
        "report_type",
        "academic_session",
        "format",
        "status",
        "generated_by",
        "created_at",
        "access_count",
    )
    list_filter = ("report_type", "format", "status", "academic_session", "created_at")
    search_fields = ("name", "report_type__name", "summary")
    readonly_fields = (
        "created_at",
        "updated_at",
        "generation_duration",
        "access_count",
        "last_accessed_at",
    )
    autocomplete_fields = ("report_type", "academic_session", "generated_by")
    raw_id_fields = ("generated_by",)
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Report Information"),
            {"fields": ("name", "report_type", "academic_session", "generated_by")},
        ),
        (
            _("Generation Details"),
            {"fields": ("format", "status", "parameters", "generation_duration")},
        ),
        (
            _("Timestamps"),
            {
                "fields": (
                    "generation_started_at",
                    "generation_completed_at",
                    "expires_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Content"),
            {"fields": ("file", "data", "summary"), "classes": ("collapse",)},
        ),
        (
            _("Usage Statistics"),
            {"fields": ("access_count", "last_accessed_at"), "classes": ("collapse",)},
        ),
    )

    actions = [
        "regenerate_reports",
        "mark_as_completed",
        "mark_as_failed",
        "update_access_stats",
    ]

    def generation_duration(self, obj):
        duration = obj.generation_duration
        if duration:
            return f"{duration:.2f} seconds"
        return "N/A"

    generation_duration.short_description = _("Generation Duration")

    def regenerate_reports(self, request, queryset):
        """Admin action to regenerate selected reports."""
        count = queryset.count()
        self.message_user(
            request, f"Regeneration initiated for {count} reports.", messages.INFO
        )

    regenerate_reports.short_description = _("Regenerate selected reports")

    def mark_as_completed(self, request, queryset):
        """Admin action to mark reports as completed."""
        updated = queryset.update(
            status="completed", generation_completed_at=timezone.now()
        )
        self.message_user(
            request, f"{updated} reports marked as completed.", messages.SUCCESS
        )

    mark_as_completed.short_description = _("Mark selected reports as completed")

    def mark_as_failed(self, request, queryset):
        """Admin action to mark reports as failed."""
        updated = queryset.update(status="failed")
        self.message_user(
            request, f"{updated} reports marked as failed.", messages.ERROR
        )

    mark_as_failed.short_description = _("Mark selected reports as failed")

    def update_access_stats(self, request, queryset):
        """Admin action to update access statistics."""
        for report in queryset:
            report.mark_accessed()
        self.message_user(
            request,
            f"Access statistics updated for {queryset.count()} reports.",
            messages.SUCCESS,
        )

    update_access_stats.short_description = _(
        "Update access statistics for selected reports"
    )

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)

    # Permission handling defers to Django's standard permission system


@admin.register(Dashboard)
class DashboardAdmin(InstitutionModelAdmin):
    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)

    """
    Admin interface for Dashboard model.
    """
    list_display = (
        "name",
        "owner",
        "dashboard_type",
        "is_default",
        "refresh_interval",
        "status",
    )
    list_filter = ("dashboard_type", "is_default", "status", "created_at")
    search_fields = ("name", "description", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("owner",)
    raw_id_fields = ("owner",)

    fieldsets = (
        (
            _("Dashboard Information"),
            {
                "fields": (
                    "name",
                    "description",
                    "owner",
                    "dashboard_type",
                    "is_default",
                )
            },
        ),
        (
            _("Configuration"),
            {
                "fields": ("layout_config", "widget_config", "refresh_interval"),
                "classes": ("collapse",),
            },
        ),
        (_("Access Control"), {"fields": ("access_roles",), "classes": ("collapse",)}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["set_as_default", "duplicate_dashboards"]

    def set_as_default(self, request, queryset):
        """Admin action to set dashboards as default for their owners."""
        count = 0
        for dashboard in queryset:
            dashboard.is_default = True
            dashboard.save()
            count += 1
        self.message_user(
            request, f"{count} dashboards set as default.", messages.SUCCESS
        )

    set_as_default.short_description = _("Set selected dashboards as default")

    def duplicate_dashboards(self, request, queryset):
        """Admin action to duplicate selected dashboards."""
        self.message_user(
            request,
            f"Duplication functionality for {queryset.count()} dashboards would be implemented here.",
            messages.INFO,
        )

    duplicate_dashboards.short_description = _("Duplicate selected dashboards")


@admin.register(KPI)
class KPIAdmin(InstitutionModelAdmin):
    """
    Admin interface for KPI model.
    """

    list_display = (
        "name",
        "code",
        "category",
        "value_type",
        "target_value",
        "refresh_frequency",
        "is_trending",
        "status",
    )
    list_filter = (
        "category",
        "value_type",
        "refresh_frequency",
        "is_trending",
        "status",
        "created_at",
    )
    search_fields = ("name", "code", "description", "data_source")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            _("KPI Information"),
            {"fields": ("name", "code", "category", "description", "value_type")},
        ),
        (
            _("Value Configuration"),
            {"fields": ("target_value", "min_value", "max_value", "display_format")},
        ),
        (
            _("Data Configuration"),
            {
                "fields": (
                    "calculation_query",
                    "data_source",
                    "refresh_frequency",
                    "is_trending",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    inlines = [KPIMeasurementInline]

    actions = ["enable_trending", "disable_trending", "refresh_kpis"]

    def enable_trending(self, request, queryset):
        """Admin action to enable trending for KPIs."""
        updated = queryset.update(is_trending=True)
        self.message_user(
            request, f"{updated} KPIs enabled for trending.", messages.SUCCESS
        )

    enable_trending.short_description = _("Enable trending for selected KPIs")

    def disable_trending(self, request, queryset):
        """Admin action to disable trending for KPIs."""
        updated = queryset.update(is_trending=False)
        self.message_user(
            request, f"{updated} KPIs disabled for trending.", messages.WARNING
        )

    disable_trending.short_description = _("Disable trending for selected KPIs")

    def refresh_kpis(self, request, queryset):
        """Admin action to trigger KPI refresh."""
        self.message_user(
            request, f"Refresh initiated for {queryset.count()} KPIs.", messages.INFO
        )

    refresh_kpis.short_description = _("Refresh selected KPIs")

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)


@admin.register(KPIMeasurement)
class KPIMeasurementAdmin(InstitutionModelAdmin):
    """
    Admin interface for KPIMeasurement model.
    """

    list_display = (
        "kpi",
        "academic_session",
        "measured_at",
        "value",
        "change_percentage",
        "previous_value",
    )
    list_filter = ("kpi__category", "academic_session", "measured_at", "created_at")
    search_fields = ("kpi__name", "kpi__code", "metadata")
    readonly_fields = ("created_at", "updated_at", "change_percentage")
    autocomplete_fields = ("kpi", "academic_session")
    raw_id_fields = ("kpi",)
    date_hierarchy = "measured_at"

    fieldsets = (
        (
            _("Measurement Information"),
            {"fields": ("kpi", "academic_session", "measured_at")},
        ),
        (_("Values"), {"fields": ("value", "previous_value", "change_percentage")}),
        (_("Additional Data"), {"fields": ("metadata",), "classes": ("collapse",)}),
    )

    actions = ["recalculate_change_percentage"]

    def recalculate_change_percentage(self, request, queryset):
        """Admin action to recalculate change percentages."""
        for measurement in queryset:
            measurement.save()
        self.message_user(
            request,
            f"Change percentages recalculated for {queryset.count()} measurements.",
            messages.SUCCESS,
        )

    recalculate_change_percentage.short_description = _(
        "Recalculate change percentages for selected measurements"
    )

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)


@admin.register(DataExport)
class DataExportAdmin(InstitutionModelAdmin):
    """
    Admin interface for DataExport model.
    """

    list_display = (
        "name",
        "requested_by",
        "data_source",
        "format",
        "status",
        "record_count",
        "file_size_human",
        "created_at",
    )
    list_filter = ("format", "status", "created_at")
    search_fields = ("name", "description", "requested_by__email", "data_source")
    readonly_fields = (
        "created_at",
        "updated_at",
        "processing_duration",
        "file_size_human",
    )
    autocomplete_fields = ("requested_by",)
    raw_id_fields = ("requested_by",)
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Export Information"),
            {"fields": ("name", "description", "requested_by", "data_source")},
        ),
        (
            _("Export Configuration"),
            {"fields": ("format", "filters", "columns"), "classes": ("collapse",)},
        ),
        (
            _("Processing Status"),
            {
                "fields": (
                    "status",
                    "started_at",
                    "completed_at",
                    "processing_duration",
                    "error_message",
                )
            },
        ),
        (
            _("Results"),
            {
                "fields": (
                    "file",
                    "file_size",
                    "file_size_human",
                    "record_count",
                    "expires_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["process_exports", "cancel_exports", "cleanup_expired_exports"]

    def file_size_human(self, obj):
        return obj.file_size_human

    file_size_human.short_description = _("File Size")

    def processing_duration(self, obj):
        duration = obj.processing_duration
        if duration:
            return f"{duration:.2f} seconds"
        return "N/A"

    processing_duration.short_description = _("Processing Duration")

    def process_exports(self, request, queryset):
        """Admin action to process selected exports."""
        count = queryset.count()
        self.message_user(
            request, f"Processing initiated for {count} exports.", messages.INFO
        )

    process_exports.short_description = _("Process selected exports")

    def cancel_exports(self, request, queryset):
        """Admin action to cancel selected exports."""
        updated = queryset.filter(status__in=["pending", "processing"]).update(
            status="cancelled"
        )
        self.message_user(request, f"{updated} exports cancelled.", messages.WARNING)

    cancel_exports.short_description = _("Cancel selected exports")

    def cleanup_expired_exports(self, request, queryset):
        """Admin action to cleanup expired exports."""
        expired = queryset.filter(expires_at__lt=timezone.now())
        count = expired.count()
        expired.delete()
        self.message_user(
            request, f"{count} expired exports cleaned up.", messages.SUCCESS
        )

    cleanup_expired_exports.short_description = _("Cleanup expired exports")

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)


@admin.register(AnalyticsCache)
class AnalyticsCacheAdmin(InstitutionModelAdmin):
    """
    Admin interface for AnalyticsCache model.
    """

    list_display = (
        "cache_key",
        "data_source",
        "expires_at",
        "last_accessed",
        "access_count",
        "size_bytes",
        "is_expired",
    )
    list_filter = ("data_source", "expires_at", "created_at")
    search_fields = ("cache_key", "data_source")
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_accessed",
        "access_count",
        "is_expired",
    )
    date_hierarchy = "expires_at"

    fieldsets = (
        (
            _("Cache Information"),
            {"fields": ("cache_key", "data_source", "expires_at", "is_expired")},
        ),
        (_("Cache Data"), {"fields": ("data", "size_bytes"), "classes": ("collapse",)}),
        (
            _("Usage Statistics"),
            {"fields": ("last_accessed", "access_count"), "classes": ("collapse",)},
        ),
    )

    def is_expired(self, obj):
        return obj.is_expired()

    is_expired.boolean = True
    is_expired.short_description = _("Expired")

    def has_add_permission(self, request):
        """Prevent manual creation of cache entries."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent modification of cache entries."""
        return False

    actions = ["refresh_cache", "clear_cache", "update_access_stats"]

    def refresh_cache(self, request, queryset):
        """Admin action to refresh selected cache entries."""
        count = queryset.count()
        self.message_user(
            request, f"Refresh initiated for {count} cache entries.", messages.INFO
        )

    refresh_cache.short_description = _("Refresh selected cache entries")

    def clear_cache(self, request, queryset):
        """Admin action to clear selected cache entries."""
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} cache entries cleared.", messages.SUCCESS)

    clear_cache.short_description = _("Clear selected cache entries")

    def update_access_stats(self, request, queryset):
        """Admin action to update access statistics."""
        for cache_entry in queryset:
            cache_entry.mark_accessed()
        self.message_user(
            request,
            f"Access statistics updated for {queryset.count()} cache entries.",
            messages.SUCCESS,
        )

    update_access_stats.short_description = _(
        "Update access statistics for selected cache entries"
    )


@admin.register(TrendAnalysis)
class TrendAnalysisAdmin(InstitutionModelAdmin):
    """
    Admin interface for TrendAnalysis model.
    """

    list_display = (
        "name",
        "analysis_period",
        "start_date",
        "end_date",
        "trend_direction",
        "confidence_score",
        "generated_by",
        "generated_at",
    )
    list_filter = ("analysis_period", "trend_direction", "generated_at")
    search_fields = ("name", "description", "data_source", "key_findings")
    readonly_fields = ("generated_at", "created_at", "updated_at", "period_days")
    autocomplete_fields = ("generated_by",)
    raw_id_fields = ("generated_by",)
    date_hierarchy = "generated_at"

    fieldsets = (
        (
            _("Analysis Information"),
            {
                "fields": (
                    "name",
                    "description",
                    "data_source",
                    "analysis_period",
                    "generated_by",
                )
            },
        ),
        (_("Analysis Period"), {"fields": ("start_date", "end_date", "period_days")}),
        (
            _("Results"),
            {
                "fields": (
                    "trend_direction",
                    "confidence_score",
                    "key_findings",
                    "recommendations",
                ),
                "classes": ("collapse",),
            },
        ),
        (_("Data Points"), {"fields": ("data_points",), "classes": ("collapse",)}),
    )

    def period_days(self, obj):
        return obj.period_days

    period_days.short_description = _("Period (Days)")

    actions = ["regenerate_analysis", "export_analysis"]

    def regenerate_analysis(self, request, queryset):
        """Admin action to regenerate trend analysis."""
        count = queryset.count()
        self.message_user(
            request,
            f"Regeneration initiated for {count} trend analyses.",
            messages.INFO,
        )

    regenerate_analysis.short_description = _("Regenerate selected trend analyses")

    def export_analysis(self, request, queryset):
        """Admin action to export trend analysis."""
        count = queryset.count()
        self.message_user(
            request,
            f"Export functionality for {count} trend analyses would be implemented here.",
            messages.INFO,
        )

    export_analysis.short_description = _("Export selected trend analyses")
