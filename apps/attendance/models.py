# apps/attendance/models.py

import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from datetime import datetime

from apps.core.models import CoreBaseModel


class AttendanceConfig(CoreBaseModel):
    """
    System-wide configuration for attendance settings.
    """
    academic_session = models.ForeignKey(
        'academics.AcademicSession',
        on_delete=models.CASCADE,
        related_name='attendance_configs',
        verbose_name=_('academic session')
    )
    school_start_time = models.TimeField(_('school start time'), default='08:00:00')
    school_end_time = models.TimeField(_('school end time'), default='14:00:00')
    late_threshold_minutes = models.PositiveIntegerField(
        _('late threshold (minutes)'),
        default=15,
        help_text=_('Minutes after start time considered as late')
    )
    half_day_threshold_hours = models.PositiveIntegerField(
        _('half day threshold (hours)'),
        default=4,
        help_text=_('Minimum hours required for half day attendance')
    )
    auto_mark_absent_after_days = models.PositiveIntegerField(
        _('auto mark absent after days'),
        default=3,
        help_text=_('Automatically mark absent if no attendance recorded after N days')
    )
    enable_biometric = models.BooleanField(_('enable biometric integration'), default=False)
    enable_geo_fencing = models.BooleanField(_('enable geo-fencing'), default=False)
    notify_parents_on_absence = models.BooleanField(_('notify parents on absence'), default=True)
    notify_after_consecutive_absences = models.PositiveIntegerField(
        _('notify after consecutive absences'),
        default=3,
        help_text=_('Send notification after N consecutive absences')
    )

    class Meta:
        verbose_name = _('Attendance Configuration')
        verbose_name_plural = _('Attendance Configurations')
        unique_together = ['academic_session']

    def __str__(self):
        return f"Attendance Config - {self.academic_session}"

    def clean(self):
        if self.late_threshold_minutes > 240:  # 4 hours
            raise ValidationError(_('Late threshold cannot exceed 4 hours.'))
        if self.half_day_threshold_hours > 8:
            raise ValidationError(_('Half day threshold cannot exceed 8 hours.'))


class AttendanceSession(CoreBaseModel):
    """
    Defines different attendance sessions throughout the day.
    """
    class SessionType(models.TextChoices):
        MORNING = 'morning', _('Morning Session')
        AFTERNOON = 'afternoon', _('Afternoon Session')
        FULL_DAY = 'full_day', _('Full Day')
        PERIOD = 'period', _('Period Wise')

    name = models.CharField(_('session name'), max_length=100)
    session_type = models.CharField(
        _('session type'),
        max_length=20,
        choices=SessionType.choices,
        default=SessionType.FULL_DAY
    )
    start_time = models.TimeField(_('start time'))
    end_time = models.TimeField(_('end time'))
    academic_session = models.ForeignKey(
        'academics.AcademicSession',
        on_delete=models.CASCADE,
        related_name='attendance_sessions',
        verbose_name=_('academic session')
    )
    is_active = models.BooleanField(_('is active'), default=True)

    class Meta:
        verbose_name = _('Attendance Session')
        verbose_name_plural = _('Attendance Sessions')
        ordering = ['start_time']
        unique_together = ['name', 'academic_session']

    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError(_('End time must be after start time.'))


class DailyAttendance(CoreBaseModel):
    """
    Main model for recording daily attendance of students.
    """
    class AttendanceStatus(models.TextChoices):
        PRESENT = 'present', _('Present')
        ABSENT = 'absent', _('Absent')
        LATE = 'late', _('Late')
        HALF_DAY = 'half_day', _('Half Day')
        HOLIDAY = 'holiday', _('Holiday')
        LEAVE = 'leave', _('On Leave')
        SICK = 'sick', _('Sick Leave')
        EXCUSED = 'excused', _('Excused Absence')

    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='daily_attendances',
        verbose_name=_('student')
    )
    date = models.DateField(_('date'), db_index=True)
    attendance_session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name='daily_attendances',
        verbose_name=_('attendance session')
    )
    status = models.CharField(
        _('attendance status'),
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.ABSENT
    )
    check_in_time = models.DateTimeField(_('check in time'), null=True, blank=True)
    check_out_time = models.DateTimeField(_('check out time'), null=True, blank=True)
    total_hours = models.DecimalField(
        _('total hours'),
        max_digits=4,
        decimal_places=2,
        null=True,                          
        blank=True,
        help_text=_('Total hours attended')
    )
    is_late = models.BooleanField(_('is late'), default=False)
    late_minutes = models.PositiveIntegerField(_('late minutes'), null=True, blank=True)
    remarks = models.TextField(_('remarks'), blank=True)
    marked_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_attendances',
        verbose_name=_('marked by')
    )
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    device_info = models.CharField(_('device information'), max_length=255, blank=True)

    class Meta:
        verbose_name = _('Daily Attendance')
        verbose_name_plural = _('Daily Attendances')
        ordering = ['-date', 'student']
        unique_together = ['student', 'date', 'attendance_session']
        indexes = [
            models.Index(fields=['date', 'status']),
            models.Index(fields=['student', 'date']),
            models.Index(fields=['status', 'date']),
        ]

    def __str__(self):
        return f"{self.student} - {self.date} - {self.status}"

    def clean(self):
        if self.check_in_time and self.check_out_time:
            if self.check_out_time <= self.check_in_time:
                raise ValidationError(_('Check-out time must be after check-in time.'))

    def save(self, *args, **kwargs):
        """Calculate total hours and late status before saving."""
        if self.check_in_time and self.check_out_time:
            # Calculate total hours
            time_diff = self.check_out_time - self.check_in_time
            self.total_hours = round(time_diff.total_seconds() / 3600, 2)

            # Check if late
            session_start = timezone.datetime.combine(self.date, self.attendance_session.start_time)
            session_start = timezone.make_aware(session_start)
            if self.check_in_time > session_start:
                self.is_late = True
                late_delta = self.check_in_time - session_start
                self.late_minutes = int(late_delta.total_seconds() / 60)
            else:
                self.is_late = False
                self.late_minutes = 0

        super().save(*args, **kwargs)

    @property
    def is_present(self):
        """Check if attendance status counts as present."""
        present_statuses = [
            self.AttendanceStatus.PRESENT,
            self.AttendanceStatus.LATE,
            self.AttendanceStatus.HALF_DAY
        ]
        return self.status in present_statuses


class PeriodAttendance(CoreBaseModel):
    """
    Model for period-wise attendance (subject/class specific).
    """
    daily_attendance = models.ForeignKey(
        DailyAttendance,
        on_delete=models.CASCADE,
        related_name='period_attendances',
        verbose_name=_('daily attendance')
    )
    subject = models.ForeignKey(
        'academics.Subject',
        on_delete=models.CASCADE,
        related_name='period_attendances',
        verbose_name=_('subject')
    )
    period_number = models.PositiveIntegerField(_('period number'))
    period_start_time = models.TimeField(_('period start time'))
    period_end_time = models.TimeField(_('period end time'))
    is_present = models.BooleanField(_('is present'), default=False)
    teacher_remarks = models.TextField(_('teacher remarks'), blank=True)
    marked_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_period_attendances',
        verbose_name=_('marked by')
    )

    class Meta:
        verbose_name = _('Period Attendance')
        verbose_name_plural = _('Period Attendances')
        ordering = ['daily_attendance', 'period_number']
        unique_together = ['daily_attendance', 'period_number']
        indexes = [
            models.Index(fields=['daily_attendance', 'is_present']),
            models.Index(fields=['subject', 'is_present']),
        ]

    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.daily_attendance.student} - Period {self.period_number} - {status}"


class LeaveType(CoreBaseModel):
    """
    Model for different types of leaves (sick, casual, etc.).
    """
    name = models.CharField(_('leave type name'), max_length=100)
    code = models.CharField(_('leave code'), max_length=20, unique=True)
    description = models.TextField(_('description'), blank=True)
    max_days_per_year = models.PositiveIntegerField(_('maximum days per year'), default=30)
    requires_approval = models.BooleanField(_('requires approval'), default=True)
    is_paid = models.BooleanField(_('is paid leave'), default=True)
    allowed_for_students = models.BooleanField(_('allowed for students'), default=True)
    allowed_for_teachers = models.BooleanField(_('allowed for teachers'), default=True)
    color = models.CharField(_('color code'), max_length=7, default='#007bff')

    class Meta:
        verbose_name = _('Leave Type')
        verbose_name_plural = _('Leave Types')
        ordering = ['name']

    def __str__(self):
        return self.name


class LeaveApplication(CoreBaseModel):
    """
    Model for managing leave applications.
    """
    class LeaveStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')
        CANCELLED = 'cancelled', _('Cancelled')

    applicant = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='leave_applications',
        verbose_name=_('applicant')
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name=_('leave type')
    )
    start_date = models.DateField(_('start date'), db_index=True)
    end_date = models.DateField(_('end date'), db_index=True)
    total_days = models.PositiveIntegerField(_('total days'))
    reason = models.TextField(_('reason for leave'))
    supporting_documents = models.ManyToManyField(
        'academics.FileAttachment',
        blank=True,
        related_name='leave_applications',
        verbose_name=_('supporting documents')
    )
    status = models.CharField(
        _('leave status'),
        max_length=20,
        choices=LeaveStatus.choices,
        default=LeaveStatus.PENDING
    )
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leaves',
        verbose_name=_('approved by')
    )
    approved_at = models.DateTimeField(_('approved at'), null=True, blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)

    class Meta:
        verbose_name = _('Leave Application')
        verbose_name_plural = _('Leave Applications')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['applicant', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.applicant} - {self.leave_type} - {self.start_date} to {self.end_date}"

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError(_('End date cannot be before start date.'))

    def save(self, *args, **kwargs):
        """Calculate total days before saving."""
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.total_days = delta.days + 1  # Inclusive of both dates
        super().save(*args, **kwargs)

    @property
    def is_approved(self):
        return self.status == self.LeaveStatus.APPROVED

    @property
    def is_pending(self):
        return self.status == self.LeaveStatus.PENDING


class AttendanceSummary(CoreBaseModel):
    """
    Pre-calculated attendance summaries for reporting and analytics.
    """
    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='attendance_summaries',
        verbose_name=_('student')
    )
    academic_session = models.ForeignKey(
        'academics.AcademicSession',
        on_delete=models.CASCADE,
        related_name='attendance_records',
        verbose_name=_('academic session')
    )
    month = models.PositiveIntegerField(_('month'))  # 1-12
    year = models.PositiveIntegerField(_('year'))
    total_school_days = models.PositiveIntegerField(_('total school days'), default=0)
    days_present = models.PositiveIntegerField(_('days present'), default=0)
    days_absent = models.PositiveIntegerField(_('days absent'), default=0)
    days_late = models.PositiveIntegerField(_('days late'), default=0)
    days_half_day = models.PositiveIntegerField(_('days half day'), default=0)
    days_on_leave = models.PositiveIntegerField(_('days on leave'), default=0)
    attendance_percentage = models.DecimalField(
        _('attendance percentage'),
        max_digits=5,
        decimal_places=2,
        default=0.00
    )
    consecutive_absences = models.PositiveIntegerField(_('consecutive absences'), default=0)

    class Meta:
        verbose_name = _('Attendance Summary')
        verbose_name_plural = _('Attendance Summaries')
        unique_together = ['student', 'academic_session', 'month', 'year']
        indexes = [
            models.Index(fields=['student', 'academic_session']),
            models.Index(fields=['attendance_percentage']),
            models.Index(fields=['month', 'year']),
        ]

    def __str__(self):
        return f"{self.student} - {self.month}/{self.year} - {self.attendance_percentage}%"

    def save(self, *args, **kwargs):
        """Calculate attendance percentage before saving."""
        if self.total_school_days > 0:
            self.attendance_percentage = round(
                (self.days_present / self.total_school_days) * 100, 2
            )
        super().save(*args, **kwargs)

    @property
    def total_days_attended(self):
        """Total days with some form of attendance."""
        return self.days_present + self.days_late + self.days_half_day


class BulkAttendanceSession(CoreBaseModel):
    """
    Model for tracking bulk attendance marking sessions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('session name'), max_length=200)
    class_obj = models.ForeignKey(
        'academics.Class',
        on_delete=models.CASCADE,
        related_name='bulk_attendance_sessions',
        verbose_name=_('class')
    )
    date = models.DateField(_('date'))
    attendance_session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name='bulk_sessions',
        verbose_name=_('attendance session')
    )
    marked_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='bulk_attendance_sessions',
        verbose_name=_('marked by')
    )
    total_students = models.PositiveIntegerField(_('total students'), default=0)
    marked_students = models.PositiveIntegerField(_('marked students'), default=0)
    is_completed = models.BooleanField(_('is completed'), default=False)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)

    class Meta:
        verbose_name = _('Bulk Attendance Session')
        verbose_name_plural = _('Bulk Attendance Sessions')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.class_obj} - {self.date}"

    @property
    def progress_percentage(self):
        """Calculate marking progress percentage."""
        if self.total_students > 0:
            return round((self.marked_students / self.total_students) * 100, 2)
        return 0


class AttendanceException(CoreBaseModel):
    """
    Model for handling attendance exceptions and overrides.
    """
    class ExceptionType(models.TextChoices):
        MANUAL_OVERRIDE = 'manual_override', _('Manual Override')
        SYSTEM_CORRECTION = 'system_correction', _('System Correction')
        MAKEUP_CLASS = 'makeup_class', _('Makeup Class')
        SPECIAL_EVENT = 'special_event', _('Special Event')

    daily_attendance = models.ForeignKey(
        DailyAttendance,
        on_delete=models.CASCADE,
        related_name='exceptions',
        verbose_name=_('daily attendance')
    )
    exception_type = models.CharField(
        _('exception type'),
        max_length=20,
        choices=ExceptionType.choices
    )
    original_status = models.CharField(
        _('original status'),
        max_length=20,
        choices=DailyAttendance.AttendanceStatus.choices
    )
    new_status = models.CharField(
        _('new status'),
        max_length=20,
        choices=DailyAttendance.AttendanceStatus.choices
    )
    reason = models.TextField(_('reason for exception'))
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_attendance_exceptions',
        verbose_name=_('approved by')
    )
    effective_date = models.DateTimeField(_('effective date'), auto_now_add=True)

    class Meta:
        verbose_name = _('Attendance Exception')
        verbose_name_plural = _('Attendance Exceptions')
        ordering = ['-effective_date']

    def __str__(self):
        return f"Exception: {self.original_status} → {self.new_status} - {self.daily_attendance}"
