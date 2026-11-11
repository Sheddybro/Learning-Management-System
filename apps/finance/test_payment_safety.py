"""Regression checks for finance endpoints that must fail closed.

Run with: python manage.py test apps.finance.test_payment_safety
These tests use request factories and mocks, not production school records.
"""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase

from apps.finance.views import (
    FlutterwaveWebhookView,
    PaystackWebhookView,
    PaymentSuccessView,
    PaymentGatewayView,
    APIPaymentStatusView,
    GetInvoiceDetailsAPIView,
    GenerateInvoiceAPIView,
    StudentInvoiceDetailView,
)
from apps.finance.models import Invoice, Payment
from apps.finance.forms import InvoiceForm, PaymentForm, FinancialReportForm
from apps.academics.models import Student


def staff_request(path, method="get"):
    factory = RequestFactory()
    request = getattr(factory, method)(path)
    request.user = SimpleNamespace(
        is_authenticated=True,
        is_staff=True,
        is_superuser=False,
        user_roles=SimpleNamespace(all=lambda: []),
    )
    return request


class UnconfiguredPaymentsTests(SimpleTestCase):
    def test_unconfigured_webhooks_do_not_acknowledge_success(self):
        for view in (PaystackWebhookView, FlutterwaveWebhookView):
            with self.subTest(view=view.__name__):
                response = view.as_view()(staff_request("/webhook/", "post"))
                self.assertEqual(response.status_code, 503)
                self.assertIn(b'"success": false', response.content)

    def test_unverified_success_callback_is_not_successful(self):
        response = PaymentSuccessView.as_view()(
            staff_request("/payments/success/"), pk="not-a-real-payment"
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"not been verified", response.content)

    @patch("apps.finance.views.get_object_or_404")
    @patch("apps.core.middleware.get_user_accessible_institutions")
    def test_unconfigured_gateway_is_not_a_payment_success(self, accessible, lookup):
        accessible.return_value = ["school-a"]
        response = PaymentGatewayView.as_view()(
            staff_request("/invoices/gateway/"), invoice_pk="invoice-1"
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(lookup.call_args.kwargs["student__institution__in"], ["school-a"])


class FinanceObjectAccessTests(SimpleTestCase):
    @patch("apps.finance.views.get_object_or_404", side_effect=Http404)
    @patch("apps.core.middleware.get_user_accessible_institutions")
    def test_invoice_details_lookup_is_scoped(self, accessible, lookup):
        accessible.return_value = ["school-a"]
        with self.assertRaises(Http404):
            GetInvoiceDetailsAPIView.as_view()(
                staff_request("/finance/api/invoice/"), pk="foreign-invoice"
            )
        self.assertEqual(lookup.call_args.kwargs["student__institution__in"], ["school-a"])

    @patch("apps.finance.views.get_object_or_404", side_effect=Http404)
    @patch("apps.core.middleware.get_user_accessible_institutions")
    def test_payment_status_lookup_is_scoped(self, accessible, lookup):
        accessible.return_value = ["school-a"]
        with self.assertRaises(Http404):
            APIPaymentStatusView.as_view()(
                staff_request("/finance/api/payment/"), payment_id="foreign-payment"
            )
        self.assertEqual(
            lookup.call_args.kwargs["invoice__student__institution__in"],
            ["school-a"],
        )


class InvoiceGenerationBoundaryTests(SimpleTestCase):
    @patch("apps.finance.views.get_object_or_404", side_effect=Http404)
    @patch("apps.core.middleware.get_user_accessible_institutions")
    def test_foreign_school_session_returns_not_found(self, accessible, lookup):
        import json

        accessible.return_value = ["school-a"]
        request = RequestFactory().post(
            "/finance/api/generate-invoices/",
            data=json.dumps({
                "student_ids": ["student-1"],
                "academic_session_id": "foreign-session",
                "billing_period": "Term 1",
                "issue_date": "2026-11-11",
                "due_date": "2026-12-11",
            }),
            content_type="application/json",
        )
        request.user = staff_request("/").user
        response = GenerateInvoiceAPIView.as_view()(request)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            lookup.call_args.kwargs["institution__in"],
            ["school-a"],
        )

    @patch("apps.finance.views.get_object_or_404")
    @patch("apps.core.middleware.get_user_accessible_institutions")
    @patch("apps.finance.views.Student.objects.filter")
    def test_foreign_school_student_is_rejected_before_invoice_creation(
        self, student_filter, accessible, lookup
    ):
        import json

        accessible.return_value = ["school-a"]
        lookup.return_value = SimpleNamespace(institution="school-a")
        student_filter.return_value.count.return_value = 0
        request = RequestFactory().post(
            "/finance/api/generate-invoices/",
            data=json.dumps({
                "student_ids": ["foreign-student"],
                "academic_session_id": "session-a",
                "billing_period": "Term 1",
                "issue_date": "2026-11-11",
                "due_date": "2026-12-11",
            }),
            content_type="application/json",
        )
        request.user = staff_request("/").user
        response = GenerateInvoiceAPIView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(student_filter.call_args.kwargs["institution"], "school-a")


class InvoiceStatusInitializationTests(SimpleTestCase):
    @patch("apps.core.models.CoreBaseModel.save")
    def test_initial_zero_total_does_not_mark_invoice_paid(self, base_save):
        from decimal import Decimal
        from django.utils import timezone
        from apps.finance.models import Invoice

        invoice = Invoice(
            invoice_number="INV-TEST-1",
            status=Invoice.InvoiceStatus.ISSUED,
            issue_date=timezone.now().date(),
            total_amount=Decimal("0.00"),
            amount_paid=Decimal("0.00"),
        )
        invoice.save()
        base_save.assert_called_once()
        self.assertEqual(invoice.status, Invoice.InvoiceStatus.ISSUED)

    @patch("apps.core.models.CoreBaseModel.save")
    def test_genuinely_fully_paid_invoice_is_paid(self, base_save):
        from decimal import Decimal
        from django.utils import timezone
        from apps.finance.models import Invoice

        invoice = Invoice(
            invoice_number="INV-TEST-2",
            status=Invoice.InvoiceStatus.ISSUED,
            issue_date=timezone.now().date(),
            total_amount=Decimal("150.00"),
            amount_paid=Decimal("150.00"),
        )
        invoice.save()
        base_save.assert_called_once()
        self.assertEqual(invoice.status, Invoice.InvoiceStatus.PAID)


class StudentInvoiceUiTests(SimpleTestCase):
    @patch("apps.finance.views.Invoice.objects.filter")
    def test_student_invoice_detail_filters_by_logged_in_owner(self, filter_mock):
        request = staff_request("/finance/student/invoices/")
        request.user = SimpleNamespace(is_authenticated=True, pk="student-user")
        view = StudentInvoiceDetailView()
        view.request = request
        view.get_queryset()
        self.assertIs(
            filter_mock.call_args.kwargs["student__user"],
            request.user,
        )

    def test_student_invoice_links_resolve_to_separate_detail_view(self):
        from uuid import uuid4
        from django.urls import resolve, reverse

        url = reverse("finance:student_invoice_detail", kwargs={"pk": uuid4()})
        self.assertIs(
            resolve(url).func.view_class,
            StudentInvoiceDetailView,
        )

    def test_student_invoice_template_is_available(self):
        from django.template.loader import get_template

        self.assertIsNotNone(get_template("finance/student/invoice_detail.html"))


class PaymentAccountingIdempotencyTests(SimpleTestCase):
    def make_payment(self, invoice, amount="50.00", status=None):
        from decimal import Decimal

        return Payment(
            payment_number="PAY-TEST-1",
            invoice_id=invoice.pk,
            institution_id="school-a",
            amount=Decimal(amount),
            status=status or Payment.PaymentStatus.COMPLETED,
        )

    @patch("apps.core.models.CoreBaseModel.save")
    @patch("apps.finance.models.Invoice.objects.select_for_update")
    def test_new_completed_payment_updates_invoice_once(self, lock_invoice, base_save):
        from decimal import Decimal

        invoice = SimpleNamespace(
            pk="invoice-a",
            amount_paid=Decimal("0.00"),
            total_amount=Decimal("100.00"),
            save=Mock(),
        )
        lock_invoice.return_value.get.return_value = invoice
        payment = self.make_payment(invoice)

        payment.save()

        self.assertEqual(invoice.amount_paid, Decimal("50.00"))
        invoice.save.assert_called_once()
        base_save.assert_called_once()

    @patch("apps.core.models.CoreBaseModel.save")
    @patch("apps.finance.models.Payment.objects.select_for_update")
    @patch("apps.finance.models.Invoice.objects.select_for_update")
    def test_resaving_completed_payment_does_not_double_count(
        self, lock_invoice, lock_payment, base_save
    ):
        from decimal import Decimal
        from uuid import uuid4

        invoice = SimpleNamespace(
            pk="invoice-a",
            amount_paid=Decimal("50.00"),
            total_amount=Decimal("100.00"),
            save=Mock(),
        )
        lock_invoice.return_value.get.return_value = invoice
        lock_payment.return_value.filter.return_value.first.return_value = (
            SimpleNamespace(
                status=Payment.PaymentStatus.COMPLETED,
                invoice_id="invoice-a",
                amount=Decimal("50.00"),
            )
        )
        payment = self.make_payment(invoice)
        payment.pk = uuid4()

        payment.save()

        self.assertEqual(invoice.amount_paid, Decimal("50.00"))
        base_save.assert_called_once()

    @patch("apps.core.models.CoreBaseModel.save")
    @patch("apps.finance.models.Payment.objects.select_for_update")
    @patch("apps.finance.models.Invoice.objects.select_for_update")
    def test_reversing_completed_payment_removes_its_amount(
        self, lock_invoice, lock_payment, base_save
    ):
        from decimal import Decimal
        from uuid import uuid4

        invoice = SimpleNamespace(
            pk="invoice-a",
            amount_paid=Decimal("50.00"),
            total_amount=Decimal("100.00"),
            save=Mock(),
        )
        lock_invoice.return_value.get.return_value = invoice
        lock_payment.return_value.filter.return_value.first.return_value = (
            SimpleNamespace(
                status=Payment.PaymentStatus.COMPLETED,
                invoice_id="invoice-a",
                amount=Decimal("50.00"),
            )
        )
        payment = self.make_payment(
            invoice, status=Payment.PaymentStatus.FAILED
        )
        payment.pk = uuid4()

        payment.save()

        self.assertEqual(invoice.amount_paid, Decimal("0.00"))
        invoice.save.assert_called_once()
        base_save.assert_called_once()

    @patch("apps.core.models.CoreBaseModel.save")
    @patch("apps.finance.models.Invoice.objects.select_for_update")
    def test_completed_payment_cannot_overpay_invoice(self, lock_invoice, base_save):
        from decimal import Decimal
        from django.core.exceptions import ValidationError

        invoice = SimpleNamespace(
            pk="invoice-a",
            amount_paid=Decimal("90.00"),
            total_amount=Decimal("100.00"),
            save=Mock(),
        )
        lock_invoice.return_value.get.return_value = invoice
        payment = self.make_payment(invoice, amount="20.00")

        with self.assertRaises(ValidationError):
            payment.save()

        invoice.save.assert_not_called()
        base_save.assert_not_called()


class FinanceFormIsolationTests(SimpleTestCase):
    def test_invoice_form_uses_student_profile_queryset(self):
        form = InvoiceForm()
        self.assertIs(form.fields["student"].queryset.model, Student)

    def test_payment_form_uses_student_profile_queryset(self):
        form = PaymentForm()
        self.assertIs(form.fields["student"].queryset.model, Student)

    def test_report_generator_is_not_user_selectable(self):
        form = FinancialReportForm()
        self.assertNotIn("generated_by", form.fields)

    def test_related_choices_fail_closed_without_active_school(self):
        for form_class in (InvoiceForm, PaymentForm, FinancialReportForm):
            with self.subTest(form=form_class.__name__):
                form = form_class()
                field_name = (
                    "student" if form_class in (InvoiceForm, PaymentForm)
                    else "academic_session"
                )
                self.assertFalse(form.fields[field_name].queryset.query.where.children == [])
