from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .models import (
    ActivityCategory, Activity, ActivityEnrollment, ActivityStaffAssignment,
    SportsTeam, Club, Competition, Equipment, ActivityBudget,
    ActivityAttendance, ActivityAchievement
)


class ActivityCategoryForm(forms.ModelForm):
    class Meta:
        model = ActivityCategory
        fields = ['name', 'category_type', 'description', 'icon', 'color_code', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'color_code': forms.TextInput(attrs={'type': 'color'}),
        }


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = [
            'title', 'description', 'category', 'activity_type', 'frequency',
            'max_participants', 'min_participants', 'start_date', 'end_date',
            'start_time', 'end_time', 'days_of_week', 'venue', 'room_number',
            'equipment_needed', 'fee_amount', 'currency', 'status',
            'academic_session', 'coordinator', 'prerequisites', 'objectives',
            'contact_info', 'registration_deadline', 'image', 'brochure'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'prerequisites': forms.Textarea(attrs={'rows': 3}),
            'objectives': forms.Textarea(attrs={'rows': 3}),
            'equipment_needed': forms.Textarea(attrs={'rows': 3}),
            'contact_info': forms.Textarea(attrs={'rows': 3}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'registration_deadline': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        registration_deadline = cleaned_data.get('registration_deadline')

        if start_date and end_date and start_date > end_date:
            raise ValidationError(_('End date must be after start date.'))

        if registration_deadline and start_date and registration_deadline > start_date:
            raise ValidationError(_('Registration deadline must be before start date.'))

        return cleaned_data


class ActivityEnrollmentForm(forms.ModelForm):
    class Meta:
        model = ActivityEnrollment
        fields = [
            'student', 'activity', 'status', 'special_requirements',
            'emergency_contact', 'medical_conditions', 'payment_status',
            'performance_notes', 'grade', 'certificate_issued'
        ]
        widgets = {
            'special_requirements': forms.Textarea(attrs={'rows': 3}),
            'medical_conditions': forms.Textarea(attrs={'rows': 3}),
            'performance_notes': forms.Textarea(attrs={'rows': 3}),
        }


class StudentActivityEnrollmentForm(forms.ModelForm):
    """Form for students to enroll in activities"""
    class Meta:
        model = ActivityEnrollment
        fields = ['special_requirements', 'emergency_contact', 'medical_conditions']
        widgets = {
            'special_requirements': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Any special requirements or accommodations needed?')}),
            'medical_conditions': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Any medical conditions we should be aware of?')}),
            'emergency_contact': forms.TextInput(attrs={'placeholder': _('Emergency contact information')}),
        }


class ActivityStaffAssignmentForm(forms.ModelForm):
    class Meta:
        model = ActivityStaffAssignment
        fields = ['staff_member', 'activity', 'role', 'is_primary', 'responsibilities', 'hourly_rate', 'hours_per_week']
        widgets = {
            'responsibilities': forms.Textarea(attrs={'rows': 3}),
        }


class SportsTeamForm(forms.ModelForm):
    class Meta:
        model = SportsTeam
        fields = [
            'activity', 'team_name', 'team_level', 'max_players', 'min_players',
            'captain', 'vice_captain', 'wins', 'losses', 'draws', 'points'
        ]


class ClubForm(forms.ModelForm):
    class Meta:
        model = Club
        fields = [
            'activity', 'club_type', 'mission_statement', 'meeting_schedule',
            'president', 'vice_president', 'secretary', 'budget_allocated', 'resources_needed'
        ]
        widgets = {
            'mission_statement': forms.Textarea(attrs={'rows': 4}),
            'meeting_schedule': forms.Textarea(attrs={'rows': 3}),
            'resources_needed': forms.Textarea(attrs={'rows': 3}),
        }


class CompetitionForm(forms.ModelForm):
    class Meta:
        model = Competition
        fields = [
            'title', 'description', 'competition_type', 'level', 'activity',
            'start_date', 'end_date', 'registration_deadline', 'max_teams',
            'max_individuals', 'rules', 'format_description', 'scoring_system',
            'first_prize', 'second_prize', 'third_prize', 'venue',
            'contact_person', 'contact_email', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'rules': forms.Textarea(attrs={'rows': 6}),
            'format_description': forms.Textarea(attrs={'rows': 4}),
            'scoring_system': forms.Textarea(attrs={'rows': 4}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'registration_deadline': forms.DateInput(attrs={'type': 'date'}),
        }


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            'name', 'equipment_type', 'description', 'quantity_total',
            'quantity_available', 'condition', 'purchase_price', 'purchase_date',
            'supplier', 'last_maintenance', 'next_maintenance', 'maintenance_notes',
            'assigned_to_activity', 'storage_location'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'maintenance_notes': forms.Textarea(attrs={'rows': 3}),
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'last_maintenance': forms.DateInput(attrs={'type': 'date'}),
            'next_maintenance': forms.DateInput(attrs={'type': 'date'}),
        }


class ActivityBudgetForm(forms.ModelForm):
    class Meta:
        model = ActivityBudget
        fields = [
            'activity', 'budget_type', 'category', 'amount', 'currency',
            'description', 'planned_date', 'actual_date', 'approved_by', 'receipt'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'planned_date': forms.DateInput(attrs={'type': 'date'}),
            'actual_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ActivityAttendanceForm(forms.ModelForm):
    class Meta:
        model = ActivityAttendance
        fields = [
            'enrollment', 'session_date', 'is_present', 'arrival_time',
            'departure_time', 'notes', 'participation_rating'
        ]
        widgets = {
            'session_date': forms.DateInput(attrs={'type': 'date'}),
            'arrival_time': forms.TimeInput(attrs={'type': 'time'}),
            'departure_time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'participation_rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
        }


class ActivityAttendanceBulkForm(forms.Form):
    """Form for bulk attendance marking"""
    session_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    activity = forms.ModelChoiceField(queryset=Activity.objects.all(), required=True)

    def __init__(self, *args, **kwargs):
        activity = kwargs.pop('activity', None)
        super().__init__(*args, **kwargs)
        if activity:
            self.fields['activity'].initial = activity
            self.fields['activity'].widget = forms.HiddenInput()


class ActivityAchievementForm(forms.ModelForm):
    class Meta:
        model = ActivityAchievement
        fields = [
            'enrollment', 'achievement_type', 'title', 'description',
            'achievement_date', 'awarded_by', 'certificate_issued', 'certificate_number', 'photo'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'achievement_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ActivitySearchForm(forms.Form):
    """Form for searching and filtering activities"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search activities...')})
    )
    category = forms.ModelChoiceField(
        queryset=ActivityCategory.objects.filter(is_active=True),
        required=False,
        empty_label=_('All Categories')
    )
    activity_type = forms.ChoiceField(
        choices=[('', _('All Types'))] + list(Activity.ActivityType.choices),
        required=False
    )
    status = forms.ChoiceField(
        choices=[('', _('All Statuses'))] + list(Activity.Status.choices),
        required=False
    )
    start_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    start_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    fee_max = forms.DecimalField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
