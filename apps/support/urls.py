from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    path('', views.support_home, name='home'),

    # Support Staff Dashboard
    path('dashboard/', views.support_staff_dashboard, name='dashboard'),

    # ===== STUDENT SUPPORT TEAM COLLABORATION =====
    # Case Management
    path('cases/', views.SupportCaseListView.as_view(), name='case_list'),
    path('cases/create/', views.SupportCaseCreateView.as_view(), name='case_create'),
    path('cases/student/<int:student_id>/create/', views.SupportCaseCreateView.as_view(), name='case_create_for_student'),
    path('cases/<uuid:pk>/', views.SupportCaseDetailView.as_view(), name='case_detail'),
    path('cases/<uuid:pk>/edit/', views.SupportCaseUpdateView.as_view(), name='case_edit'),
    path('cases/<uuid:pk>/delete/', views.SupportCaseDeleteView.as_view(), name='case_delete'),

    # Case Collaboration (AJAX)
    path('cases/<uuid:pk>/add-update/', views.add_case_update, name='case_add_update'),
    path('cases/<uuid:pk>/add-attachment/', views.add_case_attachment, name='case_add_attachment'),
    path('cases/<uuid:pk>/add-participant/', views.add_case_participant, name='case_add_participant'),
    path('cases/<uuid:pk>/remove-participant/<int:participant_pk>/', views.remove_case_participant, name='case_remove_participant'),
    path('cases/<uuid:pk>/update-status/', views.update_case_status, name='case_update_status'),
    path('cases/<uuid:pk>/escalate/', views.escalate_case, name='case_escalate'),

    # Bulk Case Actions
    path('cases/bulk-actions/', views.bulk_case_actions, name='case_bulk_actions'),

    # ===== EXISTING SUPPORT FEATURES =====
    # Ticket Management (Support Staff)
    path('tickets/', views.ContactSubmissionListView.as_view(), name='ticket_list'),
    path('tickets/<int:pk>/', views.ContactSubmissionDetailView.as_view(), name='ticket_detail'),
    path('tickets/<int:pk>/update/', views.ContactSubmissionUpdateView.as_view(), name='ticket_update'),

    # Help Center & Knowledge Base (Public)
    path('articles/', views.HelpCenterArticleListView.as_view(), name='article_list'),
    path('articles/category/<slug:category_slug>/', views.HelpCenterArticleListView.as_view(), name='article_list_by_category'),
    path('articles/<slug:slug>/', views.HelpCenterArticleDetailView.as_view(), name='article_detail'),

    # Help Center Management (Support Staff)
    path('admin/articles/create/', views.HelpCenterArticleCreateView.as_view(), name='article_create'),
    path('admin/articles/<int:pk>/update/', views.HelpCenterArticleUpdateView.as_view(), name='article_update'),
    path('admin/articles/<int:pk>/delete/', views.HelpCenterArticleDeleteView.as_view(), name='article_delete'),

    # Resources (Public)
    path('resources/', views.ResourceListView.as_view(), name='resource_list'),
    path('resources/<slug:slug>/', views.ResourceDetailView.as_view(), name='resource_detail'),

    # Resource Management (Support Staff)
    path('admin/resources/create/', views.ResourceCreateView.as_view(), name='resource_create'),
    path('admin/resources/<int:pk>/update/', views.ResourceUpdateView.as_view(), name='resource_update'),
    path('admin/resources/<int:pk>/delete/', views.ResourceDeleteView.as_view(), name='resource_delete'),

    # FAQ (Public)
    path('faq/', views.FAQListView.as_view(), name='faq_list'),

    # FAQ Management (Support Staff)
    path('admin/faq/create/', views.FAQCreateView.as_view(), name='faq_create'),
    path('admin/faq/<int:pk>/update/', views.FAQUpdateView.as_view(), name='faq_update'),
    path('admin/faq/<int:pk>/delete/', views.FAQDeleteView.as_view(), name='faq_delete'),

    # Contact Support
    path('contact/', views.ContactSupportView.as_view(), name='contact'),
    path('contact/success/', views.contact_success_view, name='contact_success'),

    # System Monitoring (Support Staff)
    path('monitoring/kpi/', views.system_kpi_monitoring, name='kpi_monitoring'),
    path('monitoring/audit/', views.audit_log_monitoring, name='audit_monitoring'),

    # Security Management (Support Staff)
    path('security/login-history/', views.login_history_monitoring, name='login_history'),
    path('security/user-sessions/', views.user_session_monitoring, name='user_sessions'),

    # Legal Documents
    path('privacy-policy/', views.privacy_policy_view, name='privacy_policy'),
    path('terms-of-service/', views.terms_of_service_view, name='terms_of_service'),
    path('data-protection/', views.data_protection_view, name='data_protection'),
    path('cookie-policy/', views.cookie_policy_view, name='cookie_policy'),
    path('accessibility/', views.accessibility_statement_view, name='accessibility_statement'),
    path('legal-documents/', views.legal_documents_list, name='legal_documents_list'),
    path('legal/<str:document_type>/', views.LegalDocumentDetailView.as_view(), name='legal_document_detail'),
]
