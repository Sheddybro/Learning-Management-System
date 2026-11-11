# apps/academics/urls.py

from django.urls import path, include
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'academics'

# URL patterns for different academic entities
urlpatterns = [
    # Dashboard
    path('dashboard/', views.AcademicsDashboardView.as_view(), name='dashboard'),

    # Student Dashboard and Features
    path('student/dashboard/', views.StudentDashboardView.as_view(), name='student_dashboard'),
    path('student/timetable/', views.StudentTimetableView.as_view(), name='student_timetable'),
    path('student/materials/', views.StudentMaterialsView.as_view(), name='student_materials'),
    path('student/performance/', views.StudentPerformanceView.as_view(), name='student_performance'),
    path('student/attendance/', views.StudentAttendanceView.as_view(), name='student_attendance'),

    # Student Academic Records
    path('my-records/', views.StudentAcademicRecordsView.as_view(), name='student_academic_records'),

    # Academic Session URLs
    path('sessions/', views.AcademicSessionListView.as_view(), name='session_list'),
    path('sessions/create/', views.AcademicSessionCreateView.as_view(), name='session_create'),
    path('sessions/<uuid:pk>/update/', views.AcademicSessionUpdateView.as_view(), name='session_update'),
    path('sessions/<uuid:pk>/delete/', views.AcademicSessionDeleteView.as_view(), name='session_delete'),
    path('sessions/<uuid:pk>/', views.AcademicSessionDetailView.as_view(), name='session_detail'),

    # Department URLs
    path('departments/', views.DepartmentListView.as_view(), name='department_list'),
    path('departments/<uuid:pk>/', views.DepartmentDetailView.as_view(), name='department_detail'),
    path('departments/create/', views.DepartmentCreateView.as_view(), name='department_create'),
    path('departments/<uuid:pk>/update/', views.DepartmentUpdateView.as_view(), name='department_update'),

    # Subject URLs
    path('subjects/', views.SubjectListView.as_view(), name='subject_list'),
    path('subjects/<uuid:pk>/', views.SubjectDetailView.as_view(), name='subject_detail'),
    path('subjects/create/', views.SubjectCreateView.as_view(), name='subject_create'),
    path('subjects/<uuid:pk>/update/', views.SubjectUpdateView.as_view(), name='subject_update'),

    # Class URLs
    path('classes/', views.ClassListView.as_view(), name='class_list'),
    path('classes/<uuid:pk>/', views.ClassDetailView.as_view(), name='class_detail'),
    path('classes/create/', views.ClassCreateView.as_view(), name='class_create'),
    path('classes/<uuid:pk>/update/', views.ClassUpdateView.as_view(), name='class_update'),

    # Student URLs
    path('students/', views.StudentListView.as_view(), name='student_list'),
    path('students/<uuid:pk>/', views.StudentDetailView.as_view(), name='student_detail'),
    path('students/create/', views.StudentCreateView.as_view(), name='student_create'),
    path('students/<uuid:pk>/update/', views.StudentUpdateView.as_view(), name='student_update'),

    # Teacher URLs
    path('teachers/', views.TeacherListView.as_view(), name='teacher_list'),
    path('teachers/<uuid:pk>/', views.TeacherDetailView.as_view(), name='teacher_detail'),
    path('teachers/<uuid:pk>/contact/', views.ContactTeacherView.as_view(), name='contact_teacher'),
    path('teachers/create/', views.TeacherCreateView.as_view(), name='teacher_create'),
    path('teachers/<uuid:pk>/update/', views.TeacherUpdateView.as_view(), name='teacher_update'),

    # Enrollment URLs
    path('enrollments/', views.EnrollmentListView.as_view(), name='enrollment_list'),
    path('enrollments/create/', views.EnrollmentCreateView.as_view(), name='enrollment_create'),
    path('enrollments/<uuid:pk>/update/', views.EnrollmentUpdateView.as_view(), name='enrollment_update'),
    path('enrollments/bulk/', views.BulkEnrollmentView.as_view(), name='bulk_enrollment'),

    # Timetable URLs
    path('timetable/', views.TimetableListView.as_view(), name='timetable_list'),
    path('timetable/create/', views.TimetableCreateView.as_view(), name='timetable_create'),
    path('timetable/<uuid:pk>/', views.TimetableDetailView.as_view(), name='timetable_detail'),
    path('timetable/<uuid:pk>/update/', views.TimetableUpdateView.as_view(), name='timetable_update'),
    path('timetable/student/', views.StudentTimetableView.as_view(), name='student_timetable'),
    path('timetable/teacher/', views.TeacherTimetableView.as_view(), name='teacher_timetable'),

    # Class Material URLs
    path('materials/', views.ClassMaterialListView.as_view(), name='material_list'),
    path('materials/<uuid:pk>/', views.ClassMaterialDetailView.as_view(), name='material_detail'),
    path('materials/create/', views.ClassMaterialCreateView.as_view(), name='material_create'),
    path('materials/<uuid:pk>/update/', views.ClassMaterialUpdateView.as_view(), name='material_update'),

    # School Policy URLs
    path('policies/', views.SchoolPolicyListView.as_view(), name='policy_list'),
    path('policies/<uuid:pk>/', views.SchoolPolicyDetailView.as_view(), name='policy_detail'),
    path('policies/create/', views.SchoolPolicyCreateView.as_view(), name='policy_create'),
    path('policies/<uuid:pk>/update/', views.SchoolPolicyUpdateView.as_view(), name='policy_update'),

    # Holiday URLs
    path('holidays/', views.HolidayListView.as_view(), name='holiday_list'),
    path('holidays/<uuid:pk>/', views.HolidayDetailView.as_view(), name='holiday_detail'),
    path('holidays/create/', views.HolidayCreateView.as_view(), name='holiday_create'),
    path('holidays/<uuid:pk>/update/', views.HolidayUpdateView.as_view(), name='holiday_update'),
    path('holidays/<uuid:pk>/delete/', views.HolidayDeleteView.as_view(), name='holiday_delete'),

    # Reports URLs
    path('reports/student/<uuid:student_id>/', views.StudentProgressReportView.as_view(), name='student_report'),
    path('reports/class/<uuid:class_id>/', views.ClassReportView.as_view(), name='class_report'),
    path('reports/enrollment-dashboard/', views.EnrollmentReportsDashboardView.as_view(), name='enrollment_reports_dashboard'),

    # Calendar
    path('calendar/', views.AcademicCalendarView.as_view(), name='academic_calendar'),

# API/AJAX URLs
    path('api/classes-by-grade/', views.GetClassesByGradeView.as_view(), name='api_classes_by_grade'),
    path('api/class-info/', views.GetClassInfoView.as_view(), name='api_class_info'),
    path('api/timetable-by-class/<uuid:class_id>/', views.GetTimetableByClassView.as_view(), name='api_timetable_by_class'),

    # Enrollment API URLs
    path('api/bulk-update-enrollments/', views.BulkUpdateEnrollmentsView.as_view(), name='api_bulk_update_enrollments'),
    path('api/transfer-student/', views.TransferStudentView.as_view(), name='api_transfer_student'),
    path('api/withdraw-student/', views.WithdrawStudentView.as_view(), name='api_withdraw_student'),
    path('api/export-enrollments/', views.ExportEnrollmentsView.as_view(), name='api_export_enrollments'),

    # Department Head URLs
    path('department-head/dashboard/', views.DepartmentHeadDashboardView.as_view(), name='department_head_dashboard'),
    path('department-head/teachers/', views.DepartmentTeachersView.as_view(), name='department_teachers'),
    path('department-head/students/', views.DepartmentStudentsView.as_view(), name='department_students'),
    path('department-head/subjects/', views.DepartmentSubjectsView.as_view(), name='department_subjects'),
    path('department-head/budget/', views.DepartmentBudgetView.as_view(), name='department_budget'),
    path('department-head/reports/', views.DepartmentReportsView.as_view(), name='department_reports'),

    # Counselor URLs
    path('counselor/dashboard/', views.CounselorDashboardView.as_view(), name='counselor_dashboard'),
    path('counselor/sessions/', views.CounselingSessionsView.as_view(), name='counselor_sessions'),
    path('counselor/referrals/', views.CounselingReferralsView.as_view(), name='counselor_referrals'),
    path('counselor/career-guidance/', views.CareerGuidanceView.as_view(), name='counselor_career_guidance'),
    path('counselor/students/', views.CounselorStudentsView.as_view(), name='counselor_students'),
    path('counselor/behavior-records/', views.BehaviorRecordsView.as_view(), name='counselor_behavior_records'),
    path('counselor/academic-warnings/', views.AcademicWarningsView.as_view(), name='counselor_academic_warnings'),

    # Academic Planning Committee URLs
    path('committee/dashboard/', views.CommitteeDashboardView.as_view(), name='committee_dashboard'),
    path('committee/meetings/', views.CommitteeMeetingsView.as_view(), name='committee_meetings'),

    # Grade Level URLs for School Admins
    path('grade-levels/', views.GradeLevelListView.as_view(), name='grade_level_list'),
    path('grade-levels/create/', views.GradeLevelCreateView.as_view(), name='grade_level_create'),
    path('grade-levels/<uuid:pk>/', views.GradeLevelDetailView.as_view(), name='grade_level_detail'),
    path('grade-levels/<uuid:pk>/update/', views.GradeLevelUpdateView.as_view(), name='grade_level_update'),

    # Subject Assignment URLs
    path('subject-assignments/', views.SubjectAssignmentListView.as_view(), name='subject_assignment_list'),
    path('subject-assignment/', views.SubjectAssignmentCreateView.as_view(), name='subject_assignment'),
    path('subject-assignments/create/', views.SubjectAssignmentCreateView.as_view(), name='subject_assignment_create'),
    path('subject-assignments/<uuid:pk>/update/', views.SubjectAssignmentUpdateView.as_view(), name='subject_assignment_update'),
    path('subject-assignments/<uuid:pk>/delete/', views.SubjectAssignmentDeleteView.as_view(), name='subject_assignment_delete'),
]
