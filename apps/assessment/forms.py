# apps/assessment/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import FileExtensionValidator

from .models import (
    ExamType, GradingSystem, Grade, Exam, ExamAttendance, Mark,
    Assignment, Result, ResultSubject, ReportCard, AssessmentRule,
    QuestionBank, Question, QuestionOption, ExamQuestion, StudentAnswer,
    QuizAttempt, AIGenerationLog
)


class ExamTypeForm(forms.ModelForm):
    """Form for ExamType model."""
    
    class Meta:
        model = ExamType
        fields = ['name', 'code', 'description', 'weightage', 'is_final', 'order', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'code': _('Unique exam type code'),
            'weightage': _('Weightage in percentage for final grade calculation'),
            'order': _('Display order in lists'),
        }

    def clean_weightage(self):
        weightage = self.cleaned_data.get('weightage')
        if weightage and (weightage < 0 or weightage > 100):
            raise ValidationError(_('Weightage must be between 0 and 100 percent.'))
        return weightage

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            existing = ExamType.objects.filter(code=code).exclude(
                pk=self.instance.pk if self.instance else None
            )
            if existing.exists():
                raise ValidationError(_('Exam type code must be unique.'))
        return code


class GradingSystemForm(forms.ModelForm):
    """Form for GradingSystem model."""
    
    class Meta:
        model = GradingSystem
        fields = ['name', 'code', 'description', 'is_active', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            existing = GradingSystem.objects.filter(code=code).exclude(
                pk=self.instance.pk if self.instance else None
            )
            if existing.exists():
                raise ValidationError(_('Grading system code must be unique.'))
        return code


class GradeForm(forms.ModelForm):
    """Form for Grade model with range validation."""
    
    class Meta:
        model = Grade
        fields = [
            'grading_system', 'grade', 'description', 'min_mark', 'max_mark',
            'grade_point', 'remark', 'status'
        ]
        help_texts = {
            'min_mark': _('Minimum percentage for this grade'),
            'max_mark': _('Maximum percentage for this grade'),
            'grade_point': _('Grade point value (0.0 - 4.0)'),
        }

    def clean_min_mark(self):
        min_mark = self.cleaned_data.get('min_mark')
        if min_mark and (min_mark < 0 or min_mark > 100):
            raise ValidationError(_('Minimum mark must be between 0 and 100.'))
        return min_mark

    def clean_max_mark(self):
        max_mark = self.cleaned_data.get('max_mark')
        if max_mark and (max_mark < 0 or max_mark > 100):
            raise ValidationError(_('Maximum mark must be between 0 and 100.'))
        return max_mark

    def clean_grade_point(self):
        grade_point = self.cleaned_data.get('grade_point')
        if grade_point and (grade_point < 0 or grade_point > 4.0):
            raise ValidationError(_('Grade point must be between 0.0 and 4.0.'))
        return grade_point

    def clean(self):
        cleaned_data = super().clean()
        min_mark = cleaned_data.get('min_mark')
        max_mark = cleaned_data.get('max_mark')
        grading_system = cleaned_data.get('grading_system')
        grade = cleaned_data.get('grade')

        if min_mark and max_mark and min_mark >= max_mark:
            self.add_error('min_mark', _('Minimum mark must be less than maximum mark.'))

        # Check for overlapping grade ranges in the same grading system
        if grading_system and grade and min_mark and max_mark:
            overlapping = Grade.objects.filter(
                grading_system=grading_system,
                min_mark__lt=max_mark,
                max_mark__gt=min_mark
            ).exclude(pk=self.instance.pk if self.instance else None)

            if overlapping.exists():
                self.add_error('min_mark', _('Grade range overlaps with existing grade in this grading system.'))

        return cleaned_data


class ExamForm(forms.ModelForm):
    """Form for Exam model with comprehensive validation."""

    # Add exam type with better queryset
    exam_type = forms.ModelChoiceField(
        queryset=ExamType.objects.filter(status='active'),
        empty_label="Select Exam Type",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Exam
        fields = [
            'name', 'code', 'exam_type', 'academic_class', 'subject', 'exam_date',
            'start_time', 'end_time', 'total_marks', 'passing_marks', 'venue',
            'instructions', 'is_published', 'status'
        ]
        widgets = {
            'exam_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'instructions': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'venue': forms.TextInput(attrs={
                'placeholder': _('Exam hall/room'),
                'class': 'form-control'
            }),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'total_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.5'}),
            'passing_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.5'}),
        }
        help_texts = {
            'code': _('Unique exam code identifier'),
            'total_marks': _('Maximum marks for this exam'),
            'passing_marks': _('Minimum marks required to pass'),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Set up exam type queryset
        self.fields['exam_type'].queryset = ExamType.objects.filter(status='active')

        # Set up academic class based on user
        if self.user and hasattr(self.user, 'teacher_profile'):
            teacher = self.user.teacher_profile
            # Limit classes to those taught by the current teacher
            from apps.academics.models import Class, Subject
            self.fields['academic_class'].queryset = Class.objects.filter(
                subject_assignments__teacher=teacher,
                subject_assignments__academic_session__is_current=True
            ).distinct()

            # Set up subjects based on selected class
            self.fields['subject'].queryset = Subject.objects.filter(
                subject_assignments__teacher=teacher,
                subject_assignments__academic_session__is_current=True
            ).distinct()

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            existing = Exam.objects.filter(code=code).exclude(
                pk=self.instance.pk if self.instance else None
            )
            if existing.exists():
                raise ValidationError(_('Exam code must be unique.'))
        return code

    def clean_passing_marks(self):
        passing_marks = self.cleaned_data.get('passing_marks')
        total_marks = self.cleaned_data.get('total_marks')
        
        if passing_marks and total_marks and passing_marks > total_marks:
            raise ValidationError(_('Passing marks cannot exceed total marks.'))
        
        return passing_marks

    def clean_end_time(self):
        end_time = self.cleaned_data.get('end_time')
        start_time = self.cleaned_data.get('start_time')
        
        if end_time and start_time and end_time <= start_time:
            raise ValidationError(_('End time must be after start time.'))
        
        return end_time

    def clean_exam_date(self):
        exam_date = self.cleaned_data.get('exam_date')
        if exam_date and exam_date < timezone.now().date():
            raise ValidationError(_('Exam date cannot be in the past.'))
        return exam_date

    def clean(self):
        cleaned_data = super().clean()
        academic_class = cleaned_data.get('academic_class')
        subject = cleaned_data.get('subject')
        exam_date = cleaned_data.get('exam_date')
        
        # Check if subject belongs to the class
        if academic_class and subject:
            if not academic_class.subjects.filter(pk=subject.pk).exists():
                self.add_error(
                    'subject',
                    _('Selected subject is not taught in this class.')
                )
        
        # Check for exam conflicts
        if academic_class and subject and exam_date:
            conflicting = Exam.objects.filter(
                academic_class=academic_class,
                subject=subject,
                exam_date=exam_date
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if conflicting.exists():
                self.add_error(
                    'exam_date',
                    _('An exam for this subject and class already exists on this date.')
                )
        
        return cleaned_data


class ExamAttendanceForm(forms.ModelForm):
    """Form for ExamAttendance model."""
    
    class Meta:
        model = ExamAttendance
        fields = ['exam', 'student', 'is_present', 'late_minutes', 'remarks']
        widgets = {
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_late_minutes(self):
        late_minutes = self.cleaned_data.get('late_minutes')
        is_present = self.cleaned_data.get('is_present')
        
        if late_minutes and late_minutes > 0 and not is_present:
            raise ValidationError(_('Late minutes can only be set for present students.'))
        
        return late_minutes

    def clean(self):
        cleaned_data = super().clean()
        exam = cleaned_data.get('exam')
        student = cleaned_data.get('student')
        
        if exam and student:
            # Check if student belongs to the exam's class
            if student.current_class != exam.academic_class:
                self.add_error(
                    'student',
                    _('Student does not belong to the exam class.')
                )
        
        return cleaned_data


class MarkForm(forms.ModelForm):
    """Form for Mark model with marks validation."""
    
    class Meta:
        model = Mark
        fields = [
            'exam', 'student', 'marks_obtained', 'is_absent', 'grace_marks',
            'remarks', 'entered_by'
        ]
        widgets = {
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set max_marks from exam if available
        if self.instance and self.instance.exam:
            self.fields['marks_obtained'].help_text = _(
                f'Maximum marks: {self.instance.exam.total_marks}'
            )

    def clean_marks_obtained(self):
        marks_obtained = self.cleaned_data.get('marks_obtained')
        is_absent = self.cleaned_data.get('is_absent')
        exam = self.cleaned_data.get('exam')
        
        if marks_obtained and is_absent:
            raise ValidationError(_('Cannot enter marks for absent students.'))
        
        if marks_obtained and exam and marks_obtained > exam.total_marks:
            raise ValidationError(_(
                'Marks obtained cannot exceed maximum marks (%(max_marks)s).'
            ) % {'max_marks': exam.total_marks})
        
        return marks_obtained

    def clean_grace_marks(self):
        grace_marks = self.cleaned_data.get('grace_marks')
        if grace_marks and grace_marks < 0:
            raise ValidationError(_('Grace marks cannot be negative.'))
        return grace_marks

    def clean(self):
        cleaned_data = super().clean()
        exam = cleaned_data.get('exam')
        student = cleaned_data.get('student')
        marks_obtained = cleaned_data.get('marks_obtained')
        is_absent = cleaned_data.get('is_absent')
        
        if exam and student and student.current_class != exam.academic_class:
            self.add_error(
                'student',
                _('Student does not belong to the exam class.')
            )
        
        # Check if marks already entered
        if exam and student and marks_obtained and not self.instance.pk:
            existing = Mark.objects.filter(exam=exam, student=student)
            if existing.exists():
                self.add_error(
                    'student',
                    _('Marks for this student have already been entered.')
                )
        
        # Validate that either marks or absence is set
        if not is_absent and not marks_obtained:
            self.add_error(
                'marks_obtained',
                _('Either enter marks or mark as absent.')
            )
        
        return cleaned_data


class AssignmentForm(forms.ModelForm):
    """Form for Assignment model with comprehensive validation."""
    
    class Meta:
        model = Assignment
        fields = [
            # Basic Information
            'title', 'assignment_type', 'description', 'instructions',
            
            # Academic Context
            'subject', 'teacher', 'academic_session', 'academic_class', 'class_assigned',
            
            # Timing & Dates
            'publish_date', 'due_date', 'assigned_date',
            
            # Grading & Marks
            'total_marks', 'passing_marks', 'weightage', 'grading_criteria',
            
            # Submission Management
            'allow_late_submissions', 'late_submission_penalty', 'max_submission_attempts',
            
            # File Management
            'attachment', 'max_file_size',
            
            # Additional Features
            'tags', 'is_published', 'display_order', 'status'
        ]
        widgets = {
            'publish_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'assigned_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 5}),
            'instructions': forms.Textarea(attrs={'rows': 4}),
            'grading_criteria': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.TextInput(attrs={
                'placeholder': _('Comma-separated tags')
            }),
        }
        help_texts = {
            'weightage': _('Weightage in percentage for final grade'),
            'late_submission_penalty': _('Percentage penalty for late submissions'),
            'max_file_size': _('Maximum file size for submissions in bytes'),
        }

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        publish_date = self.cleaned_data.get('publish_date')
        
        if due_date and publish_date and due_date <= publish_date:
            raise ValidationError(_('Due date must be after publish date.'))
        
        return due_date

    def clean_passing_marks(self):
        passing_marks = self.cleaned_data.get('passing_marks')
        total_marks = self.cleaned_data.get('total_marks')
        
        if passing_marks and total_marks and passing_marks > total_marks:
            raise ValidationError(_('Passing marks cannot exceed total marks.'))
        
        return passing_marks

    def clean_weightage(self):
        weightage = self.cleaned_data.get('weightage')
        if weightage and (weightage < 0 or weightage > 100):
            raise ValidationError(_('Weightage must be between 0 and 100 percent.'))
        return weightage

    def clean_late_submission_penalty(self):
        penalty = self.cleaned_data.get('late_submission_penalty')
        if penalty and (penalty < 0 or penalty > 100):
            raise ValidationError(_('Late submission penalty must be between 0 and 100 percent.'))
        return penalty

    def clean_max_submission_attempts(self):
        attempts = self.cleaned_data.get('max_submission_attempts')
        if attempts and attempts > 10:
            raise ValidationError(_('Maximum submission attempts cannot exceed 10.'))
        return attempts

    def clean(self):
        cleaned_data = super().clean()
        subject = cleaned_data.get('subject')
        academic_class = cleaned_data.get('academic_class')
        class_assigned = cleaned_data.get('class_assigned')
        
        # Ensure at least one class is set
        if not academic_class and not class_assigned:
            self.add_error(
                'academic_class',
                _('Either academic_class or class_assigned must be set.')
            )
        
        # Validate subject belongs to class
        if subject and academic_class:
            if not academic_class.subjects.filter(pk=subject.pk).exists():
                self.add_error(
                    'subject',
                    _('Selected subject is not taught in this class.')
                )
        
        return cleaned_data


class AssignmentSubmissionForm(forms.ModelForm):
    """Form for student assignment submissions."""
    
    class Meta:
        model = Assignment
        fields = [
            'submission_text', 'submission_attachment', 'submission_status'
        ]
        widgets = {
            'submission_text': forms.Textarea(attrs={
                'rows': 8,
                'placeholder': _('Enter your submission here...')
            }),
            'submission_status': forms.HiddenInput(),  # Auto-managed
        }
        help_texts = {
            'submission_attachment': _('Upload your submission file'),
        }

    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop('assignment', None)
        self.student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)
        
        if self.assignment:
            # Set file size limit based on assignment
            self.fields['submission_attachment'].validators.append(
                FileExtensionValidator(
                    allowed_extensions=['pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'zip', 
                                      'jpg', 'jpeg', 'png', 'mp4', 'mp3']
                )
            )

    def clean_submission_attachment(self):
        attachment = self.cleaned_data.get('submission_attachment')
        if attachment and self.assignment:
            if attachment.size > self.assignment.max_file_size:
                raise ValidationError(_(
                    'File size exceeds maximum allowed size of %(max_size)s MB.'
                ) % {'max_size': self.assignment.max_file_size // (1024 * 1024)})
        return attachment

    def clean(self):
        cleaned_data = super().clean()
        submission_text = cleaned_data.get('submission_text')
        submission_attachment = cleaned_data.get('submission_attachment')
        
        # Require either text or attachment
        if not submission_text and not submission_attachment:
            raise ValidationError(_(
                'Either submission text or attachment is required.'
            ))
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set assignment and student
        if self.assignment:
            # Create a new submission instance
            submission = Assignment.create_assignment_template(**{
                field.name: getattr(self.assignment, field.name)
                for field in Assignment._meta.fields
                if field.name not in ['id', 'pk']
            })
            submission.student = self.student
            submission.original_submission = self.assignment
            
            # Copy submission data
            for field in ['submission_text', 'submission_attachment', 'submission_status']:
                setattr(submission, field, self.cleaned_data.get(field))
            
            submission.submission_date = timezone.now()
            
            if commit:
                submission.save()
            return submission
        
        return instance


class ResultForm(forms.ModelForm):
    """Form for Result model."""
    
    class Meta:
        model = Result
        fields = [
            'student', 'academic_class', 'exam_type', 'total_marks', 'marks_obtained',
            'percentage', 'grade', 'rank', 'total_students', 'attendance_percentage',
            'remarks', 'is_promoted', 'promoted_to_class', 'status'
        ]
        widgets = {
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_marks_obtained(self):
        marks_obtained = self.cleaned_data.get('marks_obtained')
        total_marks = self.cleaned_data.get('total_marks')
        
        if marks_obtained and total_marks and marks_obtained > total_marks:
            raise ValidationError(_('Marks obtained cannot exceed total marks.'))
        
        return marks_obtained

    def clean_percentage(self):
        percentage = self.cleaned_data.get('percentage')
        if percentage and (percentage < 0 or percentage > 100):
            raise ValidationError(_('Percentage must be between 0 and 100.'))
        return percentage

    def clean_attendance_percentage(self):
        attendance_percentage = self.cleaned_data.get('attendance_percentage')
        if attendance_percentage and (attendance_percentage < 0 or attendance_percentage > 100):
            raise ValidationError(_('Attendance percentage must be between 0 and 100.'))
        return attendance_percentage

    def clean_rank(self):
        rank = self.cleaned_data.get('rank')
        total_students = self.cleaned_data.get('total_students')
        
        if rank and total_students and rank > total_students:
            raise ValidationError(_('Rank cannot exceed total number of students.'))
        
        return rank

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        academic_class = cleaned_data.get('academic_class')
        is_promoted = cleaned_data.get('is_promoted')
        promoted_to_class = cleaned_data.get('promoted_to_class')
        
        if student and academic_class and student.current_class != academic_class:
            self.add_error(
                'student',
                _('Student does not belong to this class.')
            )
        
        if is_promoted and not promoted_to_class:
            self.add_error(
                'promoted_to_class',
                _('Promoted to class must be specified when student is promoted.')
            )
        
        return cleaned_data


class ResultSubjectForm(forms.ModelForm):
    """Form for ResultSubject model."""
    
    class Meta:
        model = ResultSubject
        fields = [
            'result', 'subject', 'marks_obtained', 'max_marks', 'percentage', 'grade'
        ]

    def clean_marks_obtained(self):
        marks_obtained = self.cleaned_data.get('marks_obtained')
        max_marks = self.cleaned_data.get('max_marks')
        
        if marks_obtained and max_marks and marks_obtained > max_marks:
            raise ValidationError(_('Marks obtained cannot exceed maximum marks.'))
        
        return marks_obtained

    def clean_percentage(self):
        percentage = self.cleaned_data.get('percentage')
        if percentage and (percentage < 0 or percentage > 100):
            raise ValidationError(_('Percentage must be between 0 and 100.'))
        return percentage

    def clean(self):
        cleaned_data = super().clean()
        result = cleaned_data.get('result')
        subject = cleaned_data.get('subject')
        
        if result and subject:
            # Check if subject belongs to result's class
            if not result.academic_class.subjects.filter(pk=subject.pk).exists():
                self.add_error(
                    'subject',
                    _('Subject is not part of this class curriculum.')
                )
        
        return cleaned_data


class ReportCardForm(forms.ModelForm):
    """Form for ReportCard model."""
    
    class Meta:
        model = ReportCard
        fields = [
            'student', 'academic_class', 'exam_type', 'result', 'generated_by',
            'is_approved', 'approved_by', 'comments', 'parent_signature'
        ]
        widgets = {
            'comments': forms.Textarea(attrs={'rows': 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        academic_class = cleaned_data.get('academic_class')
        result = cleaned_data.get('result')
        
        if student and academic_class and student.current_class != academic_class:
            self.add_error(
                'student',
                _('Student does not belong to this class.')
            )
        
        if result and (result.student != student or result.academic_class != academic_class):
            self.add_error(
                'result',
                _('Result does not match the selected student and class.')
            )
        
        return cleaned_data


class AssessmentRuleForm(forms.ModelForm):
    """Form for AssessmentRule model."""
    
    class Meta:
        model = AssessmentRule
        fields = ['name', 'key', 'value', 'description', 'applies_to', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'value': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': _('Enter JSON configuration')
            }),
        }

    def clean_key(self):
        key = self.cleaned_data.get('key')
        if key:
            existing = AssessmentRule.objects.filter(key=key).exclude(
                pk=self.instance.pk if self.instance else None
            )
            if existing.exists():
                raise ValidationError(_('Rule key must be unique.'))
        return key

    def clean_value(self):
        value = self.cleaned_data.get('value')
        import json
        try:
            if value:
                json.loads(value)
        except json.JSONDecodeError:
            raise ValidationError(_('Value must be valid JSON.'))
        return value


# Search and Filter Forms
class ExamSearchForm(forms.Form):
    """Form for searching exams."""
    
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by exam name...')})
    )
    exam_type = forms.ModelChoiceField(
        required=False,
        queryset=ExamType.objects.all(),
        empty_label=_('All Exam Types')
    )
    academic_class = forms.ModelChoiceField(
        required=False,
        queryset=None,  # Will be set in view
        empty_label=_('All Classes')
    )
    subject = forms.ModelChoiceField(
        required=False,
        queryset=None,  # Will be set in view
        empty_label=_('All Subjects')
    )
    exam_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('From Date')
    )
    exam_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('To Date')
    )
    is_published = forms.BooleanField(
        required=False,
        label=_('Published Exams Only')
    )


class AssignmentSearchForm(forms.Form):
    """Form for searching assignments."""
    
    title = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by title...')})
    )
    assignment_type = forms.ChoiceField(
        required=False,
        choices=[('', _('All Types'))] + list(Assignment.AssignmentType.choices)
    )
    subject = forms.ModelChoiceField(
        required=False,
        queryset=None,  # Will be set in view
        empty_label=_('All Subjects')
    )
    teacher = forms.ModelChoiceField(
        required=False,
        queryset=None,  # Will be set in view
        empty_label=_('All Teachers')
    )
    due_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Due Date From')
    )
    due_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Due Date To')
    )
    is_published = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Published Assignments Only')
    )


class ResultSearchForm(forms.Form):
    """Form for searching results."""
    
    student_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by student name...')})
    )
    academic_class = forms.ModelChoiceField(
        required=False,
        queryset=None,  # Will be set in view
        empty_label=_('All Classes')
    )
    exam_type = forms.ModelChoiceField(
        required=False,
        queryset=ExamType.objects.all(),
        empty_label=_('All Exam Types')
    )
    min_percentage = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=100,
        label=_('Minimum Percentage')
    )
    max_percentage = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=100,
        label=_('Maximum Percentage')
    )

    def clean(self):
        cleaned_data = super().clean()
        min_percentage = cleaned_data.get('min_percentage')
        max_percentage = cleaned_data.get('max_percentage')
        
        if min_percentage and max_percentage and min_percentage > max_percentage:
            self.add_error('min_percentage', _('Minimum percentage cannot exceed maximum percentage.'))
        
        return cleaned_data


# Bulk Operations Forms
class BulkMarkEntryForm(forms.Form):
    """Form for bulk mark entry."""
    
    exam = forms.ModelChoiceField(
        queryset=Exam.objects.all(),
        label=_('Exam')
    )
    marks_file = forms.FileField(
        label=_('Marks File'),
        help_text=_('CSV file with student IDs and marks'),
        validators=[FileExtensionValidator(allowed_extensions=['csv'])]
    )
    overwrite_existing = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Overwrite Existing Marks'),
        help_text=_('Overwrite marks that have already been entered')
    )


class BulkAssignmentCreationForm(forms.Form):
    """Form for bulk assignment creation."""
    
    template_assignment = forms.ModelChoiceField(
        queryset=Assignment.objects.filter(student__isnull=True),
        label=_('Template Assignment'),
        help_text=_('Select an assignment to use as template')
    )
    classes = forms.ModelMultipleChoiceField(
        queryset=None,  # Will be set in view
        widget=forms.SelectMultiple(attrs={'class': 'select2'}),
        label=_('Target Classes'),
        help_text=_('Select classes to create assignments for')
    )
    due_date_offset = forms.IntegerField(
        initial=7,
        min_value=1,
        max_value=30,
        label=_('Due Date Offset (Days)'),
        help_text=_('Days from today to set as due date')
    )


class GradeAssignmentForm(forms.Form):
    """Form for grading assignments."""

    marks_obtained = forms.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=0,
        label=_('Marks Obtained')
    )
    feedback = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': _('Enter feedback for student...')}),
        label=_('Teacher Feedback')
    )
    rubric_scores = forms.JSONField(
        required=False,
        label=_('Rubric Scores'),
        help_text=_('JSON object with rubric criteria and scores')
    )

    def clean_marks_obtained(self):
        marks_obtained = self.cleaned_data.get('marks_obtained')
        # Max marks validation will be done in the view using assignment context
        return marks_obtained


# Question Bank and Question Forms
class QuestionBankForm(forms.ModelForm):
    """Form for QuestionBank model."""

    class Meta:
        model = QuestionBank
        fields = [
            'name', 'description', 'subject', 'academic_class', 'topic',
            'difficulty_level', 'is_active', 'status'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)

        if self.teacher:
            # Limit classes to those taught by the teacher
            from apps.academics.models import Class
            self.fields['academic_class'].queryset = Class.objects.filter(
                subject_assignments__teacher=self.teacher,
                subject_assignments__academic_session__is_current=True
            ).distinct()

            # Limit subjects to those taught by the teacher
            from apps.academics.models import Subject
            self.fields['subject'].queryset = Subject.objects.filter(
                subject_assignments__teacher=self.teacher,
                subject_assignments__academic_session__is_current=True
            ).distinct()


class QuestionForm(forms.ModelForm):
    """Form for Question model."""

    class Meta:
        model = Question
        fields = [
            'question_bank', 'question_type', 'question_text', 'explanation',
            'marks', 'time_limit', 'difficulty_level', 'tags', 'is_active'
        ]
        widgets = {
            'question_text': forms.Textarea(attrs={'rows': 4}),
            'explanation': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)

        if self.teacher:
            # Limit question banks to those accessible by the teacher
            from apps.academics.models import Class
            taught_classes = Class.objects.filter(
                subject_assignments__teacher=self.teacher,
                subject_assignments__academic_session__is_current=True
            ).distinct()

            self.fields['question_bank'].queryset = QuestionBank.objects.filter(
                academic_class__in=taught_classes,
                is_active=True
            )


class QuestionOptionForm(forms.ModelForm):
    """Form for QuestionOption model."""

    class Meta:
        model = QuestionOption
        fields = ['option_text', 'is_correct', 'order']
        widgets = {
            'option_text': forms.Textarea(attrs={'rows': 2}),
        }


class QuestionOptionFormSet(forms.BaseModelFormSet):
    """Formset for question options."""

    def __init__(self, *args, **kwargs):
        self.question_type = kwargs.pop('question_type', None)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['question_type'] = self.question_type
        return super()._construct_form(i, **kwargs)


class ExamQuestionForm(forms.ModelForm):
    """Form for ExamQuestion model."""

    class Meta:
        model = ExamQuestion
        fields = ['question', 'marks', 'order', 'time_limit']

    def __init__(self, *args, **kwargs):
        self.exam = kwargs.pop('exam', None)
        super().__init__(*args, **kwargs)

        if self.exam:
            # Limit questions to those from the exam's subject and class
            self.fields['question'].queryset = Question.objects.filter(
                question_bank__subject=self.exam.subject,
                question_bank__academic_class=self.exam.academic_class,
                is_active=True
            )


class StudentAnswerForm(forms.ModelForm):
    """Form for StudentAnswer model."""

    class Meta:
        model = StudentAnswer
        fields = ['answer_text', 'selected_options']
        widgets = {
            'answer_text': forms.Textarea(attrs={'rows': 4}),
            'selected_options': forms.MultipleChoiceField(
                required=False,
                widget=forms.CheckboxSelectMultiple
            ),
        }

    def __init__(self, *args, **kwargs):
        self.exam_question = kwargs.pop('exam_question', None)
        super().__init__(*args, **kwargs)

        if self.exam_question:
            question = self.exam_question.question

            # Set up selected_options field based on question type
            if question.question_type in ['multiple_choice', 'true_false']:
                options = question.options.all()
                self.fields['selected_options'] = forms.MultipleChoiceField(
                    choices=[(opt.id, opt.option_text) for opt in options],
                    required=False,
                    widget=forms.CheckboxSelectMultiple if question.question_type == 'multiple_choice' else forms.RadioSelect
                )

            # Hide answer_text for objective questions
            if question.question_type in ['multiple_choice', 'true_false']:
                self.fields['answer_text'].widget = forms.HiddenInput()
            else:
                self.fields['selected_options'].widget = forms.HiddenInput()


class ExamCompositionForm(forms.Form):
    """Form for composing exams from question banks."""

    question_bank = forms.ModelChoiceField(
        queryset=QuestionBank.objects.filter(is_active=True),
        label=_('Question Bank')
    )
    num_multiple_choice = forms.IntegerField(
        min_value=0,
        max_value=50,
        initial=0,
        label=_('Number of Multiple Choice Questions')
    )
    num_true_false = forms.IntegerField(
        min_value=0,
        max_value=50,
        initial=0,
        label=_('Number of True/False Questions')
    )
    num_short_answer = forms.IntegerField(
        min_value=0,
        max_value=50,
        initial=0,
        label=_('Number of Short Answer Questions')
    )
    num_essay = forms.IntegerField(
        min_value=0,
        max_value=50,
        initial=0,
        label=_('Number of Essay Questions')
    )
    marks_per_multiple_choice = forms.DecimalField(
        max_digits=4,
        decimal_places=2,
        initial=1.0,
        min_value=0.5,
        label=_('Marks per Multiple Choice Question')
    )
    marks_per_true_false = forms.DecimalField(
        max_digits=4,
        decimal_places=2,
        initial=1.0,
        min_value=0.5,
        label=_('Marks per True/False Question')
    )
    randomize_order = forms.BooleanField(
        initial=True,
        required=False,
        label=_('Randomize Question Order')
    )

    def __init__(self, *args, **kwargs):
        self.exam = kwargs.pop('exam', None)
        super().__init__(*args, **kwargs)

        if self.exam:
            # Limit question banks to exam's subject and class
            self.fields['question_bank'].queryset = QuestionBank.objects.filter(
                subject=self.exam.subject,
                academic_class=self.exam.academic_class,
                is_active=True
            )


# AI Question Generation Forms
class AIQuestionGenerationForm(forms.Form):
    """Form for AI question generation."""

    topic = forms.CharField(
        max_length=255,
        label=_('Topic'),
        help_text=_('Enter the topic for question generation'),
        widget=forms.TextInput(attrs={'placeholder': _('e.g., Photosynthesis, World War II, Algebra')})
    )
    count = forms.IntegerField(
        min_value=1,
        max_value=10,
        initial=5,
        label=_('Number of Questions'),
        help_text=_('Maximum 10 questions per generation')
    )
    difficulty = forms.ChoiceField(
        choices=[
            ('easy', _('Easy')),
            ('medium', _('Medium')),
            ('hard', _('Hard')),
            ('expert', _('Expert'))
        ],
        initial='medium',
        label=_('Difficulty Level')
    )
    question_types = forms.MultipleChoiceField(
        choices=[
            ('multiple_choice', _('Multiple Choice')),
            ('true_false', _('True/False')),
            ('short_answer', _('Short Answer'))
        ],
        initial=['multiple_choice'],
        widget=forms.CheckboxSelectMultiple,
        label=_('Question Types'),
        help_text=_('Select the types of questions to generate')
    )

    def clean_topic(self):
        topic = self.cleaned_data.get('topic')
        if not topic or len(topic.strip()) < 3:
            raise ValidationError(_('Topic must be at least 3 characters long.'))
        return topic.strip()


class QuizAttemptForm(forms.ModelForm):
    """Form for QuizAttempt model (for quiz creation/configuration)."""

    class Meta:
        model = QuizAttempt
        fields = []  # This form is for starting attempts, not editing

    def __init__(self, *args, **kwargs):
        self.question_bank = kwargs.pop('question_bank', None)
        self.student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        """Create a new quiz attempt."""
        if not self.question_bank or not self.student:
            raise ValueError("Question bank and student are required")

        # Check if student already has an incomplete attempt
        existing_attempt = QuizAttempt.objects.filter(
            student=self.student,
            question_bank=self.question_bank,
            complete=False
        ).first()

        if existing_attempt:
            return existing_attempt

        # Check single attempt restriction
        if self.question_bank.single_attempt:
            completed_attempts = QuizAttempt.objects.filter(
                student=self.student,
                question_bank=self.question_bank,
                complete=True
            )
            if completed_attempts.exists():
                raise ValidationError(_('You have already completed this quiz and multiple attempts are not allowed.'))

        # Create new attempt
        attempt = QuizAttempt(
            student=self.student,
            question_bank=self.question_bank,
            max_score=self.question_bank.questions.filter(is_active=True).count()
        )

        # Set up question order
        questions = list(self.question_bank.questions.filter(is_active=True))

        if self.question_bank.random_order:
            import random
            random.shuffle(questions)

        question_ids = [str(q.id) for q in questions]
        attempt.question_order = ",".join(question_ids) + ","
        attempt.question_list = attempt.question_order

        if commit:
            attempt.save()

        return attempt


class QuizAnswerForm(forms.Form):
    """Form for submitting quiz answers."""

    question_id = forms.IntegerField(widget=forms.HiddenInput())
    answer_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'quiz-answer-input'})
    )
    selected_options = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text=_('Comma-separated list of selected option IDs')
    )

    def __init__(self, *args, **kwargs):
        self.question = kwargs.pop('question', None)
        super().__init__(*args, **kwargs)

        if self.question:
            # Configure form based on question type
            if self.question.question_type in ['multiple_choice', 'true_false']:
                options = self.question.options.all()
                if self.question.question_type == 'multiple_choice':
                    self.fields['selected_options'] = forms.MultipleChoiceField(
                        choices=[(opt.id, opt.option_text) for opt in options],
                        widget=forms.CheckboxSelectMultiple,
                        required=False
                    )
                else:  # true_false
                    self.fields['selected_options'] = forms.ChoiceField(
                        choices=[(opt.id, opt.option_text) for opt in options],
                        widget=forms.RadioSelect,
                        required=False
                    )
                # Hide text input for objective questions
                self.fields['answer_text'].widget = forms.HiddenInput()

            elif self.question.question_type == 'short_answer':
                self.fields['selected_options'].widget = forms.HiddenInput()
                self.fields['answer_text'].widget.attrs.update({
                    'placeholder': _('Enter your answer here...'),
                    'maxlength': '500'
                })

            else:  # essay
                self.fields['selected_options'].widget = forms.HiddenInput()
                self.fields['answer_text'].widget.attrs.update({
                    'placeholder': _('Write your detailed answer here...'),
                    'rows': '6'
                })


class GPAReportForm(forms.Form):
    """Form for generating GPA reports."""

    student = forms.ModelChoiceField(
        queryset=None,  # Will be set in view
        required=False,
        label=_('Student'),
        help_text=_('Leave empty to show all students')
    )
    semester = forms.CharField(
        max_length=100,
        required=False,
        label=_('Semester'),
        help_text=_('e.g., First Semester, Second Semester')
    )
    level = forms.CharField(
        max_length=100,
        required=False,
        label=_('Academic Level'),
        help_text=_('e.g., 100 Level, 200 Level')
    )
    include_subjects = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Include Subject Breakdown'),
        help_text=_('Show detailed subject-wise performance')
    )
    report_type = forms.ChoiceField(
        choices=[
            ('gpa', _('GPA Only')),
            ('cgpa', _('CGPA Only')),
            ('both', _('Both GPA and CGPA'))
        ],
        initial='both',
        label=_('Report Type')
    )

    def __init__(self, *args, **kwargs):
        self.teacher = kwargs.pop('teacher', None)
        super().__init__(*args, **kwargs)

        if self.teacher:
            # Limit students to those in classes taught by the teacher
            from apps.academics.models import Class
            taught_classes = Class.objects.filter(
                subject_assignments__teacher=self.teacher,
                subject_assignments__academic_session__is_current=True
            ).distinct()

            self.fields['student'].queryset = None  # Will be populated in view if needed


class AIGenerationLogForm(forms.ModelForm):
    """Form for viewing AI generation logs."""

    class Meta:
        model = AIGenerationLog
        fields = ['model_used', 'topic', 'question_count', 'success', 'error_message']
        widgets = {
            'error_message': forms.Textarea(attrs={'rows': 3, 'readonly': True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields readonly for viewing
        for field in self.fields:
            self.fields[field].widget.attrs['readonly'] = True
