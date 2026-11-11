# apps/attendance/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import FileExtensionValidator

from .models import (
    AttendanceConfig, AttendanceSession, DailyAttendance, PeriodAttendance,
    LeaveType, LeaveApplication, AttendanceSummary, BulkAttendanceSession,
    AttendanceException
)


class AttendanceConfigForm(forms.ModelForm):
    """Form for AttendanceConfig model with validation."""

    class Meta:
        model = AttendanceConfig
        fields = [
            'academic_session', 'school_start_time', 'school_end_time',
            'late_threshold_minutes', 'half_day_threshold_hours',
            'auto_mark_absent_after_days', 'enable_biometric',
            'enable_geo_fencing', 'notify_parents_on_absence',
            'notify_after_consecutive_absences'
        ]
        widgets = {
            'school_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'school_end_time': forms.TimeInput(attrs={'type': 'time'}),
        }
        help_texts = {
            'late_threshold_minutes': _('Minutes after start time considered as late'),
            'half_day_threshold_hours': _('Minimum hours required for half day attendance'),
            'auto_mark_absent_after_days': _('Automatically mark absent if no attendance recorded after N days'),
            'notify_after_consecutive_absences': _('Send notification after N consecutive absences'),
        }

    def clean_school_end_time(self):
        end_time = self.cleaned_data.get('school_end_time')
        start_time = self.cleaned_data.get('school_start_time')
        
        if end_time and start_time and end_time <= start_time:
            raise ValidationError(_('School end time must be after start time.'))
        
        return end_time

    def clean_late_threshold_minutes(self):
        threshold = self.cleaned_data.get('late_threshold_minutes')
        if threshold and threshold > 240:  # 4 hours
            raise ValidationError(_('Late threshold cannot exceed 4 hours (240 minutes).'))
        return threshold

    def clean_half_day_threshold_hours(self):
        threshold = self.cleaned_data.get('half_day_threshold_hours')
        if threshold and threshold > 8:
            raise ValidationError(_('Half day threshold cannot exceed 8 hours.'))
        return threshold

    def clean_auto_mark_absent_after_days(self):
        days = self.cleaned_data.get('auto_mark_absent_after_days')
        if days and days > 30:
            raise ValidationError(_('Auto mark absent days cannot exceed 30.'))
        return days

    def clean_notify_after_consecutive_absences(self):
        absences = self.cleaned_data.get('notify_after_consecutive_absences')
        if absences and absences > 10:
            raise ValidationError(_('Consecutive absences notification threshold cannot exceed 10.'))
        return absences


class AttendanceSessionForm(forms.ModelForm):
    """Form for AttendanceSession model."""
    
    class Meta:
        model = AttendanceSession
        fields = [
            'name', 'session_type', 'start_time', 'end_time',
            'academic_session', 'is_active', 'status'
        ]
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean_end_time(self):
        end_time = self.cleaned_data.get('end_time')
        start_time = self.cleaned_data.get('start_time')
        
        if end_time and start_time and end_time <= start_time:
            raise ValidationError(_('End time must be after start time.'))
        
        return end_time

    def clean(self):
        cleaned_data = super().clean()
        academic_session = cleaned_data.get('academic_session')
        name = cleaned_data.get('name')
        
        if academic_session and name:
            existing = AttendanceSession.objects.filter(
                academic_session=academic_session,
                name=name
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                self.add_error(
                    'name',
                    _('An attendance session with this name already exists for the academic session.')
                )
        
        return cleaned_data


class DailyAttendanceForm(forms.ModelForm):
    """Form for DailyAttendance model with comprehensive validation."""
    
    class Meta:
        model = DailyAttendance
        fields = [
            'student', 'date', 'attendance_session', 'status',
            'check_in_time', 'check_out_time', 'total_hours',
            'is_late', 'late_minutes', 'remarks', 'marked_by',
            'ip_address', 'device_info', 'status'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'check_in_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'check_out_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'total_hours': _('Total hours attended (auto-calculated)'),
            'late_minutes': _('Minutes late (auto-calculated)'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make some fields read-only when appropriate
        if self.instance and self.instance.pk:
            self.fields['total_hours'].widget.attrs['readonly'] = True
            self.fields['late_minutes'].widget.attrs['readonly'] = True

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise ValidationError(_('Attendance date cannot be in the future.'))
        return date

    def clean_check_out_time(self):
        check_out_time = self.cleaned_data.get('check_out_time')
        check_in_time = self.cleaned_data.get('check_in_time')
        
        if check_out_time and check_in_time and check_out_time <= check_in_time:
            raise ValidationError(_('Check-out time must be after check-in time.'))
        
        return check_out_time

    def clean_total_hours(self):
        total_hours = self.cleaned_data.get('total_hours')
        if total_hours and total_hours < 0:
            raise ValidationError(_('Total hours cannot be negative.'))
        return total_hours

    def clean_late_minutes(self):
        late_minutes = self.cleaned_data.get('late_minutes')
        if late_minutes and late_minutes < 0:
            raise ValidationError(_('Late minutes cannot be negative.'))
        return late_minutes

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        date = cleaned_data.get('date')
        attendance_session = cleaned_data.get('attendance_session')
        status = cleaned_data.get('status')
        check_in_time = cleaned_data.get('check_in_time')
        check_out_time = cleaned_data.get('check_out_time')
        
        # Check for duplicate attendance records
        if student and date and attendance_session:
            existing = DailyAttendance.objects.filter(
                student=student,
                date=date,
                attendance_session=attendance_session
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                self.add_error(
                    'student',
                    _('Attendance record already exists for this student, date, and session.')
                )
        
        # Validate check-in/out times based on status
        if status == DailyAttendance.AttendanceStatus.PRESENT:
            if not check_in_time:
                self.add_error(
                    'check_in_time',
                    _('Check-in time is required for present status.')
                )
        elif status == DailyAttendance.AttendanceStatus.ABSENT:
            if check_in_time or check_out_time:
                self.add_error(
                    'check_in_time',
                    _('Check-in/out times should not be set for absent status.')
                )
        
        # Validate student belongs to the attendance session's academic session
        if student and attendance_session:
            if student.academic_session != attendance_session.academic_session:
                self.add_error(
                    'student',
                    _('Student does not belong to the academic session of this attendance session.')
                )
        
        return cleaned_data


class PeriodAttendanceForm(forms.ModelForm):
    """Form for PeriodAttendance model."""
    
    class Meta:
        model = PeriodAttendance
        fields = [
            'daily_attendance', 'subject', 'period_number',
            'period_start_time', 'period_end_time', 'is_present',
            'teacher_remarks', 'marked_by', 'status'
        ]
        widgets = {
            'period_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'period_end_time': forms.TimeInput(attrs={'type': 'time'}),
            'teacher_remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_period_end_time(self):
        end_time = self.cleaned_data.get('period_end_time')
        start_time = self.cleaned_data.get('period_start_time')
        
        if end_time and start_time and end_time <= start_time:
            raise ValidationError(_('Period end time must be after start time.'))
        
        return end_time

    def clean_period_number(self):
        period_number = self.cleaned_data.get('period_number')
        daily_attendance = self.cleaned_data.get('daily_attendance')
        
        if period_number and daily_attendance:
            existing = PeriodAttendance.objects.filter(
                daily_attendance=daily_attendance,
                period_number=period_number
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                self.add_error(
                    'period_number',
                    _('Period number must be unique for each daily attendance record.')
                )
        
        return period_number

    def clean(self):
        cleaned_data = super().clean()
        daily_attendance = cleaned_data.get('daily_attendance')
        subject = cleaned_data.get('subject')
        
        if daily_attendance and subject:
            # Check if subject belongs to student's class
            student_class = daily_attendance.student.current_class
            if student_class and not student_class.subjects.filter(pk=subject.pk).exists():
                self.add_error(
                    'subject',
                    _('Subject is not taught in the student\'s class.')
                )
        
        return cleaned_data


class LeaveTypeForm(forms.ModelForm):
    """Form for LeaveType model."""
    
    class Meta:
        model = LeaveType
        fields = [
            'name', 'code', 'description', 'max_days_per_year',
            'requires_approval', 'is_paid', 'allowed_for_students',
            'allowed_for_teachers', 'color', 'status'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'color': forms.TextInput(attrs={'type': 'color'}),
        }
        help_texts = {
            'code': _('Unique leave type code'),
            'max_days_per_year': _('Maximum number of leave days allowed per year'),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            existing = LeaveType.objects.filter(code=code).exclude(
                pk=self.instance.pk if self.instance else None
            )
            if existing.exists():
                raise ValidationError(_('Leave type code must be unique.'))
        return code

    def clean_max_days_per_year(self):
        max_days = self.cleaned_data.get('max_days_per_year')
        if max_days and max_days > 365:
            raise ValidationError(_('Maximum days per year cannot exceed 365.'))
        return max_days

    def clean_color(self):
        color = self.cleaned_data.get('color')
        if color and not color.startswith('#'):
            raise ValidationError(_('Color must be in hex format (e.g., #007bff).'))
        return color

    def clean(self):
        cleaned_data = super().clean()
        allowed_for_students = cleaned_data.get('allowed_for_students')
        allowed_for_teachers = cleaned_data.get('allowed_for_teachers')
        
        if not allowed_for_students and not allowed_for_teachers:
            self.add_error(
                'allowed_for_students',
                _('Leave type must be allowed for at least students or teachers.')
            )
        
        return cleaned_data


class LeaveApplicationForm(forms.ModelForm):
    """Form for LeaveApplication model with comprehensive validation."""
    
    class Meta:
        model = LeaveApplication
        fields = [
            'applicant', 'leave_type', 'start_date', 'end_date', 'total_days',
            'reason', 'supporting_documents', 'status', 'approved_by',
            'rejection_reason', 'status'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 4}),
            'rejection_reason': forms.Textarea(attrs={'rows': 3}),
            'supporting_documents': forms.SelectMultiple(attrs={'class': 'select2'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set current user as applicant if not set
        if not self.instance.pk and self.user and not self.initial.get('applicant'):
            self.initial['applicant'] = self.user
        
        # Make applicant read-only for non-staff users
        if self.user and not self.user.is_staff:
            self.fields['applicant'].disabled = True

    def clean_end_date(self):
        end_date = self.cleaned_data.get('end_date')
        start_date = self.cleaned_data.get('start_date')
        
        if end_date and start_date and end_date < start_date:
            raise ValidationError(_('End date cannot be before start date.'))
        
        return end_date

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if start_date and start_date < timezone.now().date():
            raise ValidationError(_('Leave cannot start in the past.'))
        return start_date

    def clean_total_days(self):
        total_days = self.cleaned_data.get('total_days')
        if total_days and total_days <= 0:
            raise ValidationError(_('Total days must be greater than 0.'))
        return total_days

    def clean_leave_type(self):
        leave_type = self.cleaned_data.get('leave_type')
        applicant = self.cleaned_data.get('applicant')
        
        if leave_type and applicant:
            # Check if leave type is allowed for the applicant type
            from apps.users.models import UserRole
            user_roles = UserRole.objects.filter(user=applicant, is_primary=True)
            
            if user_roles.exists():
                user_role = user_roles.first()
                if user_role.role.role_type == 'student' and not leave_type.allowed_for_students:
                    raise ValidationError(_('This leave type is not allowed for students.'))
                elif user_role.role.role_type == 'teacher' and not leave_type.allowed_for_teachers:
                    raise ValidationError(_('This leave type is not allowed for teachers.'))
        
        return leave_type

    def clean(self):
        cleaned_data = super().clean()
        applicant = cleaned_data.get('applicant')
        leave_type = cleaned_data.get('leave_type')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        total_days = cleaned_data.get('total_days')
        status = cleaned_data.get('status')
        approved_by = cleaned_data.get('approved_by')
        
        # Validate total days calculation
        if start_date and end_date and total_days:
            calculated_days = (end_date - start_date).days + 1
            if total_days != calculated_days:
                self.add_error(
                    'total_days',
                    _('Total days calculation is incorrect. Should be %(days)s days.') % {
                        'days': calculated_days
                    }
                )
        
        # Check leave balance
        if applicant and leave_type and start_date and end_date:
            current_year = start_date.year
            leaves_taken = LeaveApplication.objects.filter(
                applicant=applicant,
                leave_type=leave_type,
                start_date__year=current_year,
                status=LeaveApplication.LeaveStatus.APPROVED
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            total_leaves_taken = sum(leave.total_days for leave in leaves_taken)
            if total_leaves_taken + total_days > leave_type.max_days_per_year:
                remaining_days = leave_type.max_days_per_year - total_leaves_taken
                self.add_error(
                    'total_days',
                    _('Leave balance exceeded. Maximum %(max_days)s days per year. Remaining: %(remaining)s days.') % {
                        'max_days': leave_type.max_days_per_year,
                        'remaining': remaining_days
                    }
                )
        
        # Validate approval fields
        if status == LeaveApplication.LeaveStatus.APPROVED and not approved_by:
            self.add_error(
                'approved_by',
                _('Approver must be specified when approving leave.')
            )
        
        if status == LeaveApplication.LeaveStatus.REJECTED and not cleaned_data.get('rejection_reason'):
            self.add_error(
                'rejection_reason',
                _('Rejection reason is required when rejecting leave.')
            )
        
        return cleaned_data


class AttendanceSummaryForm(forms.ModelForm):
    """Form for AttendanceSummary model."""
    
    class Meta:
        model = AttendanceSummary
        fields = [
            'student', 'academic_session', 'month', 'year',
            'total_school_days', 'days_present', 'days_absent',
            'days_late', 'days_half_day', 'days_on_leave',
            'attendance_percentage', 'consecutive_absences', 'status'
        ]
        widgets = {
            'month': forms.Select(choices=[(i, i) for i in range(1, 13)]),
            'year': forms.NumberInput(attrs={'min': 2000, 'max': 2100}),
        }

    def clean_month(self):
        month = self.cleaned_data.get('month')
        if month and (month < 1 or month > 12):
            raise ValidationError(_('Month must be between 1 and 12.'))
        return month

    def clean_year(self):
        year = self.cleaned_data.get('year')
        if year and (year < 2000 or year > 2100):
            raise ValidationError(_('Year must be between 2000 and 2100.'))
        return year

    def clean_attendance_percentage(self):
        percentage = self.cleaned_data.get('attendance_percentage')
        if percentage and (percentage < 0 or percentage > 100):
            raise ValidationError(_('Attendance percentage must be between 0 and 100.'))
        return percentage

    def clean_days_present(self):
        days_present = self.cleaned_data.get('days_present')
        total_school_days = self.cleaned_data.get('total_school_days')
        
        if days_present and total_school_days and days_present > total_school_days:
            raise ValidationError(_('Days present cannot exceed total school days.'))
        
        return days_present

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        academic_session = cleaned_data.get('academic_session')
        total_school_days = cleaned_data.get('total_school_days')
        days_present = cleaned_data.get('days_present')
        days_absent = cleaned_data.get('days_absent')
        days_late = cleaned_data.get('days_late')
        days_half_day = cleaned_data.get('days_half_day')
        days_on_leave = cleaned_data.get('days_on_leave')
        
        if student and academic_session and student.academic_session != academic_session:
            self.add_error(
                'student',
                _('Student does not belong to the selected academic session.')
            )
        
        # Validate total days consistency
        if total_school_days:
            calculated_total = (days_present or 0) + (days_absent or 0) + (days_late or 0) + \
                             (days_half_day or 0) + (days_on_leave or 0)
            
            if calculated_total > total_school_days:
                self.add_error(
                    'total_school_days',
                    _('Sum of all attendance days cannot exceed total school days.')
                )
        
        return cleaned_data


class BulkAttendanceSessionForm(forms.ModelForm):
    """Form for BulkAttendanceSession model."""
    
    class Meta:
        model = BulkAttendanceSession
        fields = [
            'name', 'class_obj', 'date', 'attendance_session',
            'marked_by', 'total_students', 'marked_students',
            'is_completed', 'completed_at', 'status'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'completed_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise ValidationError(_('Attendance date cannot be in the future.'))
        return date

    def clean_marked_students(self):
        marked_students = self.cleaned_data.get('marked_students')
        total_students = self.cleaned_data.get('total_students')
        
        if marked_students and total_students and marked_students > total_students:
            raise ValidationError(_('Marked students cannot exceed total students.'))
        
        return marked_students

    def clean(self):
        cleaned_data = super().clean()
        class_obj = cleaned_data.get('class_obj')
        attendance_session = cleaned_data.get('attendance_session')
        date = cleaned_data.get('date')
        
        if class_obj and attendance_session and class_obj.academic_session != attendance_session.academic_session:
            self.add_error(
                'attendance_session',
                _('Attendance session does not belong to the class\'s academic session.')
            )
        
        # Check for existing bulk session for same class, date, and session
        if class_obj and date and attendance_session:
            existing = BulkAttendanceSession.objects.filter(
                class_obj=class_obj,
                date=date,
                attendance_session=attendance_session
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                self.add_error(
                    'class_obj',
                    _('Bulk attendance session already exists for this class, date, and session.')
                )
        
        return cleaned_data


class AttendanceExceptionForm(forms.ModelForm):
    """Form for AttendanceException model."""

    class Meta:
        model = AttendanceException
        fields = [
            'daily_attendance', 'exception_type', 'original_status',
            'new_status', 'reason', 'approved_by', 'status'
        ]
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4}),
            'effective_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def clean_new_status(self):
        new_status = self.cleaned_data.get('new_status')
        original_status = self.cleaned_data.get('original_status')
        
        if new_status and original_status and new_status == original_status:
            raise ValidationError(_('New status must be different from original status.'))
        
        return new_status

    def clean_effective_date(self):
        effective_date = self.cleaned_data.get('effective_date')
        if effective_date and effective_date > timezone.now():
            raise ValidationError(_('Effective date cannot be in the future.'))
        return effective_date

    def clean(self):
        cleaned_data = super().clean()
        daily_attendance = cleaned_data.get('daily_attendance')
        exception_type = cleaned_data.get('exception_type')
        approved_by = cleaned_data.get('approved_by')
        
        if exception_type == AttendanceException.ExceptionType.MANUAL_OVERRIDE and not approved_by:
            self.add_error(
                'approved_by',
                _('Approver must be specified for manual overrides.')
            )
        
        if daily_attendance and daily_attendance.status == cleaned_data.get('new_status'):
            self.add_error(
                'new_status',
                _('Attendance record already has this status.')
            )
        
        return cleaned_data


# Search and Filter Forms
class AttendanceSearchForm(forms.Form):
    """Form for searching attendance records."""
    
    student_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by student name...')})
    )
    academic_class = forms.ModelChoiceField(
        required=False,
        queryset=None,  # Will be set in view
        empty_label=_('All Classes')
    )
    attendance_session = forms.ModelChoiceField(
        required=False,
        queryset=AttendanceSession.objects.all(),
        empty_label=_('All Sessions')
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', _('All Status'))] + list(DailyAttendance.AttendanceStatus.choices)
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('From Date')
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('To Date')
    )
    include_late = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Include Late Arrivals')
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_to < date_from:
            self.add_error('date_to', _('End date must be after start date.'))
        
        return cleaned_data


class LeaveSearchForm(forms.Form):
    """Form for searching leave applications."""
    
    applicant_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by applicant name...')})
    )
    leave_type = forms.ModelChoiceField(
        required=False,
        queryset=LeaveType.objects.all(),
        empty_label=_('All Leave Types')
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', _('All Status'))] + list(LeaveApplication.LeaveStatus.choices)
    )
    start_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Start Date From')
    )
    start_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Start Date To')
    )
    applicant_type = forms.ChoiceField(
        required=False,
        choices=[
            ('', _('All Types')),
            ('student', _('Students Only')),
            ('teacher', _('Teachers Only'))
        ]
    )


class BulkAttendanceMarkingForm(forms.Form):
    """Form for bulk attendance marking."""
    
    class_obj = forms.ModelChoiceField(
        queryset=None,  # Will be set in view
        label=_('Class')
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Attendance Date'),
        initial=timezone.now().date
    )
    attendance_session = forms.ModelChoiceField(
        queryset=AttendanceSession.objects.filter(is_active=True),
        label=_('Attendance Session')
    )
    default_status = forms.ChoiceField(
        choices=DailyAttendance.AttendanceStatus.choices,
        initial=DailyAttendance.AttendanceStatus.PRESENT,
        label=_('Default Status')
    )
    marked_by = forms.ModelChoiceField(
        queryset=None,  # Will be set in view to current user
        label=_('Marked By')
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['marked_by'].queryset = type(user).objects.filter(pk=user.pk)

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise ValidationError(_('Attendance date cannot be in the future.'))
        return date


class StudentAttendanceForm(forms.Form):
    """Form for individual student attendance marking."""
    
    status = forms.ChoiceField(
        choices=DailyAttendance.AttendanceStatus.choices,
        label=_('Attendance Status')
    )
    check_in_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label=_('Check-in Time')
    )
    check_out_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label=_('Check-out Time')
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': _('Additional remarks...')}),
        label=_('Remarks')
    )

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        check_in_time = cleaned_data.get('check_in_time')
        check_out_time = cleaned_data.get('check_out_time')
        
        if status == DailyAttendance.AttendanceStatus.PRESENT and not check_in_time:
            self.add_error(
                'check_in_time',
                _('Check-in time is required for present status.')
            )
        
        if check_out_time and check_in_time and check_out_time <= check_in_time:
            self.add_error(
                'check_out_time',
                _('Check-out time must be after check-in time.')
            )
        
        return cleaned_data


class AttendanceReportForm(forms.Form):
    """Form for generating attendance reports."""
    
    REPORT_TYPES = [
        ('daily_summary', _('Daily Attendance Summary')),
        ('monthly_summary', _('Monthly Attendance Summary')),
        ('student_attendance', _('Student Attendance Report')),
        ('class_attendance', _('Class Attendance Report')),
        ('absence_report', _('Absence Report')),
        ('late_report', _('Late Arrival Report')),
        ('leave_report', _('Leave Report')),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        label=_('Report Type')
    )
    academic_class = forms.ModelChoiceField(
        required=False,
        queryset=None,  # Will be set in view
        empty_label=_('All Classes'),
        label=_('Class')
    )
    student = forms.ModelChoiceField(
        required=False,
        queryset=None,  # Will be set in view
        empty_label=_('All Students'),
        label=_('Student')
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Start Date')
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('End Date')
    )
    attendance_session = forms.ModelChoiceField(
        required=False,
        queryset=AttendanceSession.objects.all(),
        empty_label=_('All Sessions'),
        label=_('Attendance Session')
    )
    format = forms.ChoiceField(
        choices=[('pdf', 'PDF'), ('excel', 'Excel'), ('csv', 'CSV')],
        initial='pdf',
        label=_('Output Format')
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', _('End date must be after start date.'))
        
        if start_date and start_date > timezone.now().date():
            self.add_error('start_date', _('Start date cannot be in the future.'))
        
        return cleaned_data


class LeaveBalanceForm(forms.Form):
    """Form for checking leave balances."""
    
    applicant = forms.ModelChoiceField(
        queryset=None,  # Will be set in view
        label=_('Applicant')
    )
    leave_type = forms.ModelChoiceField(
        required=False,
        queryset=LeaveType.objects.all(),
        empty_label=_('All Leave Types'),
        label=_('Leave Type')
    )
    year = forms.IntegerField(
        min_value=2000,
        max_value=2100,
        initial=timezone.now().year,
        label=_('Year')
    )


class ImportAttendanceForm(forms.Form):
    """Form for importing attendance data from files."""
    
    file = forms.FileField(
        label=_('Attendance File'),
        help_text=_('CSV or Excel file containing attendance data'),
        validators=[FileExtensionValidator(allowed_extensions=['csv', 'xlsx', 'xls'])]
    )
    attendance_session = forms.ModelChoiceField(
        queryset=AttendanceSession.objects.filter(is_active=True),
        label=_('Attendance Session')
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Attendance Date')
    )
    overwrite_existing = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Overwrite Existing Records'),
        help_text=_('Overwrite attendance records that already exist')
    )

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise ValidationError(_('Attendance date cannot be in the future.'))
        return date
