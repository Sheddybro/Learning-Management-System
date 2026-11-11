from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import CoreBaseModel, AddressModel, ContactModel


class HealthRecord(CoreBaseModel):
    """
    Comprehensive health records for students
    """
    class BloodGroup(models.TextChoices):
        A_POSITIVE = 'a+', _('A+')
        A_NEGATIVE = 'a-', _('A-')
        B_POSITIVE = 'b+', _('B+')
        B_NEGATIVE = 'b-', _('B-')
        AB_POSITIVE = 'ab+', _('AB+')
        AB_NEGATIVE = 'ab-', _('AB-')
        O_POSITIVE = 'o+', _('O+')
        O_NEGATIVE = 'o-', _('O-')

    class HealthStatus(models.TextChoices):
        EXCELLENT = 'excellent', _('Excellent')
        GOOD = 'good', _('Good')
        FAIR = 'fair', _('Fair')
        POOR = 'poor', _('Poor')
        CRITICAL = 'critical', _('Critical')

    student = models.OneToOneField(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='health_record',
        verbose_name=_('student')
    )

    # Basic Health Information
    blood_group = models.CharField(
        _('blood group'),
        max_length=3,
        choices=BloodGroup.choices,
        blank=True
    )
    height_cm = models.PositiveIntegerField(
        _('height (cm)'),
        null=True,
        blank=True,
        validators=[MinValueValidator(50), MaxValueValidator(250)]
    )
    weight_kg = models.DecimalField(
        _('weight (kg)'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(5), MaxValueValidator(300)]
    )
    bmi = models.DecimalField(
        _('BMI'),
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Health Conditions
    allergies = models.TextField(_('allergies'), blank=True)
    chronic_conditions = models.TextField(_('chronic conditions'), blank=True)
    medications = models.TextField(_('current medications'), blank=True)
    disabilities = models.TextField(_('disabilities/special needs'), blank=True)

    # Emergency Information
    emergency_contact_name = models.CharField(_('emergency contact name'), max_length=100, blank=True)
    emergency_contact_relationship = models.CharField(_('relationship'), max_length=50, blank=True)
    emergency_contact_phone = models.CharField(_('emergency contact phone'), max_length=20, blank=True)
    emergency_contact_email = models.EmailField(_('emergency contact email'), blank=True)

    # Health Insurance
    has_insurance = models.BooleanField(_('has health insurance'), default=False)
    insurance_provider = models.CharField(_('insurance provider'), max_length=100, blank=True)
    insurance_policy_number = models.CharField(_('policy number'), max_length=50, blank=True)
    insurance_expiry_date = models.DateField(_('insurance expiry date'), null=True, blank=True)

    # Immunization Status
    immunization_record = models.TextField(_('immunization record'), blank=True)
    vaccination_status = models.TextField(_('vaccination status'), blank=True)

    # Current Health Status
    current_health_status = models.CharField(
        _('current health status'),
        max_length=20,
        choices=HealthStatus.choices,
        default=HealthStatus.GOOD
    )
    last_checkup_date = models.DateField(_('last checkup date'), null=True, blank=True)
    next_checkup_date = models.DateField(_('next checkup date'), null=True, blank=True)

    # Special Notes
    medical_notes = models.TextField(_('medical notes'), blank=True)
    dietary_restrictions = models.TextField(_('dietary restrictions'), blank=True)
    physical_restrictions = models.TextField(_('physical restrictions'), blank=True)

    class Meta:
        verbose_name = _('Health Record')
        verbose_name_plural = _('Health Records')
        ordering = ['student__student_id']

    def __str__(self):
        return f"Health Record - {self.student}"

    def save(self, *args, **kwargs):
        # Auto-calculate BMI if height and weight are provided
        if self.height_cm and self.weight_kg:
            height_m = self.height_cm / 100
            self.bmi = round(self.weight_kg / (height_m ** 2), 2)
        super().save(*args, **kwargs)

    @property
    def age(self):
        """Get student age from related student record."""
        return self.student.age if self.student else None


class MedicalAppointment(CoreBaseModel):
    """
    Medical appointments and visits tracking
    """
    class AppointmentType(models.TextChoices):
        CHECKUP = 'checkup', _('Regular Checkup')
        ILLNESS = 'illness', _('Illness/Injury')
        DENTAL = 'dental', _('Dental')
        VISION = 'vision', _('Vision')
        MENTAL_HEALTH = 'mental_health', _('Mental Health')
        SPECIALIST = 'specialist', _('Specialist Consultation')
        EMERGENCY = 'emergency', _('Emergency')
        FOLLOW_UP = 'follow_up', _('Follow-up')
        SCREENING = 'screening', _('Health Screening')
        OTHER = 'other', _('Other')

    class AppointmentStatus(models.TextChoices):
        SCHEDULED = 'scheduled', _('Scheduled')
        CONFIRMED = 'confirmed', _('Confirmed')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
        NO_SHOW = 'no_show', _('No Show')
        RESCHEDULED = 'rescheduled', _('Rescheduled')

    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='medical_appointments',
        verbose_name=_('student')
    )

    # Appointment Details
    appointment_type = models.CharField(
        _('appointment type'),
        max_length=20,
        choices=AppointmentType.choices,
        default=AppointmentType.CHECKUP
    )
    appointment_status = models.CharField(
        _('appointment status'),
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.SCHEDULED
    )

    # Scheduling
    appointment_date = models.DateField(_('appointment date'))
    appointment_time = models.TimeField(_('appointment time'))
    duration_minutes = models.PositiveIntegerField(
        _('duration (minutes)'),
        default=30,
        validators=[MinValueValidator(15), MaxValueValidator(480)]
    )

    # Healthcare Provider
    healthcare_provider = models.CharField(_('healthcare provider'), max_length=100)
    provider_specialty = models.CharField(_('provider specialty'), max_length=100, blank=True)
    provider_contact = models.CharField(_('provider contact'), max_length=100, blank=True)
    clinic_hospital_name = models.CharField(_('clinic/hospital name'), max_length=100, blank=True)

    # Appointment Details
    reason_for_visit = models.TextField(_('reason for visit'))
    symptoms = models.TextField(_('symptoms'), blank=True)
    diagnosis = models.TextField(_('diagnosis'), blank=True)
    treatment_provided = models.TextField(_('treatment provided'), blank=True)
    prescriptions = models.TextField(_('prescriptions'), blank=True)

    # Follow-up
    follow_up_required = models.BooleanField(_('follow up required'), default=False)
    follow_up_date = models.DateField(_('follow up date'), null=True, blank=True)
    follow_up_notes = models.TextField(_('follow up notes'), blank=True)

    # Administrative
    referred_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medical_referrals',
        verbose_name=_('referred by')
    )
    accompanied_by = models.CharField(_('accompanied by'), max_length=100, blank=True)
    parent_notified = models.BooleanField(_('parent notified'), default=False)

    # Costs and Insurance
    consultation_fee = models.DecimalField(
        _('consultation fee'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    insurance_coverage = models.BooleanField(_('insurance coverage'), default=False)
    out_of_pocket_cost = models.DecimalField(
        _('out of pocket cost'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = _('Medical Appointment')
        verbose_name_plural = _('Medical Appointments')
        ordering = ['-appointment_date', '-appointment_time']
        indexes = [
            models.Index(fields=['student', 'appointment_date']),
            models.Index(fields=['appointment_status', 'appointment_date']),
            models.Index(fields=['appointment_type', 'student']),
        ]

    def __str__(self):
        return f"{self.student} - {self.appointment_type} - {self.appointment_date}"

    @property
    def is_past_due(self):
        """Check if appointment is in the past."""
        from django.utils import timezone
        appointment_datetime = timezone.datetime.combine(
            self.appointment_date,
            self.appointment_time,
            tzinfo=timezone.get_current_timezone()
        )
        return appointment_datetime < timezone.now()

    @property
    def appointment_datetime(self):
        """Get appointment as datetime object."""
        return timezone.datetime.combine(self.appointment_date, self.appointment_time)


class Medication(CoreBaseModel):
    """
    Medication administration and tracking
    """
    class MedicationType(models.TextChoices):
        PRESCRIPTION = 'prescription', _('Prescription')
        OTC = 'otc', _('Over-the-Counter')
        SUPPLEMENT = 'supplement', _('Supplement')
        TOPICAL = 'topical', _('Topical')
        INHALER = 'inhaler', _('Inhaler')

    class DosageForm(models.TextChoices):
        TABLET = 'tablet', _('Tablet')
        CAPSULE = 'capsule', _('Capsule')
        LIQUID = 'liquid', _('Liquid/Syrup')
        INJECTION = 'injection', _('Injection')
        CREAM = 'cream', _('Cream/Ointment')
        DROPS = 'drops', _('Eye/Ear Drops')
        INHALER = 'inhaler', _('Inhaler')
        PATCH = 'patch', _('Patch')
        OTHER = 'other', _('Other')

    class AdministrationStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        ADMINISTERED = 'administered', _('Administered')
        REFUSED = 'refused', _('Refused')
        MISSED = 'missed', _('Missed')
        CANCELLED = 'cancelled', _('Cancelled')

    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='medications',
        verbose_name=_('student')
    )

    # Medication Details
    medication_name = models.CharField(_('medication name'), max_length=100)
    generic_name = models.CharField(_('generic name'), max_length=100, blank=True)
    medication_type = models.CharField(
        _('medication type'),
        max_length=20,
        choices=MedicationType.choices,
        default=MedicationType.PRESCRIPTION
    )
    dosage_form = models.CharField(
        _('dosage form'),
        max_length=20,
        choices=DosageForm.choices,
        default=DosageForm.TABLET
    )

    # Dosage Information
    dosage_amount = models.CharField(_('dosage amount'), max_length=50)  # e.g., "500mg", "10ml"
    dosage_frequency = models.CharField(_('dosage frequency'), max_length=100)  # e.g., "twice daily", "every 8 hours"
    dosage_instructions = models.TextField(_('dosage instructions'), blank=True)

    # Administration Schedule
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'), null=True, blank=True)
    administration_times = models.JSONField(
        _('administration times'),
        default=list,
        help_text=_('List of times when medication should be administered')
    )

    # Prescription Details
    prescribed_by = models.CharField(_('prescribed by'), max_length=100)
    prescription_date = models.DateField(_('prescription date'))
    prescription_number = models.CharField(_('prescription number'), max_length=50, blank=True)

    # Administration Tracking
    administered_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medication_administrations',
        verbose_name=_('administered by')
    )
    administration_status = models.CharField(
        _('administration status'),
        max_length=20,
        choices=AdministrationStatus.choices,
        default=AdministrationStatus.PENDING
    )
    administration_date = models.DateField(_('administration date'), null=True, blank=True)
    administration_time = models.TimeField(_('administration time'), null=True, blank=True)
    administration_notes = models.TextField(_('administration notes'), blank=True)

    # Side Effects and Monitoring
    side_effects = models.TextField(_('side effects'), blank=True)
    effectiveness_rating = models.PositiveIntegerField(
        _('effectiveness rating'),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Rate effectiveness from 1-5')
    )

    # Emergency/Alert Information
    requires_refrigeration = models.BooleanField(_('requires refrigeration'), default=False)
    emergency_medication = models.BooleanField(_('emergency medication'), default=False)
    self_administered = models.BooleanField(_('self-administered'), default=False)

    class Meta:
        verbose_name = _('Medication')
        verbose_name_plural = _('Medications')
        ordering = ['-start_date', 'student']
        indexes = [
            models.Index(fields=['student', 'start_date']),
            models.Index(fields=['administration_status', 'start_date']),
            models.Index(fields=['medication_name', 'student']),
        ]

    def __str__(self):
        return f"{self.student} - {self.medication_name} - {self.dosage_amount}"

    @property
    def is_active(self):
        """Check if medication is currently active."""
        today = timezone.now().date()
        if self.end_date:
            return self.start_date <= today <= self.end_date
        return self.start_date <= today

    @property
    def days_remaining(self):
        """Calculate days remaining for medication course."""
        if not self.end_date:
            return None
        today = timezone.now().date()
        if today > self.end_date:
            return 0
        return (self.end_date - today).days


class HealthScreening(CoreBaseModel):
    """
    Health screenings and checkups
    """
    class ScreeningType(models.TextChoices):
        VISION = 'vision', _('Vision Screening')
        HEARING = 'hearing', _('Hearing Screening')
        DENTAL = 'dental', _('Dental Screening')
        BMI_HEIGHT_WEIGHT = 'bmi', _('BMI/Height/Weight')
        BLOOD_PRESSURE = 'blood_pressure', _('Blood Pressure')
        GENERAL_CHECKUP = 'general', _('General Health Checkup')
        IMMUNIZATION = 'immunization', _('Immunization Review')
        MENTAL_HEALTH = 'mental_health', _('Mental Health Screening')
        POSTURAL = 'postural', _('Postural Screening')
        SKIN = 'skin', _('Skin Check')
        OTHER = 'other', _('Other')

    class ScreeningResult(models.TextChoices):
        NORMAL = 'normal', _('Normal')
        ABNORMAL = 'abnormal', _('Abnormal')
        NEEDS_ATTENTION = 'needs_attention', _('Needs Attention')
        REFERRAL_REQUIRED = 'referral_required', _('Referral Required')
        PENDING = 'pending', _('Pending Results')

    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='health_screenings',
        verbose_name=_('student')
    )

    # Screening Details
    screening_type = models.CharField(
        _('screening type'),
        max_length=20,
        choices=ScreeningType.choices
    )
    screening_date = models.DateField(_('screening date'))
    conducted_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='health_screenings',
        verbose_name=_('conducted by')
    )

    # Results
    screening_result = models.CharField(
        _('screening result'),
        max_length=20,
        choices=ScreeningResult.choices,
        default=ScreeningResult.PENDING
    )
    result_details = models.TextField(_('result details'), blank=True)
    measurements = models.JSONField(
        _('measurements'),
        default=dict,
        blank=True,
        help_text=_('Store measurement data as key-value pairs')
    )

    # Recommendations
    recommendations = models.TextField(_('recommendations'), blank=True)
    follow_up_required = models.BooleanField(_('follow up required'), default=False)
    follow_up_date = models.DateField(_('follow up date'), null=True, blank=True)
    referral_made = models.BooleanField(_('referral made'), default=False)
    referral_details = models.TextField(_('referral details'), blank=True)

    # Additional Information
    notes = models.TextField(_('additional notes'), blank=True)
    parent_notified = models.BooleanField(_('parent notified'), default=False)
    notification_date = models.DateField(_('notification date'), null=True, blank=True)

    class Meta:
        verbose_name = _('Health Screening')
        verbose_name_plural = _('Health Screenings')
        ordering = ['-screening_date', 'student']
        indexes = [
            models.Index(fields=['student', 'screening_date']),
            models.Index(fields=['screening_type', 'screening_result']),
            models.Index(fields=['screening_date', 'follow_up_required']),
        ]

    def __str__(self):
        return f"{self.student} - {self.screening_type} - {self.screening_date}"

    @property
    def is_follow_up_overdue(self):
        """Check if follow-up is overdue."""
        if not self.follow_up_required or not self.follow_up_date:
            return False
        return timezone.now().date() > self.follow_up_date


class EmergencyContact(CoreBaseModel):
    """
    Emergency contact information for students
    """
    class Relationship(models.TextChoices):
        FATHER = 'father', _('Father')
        MOTHER = 'mother', _('Mother')
        GUARDIAN = 'guardian', _('Guardian')
        GRANDPARENT = 'grandparent', _('Grandparent')
        SIBLING = 'sibling', _('Sibling')
        RELATIVE = 'relative', _('Relative')
        FRIEND = 'friend', _('Friend')
        OTHER = 'other', _('Other')

    class Priority(models.TextChoices):
        PRIMARY = 'primary', _('Primary')
        SECONDARY = 'secondary', _('Secondary')
        TERTIARY = 'tertiary', _('Tertiary')

    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='emergency_contacts',
        verbose_name=_('student')
    )

    # Contact Information
    full_name = models.CharField(_('full name'), max_length=100)
    relationship = models.CharField(
        _('relationship'),
        max_length=20,
        choices=Relationship.choices
    )
    priority = models.CharField(
        _('priority'),
        max_length=20,
        choices=Priority.choices,
        default=Priority.SECONDARY
    )

    # Contact Details
    phone_primary = models.CharField(_('primary phone'), max_length=20)
    phone_secondary = models.CharField(_('secondary phone'), max_length=20, blank=True)
    email = models.EmailField(_('email'), blank=True)
    address = models.TextField(_('address'), blank=True)

    # Additional Information
    workplace = models.CharField(_('workplace'), max_length=100, blank=True)
    work_phone = models.CharField(_('work phone'), max_length=20, blank=True)
    best_contact_time = models.CharField(_('best contact time'), max_length=50, blank=True)

    # Authorization
    can_pickup_student = models.BooleanField(_('can pickup student'), default=True)
    can_make_medical_decisions = models.BooleanField(_('can make medical decisions'), default=False)
    can_access_records = models.BooleanField(_('can access medical records'), default=False)

    # Status
    is_active = models.BooleanField(_('is active'), default=True)
    last_contacted = models.DateField(_('last contacted'), null=True, blank=True)
    contact_notes = models.TextField(_('contact notes'), blank=True)

    class Meta:
        verbose_name = _('Emergency Contact')
        verbose_name_plural = _('Emergency Contacts')
        ordering = ['student', 'priority', 'full_name']
        indexes = [
            models.Index(fields=['student', 'priority']),
            models.Index(fields=['student', 'is_active']),
            models.Index(fields=['relationship', 'student']),
        ]
        unique_together = ['student', 'full_name', 'relationship']

    def __str__(self):
        return f"{self.student} - {self.full_name} ({self.relationship})"

    @property
    def is_primary_contact(self):
        """Check if this is the primary emergency contact."""
        return self.priority == self.Priority.PRIMARY
