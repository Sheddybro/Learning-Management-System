# apps/finance/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from django.utils import timezone

from apps.core.models import CoreBaseModel, AddressModel, ContactModel
from apps.users.models import User


class FeeStructure(CoreBaseModel):
    """
    Model for defining fee structures for different classes and categories.
    """

    class FeeType(models.TextChoices):
        TUITION = "tuition", _("Tuition Fee")
        TRANSPORT = "transport", _("Transport Fee")
        HOSTEL = "hostel", _("Hostel Fee")
        LIBRARY = "library", _("Library Fee")
        LABORATORY = "laboratory", _("Laboratory Fee")
        EXAMINATION = "examination", _("Examination Fee")
        SPORTS = "sports", _("Sports Fee")
        DEVELOPMENT = "development", _("Development Fee")
        OTHER = "other", _("Other Fee")

    class BillingCycle(models.TextChoices):
        MONTHLY = "monthly", _("Monthly")
        QUARTERLY = "quarterly", _("Quarterly")
        HALF_YEARLY = "half_yearly", _("Half Yearly")
        YEARLY = "yearly", _("Yearly")
        ONE_TIME = "one_time", _("One Time")

    name = models.CharField(_("fee structure name"), max_length=200)
    code = models.CharField(_("fee code"), max_length=50, unique=True)
    fee_type = models.CharField(
        _("fee type"), max_length=20, choices=FeeType.choices, default=FeeType.TUITION
    )
    academic_session = models.ForeignKey(
        "academics.AcademicSession",
        on_delete=models.CASCADE,
        related_name="fee_structures",
        verbose_name=_("academic session"),
    )
    applicable_class = models.ForeignKey(
        "academics.Class",
        on_delete=models.CASCADE,
        related_name="fee_structures",
        verbose_name=_("applicable class"),
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        _("amount"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    billing_cycle = models.CharField(
        _("billing cycle"),
        max_length=20,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    due_day = models.PositiveIntegerField(
        _("due day of month"),
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        default=1,
    )
    is_optional = models.BooleanField(_("is optional"), default=False)
    description = models.TextField(_("description"), blank=True)
    tax_rate = models.DecimalField(
        _("tax rate (%)"),
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )
    late_fee_per_day = models.DecimalField(
        _("late fee per day"),
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    max_late_fee = models.DecimalField(
        _("maximum late fee"),
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    discount_eligible = models.BooleanField(_("discount eligible"), default=False)

    class Meta:
        verbose_name = _("Fee Structure")
        verbose_name_plural = _("Fee Structures")
        ordering = ["academic_session", "fee_type", "applicable_class"]
        indexes = [
            models.Index(fields=["academic_session", "fee_type"]),
            models.Index(fields=["applicable_class", "billing_cycle"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_session", "fee_type", "applicable_class"],
                name="unique_fee_structure",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.academic_session} - {self.amount}"

    @property
    def tax_amount(self):
        """Calculate tax amount for this fee."""
        return (self.amount * self.tax_rate) / Decimal("100.00")

    @property
    def total_amount(self):
        """Calculate total amount including tax."""
        return self.amount + self.tax_amount


class FeeDiscount(CoreBaseModel):
    """
    Model for managing fee discounts and concessions.
    """

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", _("Percentage")
        FIXED_AMOUNT = "fixed_amount", _("Fixed Amount")
        FULL_WAIVER = "full_waiver", _("Full Waiver")

    class DiscountCategory(models.TextChoices):
        SCHOLARSHIP = "scholarship", _("Scholarship")
        SIBLING = "sibling", _("Sibling Discount")
        EARLY_PAYMENT = "early_payment", _("Early Payment Discount")
        STAFF = "staff", _("Staff Discount")
        SPECIAL_NEEDS = "special_needs", _("Special Needs")
        OTHER = "other", _("Other")

    name = models.CharField(_("discount name"), max_length=200)
    code = models.CharField(_("discount code"), max_length=50, unique=True)
    discount_type = models.CharField(
        _("discount type"),
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )
    category = models.CharField(
        _("discount category"),
        max_length=20,
        choices=DiscountCategory.choices,
        default=DiscountCategory.OTHER,
    )
    value = models.DecimalField(
        _("discount value"),
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    max_discount_amount = models.DecimalField(
        _("maximum discount amount"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    applicable_fee_types = models.ManyToManyField(
        FeeStructure,
        related_name="discounts",
        verbose_name=_("applicable fee types"),
        blank=True,
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"))
    is_active = models.BooleanField(_("is active"), default=True)
    description = models.TextField(_("description"), blank=True)
    requirements = models.JSONField(_("requirements"), default=dict, blank=True)

    class Meta:
        verbose_name = _("Fee Discount")
        verbose_name_plural = _("Fee Discounts")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_discount_type_display()}"

    def calculate_discount_amount(self, base_amount):
        """Calculate discount amount based on discount type."""
        if self.discount_type == self.DiscountType.FULL_WAIVER:
            return base_amount
        elif self.discount_type == self.DiscountType.PERCENTAGE:
            discount = (base_amount * self.value) / Decimal("100.00")
            if self.max_discount_amount and discount > self.max_discount_amount:
                return self.max_discount_amount
            return discount
        elif self.discount_type == self.DiscountType.FIXED_AMOUNT:
            return min(self.value, base_amount)
        return Decimal("0.00")

    def is_applicable(self, student, fee_structure):
        """Check if discount is applicable for given student and fee structure."""
        if not self.is_active:
            return False
        today = timezone.now().date()
        if not (self.start_date <= today <= self.end_date):
            return False

        if (
            self.applicable_fee_types.exists()
            and fee_structure not in self.applicable_fee_types.all()
        ):
            return False

        # Check additional requirements from JSON field
        # This can be extended based on specific requirements
        return True


class Invoice(CoreBaseModel):
    """
    Model for student fee invoices.
    """

    class InvoiceStatus(models.TextChoices):
        DRAFT = "draft", _("Draft")
        ISSUED = "issued", _("Issued")
        PARTIAL = "partial", _("Partially Paid")
        PAID = "paid", _("Paid")
        OVERDUE = "overdue", _("Overdue")
        CANCELLED = "cancelled", _("Cancelled")
        REFUNDED = "refunded", _("Refunded")

    invoice_number = models.CharField(
        _("invoice number"), max_length=50, unique=True, db_index=True
    )
    student = models.ForeignKey(
        "academics.Student",
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("student"),
    )
    academic_session = models.ForeignKey(
        "academics.AcademicSession",
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("academic session"),
    )
    billing_period = models.CharField(_("billing period"), max_length=100)
    issue_date = models.DateField(_("issue date"))
    due_date = models.DateField(_("due date"))
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
    )
    subtotal = models.DecimalField(
        _("subtotal"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_discount = models.DecimalField(
        _("total discount"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_tax = models.DecimalField(
        _("total tax"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_amount = models.DecimalField(
        _("total amount"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    amount_paid = models.DecimalField(
        _("amount paid"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    balance_due = models.DecimalField(
        _("balance due"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    late_fee = models.DecimalField(
        _("late fee"),
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    notes = models.TextField(_("notes"), blank=True)
    terms_and_conditions = models.TextField(_("terms and conditions"), blank=True)

    class Meta:
        verbose_name = _("Invoice")
        verbose_name_plural = _("Invoices")
        ordering = ["-issue_date", "invoice_number"]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["due_date", "status"]),
            models.Index(fields=["academic_session", "status"]),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.student}"

    def save(self, *args, **kwargs):
        """Calculate totals before saving."""
        if not self.invoice_number:
            from apps.core.models import SequenceGenerator

            sequence, created = SequenceGenerator.objects.get_or_create(
                sequence_type=SequenceGenerator.SequenceType.INVOICE,
                institution=self.institution,
                defaults={"prefix": "INV", "padding": 3},
            )
            self.invoice_number = sequence.get_next_number()

        self.balance_due = self.total_amount - self.amount_paid

        # Update status based on payment
        if self.amount_paid >= self.total_amount:
            self.status = self.InvoiceStatus.PAID
        elif self.amount_paid > Decimal("0.00"):
            self.status = self.InvoiceStatus.PARTIAL
        elif self.status == self.InvoiceStatus.DRAFT and self.issue_date:
            self.status = self.InvoiceStatus.ISSUED

        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        from django.utils import timezone

        return self.due_date < timezone.now().date() and self.balance_due > Decimal(
            "0.00"
        )

    @property
    def days_overdue(self):
        """Calculate number of days overdue."""
        from django.utils import timezone

        if self.is_overdue:
            return (timezone.now().date() - self.due_date).days
        return 0

    def calculate_late_fee(self):
        """Calculate late fee based on overdue days."""
        if not self.is_overdue:
            return Decimal("0.00")

        total_late_fee = Decimal("0.00")
        for item in self.items.all():
            if item.fee_structure.late_fee_per_day > Decimal("0.00"):
                days_overdue = self.days_overdue
                late_fee = days_overdue * item.fee_structure.late_fee_per_day
                if item.fee_structure.max_late_fee > Decimal("0.00"):
                    late_fee = min(late_fee, item.fee_structure.max_late_fee)
                total_late_fee += late_fee

        return total_late_fee

    def mark_as_paid(self):
        """Mark invoice as fully paid."""
        self.amount_paid = self.total_amount
        self.balance_due = Decimal("0.00")
        self.status = self.InvoiceStatus.PAID
        self.save()


class InvoiceItem(CoreBaseModel):
    """
    Model for individual line items in an invoice.
    """

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("invoice"),
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.CASCADE,
        related_name="invoice_items",
        verbose_name=_("fee structure"),
    )
    quantity = models.PositiveIntegerField(_("quantity"), default=1)
    unit_price = models.DecimalField(
        _("unit price"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    tax_rate = models.DecimalField(
        _("tax rate (%)"), max_digits=5, decimal_places=2, default=Decimal("0.00")
    )
    discount_amount = models.DecimalField(
        _("discount amount"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    line_total = models.DecimalField(
        _("line total"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    description = models.TextField(_("description"), blank=True)

    class Meta:
        verbose_name = _("Invoice Item")
        verbose_name_plural = _("Invoice Items")
        ordering = ["invoice", "created_at"]

    def __str__(self):
        return f"{self.fee_structure.name} - {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        """Calculate line total before saving."""
        base_amount = self.unit_price * self.quantity
        tax_amount = (base_amount * self.tax_rate) / Decimal("100.00")
        self.line_total = base_amount + tax_amount - self.discount_amount
        super().save(*args, **kwargs)


class Payment(CoreBaseModel):
    """
    Model for tracking payments against invoices.
    """

    class PaymentMethod(models.TextChoices):
        CASH = "cash", _("Cash")
        CHEQUE = "cheque", _("Cheque")
        BANK_TRANSFER = "bank_transfer", _("Bank Transfer")
        CREDIT_CARD = "credit_card", _("Credit Card")
        DEBIT_CARD = "debit_card", _("Debit Card")
        ONLINE = "online", _("Online Payment")
        MOBILE = "mobile", _("Mobile Payment")
        OTHER = "other", _("Other")

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")
        CANCELLED = "cancelled", _("Cancelled")
        REFUNDED = "refunded", _("Refunded")

    payment_number = models.CharField(
        _("payment number"), max_length=50, unique=True, db_index=True
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("invoice"),
    )
    student = models.ForeignKey(
        "academics.Student",
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name=_("student"),
    )
    amount = models.DecimalField(
        _("amount"),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    payment_method = models.CharField(
        _("payment method"),
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    payment_date = models.DateField(_("payment date"))
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="received_payments",
        verbose_name=_("received by"),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    reference_number = models.CharField(
        _("reference number"), max_length=100, blank=True
    )
    bank_name = models.CharField(_("bank name"), max_length=100, blank=True)
    cheque_number = models.CharField(_("cheque number"), max_length=50, blank=True)
    transaction_id = models.CharField(_("transaction ID"), max_length=100, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    receipt_issued = models.BooleanField(_("receipt issued"), default=False)

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ["-payment_date", "-created_at"]
        indexes = [
            models.Index(fields=["student", "payment_date"]),
            models.Index(fields=["invoice", "status"]),
            models.Index(fields=["payment_method", "status"]),
        ]

    def __str__(self):
        return f"Payment {self.payment_number} - {self.amount}"

    def save(self, *args, **kwargs):
        """Generate payment number and update invoice before saving."""
        if not self.payment_number:
            from apps.core.models import SequenceGenerator

            sequence, created = SequenceGenerator.objects.get_or_create(
                sequence_type="receipt"
            )
            self.payment_number = sequence.get_next_number()

        # Update invoice payment status
        if self.status == self.PaymentStatus.COMPLETED:
            self.invoice.amount_paid += self.amount
            self.invoice.save()

        super().save(*args, **kwargs)


class Expense(CoreBaseModel):
    """
    Model for tracking school expenses.
    """

    class ExpenseCategory(models.TextChoices):
        SALARIES = "salaries", _("Salaries")
        UTILITIES = "utilities", _("Utilities")
        MAINTENANCE = "maintenance", _("Maintenance")
        TEACHING_AIDS = "teaching_aids", _("Teaching Aids")
        OFFICE_SUPPLIES = "office_supplies", _("Office Supplies")
        SPORTS_EQUIPMENT = "sports_equipment", _("Sports Equipment")
        LAB_EQUIPMENT = "lab_equipment", _("Laboratory Equipment")
        TRANSPORT = "transport", _("Transport")
        RENT = "rent", _("Rent")
        OTHER = "other", _("Other")

    expense_number = models.CharField(
        _("expense number"), max_length=50, unique=True, db_index=True
    )
    category = models.CharField(
        _("category"),
        max_length=20,
        choices=ExpenseCategory.choices,
        default=ExpenseCategory.OTHER,
    )
    description = models.CharField(_("description"), max_length=500)
    amount = models.DecimalField(
        _("amount"),
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    expense_date = models.DateField(_("expense date"))
    vendor = models.CharField(_("vendor"), max_length=200, blank=True)
    invoice_number = models.CharField(
        _("vendor invoice number"), max_length=100, blank=True
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="approved_expenses",
        verbose_name=_("approved by"),
    )
    paid_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paid_expenses",
        verbose_name=_("paid by"),
    )
    payment_method = models.CharField(
        _("payment method"),
        max_length=20,
        choices=Payment.PaymentMethod.choices,
        default=Payment.PaymentMethod.CASH,
    )
    receipt_attachment = models.ForeignKey(
        "academics.FileAttachment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("receipt attachment"),
    )
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        verbose_name = _("Expense")
        verbose_name_plural = _("Expenses")
        ordering = ["-expense_date", "-created_at"]
        indexes = [
            models.Index(fields=["category", "expense_date"]),
            models.Index(fields=["expense_date", "status"]),
        ]

    def __str__(self):
        return f"Expense {self.expense_number} - {self.amount}"

    def save(self, *args, **kwargs):
        """Generate expense number before saving."""
        if not self.expense_number:
            from apps.core.models import SequenceGenerator

            sequence, created = SequenceGenerator.objects.get_or_create(
                sequence_type="expense"
            )
            self.expense_number = sequence.get_next_number()
        super().save(*args, **kwargs)


class FinancialReport(CoreBaseModel):
    """
    Model for storing generated financial reports.
    """

    class ReportType(models.TextChoices):
        INCOME_STATEMENT = "income_statement", _("Income Statement")
        BALANCE_SHEET = "balance_sheet", _("Balance Sheet")
        CASH_FLOW = "cash_flow", _("Cash Flow Statement")
        FEE_COLLECTION = "fee_collection", _("Fee Collection Report")
        EXPENSE_SUMMARY = "expense_summary", _("Expense Summary")
        OUTSTANDING_FEES = "outstanding_fees", _("Outstanding Fees Report")
        STUDENT_LEDGER = "student_ledger", _("Student Ledger")

    report_number = models.CharField(
        _("report number"), max_length=50, unique=True, db_index=True
    )
    report_type = models.CharField(
        _("report type"), max_length=20, choices=ReportType.choices
    )
    title = models.CharField(_("report title"), max_length=200)
    academic_session = models.ForeignKey(
        "academics.AcademicSession",
        on_delete=models.CASCADE,
        related_name="financial_reports",
        verbose_name=_("academic session"),
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"))
    generated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="financial_reports",
        verbose_name=_("generated by"),
    )
    report_data = models.JSONField(_("report data"), default=dict)
    summary = models.TextField(_("summary"), blank=True)
    is_published = models.BooleanField(_("is published"), default=False)
    published_at = models.DateTimeField(_("published at"), null=True, blank=True)

    class Meta:
        verbose_name = _("Financial Report")
        verbose_name_plural = _("Financial Reports")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["report_type", "academic_session"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.academic_session}"

    def save(self, *args, **kwargs):
        """Generate report number before saving."""
        if not self.report_number:
            from apps.core.models import SequenceGenerator

            sequence, created = SequenceGenerator.objects.get_or_create(
                sequence_type="financial_report"
            )
            self.report_number = sequence.get_next_number()
        super().save(*args, **kwargs)
