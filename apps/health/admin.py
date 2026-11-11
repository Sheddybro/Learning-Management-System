from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from apps.core.admin import InstitutionModelAdmin
from .models import (
    HealthRecord,
    MedicalAppointment,
    Medication,
    HealthScreening,
    EmergencyContact,
)


@admin.register(HealthRecord)
class HealthRecordAdmin(InstitutionModelAdmin):
    """
    Admin interface for HealthRecord model.
    """

    list_display = (
        "student",
        "blood_group",
        "current_health_status",
        "last_checkup_date",
        "bmi",
    )
    list_filter = ("current_health_status", "blood_group", "has_insurance", "status")
    search_fields = (
        "student__user__email",
        "student__student_id",
        "allergies",
        "chronic_conditions",
    )
    readonly_fields = ("created_at", "updated_at", "bmi")
    autocomplete_fields = ("student",)

    fieldsets = (
        (_("Student Information"), {"fields": ("student",)}),
        (
            _("Basic Health Information"),
            {"fields": ("blood_group", "height_cm", "weight_kg", "bmi")},
        ),
        (
            _("Health Conditions"),
            {
                "fields": (
                    "allergies",
                    "chronic_conditions",
                    "medications",
                    "disabilities",
                )
            },
        ),
        (
            _("Emergency Information"),
            {
                "fields": (
                    "emergency_contact_name",
                    "emergency_contact_relationship",
                    "emergency_contact_phone",
                    "emergency_contact_email",
                )
            },
        ),
        (
            _("Health Insurance"),
            {
                "fields": (
                    "has_insurance",
                    "insurance_provider",
                    "insurance_policy_number",
                    "insurance_expiry_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Immunization Status"),
            {
                "fields": ("immunization_record", "vaccination_status"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Current Health Status"),
            {
                "fields": (
                    "current_health_status",
                    "last_checkup_date",
                    "next_checkup_date",
                )
            },
        ),
        (
            _("Special Notes"),
            {
                "fields": (
                    "medical_notes",
                    "dietary_restrictions",
                    "physical_restrictions",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(MedicalAppointment)
class MedicalAppointmentAdmin(InstitutionModelAdmin):
    """
    Admin interface for MedicalAppointment model.
    """

    list_display = (
        "student",
        "appointment_type",
        "appointment_status",
        "appointment_date",
        "healthcare_provider",
    )
    list_filter = (
        "appointment_type",
        "appointment_status",
        "appointment_date",
        "parent_notified",
    )
    search_fields = (
        "student__user__email",
        "student__student_id",
        "healthcare_provider",
        "reason_for_visit",
    )
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("student", "referred_by")
    date_hierarchy = "appointment_date"

    fieldsets = (
        (_("Student Information"), {"fields": ("student",)}),
        (
            _("Appointment Details"),
            {"fields": ("appointment_type", "appointment_status")},
        ),
        (
            _("Scheduling"),
            {"fields": ("appointment_date", "appointment_time", "duration_minutes")},
        ),
        (
            _("Healthcare Provider"),
            {
                "fields": (
                    "healthcare_provider",
                    "provider_specialty",
                    "provider_contact",
                    "clinic_hospital_name",
                )
            },
        ),
        (
            _("Appointment Details"),
            {
                "fields": (
                    "reason_for_visit",
                    "symptoms",
                    "diagnosis",
                    "treatment_provided",
                    "prescriptions",
                )
            },
        ),
        (
            _("Follow-up"),
            {
                "fields": ("follow_up_required", "follow_up_date", "follow_up_notes"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Administrative"),
            {
                "fields": ("referred_by", "accompanied_by", "parent_notified"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Costs and Insurance"),
            {
                "fields": (
                    "consultation_fee",
                    "insurance_coverage",
                    "out_of_pocket_cost",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Medication)
class MedicationAdmin(InstitutionModelAdmin):
    """
    Admin interface for Medication model.
    """

    list_display = (
        "student",
        "medication_name",
        "dosage_amount",
        "administration_status",
        "start_date",
        "is_active",
    )
    list_filter = (
        "medication_type",
        "dosage_form",
        "administration_status",
        "start_date",
        "emergency_medication",
    )
    search_fields = (
        "student__user__email",
        "student__student_id",
        "medication_name",
        "generic_name",
    )
    readonly_fields = ("created_at", "updated_at", "is_active", "days_remaining")
    autocomplete_fields = ("student", "administered_by")
    date_hierarchy = "start_date"

    fieldsets = (
        (_("Student Information"), {"fields": ("student",)}),
        (
            _("Medication Details"),
            {
                "fields": (
                    "medication_name",
                    "generic_name",
                    "medication_type",
                    "dosage_form",
                )
            },
        ),
        (
            _("Dosage Information"),
            {"fields": ("dosage_amount", "dosage_frequency", "dosage_instructions")},
        ),
        (
            _("Administration Schedule"),
            {"fields": ("start_date", "end_date", "administration_times")},
        ),
        (
            _("Prescription Details"),
            {"fields": ("prescribed_by", "prescription_date", "prescription_number")},
        ),
        (
            _("Administration Tracking"),
            {
                "fields": (
                    "administered_by",
                    "administration_status",
                    "administration_date",
                    "administration_time",
                    "administration_notes",
                )
            },
        ),
        (
            _("Side Effects and Monitoring"),
            {
                "fields": ("side_effects", "effectiveness_rating"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Emergency/Alert Information"),
            {
                "fields": (
                    "requires_refrigeration",
                    "emergency_medication",
                    "self_administered",
                )
            },
        ),
        (
            _("Status"),
            {"fields": ("is_active", "days_remaining"), "classes": ("collapse",)},
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(HealthScreening)
class HealthScreeningAdmin(InstitutionModelAdmin):
    """
    Admin interface for HealthScreening model.
    """

    list_display = (
        "student",
        "screening_type",
        "screening_result",
        "screening_date",
        "follow_up_required",
    )
    list_filter = (
        "screening_type",
        "screening_result",
        "screening_date",
        "follow_up_required",
        "parent_notified",
    )
    search_fields = ("student__user__email", "student__student_id", "result_details")
    readonly_fields = ("created_at", "updated_at", "is_follow_up_overdue")
    autocomplete_fields = ("student", "conducted_by")
    date_hierarchy = "screening_date"

    fieldsets = (
        (_("Student Information"), {"fields": ("student",)}),
        (
            _("Screening Details"),
            {"fields": ("screening_type", "screening_date", "conducted_by")},
        ),
        (
            _("Results"),
            {"fields": ("screening_result", "result_details", "measurements")},
        ),
        (
            _("Recommendations"),
            {
                "fields": (
                    "recommendations",
                    "follow_up_required",
                    "follow_up_date",
                    "referral_made",
                    "referral_details",
                )
            },
        ),
        (
            _("Additional Information"),
            {
                "fields": ("notes", "parent_notified", "notification_date"),
                "classes": ("collapse",),
            },
        ),
        (_("Status"), {"fields": ("is_follow_up_overdue",), "classes": ("collapse",)}),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(EmergencyContact)
class EmergencyContactAdmin(InstitutionModelAdmin):
    """
    Admin interface for EmergencyContact model.
    """

    list_display = (
        "student",
        "full_name",
        "relationship",
        "priority",
        "phone_primary",
        "is_active",
    )
    list_filter = (
        "relationship",
        "priority",
        "is_active",
        "can_pickup_student",
        "can_make_medical_decisions",
    )
    search_fields = (
        "student__user__email",
        "student__student_id",
        "full_name",
        "phone_primary",
        "email",
    )
    readonly_fields = ("created_at", "updated_at", "is_primary_contact")
    autocomplete_fields = ("student",)

    fieldsets = (
        (_("Student Information"), {"fields": ("student",)}),
        (
            _("Contact Information"),
            {"fields": ("full_name", "relationship", "priority")},
        ),
        (
            _("Contact Details"),
            {"fields": ("phone_primary", "phone_secondary", "email", "address")},
        ),
        (
            _("Additional Information"),
            {
                "fields": ("workplace", "work_phone", "best_contact_time"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Authorization"),
            {
                "fields": (
                    "can_pickup_student",
                    "can_make_medical_decisions",
                    "can_access_records",
                )
            },
        ),
        (
            _("Status"),
            {
                "fields": (
                    "is_active",
                    "last_contacted",
                    "contact_notes",
                    "is_primary_contact",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("System Metadata"),
            {
                "fields": ("status", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
