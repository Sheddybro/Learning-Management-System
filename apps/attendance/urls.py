# apps/attendance/urls.py

from django.urls import path, include
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'attendance'

urlpatterns = [
    # ==================== DASHBOARD & HOME ====================
    path('', views.attendance_dashboard, name='dashboard'),
    
    # ==================== CONFIGURATION URLs ====================
    path('config/', 
         login_required(views.AttendanceConfigUpdateView.as_view()), 
         name='config'),
    
    # ==================== ATTENDANCE SESSION URLs ====================
    path('sessions/', 
         views.AttendanceSessionListView.as_view(), 
         name='session_list'),
    path('sessions/create/', 
         views.AttendanceSessionCreateView.as_view(), 
         name='session_create'),
    path('sessions/<int:pk>/edit/', 
         views.AttendanceSessionUpdateView.as_view(), 
         name='session_edit'),
    
    # ==================== DAILY ATTENDANCE URLs ====================
    path('daily/',
         views.DailyAttendanceListView.as_view(),
         name='daily_list'),
    path('daily/create/',
         views.DailyAttendanceCreateView.as_view(),
         name='daily_create'),
    path('daily/<int:pk>/edit/',
         views.DailyAttendanceUpdateView.as_view(),
         name='daily_edit'),
    path('daily/<uuid:pk>/delete/',
         views.DailyAttendanceDeleteView.as_view(),
         name='daily_delete'),
    
    # ==================== BULK ATTENDANCE URLs ====================
    path('bulk/', 
         views.BulkAttendanceView.as_view(), 
         name='bulk_class_select'),
    path('bulk/<int:class_id>/', 
         views.BulkAttendanceView.as_view(), 
         name='bulk_mark'),
    
    # ==================== STUDENT ATTENDANCE URLs ====================
    path('student/', 
         views.StudentAttendanceView.as_view(), 
         name='student_my_attendance'),
    path('student/<int:pk>/', 
         views.StudentAttendanceView.as_view(), 
         name='student_attendance'),
    
    # ==================== PERIOD ATTENDANCE URLs ====================
    path('period/', 
         views.PeriodAttendanceListView.as_view(), 
         name='period_list'),
    
    # ==================== LEAVE MANAGEMENT URLs ====================
    path('leaves/',
         views.LeaveApplicationListView.as_view(),
         name='leave_list'),
    path('leaves/create/',
         views.LeaveApplicationCreateView.as_view(),
         name='leave_create'),
    path('leaves/<int:pk>/review/',
         views.LeaveApplicationUpdateView.as_view(),
         name='leave_review'),
    path('leaves/<int:pk>/delete/',
         views.LeaveApplicationDeleteView.as_view(),
         name='leave_delete'),
    
    # ==================== REPORTS & SUMMARY URLs ====================
    path('summary/', 
         views.AttendanceSummaryView.as_view(), 
         name='summary'),
    path('export/', 
         views.export_attendance_report, 
         name='export_report'),
    
    # ==================== BEHAVIOR/DISCIPLINE URLs ====================
    path('behavior/',
         views.BehaviorRecordListView.as_view(),
         name='behavior_list'),
    path('behavior/create/',
         views.BehaviorRecordCreateView.as_view(),
         name='behavior_create'),
    path('behavior/<int:pk>/edit/',
         views.BehaviorRecordUpdateView.as_view(),
         name='behavior_edit'),
    path('behavior/<int:pk>/delete/',
         views.BehaviorRecordDeleteView.as_view(),
         name='behavior_delete'),
    path('behavior/student/',
         views.StudentBehaviorView.as_view(),
         name='student_behavior'),
    path('behavior/student/<int:pk>/',
         views.StudentBehaviorView.as_view(),
         name='student_behavior_detail'),

    # ==================== API ENDPOINTS ====================
    path('api/student/<int:student_id>/attendance/',
         views.api_student_attendance,
         name='api_student_attendance'),
    path('api/mark-attendance/',
         views.api_mark_attendance,
         name='api_mark_attendance'),
]

# Error handlers
handler500 = 'apps.attendance.views.attendance_error_handler'
