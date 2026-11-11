# apps/users/urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from . import views

app_name = 'users'

urlpatterns = [
    # =========================================================================
    # PUBLIC/GUEST ROUTES
    # =========================================================================
    path('', views.guest_home, name='guest_home'),
    path('application-portal/', views.application_portal, name='application_portal'),
    path('apply/student/', views.StudentApplicationView.as_view(), name='student_application'),
    path('apply/staff/', views.StaffApplicationView.as_view(), name='staff_application'),
    path('application-submitted/', views.application_submitted, name='application_submitted'),
    
    # =========================================================================
    # AUTHENTICATION ROUTES
    # =========================================================================
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    
    # Custom password retrieval view (sends password directly)
    path('password-reset/', views.custom_password_retrieval, name='password_reset'),
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'
         ), 
         name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html',
             success_url='/users/password-reset-complete/'
         ), 
         name='password_reset_confirm'),
    
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    
    # =========================================================================
    # AUTHENTICATED USER ROUTES
    # =========================================================================
    path('dashboard/', views.user_dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/picture/upload/', views.upload_profile_picture, name='upload_profile_picture'),
    path('profile/password/', views.password_change_view, name='password_change'),
    
    # Parent-Student Relationships
    path('relationships/', views.parent_student_relationships, name='parent_student_relationships'),
    
    # =========================================================================
    # ADMIN MANAGEMENT ROUTES
    # =========================================================================
    path('admin/users/', views.user_list, name='user_list'),
    path('admin/users/create/', views.user_create, name='user_create'),
    path('admin/users/<uuid:user_id>/', views.user_detail, name='user_detail'),
    path('admin/users/<uuid:user_id>/edit/', views.user_update, name='user_update'),
    path('admin/users/<uuid:user_id>/roles/', views.user_roles_manage, name='user_roles_manage'),
    path('admin/users/<uuid:user_id>/roles/set-primary/', views.user_role_set_primary, name='user_role_set_primary'),
    path('admin/users/<uuid:user_id>/roles/set-secondary/', views.user_role_set_secondary, name='user_role_set_secondary'),
    path('admin/users/<uuid:user_id>/roles/remove/', views.user_role_remove, name='user_role_remove'),
    path('admin/users/<uuid:user_id>/toggle-status/', views.user_toggle_status, name='user_toggle_status'),
    path('admin/users/<uuid:user_id>/delete/', views.user_delete, name='user_delete'),
    
    # Staff Management
    path('admin/staff/', views.staff_list, name='staff_list'),
    path('admin/staff/<uuid:user_id>/', views.staff_detail, name='staff_detail'),

    # Role Management
    path('admin/roles/', views.role_list, name='role_list'),
    path('admin/roles/create/', views.role_create, name='role_create'),
    path('admin/roles/<uuid:role_id>/delete/', views.role_delete, name='role_delete'),
    
    # Application Management
    path('admin/applications/pending/', views.pending_applications, name='pending_applications'),
    path('admin/applications/<uuid:application_id>/approve/<str:application_type>/',
         views.approve_application, name='approve_application'),
    path('admin/applications/<uuid:application_id>/reject/<str:application_type>/',
         views.reject_application, name='reject_application'),
    path('admin/applications/<uuid:application_id>/schedule-interview/',
         views.schedule_interview, name='schedule_interview'),
    path('admin/applications/<uuid:application_id>/mark-under-review/<str:application_type>/',
         views.mark_application_under_review, name='mark_application_under_review'),
    path('admin/applications/export/<str:application_type>/',
         views.export_applications, name='export_applications'),
    path('admin/applications/counts/', views.get_application_counts, name='get_application_counts'),
    
    # Application Detail Views
    path('admin/applications/student/<uuid:application_id>/', views.student_application_detail, name='student_application_detail'),
    path('admin/applications/staff/<uuid:application_id>/', views.staff_application_detail, name='staff_application_detail'),

    # Bulk Operations
    path('admin/users/bulk-action/', views.user_bulk_action, name='user_bulk_action'),
    path('admin/users/bulk-import/', views.user_bulk_import, name='user_bulk_import'),
    path('admin/users/bulk-import/sample/', views.download_bulk_user_sample, name='download_bulk_user_sample'),

    # System Configuration
    path('admin/test-email/', views.test_email_configuration, name='test_email_configuration'),
    
    # Parent-Student Relationship Management (Admin)
    path('admin/relationships/create/',
         views.parent_student_relationship_create,
         name='parent_student_relationship_create'),

    # Parent Portal URLs
    path('parent/dashboard/', views.parent_dashboard, name='parent_dashboard'),
    path('parent/child/<uuid:child_id>/records/', views.child_academic_records, name='child_records'),
    path('parent/child/<uuid:child_id>/attendance/', views.child_attendance, name='child_attendance'),
    path('parent/child/<uuid:child_id>/fees/', views.child_fee_status, name='child_fees'),
    path('parent/message-teacher/', views.message_teacher, name='message_teacher'),

    # Teacher Portal URLs
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/classes/', views.teacher_classes, name='teacher_classes'),
    path('teacher/class/<uuid:class_id>/attendance/', views.teacher_class_attendance, name='teacher_class_attendance'),
    path('teacher/class/<uuid:class_id>/materials/', views.teacher_class_materials, name='teacher_class_materials'),
    path('teacher/materials/upload/', views.teacher_material_upload, name='teacher_material_upload'),
    path('teacher/students/', views.teacher_students, name='teacher_students'),
    path('teacher/student/<uuid:student_id>/progress/', views.teacher_student_progress, name='teacher_student_progress'),
    path('teacher/assessment/', views.teacher_assessment, name='teacher_assessment'),
    path('teacher/timetable/', views.teacher_timetable, name='teacher_timetable'),
    path('teacher/communication/', views.teacher_communication, name='teacher_communication'),

    # User Export
    path('admin/users/export/', views.export_users, name='export_users'),

    # Login History
    path('admin/login-history/', views.login_history, name='login_history'),

    # Institution Transfer Requests
    path('transfer-request/', views.institution_transfer_request_form, name='transfer_request_form'),
    path('transfer-request/student/', views.institution_transfer_request_form, {'transfer_type': 'student'}, name='student_transfer_request'),
    path('transfer-request/staff/', views.institution_transfer_request_form, {'transfer_type': 'staff'}, name='staff_transfer_request'),
    path('transfer-requests/', views.institution_transfer_requests_list, name='user_transfer_requests'),
    path('transfer-request/<uuid:request_id>/', views.institution_transfer_request_detail, name='transfer_request_detail'),

    # Admin Institution Transfer Management
    path('admin/transfer-requests/', views.admin_transfer_requests_list, name='admin_transfer_requests'),
    path('admin/transfer-request/<uuid:request_id>/approve/', views.admin_approve_transfer_request, name='admin_approve_transfer_request'),
    path('admin/transfer-request/<uuid:request_id>/reject/', views.admin_reject_transfer_request, name='admin_reject_transfer_request'),
    path('admin/transfer-request/<uuid:request_id>/complete/', views.admin_complete_transfer_request, name='admin_complete_transfer_request'),
]
