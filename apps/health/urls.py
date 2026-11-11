from django.urls import path
from . import views

app_name = 'health'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.HealthDashboardView.as_view(), name='dashboard'),

    # Health Records
    path('records/', views.HealthRecordListView.as_view(), name='record_list'),
    path('records/<uuid:pk>/', views.HealthRecordDetailView.as_view(), name='record_detail'),
    path('records/create/', views.HealthRecordCreateView.as_view(), name='record_create'),
    path('records/<uuid:pk>/update/', views.HealthRecordUpdateView.as_view(), name='record_update'),

    # Medical Appointments
    path('appointments/', views.MedicalAppointmentListView.as_view(), name='appointment_list'),
    path('appointments/<uuid:pk>/', views.MedicalAppointmentDetailView.as_view(), name='appointment_detail'),
    path('appointments/create/', views.MedicalAppointmentCreateView.as_view(), name='appointment_create'),
    path('appointments/<uuid:pk>/update/', views.MedicalAppointmentUpdateView.as_view(), name='appointment_update'),

    # Medications
    path('medications/', views.MedicationListView.as_view(), name='medication_list'),
    path('medications/<uuid:pk>/', views.MedicationDetailView.as_view(), name='medication_detail'),
    path('medications/create/', views.MedicationCreateView.as_view(), name='medication_create'),
    path('medications/<uuid:pk>/update/', views.MedicationUpdateView.as_view(), name='medication_update'),

    # Health Screenings
    path('screenings/', views.HealthScreeningListView.as_view(), name='screening_list'),
    path('screenings/<uuid:pk>/', views.HealthScreeningDetailView.as_view(), name='screening_detail'),
    path('screenings/create/', views.HealthScreeningCreateView.as_view(), name='screening_create'),
    path('screenings/<uuid:pk>/update/', views.HealthScreeningUpdateView.as_view(), name='screening_update'),

    # Emergency Contacts
    path('contacts/', views.EmergencyContactListView.as_view(), name='contact_list'),
    path('contacts/<uuid:pk>/', views.EmergencyContactDetailView.as_view(), name='contact_detail'),
    path('contacts/create/', views.EmergencyContactCreateView.as_view(), name='contact_create'),
    path('contacts/<uuid:pk>/update/', views.EmergencyContactUpdateView.as_view(), name='contact_update'),

    # Student Health View
    path('student/', views.StudentHealthView.as_view(), name='student_health'),

    # Reports
    path('reports/', views.HealthReportsView.as_view(), name='reports'),

    # API/AJAX URLs
    path('api/student-health/<uuid:student_id>/', views.GetStudentHealthRecordView.as_view(), name='api_student_health'),
    path('api/update-medication-status/', views.UpdateMedicationStatusView.as_view(), name='api_update_medication'),
]
