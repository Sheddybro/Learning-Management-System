# apps/communication/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.timezone import make_aware, is_naive
from django.core.validators import MinLengthValidator, MaxLengthValidator

from .models import (
    Announcement, Message, MessageRecipient, NoticeBoard,
    NoticeBoardItem, EmailTemplate, SMSTemplate, SentEmail, SentSMS,
    EmergencyAlert, AlertRecipient, EmergencyProtocol
)
from apps.users.models import User
from apps.academics.models import Class, Student, Teacher


class AnnouncementForm(forms.ModelForm):
    """Form for creating and updating announcements."""
    
    # Custom fields for better UX
    schedule_type = forms.ChoiceField(
        choices=[
            ('immediate', _('Publish Immediately')),
            ('schedule', _('Schedule Publishing')),
        ],
        initial='immediate',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label=_('Publishing Schedule')
    )
    
    pin_duration = forms.ChoiceField(
        choices=[
            ('none', _('Do Not Pin')),
            ('1day', _('1 Day')),
            ('3days', _('3 Days')),
            ('1week', _('1 Week')),
            ('custom', _('Custom Duration')),
        ],
        initial='none',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Pin Duration'),
        required=False
    )
    
    class Meta:
        model = Announcement
        fields = [
            'title', 'content', 'announcement_type', 'priority', 
            'target_audience', 'banner_image', 'attachments',
            'specific_users', 'specific_classes', 'expires_at',
            'schedule_publish', 'is_pinned'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter announcement title')
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': _('Enter announcement content')
            }),
            'announcement_type': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'target_audience': forms.Select(attrs={'class': 'form-control'}),
            'banner_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'attachments': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'specific_users': forms.SelectMultiple(attrs={
                'class': 'form-control select2-multiple',
                'data-placeholder': _('Select specific users')
            }),
            'specific_classes': forms.SelectMultiple(attrs={
                'class': 'form-control select2-multiple',
                'data-placeholder': _('Select specific classes')
            }),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'schedule_publish': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'is_pinned': forms.HiddenInput(),  # Handled by pin_duration field
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['specific_users'].queryset = User.objects.filter(is_active=True)
        self.fields['specific_classes'].queryset = Class.objects.filter(status='active')
        
        # Set initial values for custom fields
        if self.instance and self.instance.pk:
            if self.instance.schedule_publish and self.instance.schedule_publish > timezone.now():
                self.fields['schedule_type'].initial = 'schedule'
            
            if self.instance.is_pinned and self.instance.pin_until:
                pin_delta = self.instance.pin_until - timezone.now()
                if pin_delta.days == 1:
                    self.fields['pin_duration'].initial = '1day'
                elif pin_delta.days == 3:
                    self.fields['pin_duration'].initial = '3days'
                elif pin_delta.days == 7:
                    self.fields['pin_duration'].initial = '1week'
                else:
                    self.fields['pin_duration'].initial = 'custom'
    
    def clean(self):
        cleaned_data = super().clean()
        schedule_type = cleaned_data.get('schedule_type')
        schedule_publish = cleaned_data.get('schedule_publish')
        expires_at = cleaned_data.get('expires_at')
        target_audience = cleaned_data.get('target_audience')
        specific_users = cleaned_data.get('specific_users')
        specific_classes = cleaned_data.get('specific_classes')
        
        # Validate scheduling
        if schedule_type == 'schedule' and not schedule_publish:
            raise ValidationError(_('Scheduled publish date is required when scheduling publishing.'))
        
        if schedule_publish and schedule_publish <= timezone.now():
            raise ValidationError(_('Scheduled publish date must be in the future.'))
        
        # Validate expiration
        if expires_at and schedule_publish and expires_at <= schedule_publish:
            raise ValidationError(_('Expiration date must be after publish date.'))
        
        # Validate specific targeting
        if target_audience == 'specific' and not specific_users:
            raise ValidationError(_('Specific users must be selected when target audience is "Specific Users".'))

        if target_audience == 'specific' and not specific_users.exists():
            raise ValidationError(_('At least one specific user must be selected.'))

        # Make datetime fields timezone-aware if they are naive
        if schedule_publish and is_naive(schedule_publish):
            cleaned_data['schedule_publish'] = make_aware(schedule_publish)

        if expires_at and is_naive(expires_at):
            cleaned_data['expires_at'] = make_aware(expires_at)

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Handle publishing schedule
        if self.cleaned_data['schedule_type'] == 'immediate':
            instance.is_published = True
            instance.published_at = timezone.now()
        else:
            instance.is_published = False
        
        # Handle pin duration
        pin_duration = self.cleaned_data.get('pin_duration')
        if pin_duration == 'none':
            instance.is_pinned = False
            instance.pin_until = None
        else:
            instance.is_pinned = True
            if pin_duration == '1day':
                instance.pin_until = timezone.now() + timezone.timedelta(days=1)
            elif pin_duration == '3days':
                instance.pin_until = timezone.now() + timezone.timedelta(days=3)
            elif pin_duration == '1week':
                instance.pin_until = timezone.now() + timezone.timedelta(days=7)
            # For custom, pin_until should be set via the form field
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


class MessageForm(forms.ModelForm):
    """Form for creating and sending messages."""
    
    recipient_type = forms.ChoiceField(
        choices=[
            ('individual', _('Individual Users')),
            ('class', _('Entire Class')),
            ('role', _('By Role')),
        ],
        initial='individual',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label=_('Recipient Type')
    )
    
    selected_class = forms.ModelChoiceField(
        queryset=Class.objects.filter(status='active'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Select Class')
    )
    
    selected_role = forms.ChoiceField(
        choices=[
            ('', _('Select Role')),
            ('students', _('All Students')),
            ('teachers', _('All Teachers')),
            ('parents', _('All Parents')),
            ('staff', _('All Staff')),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Select Role')
    )
    
    class Meta:
        model = Message
        fields = [
            'subject', 'content', 'message_type', 'priority',
            'is_important', 'requires_confirmation', 'attachments', 'sender'
        ]
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter message subject')
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': _('Enter message content')
            }),
            'message_type': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'attachments': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'sender': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if self.request and hasattr(self.request, 'user'):
            self.fields['sender'].initial = self.request.user
    
    def clean(self):
        cleaned_data = super().clean()
        recipient_type = cleaned_data.get('recipient_type')
        selected_class = cleaned_data.get('selected_class')
        selected_role = cleaned_data.get('selected_role')
        
        if recipient_type == 'class' and not selected_class:
            raise ValidationError(_('Please select a class when sending to entire class.'))
        
        if recipient_type == 'role' and not selected_role:
            raise ValidationError(_('Please select a role when sending by role.'))
        
        return cleaned_data
    
    def get_recipients(self):
        """Get recipients based on the selected recipient type."""
        recipient_type = self.cleaned_data.get('recipient_type')
        selected_class = self.cleaned_data.get('selected_class')
        selected_role = self.cleaned_data.get('selected_role')
        
        recipients = User.objects.filter(is_active=True)
        
        if recipient_type == 'class' and selected_class:
            # Get students and teachers from the selected class
            from apps.academics.models import Enrollment, SubjectAssignment
            student_ids = Enrollment.objects.filter(
                class_enrolled=selected_class,
                enrollment_status='active'
            ).values_list('student__user', flat=True)
            
            teacher_ids = SubjectAssignment.objects.filter(
                class_assigned=selected_class
            ).values_list('teacher__user', flat=True)
            
            recipient_ids = set(list(student_ids) + list(teacher_ids))
            recipients = recipients.filter(id__in=recipient_ids)
        
        elif recipient_type == 'role' and selected_role:
            if selected_role == 'students':
                recipients = recipients.filter(student_profile__isnull=False)
            elif selected_role == 'teachers':
                recipients = recipients.filter(teacher_profile__isnull=False)
            elif selected_role == 'parents':
                recipients = recipients.filter(parent_profile__isnull=False)
            elif selected_role == 'staff':
                recipients = recipients.filter(is_staff=True)
        
        return recipients


class NoticeBoardForm(forms.ModelForm):
    """Form for creating and updating notice boards."""
    
    class Meta:
        model = NoticeBoard
        fields = [
            'name', 'board_type', 'description', 'location',
            'is_active', 'refresh_interval', 'allowed_users'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter notice board name')
            }),
            'board_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Enter notice board description')
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter physical location')
            }),
            'refresh_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '5',
                'max': '300'
            }),
            'allowed_users': forms.SelectMultiple(attrs={
                'class': 'form-control select2-multiple',
                'data-placeholder': _('Select allowed users')
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['allowed_users'].queryset = User.objects.filter(is_active=True)


class NoticeBoardItemForm(forms.ModelForm):
    """Form for adding announcements to notice boards."""
    
    class Meta:
        model = NoticeBoardItem
        fields = [
            'notice_board', 'announcement', 'display_order',
            'is_active', 'start_display', 'end_display', 'display_duration'
        ]
        widgets = {
            'notice_board': forms.Select(attrs={'class': 'form-control'}),
            'announcement': forms.Select(attrs={'class': 'form-control'}),
            'display_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'start_display': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_display': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'display_duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '5',
                'max': '300'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['notice_board'].queryset = NoticeBoard.objects.filter(is_active=True)
        self.fields['announcement'].queryset = Announcement.objects.filter(
            is_published=True,
            status='active'
        )
    
    def clean(self):
        cleaned_data = super().clean()
        start_display = cleaned_data.get('start_display')
        end_display = cleaned_data.get('end_display')

        if start_display and end_display and end_display <= start_display:
            raise ValidationError(_('End display time must be after start display time.'))

        # Make datetime fields timezone-aware if they are naive
        if start_display and is_naive(start_display):
            cleaned_data['start_display'] = make_aware(start_display)

        if end_display and is_naive(end_display):
            cleaned_data['end_display'] = make_aware(end_display)

        return cleaned_data


class EmailTemplateForm(forms.ModelForm):
    """Form for creating and updating email templates."""
    
    class Meta:
        model = EmailTemplate
        fields = [
            'name', 'template_type', 'subject', 'body_html',
            'body_text', 'language', 'is_active', 'variables'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter template name')
            }),
            'template_type': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter email subject')
            }),
            'body_html': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 12,
                'placeholder': _('Enter HTML content. Use {{ variable_name }} for dynamic content.')
            }),
            'body_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': _('Enter plain text content. Use {{ variable_name }} for dynamic content.')
            }),
            'language': forms.Select(attrs={'class': 'form-control'}),
            'variables': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Enter available variables in JSON format')
            }),
        }
    
    def clean_variables(self):
        variables = self.cleaned_data.get('variables')
        if variables:
            try:
                import json
                json.loads(variables)
            except json.JSONDecodeError:
                raise ValidationError(_('Variables must be valid JSON format.'))
        return variables


class SMSTemplateForm(forms.ModelForm):
    """Form for creating and updating SMS templates."""
    
    class Meta:
        model = SMSTemplate
        fields = ['name', 'content', 'is_active', 'variables']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter template name')
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'maxlength': '160',
                'placeholder': _('Enter SMS content (max 160 characters). Use {{ variable_name }} for dynamic content.')
            }),
            'variables': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Enter available variables in JSON format')
            }),
        }
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if content and len(content) > 160:
            raise ValidationError(_('SMS content cannot exceed 160 characters.'))
        return content
    
    def clean_variables(self):
        variables = self.cleaned_data.get('variables')
        if variables:
            try:
                import json
                json.loads(variables)
            except json.JSONDecodeError:
                raise ValidationError(_('Variables must be valid JSON format.'))
        return variables


class BulkMessageForm(forms.Form):
    """Form for sending bulk messages to multiple recipients."""
    
    MESSAGE_TYPES = [
        ('email', _('Email')),
        ('sms', _('SMS')),
        ('notification', _('In-App Notification')),
    ]
    
    message_type = forms.ChoiceField(
        choices=MESSAGE_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Message Type')
    )
    
    recipient_group = forms.ChoiceField(
        choices=[
            ('all_students', _('All Students')),
            ('all_teachers', _('All Teachers')),
            ('all_parents', _('All Parents')),
            ('all_staff', _('All Staff')),
            ('specific_class', _('Specific Class')),
            ('specific_users', _('Specific Users')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Recipient Group')
    )
    
    specific_class = forms.ModelChoiceField(
        queryset=Class.objects.filter(status='active'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Select Class')
    )
    
    specific_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2-multiple'}),
        label=_('Select Users')
    )
    
    subject = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label=_('Subject')
    )
    
    content = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
        label=_('Message Content')
    )
    
    template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Use Template')
    )
    
    def clean(self):
        cleaned_data = super().clean()
        message_type = cleaned_data.get('message_type')
        recipient_group = cleaned_data.get('recipient_group')
        specific_class = cleaned_data.get('specific_class')
        specific_users = cleaned_data.get('specific_users')
        subject = cleaned_data.get('subject')
        
        # Validate recipient selection
        if recipient_group == 'specific_class' and not specific_class:
            raise ValidationError(_('Please select a class for specific class recipient group.'))
        
        if recipient_group == 'specific_users' and not specific_users:
            raise ValidationError(_('Please select at least one user for specific users recipient group.'))
        
        # Validate subject for email
        if message_type == 'email' and not subject:
            raise ValidationError(_('Subject is required for email messages.'))
        
        return cleaned_data


class AnnouncementFilterForm(forms.Form):
    """Form for filtering announcements."""
    
    announcement_type = forms.ChoiceField(
        choices=[('', _('All Types'))] + list(Announcement.AnnouncementType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Type')
    )
    
    priority = forms.ChoiceField(
        choices=[('', _('All Priorities'))] + list(Announcement.PriorityLevel.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Priority')
    )
    
    target_audience = forms.ChoiceField(
        choices=[('', _('All Audiences'))] + list(Announcement.TargetAudience.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Target Audience')
    )
    
    is_published = forms.ChoiceField(
        choices=[
            ('', _('All Status')),
            ('published', _('Published Only')),
            ('draft', _('Draft Only')),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Publishing Status')
    )
    
    date_range = forms.ChoiceField(
        choices=[
            ('', _('All Time')),
            ('today', _('Today')),
            ('this_week', _('This Week')),
            ('this_month', _('This Month')),
            ('custom', _('Custom Range')),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Date Range')
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label=_('Start Date')
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label=_('End Date')
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if date_range == 'custom':
            if not start_date or not end_date:
                raise ValidationError(_('Both start and end dates are required for custom date range.'))
            if start_date and end_date and end_date < start_date:
                raise ValidationError(_('End date cannot be before start date.'))
        
        return cleaned_data


class MessageSearchForm(forms.Form):
    """Form for searching messages."""
    
    SEARCH_TYPES = [
        ('all', _('All Messages')),
        ('sent', _('Sent Messages')),
        ('received', _('Received Messages')),
    ]
    
    search_type = forms.ChoiceField(
        choices=SEARCH_TYPES,
        initial='all',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Search In')
    )
    
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by subject or content...')
        }),
        label=_('Search')
    )
    
    priority = forms.ChoiceField(
        choices=[('', _('Any Priority'))] + list(Message.Priority.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Priority')
    )
    
    is_important = forms.ChoiceField(
        choices=[
            ('', _('All Messages')),
            ('important', _('Important Only')),
            ('normal', _('Normal Only')),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Importance')
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label=_('From Date')
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label=_('To Date')
    )


class EmailTestForm(forms.Form):
    """Form for testing email templates."""

    template = forms.ModelChoiceField(
        queryset=EmailTemplate.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Template')
    )

    test_recipient = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        label=_('Test Recipient Email')
    )

    test_data = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': _('Enter test data in JSON format: {"name": "John", "amount": "100"}')
        }),
        label=_('Test Data (JSON)')
    )

    def clean_test_data(self):
        test_data = self.cleaned_data.get('test_data')
        if test_data:
            try:
                import json
                json.loads(test_data)
            except json.JSONDecodeError:
                raise ValidationError(_('Test data must be valid JSON format.'))
        return test_data


class ContactTeacherForm(forms.Form):
    """Form for contacting teachers via email."""

    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Enter message subject')
        }),
        label=_('Subject')
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': _('Enter your message...')
        }),
        label=_('Message')
    )


# Custom widgets for better UI
class RichTextEditor(forms.Textarea):
    """Custom widget for rich text editing."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({
            'class': 'rich-text-editor form-control'
        })


class DateTimePicker(forms.DateTimeInput):
    """Custom widget for datetime picker."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({
            'class': 'datetime-picker form-control',
            'type': 'datetime-local'
        })


# class Select2Multiple(forms.SelectMultiple):
#     """Custom widget for Select2 multiple selection."""
# }
