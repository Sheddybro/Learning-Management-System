from django.urls import path
from . import views

app_name = 'assessment'

urlpatterns = [
    # Exam URLs
    path('exams/', views.ExamListView.as_view(), name='exam_list'),
    path('exams/<int:pk>/', views.ExamDetailView.as_view(), name='exam_detail'),
    path('exams/create/', views.ExamCreateView.as_view(), name='exam_create'),
    path('exams/<int:pk>/update/', views.ExamUpdateView.as_view(), name='exam_update'),
    path('exams/<int:exam_id>/attendance/', views.exam_attendance, name='exam_attendance'),
    path('exams/<int:exam_id>/marks/', views.enter_marks, name='enter_marks'),
    path('grading/', views.grading_overview, name='grading_overview'),
    
    # Assignment URLs
    path('assignments/', views.AssignmentListView.as_view(), name='assignment_list'),
    path('assignments/<int:pk>/', views.AssignmentDetailView.as_view(), name='assignment_detail'),
    path('assignments/create/', views.AssignmentCreateView.as_view(), name='assignment_create'),
    path('assignments/<int:assignment_id>/submit/', views.AssignmentSubmissionView.as_view(), name='assignment_submit'),
    path('assignments/submissions/<int:submission_id>/grade/', views.grade_assignment, name='grade_assignment'),
    
    # Result URLs
    path('results/', views.ResultListView.as_view(), name='result_list'),
    path('results/<int:pk>/', views.ResultDetailView.as_view(), name='result_detail'),
    
    # Report Card URLs
    path('report-cards/', views.ReportCardListView.as_view(), name='reportcard_list'),
    path('report-cards/<int:pk>/', views.ReportCardDetailView.as_view(), name='reportcard_detail'),
    path('results/<int:result_id>/generate-report/', views.generate_report_card, name='generate_report_card'),
    path('report-cards/<int:reportcard_id>/approve/', views.approve_report_card, name='approve_report_card'),
    
    # Dashboard and Analytics
    path('dashboard/', views.assessment_dashboard, name='dashboard'),
    path('analytics/', views.assessment_analytics, name='analytics'),
    
    # Student-specific views
    path('my-marks/', views.StudentMarksView.as_view(), name='student_marks'),
    
    # Question Bank and Question Management
    path('question-banks/', views.QuestionBankListView.as_view(), name='question_bank_list'),
    path('question-banks/create/', views.QuestionBankCreateView.as_view(), name='question_bank_create'),
    path('question-banks/<int:pk>/delete/', views.QuestionBankDeleteView.as_view(), name='question_bank_delete'),
    path('questions/', views.QuestionListView.as_view(), name='question_list'),
    path('questions/create/', views.QuestionCreateView.as_view(), name='question_create'),

    # Exam Composition and Taking
    path('exams/<int:exam_id>/compose/', views.compose_exam, name='compose_exam'),
    path('exams/<int:exam_id>/take/', views.take_exam, name='take_exam'),
    path('exams/<int:exam_id>/grade-answers/', views.grade_exam_answers, name='grade_exam_answers'),
    path('exams/<int:exam_id>/auto-calculate/', views.auto_calculate_marks, name='auto_calculate_marks'),

    # AI Question Generation
    path('question-banks/<int:question_bank_id>/generate-ai/', views.generate_ai_questions, name='generate_ai_questions'),
    path('ai-generation-history/', views.ai_generation_history, name='ai_generation_history'),

    # Quiz functionality - Enhanced with Clue System Features
    path('quizzes/', views.quiz_bank_list, name='quiz_bank_list'),
    path('quizzes/<int:quiz_bank_id>/', views.quiz_bank_detail, name='quiz_bank_detail'),
    path('quizzes/<int:quiz_bank_id>/take/', views.take_quiz, name='take_quiz'),
    path('quiz-attempts/<int:attempt_id>/result/', views.quiz_result, name='quiz_result'),
    path('my-progress/', views.student_progress, name='student_progress'),

    # Quiz Marking and Grading - Enhanced from Clue System
    path('quiz-marking/', views.quiz_marking_list, name='quiz_marking_list'),
    path('quiz-marking/<int:attempt_id>/', views.quiz_marking_detail, name='quiz_marking_detail'),
    path('quiz-attempts/', views.quiz_attempt_list, name='quiz_attempt_list'),

    # Quiz Bank Management
    path('question-banks/', views.QuestionBankListView.as_view(), name='question_bank_list'),
    path('question-banks/create/', views.QuestionBankCreateView.as_view(), name='question_bank_create'),
    path('questions/', views.QuestionListView.as_view(), name='question_list'),
    path('questions/create/', views.QuestionCreateView.as_view(), name='question_create'),

    # Automatic Quiz Score Integration
    # path('quiz-attempts/<int:attempt_id>/update-grades/', views.update_course_grades_from_quiz, name='update_course_grades_from_quiz'),

    # Bulk Score Entry (from Clue System)
    path('scores/', views.add_score, name='add_score'),
    path('scores/<int:course_id>/', views.add_score_for, name='add_score_for'),

    # Additional Results Views (from Clue System Integration)
    path('results/assessment/', views.assessment_results, name='assessment_results'),
    path('results/grade/', views.grade_results, name='grade_results'),

    # PDF Generation Views (Enhanced from Clue System)
    path('results/<int:course_id>/pdf/', views.result_sheet_pdf_view, name='result_sheet_pdf'),
    path('registration/<int:course_id>/pdf/', views.course_registration_pdf_view, name='course_registration_pdf'),

    # Additional Quiz Views (Enhanced from Clue System)
    path('quiz-attempts/', views.quiz_attempt_list, name='quiz_attempt_list'),

    # GPA Calculator (utility endpoints)
    # path('gpa-calculator/', views.gpa_calculator, name='gpa_calculator'),

    # API endpoints
    path('api/class/<int:class_id>/subjects/', views.get_class_subjects, name='api_class_subjects'),
    path('api/student/<int:student_id>/progress/', views.get_student_progress, name='api_student_progress'),
]
