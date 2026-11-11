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
