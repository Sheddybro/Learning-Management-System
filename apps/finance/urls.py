# apps/finance/urls.py

from django.urls import path, include
from . import views

app_name = "finance"

urlpatterns = [
    # Invoice URLs
    path("invoices/", views.InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/create/", views.InvoiceCreateView.as_view(), name="invoice_create"),
    path(
        "invoices/<uuid:pk>/", views.InvoiceDetailView.as_view(), name="invoice_detail"
    ),
    path(
        "invoices/<uuid:pk>/update/",
        views.InvoiceUpdateView.as_view(),
        name="invoice_update",
    ),
    path(
        "invoices/<uuid:pk>/delete/",
        views.InvoiceDeleteView.as_view(),
        name="invoice_delete",
    ),
    # Payment URLs
    path(
        "invoices/<uuid:invoice_pk>/pay/",
        views.PaymentCreateView.as_view(),
        name="payment_create_invoice",
    ),
    path("payments/create/", views.PaymentCreateView.as_view(), name="payment_create"),
    path(
        "invoices/<uuid:invoice_pk>/gateway/",
        views.PaymentGatewayView.as_view(),
        name="payment_gateway",
    ),
    path(
        "payments/<uuid:pk>/success/",
        views.PaymentSuccessView.as_view(),
        name="payment_success",
    ),
    path(
        "payments/<uuid:pk>/cancel/",
        views.PaymentCancelView.as_view(),
        name="payment_cancel",
    ),
    path(
        "payments/<uuid:pk>/receipt/",
        views.ReceiptDownloadView.as_view(),
        name="receipt_download",
    ),
    path("payments/", views.PaymentListView.as_view(), name="payment_list"),
    path(
        "payments/<uuid:pk>/", views.PaymentDetailView.as_view(), name="payment_detail"
    ),
    path(
        "payments/<uuid:pk>/update/",
        views.PaymentUpdateView.as_view(),
        name="payment_update",
    ),
    path(
        "payments/<uuid:pk>/delete/",
        views.PaymentDeleteView.as_view(),
        name="payment_delete",
    ),
    # Webhook URLs (CSRF exempt)
    path(
        "webhooks/paystack/",
        views.PaystackWebhookView.as_view(),
        name="paystack_webhook",
    ),
    path(
        "webhooks/flutterwave/",
        views.FlutterwaveWebhookView.as_view(),
        name="flutterwave_webhook",
    ),
    # Fee Structure URLs
    path(
        "fee-structures/",
        views.FeeStructureListView.as_view(),
        name="feestructure_list",
    ),
    path(
        "fee-structures/create/",
        views.FeeStructureCreateView.as_view(),
        name="feestructure_create",
    ),
    path(
        "fee-structures/<uuid:pk>/",
        views.FeeStructureDetailView.as_view(),
        name="feestructure_detail",
    ),
    path(
        "fee-structures/<uuid:pk>/update/",
        views.FeeStructureUpdateView.as_view(),
        name="feestructure_update",
    ),
    path(
        "fee-structures/<uuid:pk>/delete/",
        views.FeeStructureDeleteView.as_view(),
        name="feestructure_delete",
    ),
    # Fee Discount URLs
    path(
        "fee-discounts/", views.FeeDiscountListView.as_view(), name="feediscount_list"
    ),
    path(
        "fee-discounts/create/",
        views.FeeDiscountCreateView.as_view(),
        name="feediscount_create",
    ),
    path(
        "fee-discounts/<uuid:pk>/",
        views.FeeDiscountDetailView.as_view(),
        name="feediscount_detail",
    ),
    path(
        "fee-discounts/<uuid:pk>/update/",
        views.FeeDiscountUpdateView.as_view(),
        name="feediscount_update",
    ),
    path(
        "fee-discounts/<uuid:pk>/delete/",
        views.FeeDiscountDeleteView.as_view(),
        name="feediscount_delete",
    ),
    # Expense URLs (staff only)
    path("expenses/", views.ExpenseListView.as_view(), name="expense_list"),
    path("expenses/create/", views.ExpenseCreateView.as_view(), name="expense_create"),
    path(
        "expenses/<uuid:pk>/", views.ExpenseDetailView.as_view(), name="expense_detail"
    ),
    path(
        "expenses/<uuid:pk>/update/",
        views.ExpenseUpdateView.as_view(),
        name="expense_update",
    ),
    path(
        "expenses/<uuid:pk>/delete/",
        views.ExpenseDeleteView.as_view(),
        name="expense_delete",
    ),
    # Financial Report URLs (staff only)
    path(
        "reports/", views.FinancialReportListView.as_view(), name="financialreport_list"
    ),
    path(
        "reports/create/",
        views.FinancialReportCreateView.as_view(),
        name="financialreport_create",
    ),
    path(
        "reports/<uuid:pk>/",
        views.FinancialReportDetailView.as_view(),
        name="financialreport_detail",
    ),
    path(
        "reports/<uuid:pk>/update/",
        views.FinancialReportUpdateView.as_view(),
        name="financialreport_update",
    ),
    path(
        "reports/<uuid:pk>/delete/",
        views.FinancialReportDeleteView.as_view(),
        name="financialreport_delete",
    ),
    # Dashboard
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    # Student Views
    path(
        "student/invoices/",
        views.StudentInvoiceListView.as_view(),
        name="student_invoices",
    ),
    # API Endpoints
    path(
        "api/invoices/generate/",
        views.GenerateInvoiceAPIView.as_view(),
        name="api_generate_invoices",
    ),
    path(
        "api/students/<uuid:student_id>/outstanding-fees/",
        views.GetStudentOutstandingFeesAPIView.as_view(),
        name="api_student_outstanding_fees",
    ),
    path(
        "api/expenses/summary/",
        views.GetExpenseSummaryAPIView.as_view(),
        name="api_expense_summary",
    ),
    path(
        "api/invoices/<uuid:pk>/details/",
        views.GetInvoiceDetailsAPIView.as_view(),
        name="api_invoice_details",
    ),
    path(
        "api/reports/<uuid:pk>/publish/",
        views.PublishFinancialReportAPIView.as_view(),
        name="api_publish_report",
    ),
    path("api/invoices/", views.APIInvoiceListView.as_view(), name="api_invoice_list"),
    path(
        "api/payments/<uuid:payment_id>/status/",
        views.APIPaymentStatusView.as_view(),
        name="api_payment_status",
    ),
]
