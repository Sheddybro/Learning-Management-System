# apps/finance/admin.py

from django.contrib import admin
from apps.core.admin import InstitutionModelAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
from .models import (
    FeeStructure,
    FeeDiscount,
    Invoice,
    InvoiceItem,
    Payment,
    Expense,
    FinancialReport,
)


class FeeStructureInline(admin.TabularInline):
    """
    Inline admin for FeeStructure in academic session.
    """

    model = FeeStructure
    extra = 0
    fields = (
        "name",
        "fee_type",
        "applicable_class",
        "amount",
        "billing_cycle",
        "is_optional",
    )
    readonly_fields = (
        "name",
        "fee_type",
        "applicable_class",
        "amount",
        "billing_cycle",
        "is_optional",
    )
    autocomplete_fields = ("applicable_class",)
    can_delete = False
    max_num = 0
    verbose_name_plural = _("Fee Structures")

    def has_add_permission(self, request, obj):
        return False


class InvoiceItemInline(admin.TabularInline):
    """
    Inline admin for Invoice items.
    """

    model = InvoiceItem
    extra = 1
    fields = (
        "fee_structure",
        "quantity",
        "unit_price",
        "tax_rate",
        "discount_amount",
        "line_total",
    )
    readonly_fields = ("line_total",)
    autocomplete_fields = ("fee_structure",)
    verbose_name_plural = _("Invoice Items")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("fee_structure")


class PaymentInline(admin.TabularInline):
    """
    Inline admin for Invoice payments.
    """

    model = Payment
    extra = 0
    fields = (
        "payment_number",
        "amount",
        "payment_method",
        "payment_date",
        "status",
        "receipt_issued",
    )
    readonly_fields = (
        "payment_number",
        "amount",
        "payment_method",
        "payment_date",
        "status",
        "receipt_issued",
    )
    autocomplete_fields = ("received_by",)
    can_delete = False
    max_num = 0
    verbose_name_plural = _("Payments")

    def has_add_permission(self, request, obj):
        return False


@admin.register(FeeStructure)
class FeeStructureAdmin(InstitutionModelAdmin):
    """
    Admin interface for FeeStructure model.
    """

    list_display = (
        "name",
        "code",
        "fee_type",
        "academic_session",
        "applicable_class",
        "amount",
        "billing_cycle",
        "is_optional",
        "status",
    )
    list_filter = (
        "fee_type",
        "billing_cycle",
        "is_optional",
        "academic_session",
        "status",
        "created_at",
    )
    search_fields = ("name", "code", "description")
    readonly_fields = ("created_at", "updated_at", "tax_amount", "total_amount")
    autocomplete_fields = ("academic_session", "applicable_class")

    fieldsets = (
        (
            _("Fee Structure Information"),
            {
                "fields": (
                    "name",
                    "code",
                    "fee_type",
                    "academic_session",
                    "applicable_class",
                )
            },
        ),
        (
            _("Financial Details"),
            {"fields": ("amount", "billing_cycle", "due_day", "is_optional")},
        ),
        (
            _("Tax & Late Fees"),
            {
                "fields": (
                    "tax_rate",
                    "tax_amount",
                    "total_amount",
                    "late_fee_per_day",
                    "max_late_fee",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Discount Eligibility"),
            {"fields": ("discount_eligible", "description"), "classes": ("collapse",)},
        ),
        # System metadata fields are intentionally omitted here to avoid
        # duplicate-field system checks during admin autodiscover. These
        # readonly fields are still available via model defaults and
        # are not necessary in the explicit fieldsets.
    )

    actions = ["apply_discount_eligibility", "remove_discount_eligibility"]

    def tax_amount(self, obj):
        return obj.tax_amount

    tax_amount.short_description = _("Tax Amount")

    def total_amount(self, obj):
        return obj.total_amount

    total_amount.short_description = _("Total Amount")

    def apply_discount_eligibility(self, request, queryset):
        """Admin action to make fee structures discount eligible."""
        updated = queryset.update(discount_eligible=True)
        self.message_user(
            request,
            f"{updated} fee structures marked as discount eligible.",
            messages.SUCCESS,
        )

    apply_discount_eligibility.short_description = _(
        "Make selected fee structures discount eligible"
    )

    def remove_discount_eligibility(self, request, queryset):
        """Admin action to remove discount eligibility."""
        updated = queryset.update(discount_eligible=False)
        self.message_user(
            request,
            f"{updated} fee structures marked as not discount eligible.",
            messages.WARNING,
        )

    remove_discount_eligibility.short_description = _(
        "Remove discount eligibility from selected fee structures"
    )


@admin.register(FeeDiscount)
class FeeDiscountAdmin(InstitutionModelAdmin):
    """
    Admin interface for FeeDiscount model.
    """

    list_display = (
        "name",
        "code",
        "discount_type",
        "category",
        "value",
        "max_discount_amount",
        "start_date",
        "end_date",
        "is_active",
    )
    list_filter = (
        "discount_type",
        "category",
        "is_active",
        "status",
        "start_date",
        "end_date",
    )
    search_fields = ("name", "code", "description")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("applicable_fee_types",)

    fieldsets = (
        (
            _("Discount Information"),
            {"fields": ("name", "code", "discount_type", "category", "description")},
        ),
        (_("Discount Value"), {"fields": ("value", "max_discount_amount")}),
        (
            _("Applicability"),
            {"fields": ("applicable_fee_types", "start_date", "end_date", "is_active")},
        ),
        (_("Requirements"), {"fields": ("requirements",), "classes": ("collapse",)}),
        (
            _("System Metadata"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    actions = ["activate_discounts", "deactivate_discounts"]

    def activate_discounts(self, request, queryset):
        """Admin action to activate selected discounts."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} discounts activated.", messages.SUCCESS)

    activate_discounts.short_description = _("Activate selected discounts")

    def deactivate_discounts(self, request, queryset):
        """Admin action to deactivate selected discounts."""
        updated = queryset.update(is_active=False)
        self.message_user(
            request, f"{updated} discounts deactivated.", messages.WARNING
        )

    deactivate_discounts.short_description = _("Deactivate selected discounts")


@admin.register(Invoice)
class InvoiceAdmin(InstitutionModelAdmin):
    """
    Admin interface for Invoice model.
    """

    list_display = (
        "invoice_number",
        "student",
        "academic_session",
        "billing_period",
        "issue_date",
        "due_date",
        "status",
        "total_amount",
        "balance_due",
        "is_overdue",
    )
    list_filter = ("status", "academic_session", "issue_date", "due_date", "created_at")
    search_fields = (
        "invoice_number",
        "student__user__email",
        "student__student_id",
        "billing_period",
    )
    readonly_fields = (
        "invoice_number",
        "created_at",
        "updated_at",
        "balance_due",
        "is_overdue",
        "days_overdue",
    )
    autocomplete_fields = ("student", "academic_session")
    raw_id_fields = ("student",)
    date_hierarchy = "issue_date"

    fieldsets = (
        (
            _("Invoice Information"),
            {
                "fields": (
                    "invoice_number",
                    "student",
                    "academic_session",
                    "billing_period",
                )
            },
        ),
        (_("Dates"), {"fields": ("issue_date", "due_date", "status")}),
        (
            _("Financial Summary"),
            {
                "fields": (
                    "subtotal",
                    "total_discount",
                    "total_tax",
                    "total_amount",
                    "amount_paid",
                    "balance_due",
                    "late_fee",
                )
            },
        ),
        (
            _("Overdue Status"),
            {"fields": ("is_overdue", "days_overdue"), "classes": ("collapse",)},
        ),
        (
            _("Additional Information"),
            {"fields": ("notes", "terms_and_conditions"), "classes": ("collapse",)},
        ),
        (
            _("System Metadata"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    inlines = [InvoiceItemInline, PaymentInline]

    actions = ["mark_as_paid", "mark_as_overdue", "calculate_late_fees"]

    def is_overdue(self, obj):
        return obj.is_overdue

    is_overdue.boolean = True
    is_overdue.short_description = _("Overdue")

    def days_overdue(self, obj):
        return obj.days_overdue

    days_overdue.short_description = _("Days Overdue")

    def mark_as_paid(self, request, queryset):
        """Admin action to mark invoices as paid."""
        for invoice in queryset:
            invoice.mark_as_paid()
        self.message_user(
            request, f"{queryset.count()} invoices marked as paid.", messages.SUCCESS
        )

    mark_as_paid.short_description = _("Mark selected invoices as paid")

    def mark_as_overdue(self, request, queryset):
        """Admin action to mark invoices as overdue."""
        updated = queryset.update(status="overdue")
        self.message_user(
            request, f"{updated} invoices marked as overdue.", messages.WARNING
        )

    mark_as_overdue.short_description = _("Mark selected invoices as overdue")

    def calculate_late_fees(self, request, queryset):
        """Admin action to calculate and apply late fees."""
        count = 0
        for invoice in queryset:
            if invoice.is_overdue:
                late_fee = invoice.calculate_late_fee()
                if late_fee > Decimal("0.00"):
                    invoice.late_fee = late_fee
                    invoice.total_amount += late_fee
                    invoice.balance_due = invoice.total_amount - invoice.amount_paid
                    invoice.save()
                    count += 1
        self.message_user(
            request, f"Late fees calculated for {count} invoices.", messages.SUCCESS
        )

    calculate_late_fees.short_description = _(
        "Calculate late fees for selected invoices"
    )


@admin.register(InvoiceItem)
class InvoiceItemAdmin(InstitutionModelAdmin):
    """
    Admin interface for InvoiceItem model.
    """

    list_display = (
        "invoice",
        "fee_structure",
        "quantity",
        "unit_price",
        "tax_rate",
        "discount_amount",
        "line_total",
    )
    list_filter = ("fee_structure__fee_type", "created_at")
    search_fields = ("invoice__invoice_number", "fee_structure__name", "description")
    readonly_fields = ("created_at", "updated_at", "line_total")
    autocomplete_fields = ("invoice", "fee_structure")
    raw_id_fields = ("invoice",)

    fieldsets = (
        (
            _("Invoice Item Information"),
            {"fields": ("invoice", "fee_structure", "description")},
        ),
        (
            _("Pricing"),
            {
                "fields": (
                    "quantity",
                    "unit_price",
                    "tax_rate",
                    "discount_amount",
                    "line_total",
                )
            },
        ),
        (
            _("System Metadata"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("invoice", "fee_structure")


@admin.register(Payment)
class PaymentAdmin(InstitutionModelAdmin):
    """
    Admin interface for Payment model.
    """

    list_display = (
        "payment_number",
        "invoice",
        "student",
        "amount",
        "payment_method",
        "payment_date",
        "status",
        "receipt_issued",
        "received_by",
    )
    list_filter = (
        "payment_method",
        "status",
        "receipt_issued",
        "payment_date",
        "created_at",
    )
    search_fields = (
        "payment_number",
        "invoice__invoice_number",
        "student__user__email",
        "reference_number",
        "transaction_id",
    )
    readonly_fields = ("payment_number", "created_at", "updated_at")
    autocomplete_fields = ("invoice", "student", "received_by")
    raw_id_fields = ("invoice", "student", "received_by")
    date_hierarchy = "payment_date"

    fieldsets = (
        (
            _("Payment Information"),
            {
                "fields": (
                    "payment_number",
                    "invoice",
                    "student",
                    "amount",
                    "payment_method",
                    "payment_date",
                    "status",
                )
            },
        ),
        (
            _("Payment Details"),
            {
                "fields": (
                    "reference_number",
                    "bank_name",
                    "cheque_number",
                    "transaction_id",
                ),
                "classes": ("collapse",),
            },
        ),
        (_("Processing"), {"fields": ("received_by", "receipt_issued", "notes")}),
        (
            _("System Metadata"),
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    actions = ["mark_as_completed", "mark_receipt_issued", "mark_receipt_not_issued"]

    def mark_as_completed(self, request, queryset):
        """Admin action to mark payments as completed."""
        updated = queryset.update(status="completed")
        self.message_user(
            request, f"{updated} payments marked as completed.", messages.SUCCESS
        )

    mark_as_completed.short_description = _("Mark selected payments as completed")

    def mark_receipt_issued(self, request, queryset):
        """Admin action to mark receipts as issued."""
        updated = queryset.update(receipt_issued=True)
        self.message_user(
            request, f"{updated} payments marked as receipt issued.", messages.SUCCESS
        )

    mark_receipt_issued.short_description = _(
        "Mark receipts as issued for selected payments"
    )

    def mark_receipt_not_issued(self, request, queryset):
        """Admin action to mark receipts as not issued."""
        updated = queryset.update(receipt_issued=False)
        self.message_user(
            request,
            f"{updated} payments marked as receipt not issued.",
            messages.WARNING,
        )

    mark_receipt_not_issued.short_description = _(
        "Mark receipts as not issued for selected payments"
    )


@admin.register(Expense)
class ExpenseAdmin(InstitutionModelAdmin):
    """
    Admin interface for Expense model.
    """

    list_display = (
        "expense_number",
        "category",
        "description",
        "amount",
        "expense_date",
        "vendor",
        "approved_by",
        "payment_method",
    )
    list_filter = ("category", "payment_method", "expense_date", "status", "created_at")
    search_fields = ("expense_number", "description", "vendor", "invoice_number")
    readonly_fields = ("expense_number", "created_at", "updated_at")
    autocomplete_fields = ("approved_by", "paid_by")
    raw_id_fields = ("approved_by", "paid_by", "receipt_attachment")
    date_hierarchy = "expense_date"

    fieldsets = (
        (
            _("Expense Information"),
            {
                "fields": (
                    "expense_number",
                    "category",
                    "description",
                    "amount",
                    "expense_date",
                )
            },
        ),
        (
            _("Vendor Details"),
            {"fields": ("vendor", "invoice_number"), "classes": ("collapse",)},
        ),
        (
            _("Approval & Payment"),
            {"fields": ("approved_by", "paid_by", "payment_method")},
        ),
        (
            _("Documentation"),
            {"fields": ("receipt_attachment", "notes"), "classes": ("collapse",)},
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["export_expenses_report"]

    def export_expenses_report(self, request, queryset):
        """Admin action to export expenses report."""
        # This would typically generate a CSV or PDF report
        self.message_user(
            request,
            f"Export functionality for {queryset.count()} expenses would be implemented here.",
            messages.INFO,
        )

    export_expenses_report.short_description = _("Export selected expenses report")


@admin.register(FinancialReport)
class FinancialReportAdmin(InstitutionModelAdmin):
    """
    Admin interface for FinancialReport model.
    """

    list_display = (
        "report_number",
        "report_type",
        "title",
        "academic_session",
        "start_date",
        "end_date",
        "generated_by",
        "is_published",
        "published_at",
    )
    list_filter = (
        "report_type",
        "academic_session",
        "is_published",
        "start_date",
        "end_date",
    )
    search_fields = ("report_number", "title", "summary")
    readonly_fields = ("report_number", "created_at", "updated_at", "published_at")
    autocomplete_fields = ("academic_session", "generated_by")
    raw_id_fields = ("generated_by",)
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Report Information"),
            {"fields": ("report_number", "report_type", "title", "academic_session")},
        ),
        (_("Report Period"), {"fields": ("start_date", "end_date")}),
        (
            _("Content"),
            {"fields": ("report_data", "summary"), "classes": ("collapse",)},
        ),
        (
            _("Publication"),
            {"fields": ("is_published", "published_at", "generated_by")},
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["publish_reports", "unpublish_reports"]

    def save_model(self, request, obj, form, change):
        """Set published_at when report is published."""
        if obj.is_published and not obj.published_at:
            obj.published_at = timezone.now()
        elif not obj.is_published:
            obj.published_at = None
        super().save_model(request, obj, form, change)

    def publish_reports(self, request, queryset):
        """Admin action to publish selected reports."""
        for report in queryset:
            report.is_published = True
            if not report.published_at:
                report.published_at = timezone.now()
            report.save()
        self.message_user(
            request, f"{queryset.count()} reports published.", messages.SUCCESS
        )

    publish_reports.short_description = _("Publish selected reports")

    def unpublish_reports(self, request, queryset):
        """Admin action to unpublish selected reports."""
        updated = queryset.update(is_published=False, published_at=None)
        self.message_user(request, f"{updated} reports unpublished.", messages.WARNING)

    unpublish_reports.short_description = _("Unpublish selected reports")


# NOTE: Custom FinanceAdminSite removed. Models are registered with the
# default admin site via the @admin.register decorators above.
