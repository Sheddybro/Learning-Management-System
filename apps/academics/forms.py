# apps/academics/forms.py

import logging

from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

from .models import (
    AcademicSession,
    Department,
    Subject,
    GradeLevel,
    Class,
    Student,
    Teacher,
    Enrollment,
    SubjectAssignment,
    ClassMaterial,
    BehaviorRecord,
    Achievement,
    ParentGuardian,
    StudentParentRelationship,
    ClassTransferHistory,
    AcademicWarning,
    Holiday,
    FileAttachment,
    Timetable,
    AttendanceSchedule,
    AcademicRecord,
    SchoolPolicy,
)
from apps.core.models import CoreBaseModel, Institution
from apps.users.models import User, UserProfile, Role, UserRole
from apps.core.middleware import get_user_accessible_institutions


class InstitutionFormMixin:
    """
    Mixin for ModelForms that filter related fields by user's accessible institutions.
    Automatically filters Institution-related querysets and other related models.
    """

    def __init__(self, *args, **kwargs):
        # Extract user from kwargs if provided, otherwise store for later
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Filter institution field and related fields based on user permissions
        self._filter_institution_fields()

    def _filter_institution_fields(self):
        """Filter institution and related fields based on user permissions."""
        if not self.user:
            return

        # For superusers, show all institutions
        if self.user.is_superuser:
            return

        # Get user's accessible institutions
        accessible_institutions = get_user_accessible_institutions(self.user)

        # Filter Institution fields
        for field_name, field in self.fields.items():
            if hasattr(field, "queryset") and field.queryset is not None:
                model = field.queryset.model
                if model == Institution:
                    field.queryset = field.queryset.filter(
                        id__in=accessible_institutions.values_list("id", flat=True)
                    )
                # Automatically filter models that inherit from CoreBaseModel
                elif hasattr(model, "institution"):
                    field.queryset = field.queryset.filter(
                        institution__in=accessible_institutions
                    )


class AcademicSessionForm(InstitutionFormMixin, forms.ModelForm):
    """
    Form for creating and updating AcademicSession instances.
    For school admins (admin/principal), institution is auto-set to their primary institution.
    Only super admins can choose institutions.
    """

    class Meta:
        model = AcademicSession
        fields = [
            "institution",
            "name",
            "number_of_semesters",
            "term_number",
            "start_date",
            "end_date",
            "is_current",
            "status",
        ]
        widgets = {
            "institution": forms.Select(attrs={"class": "form-control"}),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("e.g., Academic Year 2024-2025"),
                }
            ),
            "number_of_semesters": forms.Select(attrs={"class": "form-control"}),
            "term_number": forms.Select(attrs={"class": "form-control"}),
            "start_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "is_current": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }
        labels = {
            "is_current": _("Set as current academic session"),
        }
        help_texts = {
            "term_number": _("Leave blank for full session models"),
            "number_of_semesters": _(
                "Select 2 for two semesters or 3 for three semesters"
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Check if user has super_admin role
        is_super_admin = False
        if self.user:
            is_super_admin = (
                self.user.user_roles.filter(
                    role__role_type="super_admin", status="active"
                ).exists()
                or self.user.is_superuser
            )

        if not is_super_admin:
            # For non-super-admins, hide institution field and auto-set to primary institution
            if "institution" in self.fields:
                self.fields.pop("institution")

            # Auto-set institution if not already set
            if not self.instance.pk:
                primary_institution = self._get_user_primary_institution()
                if primary_institution:
                    self.instance.institution = primary_institution
        else:
            # For super-admins, ensure institution field is shown and required
            if "institution" in self.fields:
                self.fields["institution"].required = True

    def _get_user_primary_institution(self):
        """Get the user's primary institution."""
        if not self.user:
            return None

        # Try to get from institution membership
        try:
            primary_membership = self.user.institution_memberships.filter(
                is_primary=True
            ).first()
            if primary_membership:
                return primary_membership.institution
        except:
            pass

        # Fallback: get first accessible institution
        accessible_institutions = get_user_accessible_institutions(self.user)
        return (
            accessible_institutions.first()
            if accessible_institutions.exists()
            else None
        )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        term_number = cleaned_data.get("term_number")
        number_of_semesters = cleaned_data.get("number_of_semesters")

        # Validate date range
        if start_date and end_date:
            if end_date <= start_date:
                raise ValidationError(
                    {"end_date": _("End date must be after start date.")}
                )

            # Check for overlapping sessions (excluding current instance)
            overlapping_sessions = AcademicSession.objects.filter(
                start_date__lte=end_date, end_date__gte=start_date
            )
            if self.instance.pk:
                overlapping_sessions = overlapping_sessions.exclude(pk=self.instance.pk)

            if overlapping_sessions.exists():
                raise ValidationError(
                    _("This academic session overlaps with an existing session.")
                )

        # Validate term number against number of semesters
        if term_number and number_of_semesters:
            if term_number > number_of_semesters:
                raise ValidationError(
                    {
                        "term_number": _(
                            "Term number cannot exceed the number of semesters "
                            "configured for this session."
                        )
                    }
                )

        return cleaned_data


class DepartmentForm(forms.ModelForm):
    """
    Form for creating and updating departments.
    """

    class Meta:
        model = Department
        fields = [
            "name",
            "code",
            "description",
            "head_of_department",
            "established_date",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("e.g., Science Department"),
                }
            ),
            "code": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., SCI")}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Brief description of the department"),
                }
            ),
            "head_of_department": forms.Select(attrs={"class": "form-control"}),
            "established_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # Limit head_of_department choices to active teachers
        self.fields["head_of_department"].queryset = Teacher.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["head_of_department"].empty_label = _("Select Head of Department")

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if name and self.user:
            # Get user's accessible institutions
            from apps.core.middleware import get_user_accessible_institutions

            try:
                accessible_institutions = get_user_accessible_institutions(self.user)
                if accessible_institutions.exists():
                    # Check if department with this name exists in any of user's institutions
                    existing_department = (
                        Department.objects.filter(
                            name__iexact=name.strip(),
                            institution__in=accessible_institutions,
                        )
                        .exclude(pk=self.instance.pk)
                        .first()
                    )

                    if existing_department:
                        raise forms.ValidationError(
                            _(
                                "A department with this name already exists in your institution(s)."
                            )
                        )
            except ImportError:
                # Fallback if middleware not available
                pass
        return name

    def clean_code(self):
        code = self.cleaned_data.get("code")
        if code:
            code = code.upper()
            if (
                Department.objects.filter(code=code)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise forms.ValidationError(
                    _("A department with this code already exists.")
                )
        return code


class SubjectForm(forms.ModelForm):
    """
    Form for creating and updating subjects.
    """

    class Meta:
        model = Subject
        fields = [
            "name",
            "code",
            "subject_type",
            "description",
            "credits",
            "department",
            "is_active",
            "prerequisites",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., Mathematics")}
            ),
            "code": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., MATH101")}
            ),
            "subject_type": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Brief description of the subject content"),
                }
            ),
            "credits": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 10}
            ),
            "department": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "prerequisites": forms.SelectMultiple(
                attrs={"class": "form-control", "size": 5}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Filter departments by user's accessible institutions
        if self.user:
            from apps.core.middleware import get_user_accessible_institutions

            try:
                accessible_institutions = get_user_accessible_institutions(self.user)
                self.fields["department"].queryset = Department.objects.filter(
                    status="active", institution__in=accessible_institutions
                )
            except ImportError:
                # Fallback if middleware not available
                self.fields["department"].queryset = Department.objects.filter(
                    status="active"
                )
        else:
            self.fields["department"].queryset = Department.objects.filter(
                status="active"
            )

        self.fields["prerequisites"].queryset = Subject.objects.filter(
            is_active=True
        ).exclude(pk=self.instance.pk)
        self.fields["department"].empty_label = _("Select Department")

    def clean_code(self):
        code = self.cleaned_data.get("code")
        if code:
            code = code.upper()
            if Subject.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError(
                    _("A subject with this code already exists.")
                )
        return code


class GradeLevelForm(forms.ModelForm):
    """
    Form for creating and updating grade levels.
    """

    class Meta:
        model = GradeLevel
        fields = [
            "name",
            "code",
            "education_stage",
            "grade_type",
            "short_name",
            "description",
            "typical_start_age",
            "typical_end_age",
            "credit_hours",
            "base_tuition_fee",
            "is_entry_level",
            "is_final_level",
            "next_level",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., Grade 1")}
            ),
            "code": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., G1")}
            ),
            "education_stage": forms.Select(attrs={"class": "form-control"}),
            "grade_type": forms.Select(attrs={"class": "form-control"}),
            "short_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., G1")}
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "typical_start_age": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "max": 30}
            ),
            "typical_end_age": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "max": 30}
            ),
            "credit_hours": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "base_tuition_fee": forms.NumberInput(
                attrs={"class": "form-control", "min": 0.00}
            ),
            "is_entry_level": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_final_level": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "next_level": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["next_level"].queryset = GradeLevel.objects.filter(
            status="active"
        ).exclude(pk=self.instance.pk)
        self.fields["next_level"].empty_label = _("Select Next Level (Optional)")

    def clean(self):
        cleaned_data = super().clean()
        start_age = cleaned_data.get("typical_start_age")
        end_age = cleaned_data.get("typical_end_age")
        next_level = cleaned_data.get("next_level")

        if start_age and end_age and start_age >= end_age:
            self.add_error(
                "typical_end_age", _("Typical end age must be greater than start age.")
            )

        if next_level and next_level == self.instance:
            self.add_error(
                "next_level", _("A grade level cannot be its own next level.")
            )

        return cleaned_data


class ClassForm(forms.ModelForm):
    """
    Form for creating and updating classes.
    """

    class Meta:
        model = Class
        fields = [
            "name",
            "code",
            "grade_level",
            "class_type",
            "capacity",
            "class_teacher",
            "room_number",
            "academic_session",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., Grade 10 A")}
            ),
            "code": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., G10A")}
            ),
            "grade_level": forms.Select(attrs={"class": "form-control"}),
            "class_type": forms.Select(attrs={"class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "class_teacher": forms.Select(attrs={"class": "form-control"}),
            "room_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., A101")}
            ),
            "academic_session": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        institution = kwargs.pop("institution", None)
        super().__init__(*args, **kwargs)
        self.fields["grade_level"].queryset = GradeLevel.objects.filter(status="active")
        self.fields["class_teacher"].queryset = Teacher.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["academic_session"].queryset = AcademicSession.objects.filter(
            status="active"
        )
        if institution is not None:
            self.fields["class_teacher"].queryset = self.fields[
                "class_teacher"
            ].queryset.filter(institution=institution)
            self.fields["academic_session"].queryset = self.fields[
                "academic_session"
            ].queryset.filter(institution=institution)

        self.fields["grade_level"].empty_label = _("Select Grade Level")
        self.fields["class_teacher"].empty_label = _("Select Class Teacher (Optional)")
        self.fields["academic_session"].empty_label = _("Select Academic Session")

    def clean(self):
        cleaned_data = super().clean()
        grade_level = cleaned_data.get("grade_level")
        class_type = cleaned_data.get("class_type")
        academic_session = cleaned_data.get("academic_session")

        if grade_level and class_type and academic_session:
            duplicate_class = (
                Class.objects.filter(
                    grade_level=grade_level,
                    class_type=class_type,
                    academic_session=academic_session,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate_class:
                raise forms.ValidationError(
                    _(
                        "A class with this grade level, type, and academic session already exists."
                    )
                )
        return cleaned_data


class StudentForm(forms.ModelForm):
    """
    Form for creating and updating student profiles.
    """

    class Meta:
        model = Student
        fields = [
            "user",
            "student_id",
            "admission_number",
            "admission_date",
            "date_of_birth",
            "place_of_birth",
            "gender",
            "blood_group",
            "nationality",
            "religion",
            "student_type",
            "is_boarder",
            "has_special_needs",
            "special_needs_description",
            "department",
            "previous_school",
            "photo",
            "father_name",
            "father_occupation",
            "father_phone",
            "father_email",
            "mother_name",
            "mother_occupation",
            "mother_phone",
            "mother_email",
            "guardian_name",
            "guardian_relation",
            "guardian_occupation",
            "guardian_phone",
            "guardian_email",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
            "phone",
            "mobile",
            "email",
            "emergency_contact",
            "emergency_phone",
            "status",
        ]
        widgets = {
            "user": forms.Select(attrs={"class": "form-control"}),
            "student_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Auto-generated or enter manually"),
                }
            ),
            "admission_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Admission number")}
            ),
            "admission_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "date_of_birth": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "place_of_birth": forms.TextInput(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "blood_group": forms.Select(attrs={"class": "form-control"}),
            "nationality": forms.TextInput(attrs={"class": "form-control"}),
            "religion": forms.TextInput(attrs={"class": "form-control"}),
            "student_type": forms.Select(attrs={"class": "form-control"}),
            "is_boarder": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "has_special_needs": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "special_needs_description": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "department": forms.Select(attrs={"class": "form-control"}),
            "previous_school": forms.TextInput(attrs={"class": "form-control"}),
            "photo": forms.FileInput(attrs={"class": "form-control"}),
            "father_name": forms.TextInput(attrs={"class": "form-control"}),
            "father_occupation": forms.TextInput(attrs={"class": "form-control"}),
            "father_phone": forms.TextInput(attrs={"class": "form-control"}),
            "father_email": forms.EmailInput(attrs={"class": "form-control"}),
            "mother_name": forms.TextInput(attrs={"class": "form-control"}),
            "mother_occupation": forms.TextInput(attrs={"class": "form-control"}),
            "mother_phone": forms.TextInput(attrs={"class": "form-control"}),
            "mother_email": forms.EmailInput(attrs={"class": "form-control"}),
            "guardian_name": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_relation": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_occupation": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_phone": forms.TextInput(attrs={"class": "form-control"}),
            "guardian_email": forms.EmailInput(attrs={"class": "form-control"}),
            "address_line_1": forms.TextInput(attrs={"class": "form-control"}),
            "address_line_2": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "mobile": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "emergency_contact": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_phone": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        institution = kwargs.pop("institution", None)
        super().__init__(*args, **kwargs)
        # Limit user choices to those not already linked to a student profile
        if self.instance.pk:
            self.fields["user"].queryset = User.objects.filter(
                Q(student_profile=self.instance) | Q(student_profile__isnull=True)
            ).filter(is_active=True)
        else:
            self.fields["user"].queryset = User.objects.filter(
                student_profile__isnull=True, is_active=True
            )
        if institution is not None:
            self.fields["user"].queryset = self.fields["user"].queryset.filter(
                institution_memberships__institution=institution
            ).distinct()
        self.fields["user"].empty_label = _("Select User Account")

        # Configure department field
        self.fields["department"].queryset = Department.objects.filter(status="active")
        self.fields["department"].empty_label = _(
            "Select Department (for tertiary education)"
        )

        # Make department required for tertiary education students only
        # This will be handled by JavaScript in the template or by checking the grade level during enrollment


class TeacherForm(forms.ModelForm):
    """
    Form for creating and updating teacher profiles.
    """

    class Meta:
        model = Teacher
        fields = [
            "user",
            "teacher_id",
            "employee_id",
            "date_of_birth",
            "gender",
            "teacher_type",
            "qualification",
            "specialization",
            "joining_date",
            "experience_years",
            "department",
            "is_class_teacher",
            "is_system_admin",
            "bio",
            "photo",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
            "phone",
            "mobile",
            "email",
            "emergency_contact",
            "emergency_phone",
            "status",
        ]
        widgets = {
            "user": forms.Select(attrs={"class": "form-control"}),
            "teacher_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Auto-generated or enter manually"),
                }
            ),
            "employee_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Auto-generated or enter manually"),
                }
            ),
            "date_of_birth": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "teacher_type": forms.Select(attrs={"class": "form-control"}),
            "qualification": forms.Select(attrs={"class": "form-control"}),
            "specialization": forms.TextInput(attrs={"class": "form-control"}),
            "joining_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "experience_years": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "department": forms.Select(attrs={"class": "form-control"}),
            "is_class_teacher": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "is_system_admin": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "bio": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "photo": forms.FileInput(attrs={"class": "form-control"}),
            "address_line_1": forms.TextInput(attrs={"class": "form-control"}),
            "address_line_2": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "mobile": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "emergency_contact": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_phone": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        institution = kwargs.pop("institution", None)
        super().__init__(*args, **kwargs)
        # Limit user choices to those not already linked to a teacher profile
        if self.instance.pk:
            self.fields["user"].queryset = User.objects.filter(
                Q(teacher_profile=self.instance) | Q(teacher_profile__isnull=True)
            ).filter(is_active=True)
        else:
            self.fields["user"].queryset = User.objects.filter(
                teacher_profile__isnull=True, is_active=True
            )
        if institution is not None:
            self.fields["user"].queryset = self.fields["user"].queryset.filter(
                institution_memberships__institution=institution
            ).distinct()
        self.fields["user"].empty_label = _("Select User Account")
        self.fields["department"].queryset = Department.objects.filter(status="active")
        self.fields["department"].empty_label = _("Select Department (Optional)")

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get("employee_id")
        if employee_id:
            if (
                Teacher.objects.filter(employee_id=employee_id)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise forms.ValidationError(
                    _("A teacher with this employee ID already exists.")
                )
        return employee_id


class EnrollmentForm(forms.ModelForm):
    """
    Form for student enrollment in classes.
    """

    class Meta:
        model = Enrollment
        fields = [
            "student",
            "class_enrolled",
            "academic_session",
            "department",
            "enrollment_date",
            "enrollment_status",
            "roll_number",
            "remarks",
            "status",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "class_enrolled": forms.Select(attrs={"class": "form-control"}),
            "academic_session": forms.Select(attrs={"class": "form-control"}),
            "department": forms.Select(attrs={"class": "form-control"}),
            "enrollment_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "enrollment_status": forms.Select(attrs={"class": "form-control"}),
            "roll_number": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        institution = kwargs.pop("institution", None)
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(
            status="active", institution=institution
        ).select_related("user")
        self.fields["class_enrolled"].queryset = Class.objects.filter(
            status="active", institution=institution
        ).select_related("grade_level", "academic_session")
        self.fields["academic_session"].queryset = AcademicSession.objects.filter(
            status="active", institution=institution
        )
        self.fields["department"].queryset = Department.objects.filter(
            status="active", institution=institution
        )

        self.fields["student"].empty_label = _("Select Student")
        self.fields["class_enrolled"].empty_label = _("Select Class")
        self.fields["academic_session"].empty_label = _(
            "Select Academic Session (Optional)"
        )
        self.fields["academic_session"].required = False
        self.fields["department"].empty_label = _(
            "Select Department (for tertiary education)"
        )

        # Make department field conditional based on class grade level
        try:
            class_enrolled = getattr(self.instance, "class_enrolled", None)
            if class_enrolled:
                is_tertiary = getattr(
                    getattr(class_enrolled, "grade_level", None),
                    "is_tertiary_level",
                    False,
                )
                self.fields["department"].required = is_tertiary
                if not is_tertiary:
                    self.fields["department"].widget = forms.HiddenInput()
            else:
                # For new enrollments, department is optional by default
                self.fields["department"].required = False
        except Exception:
            # Be defensive during form introspection/instantiation
            self.fields["department"].required = False

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        class_enrolled = cleaned_data.get("class_enrolled")
        academic_session = cleaned_data.get("academic_session")
        department = cleaned_data.get("department")
        enrollment_date = cleaned_data.get("enrollment_date")
        roll_number = cleaned_data.get("roll_number")

        # Only check for duplicates if academic_session is provided
        if student and academic_session:
            duplicate_enrollment = (
                Enrollment.objects.filter(
                    student=student, academic_session=academic_session
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate_enrollment:
                raise forms.ValidationError(
                    _(
                        "This student is already enrolled in a class for this academic session."
                    )
                )

        if class_enrolled and roll_number and academic_session:
            duplicate_roll_number = (
                Enrollment.objects.filter(
                    class_enrolled=class_enrolled,
                    roll_number=roll_number,
                    academic_session=academic_session,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate_roll_number:
                raise forms.ValidationError(
                    _(
                        "This roll number is already taken in this class for this academic session."
                    )
                )

        # Validate enrollment date only if session is provided
        if enrollment_date and academic_session:
            if (
                enrollment_date < academic_session.start_date
                or enrollment_date > academic_session.end_date
            ):
                raise forms.ValidationError(
                    _("Enrollment date must be within the academic session dates.")
                )

        # Validate department for tertiary education
        if class_enrolled and class_enrolled.grade_level:
            is_tertiary = class_enrolled.grade_level.is_tertiary_level
            if is_tertiary and not department:
                raise forms.ValidationError(
                    _("Department is required for tertiary education enrollments.")
                )

        return cleaned_data


class SubjectAssignmentForm(forms.ModelForm):
    """
    Form for assigning teachers to subjects in classes.
    """

    class Meta:
        model = SubjectAssignment
        fields = [
            "teacher",
            "subject",
            "class_assigned",
            "academic_session",
            "periods_per_week",
            "is_primary_teacher",
            "status",
        ]
        widgets = {
            "teacher": forms.Select(attrs={"class": "form-control"}),
            "subject": forms.Select(attrs={"class": "form-control"}),
            "class_assigned": forms.Select(attrs={"class": "form-control"}),
            "academic_session": forms.Select(attrs={"class": "form-control"}),
            "periods_per_week": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 20}
            ),
            "is_primary_teacher": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = Teacher.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["subject"].queryset = Subject.objects.filter(is_active=True)
        self.fields["class_assigned"].queryset = Class.objects.filter(
            status="active"
        ).select_related("grade_level", "academic_session")
        self.fields["academic_session"].queryset = AcademicSession.objects.filter(
            status="active"
        )

        self.fields["teacher"].empty_label = _("Select Teacher")
        self.fields["subject"].empty_label = _("Select Subject")
        self.fields["class_assigned"].empty_label = _("Select Class")
        self.fields["academic_session"].empty_label = _("Select Academic Session")

    def clean(self):
        cleaned_data = super().clean()
        teacher = cleaned_data.get("teacher")
        subject = cleaned_data.get("subject")
        class_assigned = cleaned_data.get("class_assigned")
        academic_session = cleaned_data.get("academic_session")

        if teacher and subject and class_assigned and academic_session:
            duplicate_assignment = (
                SubjectAssignment.objects.filter(
                    teacher=teacher,
                    subject=subject,
                    class_assigned=class_assigned,
                    academic_session=academic_session,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate_assignment:
                raise forms.ValidationError(
                    _(
                        "This teacher is already assigned to this subject in this class for this academic session."
                    )
                )
        return cleaned_data


class TimetableForm(forms.ModelForm):
    """
    Form for creating and updating timetable entries.
    """

    class Meta:
        model = Timetable
        fields = [
            "class_assigned",
            "academic_session",
            "day_of_week",
            "period_number",
            "period_type",
            "start_time",
            "end_time",
            "subject",
            "teacher",
            "room_number",
            "room_name",
            "room_type",
            "room_capacity",
            "room_building",
            "room_floor",
            "room_facilities",
            "title",
            "description",
            "is_shared_event",
            "shared_with_classes",
            "color_code",
            "is_published",
            "is_room_available",
            "status",
        ]
        widgets = {
            "class_assigned": forms.Select(attrs={"class": "form-control"}),
            "academic_session": forms.Select(attrs={"class": "form-control"}),
            "day_of_week": forms.Select(attrs={"class": "form-control"}),
            "period_number": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 15}
            ),
            "period_type": forms.Select(attrs={"class": "form-control"}),
            "start_time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "end_time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "subject": forms.Select(attrs={"class": "form-control"}),
            "teacher": forms.Select(attrs={"class": "form-control"}),
            "room_number": forms.TextInput(attrs={"class": "form-control"}),
            "room_name": forms.TextInput(attrs={"class": "form-control"}),
            "room_type": forms.Select(attrs={"class": "form-control"}),
            "room_capacity": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "room_building": forms.TextInput(attrs={"class": "form-control"}),
            "room_floor": forms.TextInput(attrs={"class": "form-control"}),
            "room_facilities": forms.Textarea(
                attrs={"class": "form-control", "rows": 2}
            ),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_shared_event": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "shared_with_classes": forms.SelectMultiple(
                attrs={"class": "form-control", "size": 5}
            ),
            "color_code": forms.TextInput(
                attrs={"class": "form-control", "type": "color"}
            ),
            "is_published": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_room_available": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        institution = kwargs.pop("institution", None)
        super().__init__(*args, **kwargs)
        self.fields["class_assigned"].queryset = Class.objects.filter(status="active")
        self.fields["academic_session"].queryset = AcademicSession.objects.filter(
            status="active"
        )
        self.fields["subject"].queryset = Subject.objects.filter(is_active=True)
        self.fields["teacher"].queryset = Teacher.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["shared_with_classes"].queryset = Class.objects.filter(
            status="active"
        )
        if institution is not None:
            for field in ("class_assigned", "academic_session", "subject", "teacher", "shared_with_classes"):
                self.fields[field].queryset = self.fields[field].queryset.filter(
                    institution=institution
                )

        self.fields["class_assigned"].empty_label = _("Select Class (Optional)")
        self.fields["academic_session"].empty_label = _("Select Academic Session")
        self.fields["subject"].empty_label = _("Select Subject (Optional)")
        self.fields["teacher"].empty_label = _("Select Teacher (Optional)")

    def clean(self):
        cleaned_data = super().clean()
        class_assigned = cleaned_data.get("class_assigned")
        academic_session = cleaned_data.get("academic_session")
        day_of_week = cleaned_data.get("day_of_week")
        period_number = cleaned_data.get("period_number")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        period_type = cleaned_data.get("period_type")
        subject = cleaned_data.get("subject")
        teacher = cleaned_data.get("teacher")
        room_number = cleaned_data.get("room_number")

        if start_time and end_time and start_time >= end_time:
            self.add_error("end_time", _("End time must be after start time."))

        # Unique constraint checks
        if class_assigned and day_of_week and period_number and academic_session:
            duplicate_entry = (
                Timetable.objects.filter(
                    class_assigned=class_assigned,
                    day_of_week=day_of_week,
                    period_number=period_number,
                    academic_session=academic_session,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate_entry:
                self.add_error(
                    None,
                    _("This class already has an entry for this period on this day."),
                )

        if teacher and day_of_week and period_number and academic_session:
            duplicate_entry = (
                Timetable.objects.filter(
                    teacher=teacher,
                    day_of_week=day_of_week,
                    period_number=period_number,
                    academic_session=academic_session,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate_entry:
                self.add_error(
                    None,
                    _(
                        "This teacher is already assigned to another period at this time."
                    ),
                )

        if room_number and day_of_week and period_number and academic_session:
            duplicate_entry = (
                Timetable.objects.filter(
                    room_number=room_number,
                    day_of_week=day_of_week,
                    period_number=period_number,
                    academic_session=academic_session,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate_entry:
                self.add_error(
                    None,
                    _("This room is already booked for another period at this time."),
                )

        # Regular class specific validations
        if period_type == Timetable.PeriodType.REGULAR_CLASS:
            if not subject:
                self.add_error("subject", _("Subject is required for regular classes."))
            if not teacher:
                self.add_error("teacher", _("Teacher is required for regular classes."))
            if not class_assigned:
                self.add_error(
                    "class_assigned", _("Class is required for regular classes.")
                )
            if not room_number:
                self.add_error(
                    "room_number", _("Room number is required for regular classes.")
                )

        return cleaned_data


class AttendanceScheduleForm(forms.ModelForm):
    """
    Form for creating and updating attendance schedules.
    """

    class Meta:
        model = AttendanceSchedule
        fields = [
            "class_assigned",
            "academic_session",
            "session_type",
            "session_start_time",
            "session_end_time",
            "late_mark_minutes",
            "early_departure_minutes",
            "has_break",
            "break_start_time",
            "break_end_time",
            "status",
        ]
        widgets = {
            "class_assigned": forms.Select(attrs={"class": "form-control"}),
            "academic_session": forms.Select(attrs={"class": "form-control"}),
            "session_type": forms.Select(attrs={"class": "form-control"}),
            "session_start_time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "session_end_time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "late_mark_minutes": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "early_departure_minutes": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "has_break": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "break_start_time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "break_end_time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["class_assigned"].queryset = Class.objects.filter(status="active")
        self.fields["academic_session"].queryset = AcademicSession.objects.filter(
            status="active"
        )

        self.fields["class_assigned"].empty_label = _("Select Class")
        self.fields["academic_session"].empty_label = _("Select Academic Session")

    def clean(self):
        cleaned_data = super().clean()
        session_start_time = cleaned_data.get("session_start_time")
        session_end_time = cleaned_data.get("session_end_time")
        has_break = cleaned_data.get("has_break")
        break_start_time = cleaned_data.get("break_start_time")
        break_end_time = cleaned_data.get("break_end_time")

        if (
            session_start_time
            and session_end_time
            and session_start_time >= session_end_time
        ):
            self.add_error(
                "session_end_time", _("Session end time must be after start time.")
            )

        if has_break:
            if not break_start_time:
                self.add_error(
                    "break_start_time",
                    _("Break start time is required when break is enabled."),
                )
            if not break_end_time:
                self.add_error(
                    "break_end_time",
                    _("Break end time is required when break is enabled."),
                )
            if (
                break_start_time
                and break_end_time
                and break_start_time >= break_end_time
            ):
                self.add_error(
                    "break_end_time",
                    _("Break end time must be after break start time."),
                )
            if (
                session_start_time
                and session_end_time
                and break_start_time
                and break_end_time
                and not (
                    session_start_time <= break_start_time
                    and break_end_time <= session_end_time
                )
            ):
                self.add_error(None, _("Break times must be within the session times."))

        return cleaned_data


class ClassMaterialForm(forms.ModelForm):
    """
    Form for managing class materials.
    """

    class Meta:
        model = ClassMaterial
        fields = [
            "title",
            "material_type",
            "description",
            "file",
            "external_url",
            "thumbnail",
            "version",
            "parent_material",
            "is_latest_version",
            "change_log",
            "subject",
            "class_assigned",
            "teacher",
            "academic_session",
            "access_level",
            "allowed_students",
            "requires_acknowledgment",
            "is_public",
            "is_featured",
            "publish_date",
            "expiry_date",
            "tags",
            "display_order",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "material_type": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
            "external_url": forms.URLInput(attrs={"class": "form-control"}),
            "thumbnail": forms.FileInput(attrs={"class": "form-control"}),
            "version": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "parent_material": forms.Select(attrs={"class": "form-control"}),
            "is_latest_version": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "change_log": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "subject": forms.Select(attrs={"class": "form-control"}),
            "class_assigned": forms.Select(attrs={"class": "form-control"}),
            "teacher": forms.Select(attrs={"class": "form-control"}),
            "academic_session": forms.Select(attrs={"class": "form-control"}),
            "access_level": forms.Select(attrs={"class": "form-control"}),
            "allowed_students": forms.SelectMultiple(
                attrs={"class": "form-control", "size": 5}
            ),
            "requires_acknowledgment": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "publish_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "expiry_date": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            ),
            "tags": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Comma-separated tags"),
                }
            ),
            "display_order": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = Subject.objects.filter(is_active=True)
        self.fields["class_assigned"].queryset = Class.objects.filter(status="active")
        self.fields["teacher"].queryset = Teacher.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["academic_session"].queryset = AcademicSession.objects.filter(
            status="active"
        )
        self.fields["allowed_students"].queryset = Student.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["parent_material"].queryset = ClassMaterial.objects.filter(
            status="active"
        ).exclude(pk=self.instance.pk)

        self.fields["subject"].empty_label = _("Select Subject")
        self.fields["class_assigned"].empty_label = _("Select Class")
        self.fields["teacher"].empty_label = _("Select Teacher")
        self.fields["academic_session"].empty_label = _("Select Academic Session")
        self.fields["parent_material"].empty_label = _(
            "Select Parent Material (Optional)"
        )

    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get("file")
        external_url = cleaned_data.get("external_url")
        expiry_date = cleaned_data.get("expiry_date")
        parent_material = cleaned_data.get("parent_material")

        if not file and not external_url:
            raise forms.ValidationError(
                _("Either a file or an external URL must be provided.")
            )

        if expiry_date and expiry_date <= timezone.now():
            self.add_error("expiry_date", _("Expiry date must be in the future."))

        if parent_material and parent_material == self.instance:
            self.add_error("parent_material", _("A material cannot be its own parent."))

        return cleaned_data


class BehaviorRecordForm(forms.ModelForm):
    """
    Form for creating and updating student behavior records.
    """

    class Meta:
        model = BehaviorRecord
        fields = [
            "student",
            "behavior_type",
            "severity",
            "incident_category",
            "title",
            "description",
            "incident_date",
            "incident_time",
            "location",
            "reported_by",
            "evidence_files",
            "evidence_description",
            "has_witnesses",
            "witnesses",
            "witness_statements",
            "action_taken",
            "consequence_type",
            "consequence_duration",
            "action_deadline",
            "action_completed",
            "follow_up_required",
            "follow_up_date",
            "next_follow_up_date",
            "follow_up_notes",
            "resolution",
            "is_resolved",
            "resolution_date",
            "parent_notified",
            "parent_notification_date",
            "parent_response",
            "parent_meeting_scheduled",
            "parent_meeting_date",
            "escalated_to",
            "escalation_date",
            "escalation_reason",
            "tags",
            "status",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "behavior_type": forms.Select(attrs={"class": "form-control"}),
            "severity": forms.Select(attrs={"class": "form-control"}),
            "incident_category": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "incident_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "incident_time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "reported_by": forms.Select(attrs={"class": "form-control"}),
            "evidence_files": forms.FileInput(attrs={"class": "form-control"}),
            "evidence_description": forms.Textarea(
                attrs={"class": "form-control", "rows": 2}
            ),
            "has_witnesses": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "witnesses": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "witness_statements": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "action_taken": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "consequence_type": forms.Select(attrs={"class": "form-control"}),
            "consequence_duration": forms.TextInput(attrs={"class": "form-control"}),
            "action_deadline": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "action_completed": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "follow_up_required": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "follow_up_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "next_follow_up_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "follow_up_notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "resolution": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_resolved": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "resolution_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "parent_notified": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "parent_notification_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "parent_response": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "parent_meeting_scheduled": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "parent_meeting_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "escalated_to": forms.Select(attrs={"class": "form-control"}),
            "escalation_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "escalation_reason": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "tags": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Comma-separated tags"),
                }
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["reported_by"].queryset = Teacher.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["escalated_to"].queryset = User.objects.filter(
            is_staff=True, is_active=True
        )

        self.fields["student"].empty_label = _("Select Student")
        self.fields["reported_by"].empty_label = _("Select Reporter")
        self.fields["escalated_to"].empty_label = _("Select Staff (Optional)")

    def clean(self):
        cleaned_data = super().clean()
        incident_date = cleaned_data.get("incident_date")
        follow_up_date = cleaned_data.get("follow_up_date")
        action_deadline = cleaned_data.get("action_deadline")
        resolution_date = cleaned_data.get("resolution_date")

        if follow_up_date and incident_date and follow_up_date < incident_date:
            self.add_error(
                "follow_up_date", _("Follow-up date cannot be before incident date.")
            )

        if action_deadline and incident_date and action_deadline < incident_date:
            self.add_error(
                "action_deadline", _("Action deadline cannot be before incident date.")
            )

        if resolution_date and incident_date and resolution_date < incident_date:
            self.add_error(
                "resolution_date", _("Resolution date cannot be before incident date.")
            )

        return cleaned_data


class AchievementForm(forms.ModelForm):
    """
    Form for creating and updating student achievements.
    """

    class Meta:
        model = Achievement
        fields = [
            "student",
            "achievement_type",
            "achievement_level",
            "title",
            "description",
            "achievement_date",
            "organization",
            "position",
            "certificate",
            "prize_money",
            "recognized_by",
            "notes",
            "status",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "achievement_type": forms.Select(attrs={"class": "form-control"}),
            "achievement_level": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "achievement_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "organization": forms.TextInput(attrs={"class": "form-control"}),
            "position": forms.TextInput(attrs={"class": "form-control"}),
            "certificate": forms.FileInput(attrs={"class": "form-control"}),
            "prize_money": forms.NumberInput(
                attrs={"class": "form-control", "min": 0.00}
            ),
            "recognized_by": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["student"].empty_label = _("Select Student")


class ParentGuardianForm(forms.ModelForm):
    """
    Form for creating and updating parent/guardian profiles.
    """

    class Meta:
        model = ParentGuardian
        fields = [
            "user",
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "occupation",
            "employer",
            "annual_income",
            "education_level",
            "is_primary_contact",
            "can_pickup_student",
            "emergency_contact_priority",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
            "phone",
            "mobile",
            "email",
            "emergency_contact",
            "emergency_phone",
            "status",
        ]
        widgets = {
            "user": forms.Select(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "date_of_birth": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "occupation": forms.TextInput(attrs={"class": "form-control"}),
            "employer": forms.TextInput(attrs={"class": "form-control"}),
            "annual_income": forms.NumberInput(
                attrs={"class": "form-control", "min": 0.00}
            ),
            "education_level": forms.TextInput(attrs={"class": "form-control"}),
            "is_primary_contact": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "can_pickup_student": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "emergency_contact_priority": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 3}
            ),
            "address_line_1": forms.TextInput(attrs={"class": "form-control"}),
            "address_line_2": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "state": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "mobile": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "emergency_contact": forms.TextInput(attrs={"class": "form-control"}),
            "emergency_phone": forms.TextInput(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit user choices to those not already linked to a parent profile
        if self.instance.pk:
            self.fields["user"].queryset = User.objects.filter(
                Q(parent_profile=self.instance) | Q(parent_profile__isnull=True)
            ).filter(is_active=True)
        else:
            self.fields["user"].queryset = User.objects.filter(
                parent_profile__isnull=True, is_active=True
            )
        self.fields["user"].empty_label = _("Select User Account (Optional)")


class StudentParentRelationshipForm(forms.ModelForm):
    """
    Form for managing student-parent relationships.
    """

    class Meta:
        model = StudentParentRelationship
        fields = [
            "student",
            "parent",
            "relationship",
            "is_legal_guardian",
            "has_custody",
            "lives_with_student",
            "can_authorize_medical",
            "can_access_records",
            "notes",
            "status",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "parent": forms.Select(attrs={"class": "form-control"}),
            "relationship": forms.Select(attrs={"class": "form-control"}),
            "is_legal_guardian": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "has_custody": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "lives_with_student": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "can_authorize_medical": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "can_access_records": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["parent"].queryset = ParentGuardian.objects.filter(
            status="active"
        ).select_related("user")

        self.fields["student"].empty_label = _("Select Student")
        self.fields["parent"].empty_label = _("Select Parent/Guardian")

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        parent = cleaned_data.get("parent")

        if student and parent:
            duplicate_relationship = (
                StudentParentRelationship.objects.filter(student=student, parent=parent)
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate_relationship:
                raise forms.ValidationError(
                    _("This relationship already exists for this student and parent.")
                )
        return cleaned_data


class ClassTransferHistoryForm(forms.ModelForm):
    """
    Form for recording student class transfers.
    """

    class Meta:
        model = ClassTransferHistory
        fields = [
            "student",
            "from_class",
            "to_class",
            "transfer_date",
            "academic_session",
            "reason",
            "initiated_by",
            "approved_by",
            "notes",
            "status",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "from_class": forms.Select(attrs={"class": "form-control"}),
            "to_class": forms.Select(attrs={"class": "form-control"}),
            "transfer_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "academic_session": forms.Select(attrs={"class": "form-control"}),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "initiated_by": forms.Select(attrs={"class": "form-control"}),
            "approved_by": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["from_class"].queryset = Class.objects.filter(status="active")
        self.fields["to_class"].queryset = Class.objects.filter(status="active")
        self.fields["academic_session"].queryset = AcademicSession.objects.filter(
            status="active"
        )
        self.fields["initiated_by"].queryset = User.objects.filter(
            is_staff=True, is_active=True
        )
        self.fields["approved_by"].queryset = User.objects.filter(
            is_staff=True, is_active=True
        )

        self.fields["student"].empty_label = _("Select Student")
        self.fields["from_class"].empty_label = _("Select From Class")
        self.fields["to_class"].empty_label = _("Select To Class")
        self.fields["academic_session"].empty_label = _("Select Academic Session")
        self.fields["initiated_by"].empty_label = _("Select Initiator")
        self.fields["approved_by"].empty_label = _("Select Approver (Optional)")

    def clean(self):
        cleaned_data = super().clean()
        from_class = cleaned_data.get("from_class")
        to_class = cleaned_data.get("to_class")
        transfer_date = cleaned_data.get("transfer_date")
        academic_session = cleaned_data.get("academic_session")

        if from_class and to_class and from_class == to_class:
            self.add_error(
                "to_class", _("Student cannot be transferred to the same class.")
            )

        if transfer_date and academic_session:
            if (
                transfer_date < academic_session.start_date
                or transfer_date > academic_session.end_date
            ):
                self.add_error(
                    "transfer_date",
                    _("Transfer date must be within the academic session dates."),
                )

        return cleaned_data


class AcademicWarningForm(forms.ModelForm):
    """
    Form for creating and updating academic warnings.
    """

    class Meta:
        model = AcademicWarning
        fields = [
            "student",
            "warning_type",
            "warning_level",
            "title",
            "description",
            "issued_by",
            "due_date",
            "is_resolved",
            "resolution_date",
            "resolution_notes",
            "parent_notified",
            "parent_notification_date",
            "status",
        ]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "warning_type": forms.Select(attrs={"class": "form-control"}),
            "warning_level": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "issued_by": forms.Select(attrs={"class": "form-control"}),
            "due_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "is_resolved": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "resolution_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "resolution_notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "parent_notified": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "parent_notification_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.filter(
            status="active"
        ).select_related("user")
        self.fields["issued_by"].queryset = Teacher.objects.filter(
            status="active"
        ).select_related("user")

        self.fields["student"].empty_label = _("Select Student")
        self.fields["issued_by"].empty_label = _("Select Issuer")

    def clean(self):
        cleaned_data = super().clean()
        due_date = cleaned_data.get("due_date")
        resolution_date = cleaned_data.get("resolution_date")
        issued_date = (
            self.instance.issued_date if self.instance.pk else timezone.now().date()
        )

        if due_date and due_date < issued_date:
            self.add_error("due_date", _("Due date cannot be before issued date."))

        if resolution_date and resolution_date < issued_date:
            self.add_error(
                "resolution_date", _("Resolution date cannot be before issued date.")
            )

        return cleaned_data


class HolidayForm(forms.ModelForm):
    """
    Form for creating and updating holidays.
    """

    class Meta:
        model = Holiday
        fields = [
            "name",
            "date",
            "academic_session",
            "is_recurring",
            "description",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "academic_session": forms.Select(attrs={"class": "form-control"}),
            "is_recurring": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_session"].queryset = AcademicSession.objects.filter(
            status="active"
        )
        self.fields["academic_session"].empty_label = _("Select Academic Session")

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get("date")
        academic_session = cleaned_data.get("academic_session")

        if date and academic_session:
            duplicate_holiday = (
                Holiday.objects.filter(date=date, academic_session=academic_session)
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicate_holiday:
                raise forms.ValidationError(
                    _(
                        "A holiday with this date already exists for this academic session."
                    )
                )
        return cleaned_data


class FileAttachmentForm(forms.ModelForm):
    """
    Form for uploading and managing generic file attachments.
    """

    class Meta:
        model = FileAttachment
        fields = ["title", "file", "uploaded_by", "description", "status"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
            "uploaded_by": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["uploaded_by"].queryset = User.objects.filter(is_active=True)
        self.fields["uploaded_by"].empty_label = _("Select Uploader")


class SchoolPolicyForm(forms.ModelForm):
    """
    Form for creating and updating school policies.
    """

    class Meta:
        model = SchoolPolicy
        fields = [
            "policy_name",
            "policy_type",
            "description",
            "policy_content",
            "effective_date",
            "expiry_date",
            "academic_session",
            "department",
            "is_active",
            "attachments",
            "status",
        ]
        widgets = {
            "policy_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("e.g., Student Dress Code"),
                }
            ),
            "policy_type": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": _("Detailed description of the policy"),
                }
            ),
            "policy_content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": _("JSON content for policy details (optional)"),
                }
            ),
            "effective_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "expiry_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "academic_session": forms.Select(attrs={"class": "form-control"}),
            "department": forms.Select(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "attachments": forms.SelectMultiple(
                attrs={"class": "form-control", "size": 5}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }
        help_texts = {
            "policy_content": _(
                'Enter policy details in JSON format (e.g., {"rules": ["Rule 1", "Rule 2"]}).'
            ),
            "expiry_date": _("Leave blank if the policy does not expire."),
        }

    def __init__(self, *args, **kwargs):
        institution = kwargs.pop("institution", None)
        super().__init__(*args, **kwargs)
        self.fields["academic_session"].queryset = AcademicSession.objects.filter(
            status="active"
        )
        self.fields["department"].queryset = Department.objects.filter(status="active")
        self.fields["attachments"].queryset = FileAttachment.objects.filter(
            status="active"
        )
        if institution is not None:
            self.fields["academic_session"].queryset = self.fields[
                "academic_session"
            ].queryset.filter(institution=institution)
            self.fields["attachments"].queryset = self.fields[
                "attachments"
            ].queryset.filter(institution=institution)

        self.fields["academic_session"].empty_label = _(
            "Select Academic Session (Optional)"
        )
        self.fields["department"].empty_label = _("Select Department (Optional)")
        self.fields["attachments"].help_text = _(
            "Select relevant attachments for this policy."
        )

    def clean(self):
        cleaned_data = super().clean()
        effective_date = cleaned_data.get("effective_date")
        expiry_date = cleaned_data.get("expiry_date")

        if effective_date and expiry_date and expiry_date <= effective_date:
            self.add_error(
                "expiry_date", _("Expiry date must be after effective date.")
            )

        return cleaned_data


# New Forms for Search and Bulk Operations


class StudentSearchForm(forms.Form):
    name = forms.CharField(
        label=_("Student Name"),
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search by name")}
        ),
    )
    student_id = forms.CharField(
        label=_("Student ID"),
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search by ID")}
        ),
    )
    class_enrolled = forms.ModelChoiceField(
        label=_("Class"),
        queryset=Class.objects.filter(status="active").order_by("name"),
        required=False,
        empty_label=_("All Classes"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    department = forms.ModelChoiceField(
        label=_("Department"),
        queryset=Department.objects.filter(status="active").order_by("name"),
        required=False,
        empty_label=_("All Departments"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    student_type = forms.ChoiceField(
        label=_("Student Type"),
        choices=[("", _("All Types"))] + list(Student.StudentType.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    status = forms.ChoiceField(
        label=_("Status"),
        choices=[("", _("All Statuses"))] + list(CoreBaseModel.Status.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class TeacherSearchForm(forms.Form):
    name = forms.CharField(
        label=_("Teacher Name"),
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search by name")}
        ),
    )
    teacher_id = forms.CharField(
        label=_("Teacher ID"),
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Search by ID")}
        ),
    )
    department = forms.ModelChoiceField(
        label=_("Department"),
        queryset=Department.objects.filter(status="active").order_by("name"),
        required=False,
        empty_label=_("All Departments"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    teacher_type = forms.ChoiceField(
        label=_("Teacher Type"),
        choices=[("", _("All Types"))] + list(Teacher.TeacherType.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    status = forms.ChoiceField(
        label=_("Status"),
        choices=[("", _("All Statuses"))] + list(CoreBaseModel.Status.choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
    )


class BulkEnrollmentForm(forms.Form):
    students = forms.ModelMultipleChoiceField(
        label=_("Students to Enroll"),
        queryset=Student.objects.filter(status="active")
        .select_related("user")
        .order_by("user__first_name", "user__last_name"),
        widget=forms.SelectMultiple(attrs={"class": "form-control", "size": 10}),
        help_text=_("Select multiple students to enroll."),
    )
    class_enrolled = forms.ModelChoiceField(
        label=_("Class to Enroll In"),
        queryset=Class.objects.filter(status="active")
        .select_related("grade_level", "academic_session")
        .order_by("name"),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label=_("Select a Class"),
    )
    academic_session = forms.ModelChoiceField(
        label=_("Academic Session"),
        queryset=AcademicSession.objects.filter(status="active").order_by(
            "-start_date"
        ),
        widget=forms.Select(attrs={"class": "form-control"}),
        empty_label=_("Select an Academic Session"),
    )
    enrollment_date = forms.DateField(
        label=_("Enrollment Date"),
        initial=timezone.now().date(),
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        institution = kwargs.pop("institution", None)
        super().__init__(*args, **kwargs)
        if institution is not None:
            for field in ("students", "class_enrolled", "academic_session"):
                self.fields[field].queryset = self.fields[field].queryset.filter(
                    institution=institution
                )

    def clean(self):
        cleaned_data = super().clean()
        students = cleaned_data.get("students")
        class_enrolled = cleaned_data.get("class_enrolled")
        academic_session = cleaned_data.get("academic_session")

        if class_enrolled and academic_session and class_enrolled.academic_session_id != academic_session.pk:
            self.add_error("academic_session", _("The selected class belongs to a different academic session."))

        enrollment_date = cleaned_data.get("enrollment_date")
        if academic_session and enrollment_date and not (
            academic_session.start_date <= enrollment_date <= academic_session.end_date
        ):
            self.add_error("enrollment_date", _("Enrollment date must fall within the academic session."))

        if students and class_enrolled and academic_session:
            # Check for existing enrollments to prevent duplicates
            for student in students:
                if Enrollment.objects.filter(
                    student=student,
                    academic_session=academic_session,
                ).exists():
                    self.add_error(
                        "students",
                        _(
                            f"{student.user.get_full_name()} is already enrolled in this academic session."
                        ),
                    )

            # Check class capacity
            current_student_count = class_enrolled.current_student_count
            if (current_student_count + len(students)) > class_enrolled.capacity:
                self.add_error(
                    "class_enrolled",
                    _("Adding these students would exceed the class capacity."),
                )
        return cleaned_data


class BulkEnrollmentCsvForm(BulkEnrollmentForm):
    """CSV upload of existing student IDs, using the same class/session validation."""

    csv_file = forms.FileField(
        label=_("CSV file"),
        help_text=_("UTF-8 CSV with a student_id header, maximum 1,000 students and 5 MB."),
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".csv,text/csv"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["students"]

    def clean_csv_file(self):
        upload = self.cleaned_data["csv_file"]
        if not upload.name.lower().endswith(".csv") or upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError(_("Upload a CSV file of 5 MB or less."))
        return upload
