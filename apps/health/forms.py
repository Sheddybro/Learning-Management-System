from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import (
    HealthRecord, MedicalAppointment, Medication,
    HealthScreening, EmergencyContact
)


class HealthRecordForm(forms.ModelForm):
    """
    Form for creating and updating health records.
    """
    class Meta:
        model = HealthRecord
        fields = [
            'student', 'blood_group', 'height_cm', 'weight_kg',
            'allergies', 'chronic_conditions', 'medications', 'disabilities',
            'emergency_contact_name', 'emergency_contact_relationship',
            'emergency_contact_phone', 'emergency_contact_email',
            'has_insurance', 'insurance_provider', 'insurance_policy_number', 'insurance_expiry_date',
            'immunization_record', 'vaccination_status',
            'current_health_status', 'last_checkup_date', 'next_checkup_date',
            'medical_notes', 'dietary_restrictions', 'physical_restrictions', 'status'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'blood_group': forms.Select(attrs={'class': 'form-control'}),
            'height_cm': forms.NumberInput(attrs={'class': 'form-control', 'min': 50, 'max': 250}),
            'weight_kg': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 300, 'step': '0.1'}),
            'allergies': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'chronic_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'medications': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'disabilities': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_relationship': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'has_insurance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'insurance_provider': forms.TextInput(attrs={'class': 'form-control'}),
            'insurance_policy_number': forms.TextInput(attrs={'class': 'form-control'}),
            'insurance_expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'immunization_record': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'vaccination_status': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'current_health_status': forms.Select(attrs={'class': 'form-control'}),
            'last_checkup_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_checkup_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'medical_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'dietary_restrictions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'physical_restrictions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.academics.models import Student
        self.fields['student'].queryset = Student.objects.filter(status='active').select_related('user')
        self.fields['student'].empty_label = _("Select Student")


class MedicalAppointmentForm(forms.ModelForm):
    """
    Form for creating and updating medical appointments.
    """
    class Meta:
        model = MedicalAppointment
        fields = [
            'student', 'appointment_type', 'appointment_status',
            'appointment_date', 'appointment_time', 'duration_minutes',
            'healthcare_provider', 'provider_specialty', 'provider_contact', 'clinic_hospital_name',
            'reason_for_visit', 'symptoms', 'diagnosis', 'treatment_provided', 'prescriptions',
            'follow_up_required', 'follow_up_date', 'follow_up_notes',
            'referred_by', 'accompanied_by', 'parent_notified',
            'consultation_fee', 'insurance_coverage', 'out_of_pocket_cost', 'status'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'appointment_type': forms.Select(attrs={'class': 'form-control'}),
            'appointment_status': forms.Select(attrs={'class': 'form-control'}),
            'appointment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'appointment_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 15, 'max': 480}),
            'healthcare_provider': forms.TextInput(attrs={'class': 'form-control'}),
            'provider_specialty': forms.TextInput(attrs={'class': 'form-control'}),
            'provider_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'clinic_hospital_name': forms.TextInput(attrs={'class': 'form-control'}),
            'reason_for_visit': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'symptoms': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'diagnosis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'treatment_provided': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'prescriptions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'follow_up_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'follow_up_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'follow_up_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'referred_by': forms.Select(attrs={'class': 'form-control'}),
            'accompanied_by': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_notified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'consultation_fee': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
            'insurance_coverage': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'out_of_pocket_cost': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.academics.models import Student
        from apps.users.models import User
        self.fields['student'].queryset = Student.objects.filter(status='active').select_related('user')
        self.fields['referred_by'].queryset = User.objects.filter(is_active=True)
        self.fields['student'].empty_label = _("Select Student")
        self.fields['referred_by'].empty_label = _("Select Referrer (Optional)")


class MedicationForm(forms.ModelForm):
    """
    Form for creating and updating medication records.
    """
    class Meta:
        model = Medication
        fields = [
            'student', 'medication_name', 'generic_name', 'medication_type', 'dosage_form',
            'dosage_amount', 'dosage_frequency', 'dosage_instructions',
            'start_date', 'end_date', 'administration_times',
            'prescribed_by', 'prescription_date', 'prescription_number',
            'administered_by', 'administration_status', 'administration_date', 'administration_time', 'administration_notes',
            'side_effects', 'effectiveness_rating',
            'requires_refrigeration', 'emergency_medication', 'self_administered', 'status'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'medication_name': forms.TextInput(attrs={'class': 'form-control'}),
            'generic_name': forms.TextInput(attrs={'class': 'form-control'}),
            'medication_type': forms.Select(attrs={'class': 'form-control'}),
            'dosage_form': forms.Select(attrs={'class': 'form-control'}),
            'dosage_amount': forms.TextInput(attrs={'class': 'form-control'}),
            'dosage_frequency': forms.TextInput(attrs={'class': 'form-control'}),
            'dosage_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'administration_times': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'e.g., ["08:00", "14:00", "20:00"]'}),
            'prescribed_by': forms.TextInput(attrs={'class': 'form-control'}),
            'prescription_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'prescription_number': forms.TextInput(attrs={'class': 'form-control'}),
            'administered_by': forms.Select(attrs={'class': 'form-control'}),
            'administration_status': forms.Select(attrs={'class': 'form-control'}),
            'administration_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'administration_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'administration_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'side_effects': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'effectiveness_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'requires_refrigeration': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'emergency_medication': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'self_administered': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.academics.models import Student
        from apps.users.models import User
        self.fields['student'].queryset = Student.objects.filter(status='active').select_related('user')
        self.fields['administered_by'].queryset = User.objects.filter(is_active=True)
        self.fields['student'].empty_label = _("Select Student")
        self.fields['administered_by'].empty_label = _("Select Administrator (Optional)")


class HealthScreeningForm(forms.ModelForm):
    """
    Form for creating and updating health screenings.
    """
    class Meta:
        model = HealthScreening
        fields = [
            'student', 'screening_type', 'screening_date', 'conducted_by',
            'screening_result', 'result_details', 'measurements',
            'recommendations', 'follow_up_required', 'follow_up_date', 'referral_made', 'referral_details',
            'notes', 'parent_notified', 'notification_date', 'status'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'screening_type': forms.Select(attrs={'class': 'form-control'}),
            'screening_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'conducted_by': forms.Select(attrs={'class': 'form-control'}),
            'screening_result': forms.Select(attrs={'class': 'form-control'}),
            'result_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'measurements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'e.g., {"height": 150, "weight": 45}'}),
            'recommendations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'follow_up_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'follow_up_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'referral_made': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'referral_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'parent_notified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notification_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.academics.models import Student
        from apps.users.models import User
        self.fields['student'].queryset = Student.objects.filter(status='active').select_related('user')
        self.fields['conducted_by'].queryset = User.objects.filter(is_active=True)
        self.fields['student'].empty_label = _("Select Student")
        self.fields['conducted_by'].empty_label = _("Select Conductor (Optional)")


class EmergencyContactForm(forms.ModelForm):
    """
    Form for creating and updating emergency contacts.
    """
    class Meta:
        model = EmergencyContact
        fields = [
            'student', 'full_name', 'relationship', 'priority',
            'phone_primary', 'phone_secondary', 'email', 'address',
            'workplace', 'work_phone', 'best_contact_time',
            'can_pickup_student', 'can_make_medical_decisions', 'can_access_records',
            'is_active', 'last_contacted', 'contact_notes', 'status'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'phone_primary': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_secondary': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'workplace': forms.TextInput(attrs={'class': 'form-control'}),
            'work_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'best_contact_time': forms.TextInput(attrs={'class': 'form-control'}),
            'can_pickup_student': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_make_medical_decisions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_access_records': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'last_contacted': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'contact_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.academics.models import Student
        self.fields['student'].queryset = Student.objects.filter(status='active').select_related('user')
        self.fields['student'].empty_label = _("Select Student")


# Search Forms
class HealthRecordSearchForm(forms.Form):
    """Form for searching health records."""
    student_name = forms.CharField(
        label=_('Student Name'),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Search by student name')})
    )
    student_id = forms.CharField(
        label=_('Student ID'),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Search by student ID')})
    )
    blood_group = forms.ChoiceField(
        label=_('Blood Group'),
        choices=[('', _('All Groups'))] + list(HealthRecord.BloodGroup.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    health_status = forms.ChoiceField(
        label=_('Health Status'),
        choices=[('', _('All Statuses'))] + list(HealthRecord.HealthStatus.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    has_insurance = forms.NullBooleanField(
        label=_('Has Insurance'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}, choices=[
            ('', _('All')),
            ('True', _('Yes')),
            ('False', _('No'))
        ])
    )


class MedicalAppointmentSearchForm(forms.Form):
    """Form for searching medical appointments."""
    student_name = forms.CharField(
        label=_('Student Name'),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Search by student name')})
    )
    appointment_type = forms.ChoiceField(
        label=_('Appointment Type'),
        choices=[('', _('All Types'))] + list(MedicalAppointment.AppointmentType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    appointment_status = forms.ChoiceField(
        label=_('Appointment Status'),
        choices=[('', _('All Statuses'))] + list(MedicalAppointment.AppointmentStatus.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        label=_('Date From'),
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        label=_('Date To'),
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    healthcare_provider = forms.CharField(
        label=_('Healthcare Provider'),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Search by provider name')})
    )


class MedicationSearchForm(forms.Form):
    """Form for searching medications."""
    student_name = forms.CharField(
        label=_('Student Name'),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Search by student name')})
    )
    medication_name = forms.CharField(
        label=_('Medication Name'),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Search by medication name')})
    )
    medication_type = forms.ChoiceField(
        label=_('Medication Type'),
        choices=[('', _('All Types'))] + list(Medication.MedicationType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    administration_status = forms.ChoiceField(
        label=_('Administration Status'),
        choices=[('', _('All Statuses'))] + list(Medication.AdministrationStatus.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_active = forms.NullBooleanField(
        label=_('Is Active'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}, choices=[
            ('', _('All')),
            ('True', _('Active')),
            ('False', _('Inactive'))
        ])
    )


class HealthScreeningSearchForm(forms.Form):
    """Form for searching health screenings."""
    student_name = forms.CharField(
        label=_('Student Name'),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Search by student name')})
    )
    screening_type = forms.ChoiceField(
        label=_('Screening Type'),
        choices=[('', _('All Types'))] + list(HealthScreening.ScreeningType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    screening_result = forms.ChoiceField(
        label=_('Screening Result'),
        choices=[('', _('All Results'))] + list(HealthScreening.ScreeningResult.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        label=_('Date From'),
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        label=_('Date To'),
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    follow_up_required = forms.NullBooleanField(
        label=_('Follow-up Required'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}, choices=[
            ('', _('All')),
            ('True', _('Yes')),
            ('False', _('No'))
        ])
    )
