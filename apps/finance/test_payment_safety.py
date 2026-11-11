"""Regression checks for finance endpoints that must fail closed.

Run with: python manage.py test apps.finance.test_payment_safety
These tests use request factories and mocks, not production school records.
"""
from types import SimpleNamespace
from unittest.mock import patch

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
