# apps/attendance/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import (
    AttendanceConfig, AttendanceSession, DailyAttendance, PeriodAttendance,
    LeaveType, LeaveApplication, AttendanceSummary, BulkAttendanceSession,
    AttendanceException
)
from .forms import (
    AttendanceConfigForm
)
from apps.academics.models import BehaviorRecord, Student, Class, AcademicSession
from apps.users.models import User
from apps.core.mixins import TeacherRequiredMixin


# ==================== MIXIN CLASSES ====================

class AttendancePermissionMixin:
    """Mixin to check attendance-related permissions"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Check if user has permission to access attendance features
        if not (request.user.is_staff or
                request.user.has_perm('attendance.view_dailyattendance') or
                hasattr(request.user, 'teacher_profile') or
                hasattr(request.user, 'student_profile')):
            messages.error(request, "You don't have permission to access attendance features.")
            return redirect('users:dashboard')
        
        return super().dispatch(request, *args, **kwargs)





# ==================== CONFIGURATION VIEWS ====================

@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.change_attendanceconfig', raise_exception=True), name='dispatch')
class AttendanceConfigUpdateView(UpdateView):
    """View for updating attendance configuration"""
    model = AttendanceConfig
    form_class = AttendanceConfigForm
    template_name = 'attendance/config/config_form.html'
    success_url = reverse_lazy('config')

    def get_object(self):
        # Get or create config for current academic session
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            obj, created = AttendanceConfig.objects.get_or_create(
                academic_session=current_session,
                defaults={
                    'school_start_time': '08:00:00',
                    'school_end_time': '14:00:00',
                    'late_threshold_minutes': 15,
                    'half_day_threshold_hours': 4,
                    'auto_mark_absent_after_days': 3,
                    'notify_parents_on_absence': True,
                    'notify_after_consecutive_absences': 3
                }
            )
            return obj
        return None

    def get_initial(self):
        initial = super().get_initial()
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            initial['academic_session'] = current_session
        return initial

    def form_valid(self, form):
        # Ensure academic_session is set correctly to prevent tampering
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            form.instance.academic_session = current_session
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_session'] = AcademicSession.objects.filter(is_current=True).first()
        return context


# ==================== ATTENDANCE SESSION VIEWS ====================

@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.view_attendancesession', raise_exception=True), name='dispatch')
class AttendanceSessionListView(ListView):
    """List all attendance sessions"""
    model = AttendanceSession
    template_name = 'attendance/sessions/session_list.html'
    context_object_name = 'sessions'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        academic_session = self.request.GET.get('session')
        
        if academic_session:
            queryset = queryset.filter(academic_session_id=academic_session)
        else:
            current_session = AcademicSession.objects.filter(is_current=True).first()
            if current_session:
                queryset = queryset.filter(academic_session=current_session)
        
        return queryset.select_related('academic_session')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['academic_sessions'] = AcademicSession.objects.all()
        context['current_session'] = AcademicSession.objects.filter(is_current=True).first()
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.add_attendancesession', raise_exception=True), name='dispatch')
class AttendanceSessionCreateView(CreateView):
    """Create a new attendance session"""
    model = AttendanceSession
    template_name = 'attendance/sessions/session_form.html'
    fields = ['name', 'session_type', 'start_time', 'end_time', 'academic_session', 'is_active']
    success_url = reverse_lazy('session_list')
    
    def get_initial(self):
        initial = super().get_initial()
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            initial['academic_session'] = current_session
        return initial


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.change_attendancesession', raise_exception=True), name='dispatch')
class AttendanceSessionUpdateView(UpdateView):
    """Update an attendance session"""
    model = AttendanceSession
    template_name = 'attendance/sessions/session_form.html'
    fields = ['name', 'session_type', 'start_time', 'end_time', 'academic_session', 'is_active']
    success_url = reverse_lazy('session_list')


# ==================== DAILY ATTENDANCE VIEWS ====================

@method_decorator(login_required, name='dispatch')
class DailyAttendanceListView(AttendancePermissionMixin, ListView):
    """List daily attendance records with filtering"""
    model = DailyAttendance
    template_name = 'attendance/daily/daily_list.html'
    context_object_name = 'attendances'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = DailyAttendance.objects.all()
        
        # Apply filters
        student_id = self.request.GET.get('student')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        status = self.request.GET.get('status')
        session = self.request.GET.get('session')
        
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        if status:
            queryset = queryset.filter(status=status)
        if session:
            queryset = queryset.filter(attendance_session_id=session)
        
        # Restrict access based on user role
        if hasattr(self.request.user, 'student_profile'):
            queryset = queryset.filter(student=self.request.user.student_profile)
        elif hasattr(self.request.user, 'teacher_profile'):
            # Teachers can see attendance for their classes
            teacher_classes = Class.objects.filter(
                Q(class_teacher=self.request.user.teacher_profile) |
                Q(subject_assignments__teacher=self.request.user.teacher_profile)
            ).distinct()
            student_ids = Student.objects.filter(
                enrollments__class_enrolled__in=teacher_classes
            ).values_list('id', flat=True)
            queryset = queryset.filter(student_id__in=student_ids)
        
        return queryset.select_related('student__user', 'attendance_session', 'marked_by')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['attendance_sessions'] = AttendanceSession.objects.filter(is_active=True)
        context['status_choices'] = DailyAttendance.AttendanceStatus.choices
        
        # Add student filter options for teachers/admins
        if self.request.user.is_staff or hasattr(self.request.user, 'teacher_profile'):
            context['students'] = Student.objects.all()[:100]  # Limit for performance
        elif hasattr(self.request.user, 'student_profile'):
            context['current_student'] = self.request.user.student_profile
        
        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.add_dailyattendance', raise_exception=True), name='dispatch')
class DailyAttendanceCreateView(CreateView):
    """Create a new daily attendance record"""
    model = DailyAttendance
    template_name = 'attendance/daily/daily_form.html'
    fields = ['student', 'date', 'attendance_session', 'status', 'check_in_time', 'check_out_time', 'remarks']

    def get_success_url(self):
        return reverse_lazy('daily_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = timezone.now().date()
        context['attendance_sessions'] = AttendanceSession.objects.filter(is_active=True)
        context['status_choices'] = DailyAttendance.AttendanceStatus.choices

        # Get student from URL parameter or form initial data
        student_id = self.request.GET.get('student') or self.kwargs.get('student_id')
        if student_id:
            student = get_object_or_404(Student, pk=student_id)
            context['student'] = student

            # Get recent attendance records for the student
            context['recent_attendances'] = DailyAttendance.objects.filter(
                student=student
            ).select_related('attendance_session', 'marked_by').order_by('-date')[:5]

        return context

    def get_initial(self):
        initial = super().get_initial()
        # Set initial student if provided in URL
        student_id = self.request.GET.get('student') or self.kwargs.get('student_id')
        if student_id:
            initial['student'] = student_id
        return initial

    def form_valid(self, form):
        form.instance.marked_by = self.request.user
        messages.success(self.request, "Attendance record created successfully.")
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.change_dailyattendance', raise_exception=True), name='dispatch')
class DailyAttendanceUpdateView(UpdateView):
    """Update a daily attendance record"""
    model = DailyAttendance
    template_name = 'attendance/daily/daily_form.html'
    fields = ['student', 'date', 'attendance_session', 'status', 'check_in_time', 'check_out_time', 'remarks']

    def get_success_url(self):
        return reverse_lazy('daily_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = timezone.now().date()
        context['attendance_sessions'] = AttendanceSession.objects.filter(is_active=True)
        context['status_choices'] = DailyAttendance.AttendanceStatus.choices

        # Get student from the attendance record
        attendance = self.get_object()
        context['student'] = attendance.student

        # Get recent attendance records for the student (excluding current record)
        context['recent_attendances'] = DailyAttendance.objects.filter(
            student=attendance.student
        ).exclude(pk=attendance.pk).select_related('attendance_session', 'marked_by').order_by('-date')[:5]

        return context

    def form_valid(self, form):
        messages.success(self.request, "Attendance record updated successfully.")
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.delete_dailyattendance', raise_exception=True), name='dispatch')
class DailyAttendanceDeleteView(DeleteView):
    """Delete a daily attendance record"""
    model = DailyAttendance
    template_name = 'attendance/daily/daily_confirm_delete.html'
    success_url = reverse_lazy('daily_list')

    def get_success_url(self):
        messages.success(self.request, "Attendance record deleted successfully.")
        return super().get_success_url()


@method_decorator(login_required, name='dispatch')
class StudentAttendanceView(AttendancePermissionMixin, DetailView):
    """View for students to see their own attendance"""
    model = Student
    template_name = 'attendance/daily/student_attendance.html'
    context_object_name = 'student'

    def dispatch(self, request, *args, **kwargs):
        # If user is not a student and no pk is provided, redirect to daily attendance list
        if not hasattr(request.user, 'student_profile') and not self.kwargs.get('pk'):
            messages.info(request, "Please select a student to view their attendance.")
            return redirect('daily_list')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self):
        # If user is a student, show their own attendance
        if hasattr(self.request.user, 'student_profile'):
            return self.request.user.student_profile

        # If pk is provided, show specific student's attendance (for admins/teachers)
        pk = self.kwargs.get('pk')
        if pk:
            return get_object_or_404(Student, pk=pk)

        # This should not be reached due to dispatch check, but fallback
        raise Http404("Student not found")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()
        
        # Get attendance summary for current academic session
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            attendance_data = DailyAttendance.objects.filter(
                student=student,
                attendance_session__academic_session=current_session
            )
            
            context['attendance_records'] = attendance_data.order_by('-date')[:50]
            context['total_present'] = attendance_data.filter(status='present').count()
            context['total_absent'] = attendance_data.filter(status='absent').count()
            context['total_late'] = attendance_data.filter(status='late').count()
            context['attendance_percentage'] = round(
                (context['total_present'] / attendance_data.count() * 100), 2
            ) if attendance_data.count() > 0 else 0
        
        return context


# ==================== BULK ATTENDANCE VIEWS ====================

@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.add_dailyattendance', raise_exception=True), name='dispatch')
class BulkAttendanceView(TeacherRequiredMixin, View):
    """View for bulk attendance marking"""
    
    def get(self, request, class_id=None):
        if class_id:
            class_obj = get_object_or_404(Class, pk=class_id)
            students = Student.objects.filter(
                enrollments__class_enrolled=class_obj,
                enrollments__enrollment_status='active'
            ).select_related('user')
            
            context = {
                'class_obj': class_obj,
                'students': students,
                'attendance_sessions': AttendanceSession.objects.filter(is_active=True),
                'today': timezone.now().date()
            }
            return render(request, 'attendance/bulk/bulk_mark.html', context)
        else:
            # Show class selection
            if hasattr(request.user, 'teacher_profile'):
                classes = Class.objects.filter(
                    Q(class_teacher=request.user.teacher_profile) |
                    Q(subject_assignments__teacher=request.user.teacher_profile)
                ).distinct()
            else:
                classes = Class.objects.all()
            
            context = {'classes': classes}
            return render(request, 'attendance/bulk/bulk_class_select.html', context)
    
    def post(self, request, class_id):
        class_obj = get_object_or_404(Class, pk=class_id)
        date = request.POST.get('date')
        attendance_session_id = request.POST.get('attendance_session')
        
        if not date or not attendance_session_id:
            messages.error(request, "Please provide both date and attendance session.")
            return redirect('bulk_mark', class_id=class_id)
        
        attendance_session = get_object_or_404(AttendanceSession, pk=attendance_session_id)
        students = Student.objects.filter(
            enrollments__class_enrolled=class_obj,
            enrollments__enrollment_status='active'
        )
        
        marked_count = 0
        for student in students:
            status_field = f'status_{student.id}'
            remarks_field = f'remarks_{student.id}'
            
            if status_field in request.POST:
                status = request.POST[status_field]
                remarks = request.POST.get(remarks_field, '')
                
                # Create or update attendance record
                attendance, created = DailyAttendance.objects.update_or_create(
                    student=student,
                    date=date,
                    attendance_session=attendance_session,
                    defaults={
                        'status': status,
                        'remarks': remarks,
                        'marked_by': request.user
                    }
                )
                marked_count += 1
        
        messages.success(request, f"Successfully marked attendance for {marked_count} students.")
        return redirect('bulk_mark', class_id=class_id)


# ==================== PERIOD ATTENDANCE VIEWS ====================

@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.view_periodattendance', raise_exception=True), name='dispatch')
class PeriodAttendanceListView(ListView):
    """List period attendance records"""
    model = PeriodAttendance
    template_name = 'attendance/period/period_list.html'
    context_object_name = 'period_attendances'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = PeriodAttendance.objects.all()
        
        # Apply filters
        student_id = self.request.GET.get('student')
        subject_id = self.request.GET.get('subject')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if student_id:
            queryset = queryset.filter(daily_attendance__student_id=student_id)
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if date_from:
            queryset = queryset.filter(daily_attendance__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(daily_attendance__date__lte=date_to)
        
        return queryset.select_related(
            'daily_attendance__student__user',
            'subject',
            'marked_by'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add filter options
        return context


# ==================== LEAVE MANAGEMENT VIEWS ====================

@method_decorator(login_required, name='dispatch')
class LeaveApplicationListView(AttendancePermissionMixin, ListView):
    """List leave applications"""
    model = LeaveApplication
    template_name = 'attendance/leave/leave_list.html'
    context_object_name = 'leaves'
    paginate_by = 20

    def get_queryset(self):
        queryset = LeaveApplication.objects.all()

        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filter by leave type
        leave_type = self.request.GET.get('leave_type')
        if leave_type:
            queryset = queryset.filter(leave_type_id=leave_type)

        # Search by applicant name
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(applicant__first_name__icontains=search) |
                Q(applicant__last_name__icontains=search) |
                Q(applicant__username__icontains=search)
            )

        # Restrict access based on user role
        if not self.request.user.is_staff:
            if hasattr(self.request.user, 'student_profile') or hasattr(self.request.user, 'teacher_profile'):
                queryset = queryset.filter(applicant=self.request.user)

        return queryset.select_related('applicant', 'applicant__profile', 'leave_type', 'approved_by').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = LeaveApplication.LeaveStatus.choices
        context['leave_types'] = LeaveType.objects.filter(
            Q(allowed_for_students=True) | Q(allowed_for_teachers=True)
        )
        return context


@method_decorator(login_required, name='dispatch')
class LeaveApplicationCreateView(CreateView):
    """Create a new leave application"""
    model = LeaveApplication
    template_name = 'attendance/leave/leave_form.html'
    fields = ['leave_type', 'start_date', 'end_date', 'reason', 'supporting_documents']
    
    def get_success_url(self):
        return reverse_lazy('leave_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filter leave types based on user role
        if hasattr(self.request.user, 'student_profile'):
            form.fields['leave_type'].queryset = LeaveType.objects.filter(allowed_for_students=True)
        elif hasattr(self.request.user, 'teacher_profile'):
            form.fields['leave_type'].queryset = LeaveType.objects.filter(allowed_for_teachers=True)
        return form
    
    def form_valid(self, form):
        form.instance.applicant = self.request.user
        messages.success(self.request, "Leave application submitted successfully.")
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.change_leaveapplication', raise_exception=True), name='dispatch')
class LeaveApplicationUpdateView(UpdateView):
    """Update leave application (for approval/rejection)"""
    model = LeaveApplication
    template_name = 'attendance/leave/leave_review.html'
    fields = ['status', 'rejection_reason']

    def get_success_url(self):
        return reverse_lazy('leave_list')

    def form_valid(self, form):
        if form.instance.status == LeaveApplication.LeaveStatus.APPROVED:
            form.instance.approved_by = self.request.user
            form.instance.approved_at = timezone.now()
        messages.success(self.request, "Leave application updated successfully.")
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('attendance.delete_leaveapplication', raise_exception=True), name='dispatch')
class LeaveApplicationDeleteView(DeleteView):
    """Delete leave application"""
    model = LeaveApplication
    template_name = 'attendance/leave/leave_confirm_delete.html'
    success_url = reverse_lazy('leave_list')

    def get_success_url(self):
        messages.success(self.request, "Leave application deleted successfully.")
        return super().get_success_url()


# ==================== ATTENDANCE SUMMARY & REPORTS ====================

@method_decorator(login_required, name='dispatch')
class AttendanceSummaryView(AttendancePermissionMixin, View):
    """View for attendance summary and reports"""
    
    def get(self, request):
        context = {}
        
        # Get current academic session
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if not current_session:
            messages.error(request, "No active academic session found.")
            return render(request, 'attendance/summary/summary.html', context)
        
        # Get summary data based on user role
        if hasattr(request.user, 'student_profile'):
            context['student_summary'] = self.get_student_summary(request.user.student_profile, current_session)
        elif hasattr(request.user, 'teacher_profile'):
            context['class_summaries'] = self.get_teacher_class_summaries(request.user.teacher_profile, current_session)
        elif request.user.is_staff:
            context['overall_summary'] = self.get_overall_summary(current_session)
        
        context['current_session'] = current_session
        return render(request, 'attendance/summary/summary.html', context)
    
    def get_student_summary(self, student, session):
        """Get attendance summary for a specific student"""
        attendances = DailyAttendance.objects.filter(
            student=student,
            attendance_session__academic_session=session
        )
        
        total_days = attendances.count()
        present_days = attendances.filter(status='present').count()
        absent_days = attendances.filter(status='absent').count()
        late_days = attendances.filter(status='late').count()
        
        return {
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'late_days': late_days,
            'attendance_percentage': round((present_days / total_days * 100), 2) if total_days > 0 else 0,
            'recent_attendances': attendances.order_by('-date')[:10]
        }
    
    def get_teacher_class_summaries(self, teacher, session):
        """Get attendance summaries for teacher's classes"""
        classes = Class.objects.filter(
            Q(class_teacher=teacher) |
            Q(subject_assignments__teacher=teacher)
        ).distinct()
        
        summaries = []
        for class_obj in classes:
            students = Student.objects.filter(
                enrollments__class_enrolled=class_obj,
                enrollments__enrollment_status='active'
            )
            
            class_attendances = DailyAttendance.objects.filter(
                student__in=students,
                attendance_session__academic_session=session
            )
            
            total_days = class_attendances.count()
            present_days = class_attendances.filter(status='present').count()
            
            summaries.append({
                'class': class_obj,
                'student_count': students.count(),
                'total_days': total_days,
                'present_days': present_days,
                'attendance_percentage': round((present_days / total_days * 100), 2) if total_days > 0 else 0
            })
        
        return summaries
    
    def get_overall_summary(self, session):
        """Get overall attendance summary for admin"""
        total_attendances = DailyAttendance.objects.filter(
            attendance_session__academic_session=session
        )
        
        return {
            'total_records': total_attendances.count(),
            'present_count': total_attendances.filter(status='present').count(),
            'absent_count': total_attendances.filter(status='absent').count(),
            'late_count': total_attendances.filter(status='late').count(),
            'attendance_rate': round(
                (total_attendances.filter(status='present').count() / total_attendances.count() * 100), 2
            ) if total_attendances.count() > 0 else 0
        }


# ==================== API VIEWS FOR AJAX ====================

@login_required
@require_http_methods(["GET"])
def api_student_attendance(request, student_id):
    """API endpoint to get student attendance data for charts"""
    student = get_object_or_404(Student, pk=student_id)
    
    # Check permission
    if (hasattr(request.user, 'student_profile') and 
        request.user.student_profile != student and
        not request.user.is_staff):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    current_session = AcademicSession.objects.filter(is_current=True).first()
    if not current_session:
        return JsonResponse({'error': 'No active session'}, status=404)
    
    attendances = DailyAttendance.objects.filter(
        student=student,
        attendance_session__academic_session=current_session
    )
    
    # Monthly breakdown
    monthly_data = []
    for month in range(1, 13):
        month_attendances = attendances.filter(date__month=month)
        if month_attendances.exists():
            present_count = month_attendances.filter(status='present').count()
            total_count = month_attendances.count()
            monthly_data.append({
                'month': month,
                'present': present_count,
                'total': total_count,
                'percentage': round((present_count / total_count * 100), 2) if total_count > 0 else 0
            })
    
    # Status breakdown
    status_breakdown = {
        'present': attendances.filter(status='present').count(),
        'absent': attendances.filter(status='absent').count(),
        'late': attendances.filter(status='late').count(),
        'half_day': attendances.filter(status='half_day').count(),
        'leave': attendances.filter(status='leave').count()
    }
    
    return JsonResponse({
        'monthly_data': monthly_data,
        'status_breakdown': status_breakdown,
        'total_days': attendances.count()
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_mark_attendance(request):
    """API endpoint to mark attendance via AJAX"""
    try:
        student_id = request.POST.get('student_id')
        date = request.POST.get('date')
        session_id = request.POST.get('session_id')
        status = request.POST.get('status')
        remarks = request.POST.get('remarks', '')
        
        student = get_object_or_404(Student, pk=student_id)
        attendance_session = get_object_or_404(AttendanceSession, pk=session_id)
        
        # Check permission
        if not (request.user.is_staff or hasattr(request.user, 'teacher_profile')):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Create or update attendance
        attendance, created = DailyAttendance.objects.update_or_create(
            student=student,
            date=date,
            attendance_session=attendance_session,
            defaults={
                'status': status,
                'remarks': remarks,
                'marked_by': request.user
            }
        )
        
        return JsonResponse({
            'success': True,
            'created': created,
            'attendance_id': attendance.id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ==================== DASHBOARD VIEWS ====================

@login_required
def attendance_dashboard(request):
    """Main attendance dashboard"""
    context = {}
    
    if hasattr(request.user, 'student_profile'):
        # Student dashboard
        student = request.user.student_profile
        current_session = AcademicSession.objects.filter(is_current=True).first()
        
        if current_session:
            recent_attendances = DailyAttendance.objects.filter(
                student=student,
                attendance_session__academic_session=current_session
            ).order_by('-date')[:10]
            
            total_attendances = DailyAttendance.objects.filter(
                student=student,
                attendance_session__academic_session=current_session
            )
            present_count = total_attendances.filter(status='present').count()
            total_count = total_attendances.count()
            
            context.update({
                'recent_attendances': recent_attendances,
                'attendance_percentage': round((present_count / total_count * 100), 2) if total_count > 0 else 0,
                'present_count': present_count,
                'total_count': total_count
            })
    
    elif hasattr(request.user, 'teacher_profile'):
        # Teacher dashboard
        teacher = request.user.teacher_profile
        classes = Class.objects.filter(
            Q(class_teacher=teacher) |
            Q(subject_assignments__teacher=teacher)
        ).distinct()
        
        today = timezone.now().date()
        today_attendances = DailyAttendance.objects.filter(
            date=today,
            student__enrollments__class_enrolled__in=classes
        )
        
        context.update({
            'classes': classes,
            'today_attendance_count': today_attendances.count(),
            'today_present_count': today_attendances.filter(status='present').count()
        })
    
    elif request.user.is_staff:
        # Admin dashboard
        current_session = AcademicSession.objects.filter(is_current=True).first()
        if current_session:
            today = timezone.now().date()
            today_attendances = DailyAttendance.objects.filter(
                date=today,
                attendance_session__academic_session=current_session
            )
            
            context.update({
                'today_attendance_count': today_attendances.count(),
                'today_present_count': today_attendances.filter(status='present').count(),
                'total_students': Student.objects.count()
            })
    
    return render(request, 'attendance/dashboard/dashboard.html', context)


# ==================== EXPORT VIEWS ====================

@login_required
@permission_required('attendance.view_dailyattendance', raise_exception=True)
def export_attendance_report(request):
    """Export attendance data as CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Student Name', 'Date', 'Session', 'Status', 'Check-in', 'Check-out', 'Remarks'])
    
    # Get filtered data
    attendances = DailyAttendance.objects.all()
    
    # Apply filters from request
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    student_id = request.GET.get('student')
    
    if date_from:
        attendances = attendances.filter(date__gte=date_from)
    if date_to:
        attendances = attendances.filter(date__lte=date_to)
    if student_id:
        attendances = attendances.filter(student_id=student_id)
    
    for attendance in attendances.select_related('student__user', 'attendance_session'):
        writer.writerow([
            attendance.student.student_id,
            attendance.student.user.get_full_name(),
            attendance.date,
            attendance.attendance_session.name,
            attendance.get_status_display(),
            attendance.check_in_time,
            attendance.check_out_time,
            attendance.remarks
        ])
    
    return response


# ==================== BEHAVIOR/DISCIPLINE VIEWS ====================

@method_decorator(login_required, name='dispatch')
class BehaviorRecordListView(AttendancePermissionMixin, ListView):
    """List behavior records with filtering"""
    model = BehaviorRecord
    template_name = 'attendance/behavior/behavior_list.html'
    context_object_name = 'behavior_records'
    paginate_by = 25

    def get_queryset(self):
        queryset = BehaviorRecord.objects.all()

        # Apply filters
        student_id = self.request.GET.get('student')
        behavior_type = self.request.GET.get('behavior_type')
        severity = self.request.GET.get('severity')
        incident_category = self.request.GET.get('incident_category')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        is_resolved = self.request.GET.get('is_resolved')

        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if behavior_type:
            queryset = queryset.filter(behavior_type=behavior_type)
        if severity:
            queryset = queryset.filter(severity=severity)
        if incident_category:
            queryset = queryset.filter(incident_category=incident_category)
        if date_from:
            queryset = queryset.filter(incident_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(incident_date__lte=date_to)
        if is_resolved is not None:
            queryset = queryset.filter(is_resolved=is_resolved == 'true')

        # Restrict access based on user role
        if hasattr(self.request.user, 'student_profile'):
            queryset = queryset.filter(student=self.request.user.student_profile)
        elif hasattr(self.request.user, 'teacher_profile'):
            # Teachers can see behavior records for their classes
            teacher_classes = Class.objects.filter(
                Q(class_teacher=self.request.user.teacher_profile) |
                Q(subject_assignments__teacher=self.request.user.teacher_profile)
            ).distinct()
            student_ids = Student.objects.filter(
                enrollments__class_enrolled__in=teacher_classes
            ).values_list('id', flat=True)
            queryset = queryset.filter(student_id__in=student_ids)

        return queryset.select_related('student__user', 'reported_by').order_by('-incident_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['behavior_type_choices'] = BehaviorRecord.BehaviorType.choices
        context['severity_choices'] = BehaviorRecord.Severity.choices
        context['incident_category_choices'] = BehaviorRecord.IncidentCategory.choices

        # Add student filter options for teachers/admins
        if self.request.user.is_staff or hasattr(self.request.user, 'teacher_profile'):
            context['students'] = Student.objects.all()[:100]  # Limit for performance
        elif hasattr(self.request.user, 'student_profile'):
            context['current_student'] = self.request.user.student_profile

        return context


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('academics.add_behaviorrecord', raise_exception=True), name='dispatch')
class BehaviorRecordCreateView(CreateView):
    """Create a new behavior record"""
    model = BehaviorRecord
    template_name = 'attendance/behavior/behavior_form.html'
    fields = [
        'student', 'behavior_type', 'severity', 'incident_category',
        'title', 'description', 'incident_date', 'incident_time',
        'location', 'evidence_description', 'has_witnesses',
        'witnesses', 'witness_statements', 'action_taken',
        'consequence_type', 'consequence_duration', 'action_deadline',
        'follow_up_required', 'follow_up_date', 'next_follow_up_date',
        'follow_up_notes', 'resolution', 'is_resolved', 'resolution_date',
        'parent_notified', 'parent_notification_date', 'parent_response',
        'parent_meeting_scheduled', 'parent_meeting_date', 'escalated_to',
        'escalation_date', 'escalation_reason', 'tags'
    ]
    success_url = reverse_lazy('behavior_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = timezone.now().date()
        context['behavior_type_choices'] = BehaviorRecord.BehaviorType.choices
        context['severity_choices'] = BehaviorRecord.Severity.choices
        context['incident_category_choices'] = BehaviorRecord.IncidentCategory.choices
        context['consequence_type_choices'] = BehaviorRecord.ConsequenceType.choices

        # Get student from URL parameter
        student_id = self.request.GET.get('student') or self.kwargs.get('student_id')
        if student_id:
            student = get_object_or_404(Student, pk=student_id)
            context['student'] = student

        return context

    def get_initial(self):
        initial = super().get_initial()
        # Set initial student if provided in URL
        student_id = self.request.GET.get('student') or self.kwargs.get('student_id')
        if student_id:
            initial['student'] = student_id
        return initial

    def form_valid(self, form):
        form.instance.reported_by = self.request.user
        messages.success(self.request, "Behavior record created successfully.")
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('academics.change_behaviorrecord', raise_exception=True), name='dispatch')
class BehaviorRecordUpdateView(UpdateView):
    """Update a behavior record"""
    model = BehaviorRecord
    template_name = 'attendance/behavior/behavior_form.html'
    fields = [
        'student', 'behavior_type', 'severity', 'incident_category',
        'title', 'description', 'incident_date', 'incident_time',
        'location', 'evidence_description', 'has_witnesses',
        'witnesses', 'witness_statements', 'action_taken',
        'consequence_type', 'consequence_duration', 'action_deadline',
        'follow_up_required', 'follow_up_date', 'next_follow_up_date',
        'follow_up_notes', 'resolution', 'is_resolved', 'resolution_date',
        'parent_notified', 'parent_notification_date', 'parent_response',
        'parent_meeting_scheduled', 'parent_meeting_date', 'escalated_to',
        'escalation_date', 'escalation_reason', 'tags'
    ]
    success_url = reverse_lazy('behavior_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = timezone.now().date()
        context['behavior_type_choices'] = BehaviorRecord.BehaviorType.choices
        context['severity_choices'] = BehaviorRecord.Severity.choices
        context['incident_category_choices'] = BehaviorRecord.IncidentCategory.choices
        context['consequence_type_choices'] = BehaviorRecord.ConsequenceType.choices

        behavior_record = self.get_object()
        context['student'] = behavior_record.student

        return context

    def form_valid(self, form):
        messages.success(self.request, "Behavior record updated successfully.")
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(permission_required('academics.delete_behaviorrecord', raise_exception=True), name='dispatch')
class BehaviorRecordDeleteView(DeleteView):
    """Delete a behavior record"""
    model = BehaviorRecord
    template_name = 'attendance/behavior/behavior_confirm_delete.html'
    success_url = reverse_lazy('behavior_list')

    def get_success_url(self):
        messages.success(self.request, "Behavior record deleted successfully.")
        return super().get_success_url()


@method_decorator(login_required, name='dispatch')
class StudentBehaviorView(AttendancePermissionMixin, DetailView):
    """View for students to see their own behavior records"""
    model = Student
    template_name = 'attendance/behavior/student_behavior.html'
    context_object_name = 'student'

    def get_object(self):
        if hasattr(self.request.user, 'student_profile'):
            return self.request.user.student_profile
        return get_object_or_404(Student, pk=self.kwargs.get('pk'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()

        # Get behavior records for the student
        behavior_records = BehaviorRecord.objects.filter(student=student)

        context['behavior_records'] = behavior_records.order_by('-incident_date')[:50]
        context['total_records'] = behavior_records.count()
        context['resolved_records'] = behavior_records.filter(is_resolved=True).count()
        context['unresolved_records'] = behavior_records.filter(is_resolved=False).count()
        context['positive_records'] = behavior_records.filter(behavior_type='positive').count()
        context['negative_records'] = behavior_records.filter(behavior_type='negative').count()

        return context


# ==================== ERROR HANDLING ====================

def attendance_error_handler(request, exception=None):
    """Custom error handler for attendance app"""
    return render(request, 'errors/500.html', {
        'error_message': 'An error occurred while processing your attendance request.'
    }, status=500)
