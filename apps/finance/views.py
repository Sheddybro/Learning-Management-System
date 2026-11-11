# apps/finance/views.py

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
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _
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
from .forms import (
    FeeStructureForm,
    FeeDiscountForm,
    InvoiceForm,
    InvoiceItemForm,
    PaymentForm,
    ExpenseForm,
    FinancialReportForm,
)
from apps.academics.models import AcademicSession, Student, Class
from apps.users.models import User, Role
from apps.audit.models import AuditLog


# =============================================================================
# MIXINS AND BASE CLASSES
# =============================================================================


class FinanceAccessMixin(LoginRequiredMixin):
    """Base mixin for finance app access control."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Check if user has finance-related role or is staff/admin
        user_roles = request.user.user_roles.all()
        finance_roles = ["accountant", "admin", "principal", "super_admin"]

        if not any(role.role.role_type in finance_roles for role in user_roles):
            if not request.user.is_staff:
                messages.error(
                    request, _("You don't have permission to access finance resources.")
                )
                return redirect("users:dashboard")

        return super().dispatch(request, *args, **kwargs)


class AccountantRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is an accountant, staff, or admin."""

    def test_func(self):
        user = self.request.user
        if user.is_staff:
            return True

        # Check if user has accountant role
        return user.user_roles.filter(role__role_type="accountant").exists()


# =============================================================================
# DASHBOARD VIEWS
# =============================================================================


class DashboardView(AccountantRequiredMixin, View):
    """Accountant dashboard showing financial overview."""

    def get(self, request):
        current_session = AcademicSession.objects.filter(is_current=True).first()

        # Get current institution for filtering
        from apps.core.middleware import get_current_institution

        current_institution = get_current_institution()

        # Fee Collection Summary - FILTERED BY INSTITUTION
        total_invoiced = Invoice.objects.filter(
            academic_session=current_session, student__institution=current_institution
        ).aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")

        total_paid = Invoice.objects.filter(
            academic_session=current_session, student__institution=current_institution
        ).aggregate(Sum("amount_paid"))["amount_paid__sum"] or Decimal("0.00")

        total_outstanding = total_invoiced - total_paid

        # Recent Invoices - FILTERED BY INSTITUTION
        recent_invoices = (
            Invoice.objects.filter(
                academic_session=current_session,
                student__institution=current_institution,
            )
            .select_related("student__user")
            .order_by("-issue_date")[:5]
        )

        # Recent Payments - FILTERED BY INSTITUTION
        recent_payments = (
            Payment.objects.filter(
                invoice__academic_session=current_session,
                invoice__student__institution=current_institution,
            )
            .select_related("student__user", "invoice")
            .order_by("-payment_date")[:5]
        )

        # Expense Summary - FILTERED BY INSTITUTION
        total_expenses = Expense.objects.filter(
            expense_date__year=timezone.now().year,
            expense_date__month=timezone.now().month,
            institution=current_institution,
        ).aggregate(Sum("amount"))["amount__sum"] or Decimal("0.00")

        # Overdue Invoices - FILTERED BY INSTITUTION
        overdue_invoices_count = Invoice.objects.filter(
            academic_session=current_session,
            student__institution=current_institution,
            due_date__lt=timezone.now().date(),
            balance_due__gt=Decimal("0.00"),
        ).count()

        context = {
            "title": _("Accountant Dashboard"),
            "current_session": current_session,
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "total_outstanding": total_outstanding,
            "recent_invoices": recent_invoices,
            "recent_payments": recent_payments,
            "total_expenses": total_expenses,
            "overdue_invoices_count": overdue_invoices_count,
        }
        return render(request, "finance/dashboard/accountant_dashboard.html", context)


# =============================================================================
# FEE STRUCTURE VIEWS
# =============================================================================


class FeeStructureListView(FinanceAccessMixin, ListView):
    """List all fee structures."""

    model = FeeStructure
    template_name = "finance/fee_structures/fee_structure_list.html"
    context_object_name = "fee_structures"
    paginate_by = 10

    def get_queryset(self):
        # Get current institution for filtering
        from apps.core.middleware import get_current_institution

        current_institution = get_current_institution()

        queryset = (
            FeeStructure.objects.select_related("academic_session", "applicable_class")
            .filter(institution=current_institution)
            .order_by("-academic_session__start_date", "fee_type")
        )

        session_id = self.request.GET.get("session")
        fee_type = self.request.GET.get("fee_type")

        if session_id:
            queryset = queryset.filter(academic_session_id=session_id)
        if fee_type:
            queryset = queryset.filter(fee_type=fee_type)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["academic_sessions"] = AcademicSession.objects.filter(status="active")
        context["fee_types"] = FeeStructure.FeeType.choices
        return context


class FeeStructureDetailView(FinanceAccessMixin, DetailView):
    """Detail view for a fee structure."""

    model = FeeStructure
    template_name = "finance/fee_structures/fee_structure_detail.html"
    context_object_name = "fee_structure"


class FeeStructureCreateView(AccountantRequiredMixin, CreateView):
    """Create a new fee structure."""

    model = FeeStructure
    form_class = FeeStructureForm
    template_name = "finance/fee_structures/fee_structure_form.html"
    success_url = reverse_lazy("finance:fee_structure_list")

    def form_valid(self, form):
        messages.success(self.request, _("Fee structure created successfully."))
        return super().form_valid(form)


class FeeStructureUpdateView(AccountantRequiredMixin, UpdateView):
    """Update an existing fee structure."""

    model = FeeStructure
    form_class = FeeStructureForm
    template_name = "finance/fee_structures/fee_structure_form.html"
    success_url = reverse_lazy("finance:fee_structure_list")

    def form_valid(self, form):
        messages.success(self.request, _("Fee structure updated successfully."))
        return super().form_valid(form)


class FeeStructureDeleteView(AccountantRequiredMixin, DeleteView):
    """Delete a fee structure."""

    model = FeeStructure
    template_name = "finance/fee_structures/fee_structure_confirm_delete.html"
    success_url = reverse_lazy("finance:fee_structure_list")

    def post(self, request, *args, **kwargs):
        messages.success(self.request, _("Fee structure deleted successfully."))
        return super().post(request, *args, **kwargs)


# =============================================================================
# FEE DISCOUNT VIEWS
# =============================================================================


class FeeDiscountListView(FinanceAccessMixin, ListView):
    """List all fee discounts."""

    model = FeeDiscount
    template_name = "finance/fee_discounts/fee_discount_list.html"
    context_object_name = "fee_discounts"
    paginate_by = 10

    def get_queryset(self):
        # Get current institution for filtering
        from apps.core.middleware import get_current_institution

        current_institution = get_current_institution()

        queryset = (
            FeeDiscount.objects.prefetch_related("applicable_fee_types")
            .filter(institution=current_institution)
            .order_by("-start_date")
        )

        category = self.request.GET.get("category")
        is_active = self.request.GET.get("is_active")

        if category:
            queryset = queryset.filter(category=category)
        if is_active:
            queryset = queryset.filter(is_active=(is_active == "true"))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = FeeDiscount.DiscountCategory.choices
        return context


class FeeDiscountDetailView(FinanceAccessMixin, DetailView):
    """Detail view for a fee discount."""

    model = FeeDiscount
    template_name = "finance/fee_discounts/fee_discount_detail.html"
    context_object_name = "fee_discount"


class FeeDiscountCreateView(AccountantRequiredMixin, CreateView):
    """Create a new fee discount."""

    model = FeeDiscount
    form_class = FeeDiscountForm
    template_name = "finance/fee_discounts/fee_discount_form.html"
    success_url = reverse_lazy("finance:fee_discount_list")

    def form_valid(self, form):
        messages.success(self.request, _("Fee discount created successfully."))
        return super().form_valid(form)


class FeeDiscountUpdateView(AccountantRequiredMixin, UpdateView):
    """Update an existing fee discount."""

    model = FeeDiscount
    form_class = FeeDiscountForm
    template_name = "finance/fee_discounts/fee_discount_form.html"
    success_url = reverse_lazy("finance:fee_discount_list")

    def form_valid(self, form):
        messages.success(self.request, _("Fee discount updated successfully."))
        return super().form_valid(form)


class FeeDiscountDeleteView(AccountantRequiredMixin, DeleteView):
    """Delete a fee discount."""

    model = FeeDiscount
    template_name = "finance/fee_discounts/fee_discount_confirm_delete.html"
    success_url = reverse_lazy("finance:fee_discount_list")

    def post(self, request, *args, **kwargs):
        messages.success(self.request, _("Fee discount deleted successfully."))
        return super().post(request, *args, **kwargs)


# =============================================================================
# INVOICE VIEWS
# =============================================================================


class InvoiceListView(FinanceAccessMixin, ListView):
    """List all invoices."""

    model = Invoice
    template_name = "finance/invoices/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 10

    def get_queryset(self):
        # Get current institution for filtering
        from apps.core.middleware import get_current_institution

        current_institution = get_current_institution()

        queryset = (
            Invoice.objects.select_related("student__user", "academic_session")
            .filter(student__institution=current_institution)
            .order_by("-issue_date")
        )

        session_id = self.request.GET.get("session")
        student_id = self.request.GET.get("student")
        status = self.request.GET.get("status")

        if session_id:
            queryset = queryset.filter(academic_session_id=session_id)
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["academic_sessions"] = AcademicSession.objects.filter(status="active")
        context["students"] = Student.objects.filter(status="active").select_related(
            "user"
        )
        context["invoice_statuses"] = Invoice.InvoiceStatus.choices
        return context


class InvoiceDetailView(FinanceAccessMixin, DetailView):
    """Detail view for an invoice."""

    model = Invoice
    template_name = "finance/invoices/invoice_detail.html"
    context_object_name = "invoice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invoice_items"] = self.object.items.select_related("fee_structure")
        context["payments"] = self.object.payments.select_related("received_by")
        return context


class InvoiceCreateView(AccountantRequiredMixin, CreateView):
    """Create a new invoice."""

    model = Invoice
    form_class = InvoiceForm
    template_name = "finance/invoices/invoice_form.html"
    success_url = reverse_lazy("finance:invoice_list")

    def form_valid(self, form):
        messages.success(self.request, _("Invoice created successfully."))
        return super().form_valid(form)


class InvoiceUpdateView(AccountantRequiredMixin, UpdateView):
    """Update an existing invoice."""

    model = Invoice
    form_class = InvoiceForm
    template_name = "finance/invoices/invoice_form.html"
    success_url = reverse_lazy("finance:invoice_list")

    def form_valid(self, form):
        messages.success(self.request, _("Invoice updated successfully."))
        return super().form_valid(form)


class InvoiceDeleteView(AccountantRequiredMixin, DeleteView):
    """Delete an invoice."""

    model = Invoice
    template_name = "finance/invoices/invoice_confirm_delete.html"
    success_url = reverse_lazy("finance:invoice_list")

    def post(self, request, *args, **kwargs):
        messages.success(self.request, _("Invoice deleted successfully."))
        return super().post(request, *args, **kwargs)


# =============================================================================
# PAYMENT VIEWS
# =============================================================================


class PaymentListView(FinanceAccessMixin, ListView):
    """List all payments."""

    model = Payment
    template_name = "finance/payments/payment_list.html"
    context_object_name = "payments"
    paginate_by = 10

    def get_queryset(self):
        # Get current institution for filtering
        from apps.core.middleware import get_current_institution

        current_institution = get_current_institution()

        queryset = (
            Payment.objects.select_related("invoice", "student__user", "received_by")
            .filter(invoice__student__institution=current_institution)
            .order_by("-payment_date")
        )

        session_id = self.request.GET.get("session")
        student_id = self.request.GET.get("student")
        payment_method = self.request.GET.get("payment_method")
        status = self.request.GET.get("status")

        if session_id:
            queryset = queryset.filter(invoice__academic_session_id=session_id)
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["academic_sessions"] = AcademicSession.objects.filter(status="active")
        context["students"] = Student.objects.filter(status="active").select_related(
            "user"
        )
        context["payment_methods"] = Payment.PaymentMethod.choices
        context["payment_statuses"] = Payment.PaymentStatus.choices
        return context


class PaymentDetailView(FinanceAccessMixin, DetailView):
    """Detail view for a payment."""

    model = Payment
    template_name = "finance/payments/payment_detail.html"
    context_object_name = "payment"


class PaymentGatewayView(FinanceAccessMixin, View):
    """
    Placeholder view for handling payment gateway redirection and processing.
    Actual payment gateway integration logic would go here.
    """

    def get(self, request, invoice_pk):
        invoice = get_object_or_404(Invoice, pk=invoice_pk)
        # In a real scenario, this would redirect to a payment gateway
        # or render a page with payment options.
        messages.info(
            request,
            _(
                f"Redirecting to payment gateway for Invoice #{invoice.invoice_number}. (Placeholder)"
            ),
        )
        return redirect(
            reverse_lazy("finance:invoice_detail", kwargs={"pk": invoice_pk})
        )

    def post(self, request, invoice_pk):
        invoice = get_object_or_404(Invoice, pk=invoice_pk)
        # This would handle the callback from the payment gateway
        messages.info(
            request,
            _(
                f"Processing payment callback for Invoice #{invoice.invoice_number}. (Placeholder)"
            ),
        )
        return redirect(
            reverse_lazy("finance:payment_success", kwargs={"pk": invoice_pk})
        )


class PaymentCancelView(FinanceAccessMixin, View):
    """
    Placeholder view for handling cancelled payment redirects.
    In a real scenario, this would log the cancellation and inform the user.
    """

    def get(self, request, pk):
        # pk here would typically be a payment ID or invoice ID
        messages.warning(
            request, _(f"Payment for ID {pk} was cancelled. (Placeholder)")
        )
        return redirect(
            reverse_lazy("finance:invoice_list")
        )  # Redirect to invoice list or detail


class PaymentSuccessView(FinanceAccessMixin, View):
    """
    Placeholder view for handling successful payment redirects.
    In a real scenario, this would confirm the payment and update invoice status.
    """

    def get(self, request, pk):
        # pk here would typically be a payment ID or invoice ID
        # For now, we'll just show a success message.
        messages.success(
            request, _(f"Payment for ID {pk} was successful! (Placeholder)")
        )
        return redirect(
            reverse_lazy("finance:invoice_list")
        )  # Redirect to invoice list or detail


class PaymentCreateView(AccountantRequiredMixin, CreateView):
    """Create a new payment."""

    model = Payment
    form_class = PaymentForm
    template_name = "finance/payments/payment_form.html"
    success_url = reverse_lazy("finance:payment_list")

    def form_valid(self, form):
        messages.success(self.request, _("Payment recorded successfully."))
        return super().form_valid(form)


class PaymentUpdateView(AccountantRequiredMixin, UpdateView):
    """Update an existing payment."""

    model = Payment
    form_class = PaymentForm
    template_name = "finance/payments/payment_form.html"
    success_url = reverse_lazy("finance:payment_list")

    def form_valid(self, form):
        messages.success(self.request, _("Payment updated successfully."))
        return super().form_valid(form)


class PaymentDeleteView(AccountantRequiredMixin, DeleteView):
    """Delete a payment."""

    model = Payment
    template_name = "finance/payments/payment_confirm_delete.html"
    success_url = reverse_lazy("finance:payment_list")

    def post(self, request, *args, **kwargs):
        messages.success(self.request, _("Payment deleted successfully."))
        return super().post(request, *args, **kwargs)


# =============================================================================
# EXPENSE VIEWS
# =============================================================================


class ExpenseListView(FinanceAccessMixin, ListView):
    """List all expenses."""

    model = Expense
    template_name = "finance/expenses/expense_list.html"
    context_object_name = "expenses"
    paginate_by = 10

    def get_queryset(self):
        # Get current institution for filtering
        from apps.core.middleware import get_current_institution

        current_institution = get_current_institution()

        queryset = (
            Expense.objects.select_related(
                "approved_by", "paid_by", "receipt_attachment"
            )
            .filter(institution=current_institution)
            .order_by("-expense_date")
        )

        category = self.request.GET.get("category")
        year = self.request.GET.get("year")
        month = self.request.GET.get("month")

        if category:
            queryset = queryset.filter(category=category)
        if year:
            queryset = queryset.filter(expense_date__year=year)
        if month:
            queryset = queryset.filter(expense_date__month=month)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["expense_categories"] = Expense.ExpenseCategory.choices
        context["years"] = Expense.objects.dates("expense_date", "year").order_by(
            "-date"
        )
        context["months"] = [
            (i, timezone.datetime(1, i, 1).strftime("%B")) for i in range(1, 13)
        ]
        return context


class ExpenseDetailView(FinanceAccessMixin, DetailView):
    """Detail view for an expense."""

    model = Expense
    template_name = "finance/expenses/expense_detail.html"
    context_object_name = "expense"


class ExpenseCreateView(AccountantRequiredMixin, CreateView):
    """Create a new expense."""

    model = Expense
    form_class = ExpenseForm
    template_name = "finance/expenses/expense_form.html"
    success_url = reverse_lazy("finance:expense_list")

    def form_valid(self, form):
        messages.success(self.request, _("Expense created successfully."))
        return super().form_valid(form)


class ExpenseUpdateView(AccountantRequiredMixin, UpdateView):
    """Update an existing expense."""

    model = Expense
    form_class = ExpenseForm
    template_name = "finance/expenses/expense_form.html"
    success_url = reverse_lazy("finance:expense_list")

    def form_valid(self, form):
        messages.success(self.request, _("Expense updated successfully."))
        return super().form_valid(form)


class ExpenseDeleteView(AccountantRequiredMixin, DeleteView):
    """Delete an expense."""

    model = Expense
    template_name = "finance/expenses/expense_confirm_delete.html"
    success_url = reverse_lazy("finance:expense_list")

    def post(self, request, *args, **kwargs):
        messages.success(self.request, _("Expense deleted successfully."))
        return super().post(request, *args, **kwargs)


# =============================================================================
# FINANCIAL REPORT VIEWS
# =============================================================================


class FinancialReportListView(FinanceAccessMixin, ListView):
    """List all financial reports."""

    model = FinancialReport
    template_name = "finance/reports/financial_report_list.html"
    context_object_name = "reports"
    paginate_by = 10

    def get_queryset(self):
        # Get current institution for filtering
        from apps.core.middleware import get_current_institution

        current_institution = get_current_institution()

        queryset = (
            FinancialReport.objects.select_related("academic_session", "generated_by")
            .filter(institution=current_institution)
            .order_by("-created_at")
        )

        report_type = self.request.GET.get("report_type")
        session_id = self.request.GET.get("session")
        is_published = self.request.GET.get("is_published")

        if report_type:
            queryset = queryset.filter(report_type=report_type)
        if session_id:
            queryset = queryset.filter(academic_session_id=session_id)
        if is_published:
            queryset = queryset.filter(is_published=(is_published == "true"))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["report_types"] = FinancialReport.ReportType.choices
        context["academic_sessions"] = AcademicSession.objects.filter(status="active")
        return context


class FinancialReportDetailView(FinanceAccessMixin, DetailView):
    """Detail view for a financial report."""

    model = FinancialReport
    template_name = "finance/reports/financial_report_detail.html"
    context_object_name = "report"


class FinancialReportCreateView(AccountantRequiredMixin, CreateView):
    """Create a new financial report."""

    model = FinancialReport
    form_class = FinancialReportForm
    template_name = "finance/reports/financial_report_form.html"
    success_url = reverse_lazy("finance:financial_report_list")

    def form_valid(self, form):
        form.instance.generated_by = self.request.user
        messages.success(self.request, _("Financial report created successfully."))
        return super().form_valid(form)


class FinancialReportUpdateView(AccountantRequiredMixin, UpdateView):
    """Update an existing financial report."""

    model = FinancialReport
    form_class = FinancialReportForm
    template_name = "finance/reports/financial_report_form.html"
    success_url = reverse_lazy("finance:financial_report_list")

    def form_valid(self, form):
        messages.success(self.request, _("Financial report updated successfully."))
        return super().form_valid(form)


class FinancialReportDeleteView(AccountantRequiredMixin, DeleteView):
    """Delete a financial report."""

    model = FinancialReport
    template_name = "finance/reports/financial_report_confirm_delete.html"
    success_url = reverse_lazy("finance:financial_report_list")

    def post(self, request, *args, **kwargs):
        messages.success(self.request, _("Financial report deleted successfully."))
        return super().post(request, *args, **kwargs)


# =============================================================================
# API & AJAX VIEWS
# =============================================================================


class ReceiptDownloadView(FinanceAccessMixin, View):
    """Placeholder view for downloading receipts."""

    def get(self, request, pk):
        messages.info(
            request, _(f"Receipt download for Payment ID {pk}. (Placeholder)")
        )
        return HttpResponse(_("Receipt Download Placeholder"))


class PaystackWebhookView(View):
    """Placeholder view for Paystack webhook."""

    def post(self, request):
        # In a real scenario, verify webhook signature and process payment update
        messages.info(request, _("Paystack webhook received. (Placeholder)"))
        return JsonResponse({"status": "success"}, status=200)


class FlutterwaveWebhookView(View):
    """Placeholder view for Flutterwave webhook."""

    def post(self, request):
        # In a real scenario, verify webhook signature and process payment update
        messages.info(request, _("Flutterwave webhook received. (Placeholder)"))
        return JsonResponse({"status": "success"}, status=200)


class APIInvoiceListView(FinanceAccessMixin, ListView):
    """API to list invoices (placeholder for a more robust API)."""

    model = Invoice

    def get_queryset(self):
        # Get current institution for filtering
        from apps.core.middleware import get_current_institution

        current_institution = get_current_institution()

        return Invoice.objects.filter(
            student__institution=current_institution
        ).order_by("-issue_date")

    def get(self, request, *args, **kwargs):
        invoices = self.get_queryset()
        data = [
            {
                "invoice_number": inv.invoice_number,
                "total_amount": str(inv.total_amount),
            }
            for inv in invoices
        ]
        return JsonResponse(data, safe=False)


class APIPaymentStatusView(FinanceAccessMixin, View):
    """API to get payment status (placeholder)."""

    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, pk=payment_id)
        data = {
            "payment_number": payment.payment_number,
            "status": payment.get_status_display(),
            "amount": str(payment.amount),
            "invoice_number": payment.invoice.invoice_number,
        }
        return JsonResponse(data)


class GenerateInvoiceAPIView(AccountantRequiredMixin, View):
    """API to generate invoices for students based on fee structures."""

    def post(self, request):
        import json
        from django.db import transaction

        try:
            data = json.loads(request.body)
            student_ids = data.get("student_ids")
            academic_session_id = data.get("academic_session_id")
            billing_period = data.get("billing_period")
            issue_date_str = data.get("issue_date")
            due_date_str = data.get("due_date")

            if not all(
                [
                    student_ids,
                    academic_session_id,
                    billing_period,
                    issue_date_str,
                    due_date_str,
                ]
            ):
                return JsonResponse(
                    {"success": False, "message": _("Missing required fields.")},
                    status=400,
                )

            academic_session = get_object_or_404(
                AcademicSession, id=academic_session_id
            )
            students = Student.objects.filter(id__in=student_ids, status="active")

            issue_date = timezone.datetime.strptime(issue_date_str, "%Y-%m-%d").date()
            due_date = timezone.datetime.strptime(due_date_str, "%Y-%m-%d").date()

            generated_invoices = []
            with transaction.atomic():
                for student in students:
                    # Check if an invoice for this student and billing period already exists
                    existing_invoice = Invoice.objects.filter(
                        student=student,
                        academic_session=academic_session,
                        billing_period=billing_period,
                    ).first()

                    if existing_invoice:
                        generated_invoices.append(
                            {
                                "student": student.user.get_full_name(),
                                "status": "skipped",
                                "reason": _("Invoice already exists for this period."),
                            }
                        )
                        continue

                    # Get applicable fee structures for the student's current class
                    current_enrollment = student.enrollments.filter(
                        academic_session=academic_session, enrollment_status="active"
                    ).first()

                    if not current_enrollment:
                        generated_invoices.append(
                            {
                                "student": student.user.get_full_name(),
                                "status": "skipped",
                                "reason": _(
                                    "Student not enrolled in an active class for this session."
                                ),
                            }
                        )
                        continue

                    applicable_fees = FeeStructure.objects.filter(
                        Q(academic_session=academic_session),
                        Q(applicable_class=current_enrollment.class_enrolled)
                        | Q(applicable_class__isnull=True),
                        status="active",
                    )

                    if not applicable_fees.exists():
                        generated_invoices.append(
                            {
                                "student": student.user.get_full_name(),
                                "status": "skipped",
                                "reason": _("No applicable fee structures found."),
                            }
                        )
                        continue

                    # Create invoice
                    invoice = Invoice.objects.create(
                        student=student,
                        academic_session=academic_session,
                        billing_period=billing_period,
                        issue_date=issue_date,
                        due_date=due_date,
                        status=Invoice.InvoiceStatus.ISSUED,
                        total_amount=Decimal("0.00"),  # Will be updated by items
                        subtotal=Decimal("0.00"),
                        total_tax=Decimal("0.00"),
                        total_discount=Decimal("0.00"),
                    )

                    invoice_subtotal = Decimal("0.00")
                    invoice_total_tax = Decimal("0.00")
                    invoice_total_discount = Decimal("0.00")

                    for fee in applicable_fees:
                        # Calculate discounts
                        discount_amount = Decimal("0.00")
                        if fee.discount_eligible:
                            applicable_discounts = FeeDiscount.objects.filter(
                                applicable_fee_types=fee,
                                is_active=True,
                                start_date__lte=issue_date,
                                end_date__gte=issue_date,
                            )
                            for discount in applicable_discounts:
                                if discount.is_applicable(
                                    student, fee
                                ):  # Custom logic in FeeDiscount model
                                    discount_amount += (
                                        discount.calculate_discount_amount(fee.amount)
                                    )

                        # Ensure discount doesn't exceed fee amount
                        discount_amount = min(discount_amount, fee.amount)

                        # Calculate tax
                        tax_amount = (fee.amount - discount_amount) * (
                            fee.tax_rate / Decimal("100.00")
                        )

                        line_total = fee.amount + tax_amount - discount_amount

                        InvoiceItem.objects.create(
                            invoice=invoice,
                            fee_structure=fee,
                            quantity=1,
                            unit_price=fee.amount,
                            tax_rate=fee.tax_rate,
                            discount_amount=discount_amount,
                            line_total=line_total,
                            description=fee.description,
                        )
                        invoice_subtotal += fee.amount
                        invoice_total_tax += tax_amount
                        invoice_total_discount += discount_amount

                    invoice.subtotal = invoice_subtotal
                    invoice.total_tax = invoice_total_tax
                    invoice.total_discount = invoice_total_discount
                    invoice.total_amount = (
                        invoice_subtotal + invoice_total_tax - invoice_total_discount
                    )
                    invoice.balance_due = invoice.total_amount
                    invoice.save()  # This will also generate invoice_number

                    generated_invoices.append(
                        {
                            "student": student.user.get_full_name(),
                            "status": "created",
                            "invoice_number": invoice.invoice_number,
                            "total_amount": str(invoice.total_amount),
                        }
                    )

            return JsonResponse(
                {
                    "success": True,
                    "message": _("Invoices generated successfully."),
                    "results": generated_invoices,
                }
            )

        except AcademicSession.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": _("Academic session not found.")},
                status=404,
            )
        except Student.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": _("One or more students not found.")},
                status=404,
            )
        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "message": _("Invalid JSON data.")}, status=400
            )
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)


class GetStudentOutstandingFeesAPIView(FinanceAccessMixin, View):
    """API to get outstanding fees for a specific student."""

    def get(self, request, student_id):
        student = get_object_or_404(Student, id=student_id)
        current_session = AcademicSession.objects.filter(is_current=True).first()

        if not current_session:
            return JsonResponse(
                {"success": False, "message": _("No current academic session found.")},
                status=404,
            )

        outstanding_invoices = Invoice.objects.filter(
            student=student,
            academic_session=current_session,
            balance_due__gt=Decimal("0.00"),
            status__in=["issued", "partial", "overdue"],
        ).order_by("due_date")

        fees_data = []
        total_outstanding = Decimal("0.00")
        for invoice in outstanding_invoices:
            fees_data.append(
                {
                    "invoice_number": invoice.invoice_number,
                    "billing_period": invoice.billing_period,
                    "due_date": invoice.due_date.strftime("%Y-%m-%d"),
                    "total_amount": str(invoice.total_amount),
                    "amount_paid": str(invoice.amount_paid),
                    "balance_due": str(invoice.balance_due),
                    "is_overdue": invoice.is_overdue,
                    "days_overdue": invoice.days_overdue,
                    "late_fee_calculated": str(invoice.calculate_late_fee()),
                }
            )
            total_outstanding += invoice.balance_due

        return JsonResponse(
            {
                "success": True,
                "student_name": student.user.get_full_name(),
                "total_outstanding": str(total_outstanding),
                "fees": fees_data,
            }
        )


class GetExpenseSummaryAPIView(FinanceAccessMixin, View):
    """API to get a summary of expenses for a given period."""

    def get(self, request):
        # Get current institution for filtering
        from apps.core.middleware import get_current_institution

        current_institution = get_current_institution()

        start_date_str = request.GET.get("start_date")
        end_date_str = request.GET.get("end_date")
        category = request.GET.get("category")

        if not all([start_date_str, end_date_str]):
            return JsonResponse(
                {
                    "success": False,
                    "message": _("Start date and end date are required."),
                },
                status=400,
            )

        start_date = timezone.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = timezone.datetime.strptime(end_date_str, "%Y-%m-%d").date()

        expenses = Expense.objects.filter(
            expense_date__range=[start_date, end_date],
            institution=current_institution,
        )

        if category:
            expenses = expenses.filter(category=category)

        total_amount = expenses.aggregate(Sum("amount"))["amount__sum"] or Decimal(
            "0.00"
        )

        category_summary = (
            expenses.values("category").annotate(total=Sum("amount")).order_by("-total")
        )

        summary_data = []
        for item in category_summary:
            summary_data.append(
                {
                    "category": dict(Expense.ExpenseCategory.choices).get(
                        item["category"], item["category"]
                    ),
                    "total": str(item["total"]),
                }
            )

        return JsonResponse(
            {
                "success": True,
                "start_date": start_date_str,
                "end_date": end_date_str,
                "total_expenses": str(total_amount),
                "category_summary": summary_data,
            }
        )


class GetInvoiceDetailsAPIView(FinanceAccessMixin, View):
    """API to get details of a single invoice."""

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        data = {
            "success": True,
            "invoice_number": invoice.invoice_number,
            "student_id": str(invoice.student.pk),
            "total_amount": str(invoice.total_amount),
            "amount_paid": str(invoice.amount_paid),
            "balance_due": str(invoice.balance_due),
            "issue_date": invoice.issue_date.strftime("%Y-%m-%d"),
            "due_date": invoice.due_date.strftime("%Y-%m-%d"),
            "status": invoice.get_status_display(),
        }
        return JsonResponse(data)


class PublishFinancialReportAPIView(AccountantRequiredMixin, View):
    """API to publish a financial report."""

    def post(self, request, pk):
        report = get_object_or_404(FinancialReport, pk=pk)
        if report.is_published:
            return JsonResponse(
                {"success": False, "message": _("Report is already published.")},
                status=400,
            )

        report.is_published = True
        report.published_at = timezone.now()
        report.save()
        messages.success(
            request, _(f'Financial report "{report.title}" published successfully.')
        )
        return JsonResponse(
            {"success": True, "message": _("Report published successfully.")}
        )


# =============================================================================
# STUDENT FEE VIEWS
# =============================================================================


class StudentInvoiceListView(LoginRequiredMixin, ListView):
    """View for students to see their invoices."""

    model = Invoice
    template_name = "finance/student/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 10

    def get_queryset(self):
        # Only show invoices for the logged-in student
        if hasattr(self.request.user, "student_profile"):
            queryset = (
                Invoice.objects.filter(student=self.request.user.student_profile)
                .select_related("academic_session")
                .order_by("-issue_date")
            )

            # Filter by status if provided
            status = self.request.GET.get("status")
            if status:
                queryset = queryset.filter(status=status)

            return queryset
        else:
            # If user is not a student, return empty queryset
            return Invoice.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["invoice_statuses"] = Invoice.InvoiceStatus.choices

        # Calculate summary statistics
        if hasattr(self.request.user, "student_profile"):
            student = self.request.user.student_profile
            current_session = AcademicSession.objects.filter(is_current=True).first()

            if current_session:
                # Total outstanding amount
                outstanding_invoices = Invoice.objects.filter(
                    student=student,
                    academic_session=current_session,
                    balance_due__gt=Decimal("0.00"),
                )
                total_outstanding = outstanding_invoices.aggregate(Sum("balance_due"))[
                    "balance_due__sum"
                ] or Decimal("0.00")

                # Recent payments
                recent_payments = (
                    Payment.objects.filter(student=student)
                    .select_related("invoice")
                    .order_by("-payment_date")[:5]
                )

                context.update(
                    {
                        "total_outstanding": total_outstanding,
                        "recent_payments": recent_payments,
                        "current_session": current_session,
                    }
                )

        return context
