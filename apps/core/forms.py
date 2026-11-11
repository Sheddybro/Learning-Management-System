# apps/core/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import SystemConfig, SequenceGenerator, Institution, InstitutionConfig
from apps.academics.models import AcademicSession, Holiday, FileAttachment
from .middleware import get_user_accessible_institutions


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


class InstitutionForm(forms.ModelForm):
    """
    Form for creating and updating Institution instances.
    """

    class Meta:
        model = Institution
        fields = [
            "name",
            "code",
            "short_name",
            "description",
            "institution_type",
            "ownership_type",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
            "phone",
            "mobile",
            "email",
            "website",
            "established_date",
            "max_students",
            "max_staff",
            "timezone",
            "is_active",
            "allows_online_enrollment",
            "requires_parent_approval",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Full institution name"),
                }
            ),
            "code": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Unique institution code (e.g., SCH001)"),
                }
            ),
            "short_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Short name or acronym"),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Brief description of the institution"),
                }
            ),
            "institution_type": forms.Select(attrs={"class": "form-control"}),
            "ownership_type": forms.Select(attrs={"class": "form-control"}),
            "address_line_1": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Street address")}
            ),
            "address_line_2": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Apartment, suite, etc."),
                }
            ),
            "city": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("City")}
            ),
            "state": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("State/Province")}
            ),
            "postal_code": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Postal/ZIP code")}
            ),
            "country": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Country")}
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Primary phone number"),
                }
            ),
            "mobile": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Mobile phone number")}
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Primary email address"),
                }
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Institution website URL"),
                }
            ),
            "established_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "max_students": forms.NumberInput(
                attrs={"class": "form-control", "min": 1}
            ),
            "max_staff": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "timezone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("e.g., UTC, America/New_York"),
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "allows_online_enrollment": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "requires_parent_approval": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_code(self):
        code = self.cleaned_data.get("code")
        if code:
            # Ensure code is unique (excluding current instance)
            duplicate_institutions = Institution.objects.filter(code__iexact=code)
            if self.instance.pk:
                duplicate_institutions = duplicate_institutions.exclude(
                    pk=self.instance.pk
                )

            if duplicate_institutions.exists():
                raise ValidationError(
                    _("An institution with this code already exists.")
                )

            # Validate code format
            if not code.replace("_", "").replace("-", "").isalnum():
                raise ValidationError(
                    _(
                        "Institution code can only contain alphanumeric characters, underscores, and hyphens."
                    )
                )

        return code

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if name:
            # Ensure name is unique (excluding current instance)
            duplicate_institutions = Institution.objects.filter(name__iexact=name)
            if self.instance.pk:
                duplicate_institutions = duplicate_institutions.exclude(
                    pk=self.instance.pk
                )

            if duplicate_institutions.exists():
                raise ValidationError(
                    _("An institution with this name already exists.")
                )

        return name


class InstitutionConfigForm(forms.ModelForm):
    """
    Form for creating and updating InstitutionConfig instances.
    """

    class Meta:
        model = InstitutionConfig
        fields = ["system_config", "override_value", "is_active", "status"]
        widgets = {
            "system_config": forms.Select(attrs={"class": "form-control"}),
            "override_value": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Override value as JSON"),
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        institution = kwargs.pop("institution", None)
        super().__init__(*args, **kwargs)

        if institution:
            # Only show configs that allow institution overrides
            self.fields["system_config"].queryset = SystemConfig.objects.filter(
                allows_institution_override=True, status="active"
            ).exclude(
                # Exclude configs that already have overrides for this institution
                institution_overrides__institution=institution
            )

    def clean_override_value(self):
        value = self.cleaned_data.get("override_value")
        # Basic JSON validation
        if value and not value.strip().startswith(("{", "[", '"')):
            try:
                import json

                json.loads(value)
            except (json.JSONDecodeError, ValueError):
                raise ValidationError(_("Override value must be valid JSON format."))
        return value


class InstitutionConfigOverrideForm(forms.Form):
    """
    Form for bulk managing institution configuration overrides.
    """

    def __init__(self, *args, **kwargs):
        institution = kwargs.pop("institution", None)
        super().__init__(*args, **kwargs)

        if institution:
            # Get all system configs that allow overrides
            system_configs = SystemConfig.objects.filter(
                allows_institution_override=True, status="active"
            )

            for config in system_configs:
                # Check if there's an existing override
                existing_override = InstitutionConfig.objects.filter(
                    institution=institution, system_config=config, is_active=True
                ).first()

                field_name = f"config_{config.id}"
                initial_value = (
                    existing_override.override_value
                    if existing_override
                    else config.value
                )

                self.fields[field_name] = forms.CharField(
                    initial=initial_value,
                    label=f"{config.key} ({config.get_config_type_display()})",
                    help_text=config.description,
                    widget=forms.Textarea(
                        attrs={
                            "class": "form-control",
                            "rows": 2,
                            "data-config-id": config.id,
                            "data-has-override": (
                                "true" if existing_override else "false"
                            ),
                        }
                    ),
                    required=False,
                )


class SystemConfigForm(forms.ModelForm):
    """
    Form for creating and updating SystemConfig instances.
    """

    class Meta:
        model = SystemConfig
        fields = [
            "key",
            "value",
            "config_type",
            "description",
            "is_public",
            "is_encrypted",
            "status",
        ]
        widgets = {
            "key": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("e.g., site_name, max_login_attempts"),
                }
            ),
            "value": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": _("Enter configuration value as JSON"),
                }
            ),
            "config_type": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": _("Description of what this configuration controls"),
                }
            ),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_encrypted": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def clean_key(self):
        key = self.cleaned_data.get("key")
        if key:
            # Ensure key follows naming conventions
            if not key.replace("_", "").isalnum():
                raise ValidationError(
                    _("Key can only contain alphanumeric characters and underscores.")
                )

            # Check for duplicate keys (excluding current instance)
            duplicate_configs = SystemConfig.objects.filter(key=key)
            if self.instance.pk:
                duplicate_configs = duplicate_configs.exclude(pk=self.instance.pk)

            if duplicate_configs.exists():
                raise ValidationError(
                    _("A configuration with this key already exists.")
                )

        return key

    def clean_value(self):
        value = self.cleaned_data.get("value")
        # Basic JSON validation - in practice, you might want more robust validation
        if value and not value.strip().startswith(("{", "[", '"')):
            try:
                # Try to parse as simple values
                import json

                json.loads(value)
            except (json.JSONDecodeError, ValueError):
                raise ValidationError(_("Value must be valid JSON format."))
        return value


class SequenceGeneratorForm(InstitutionFormMixin, forms.ModelForm):
    """
    Form for creating and updating SequenceGenerator instances.
    """

    class Meta:
        model = SequenceGenerator
        fields = [
            "institution",
            "sequence_type",
            "prefix",
            "suffix",
            "last_number",
            "padding",
            "reset_frequency",
            "status",
        ]
        widgets = {
            "institution": forms.Select(attrs={"class": "form-control"}),
            "sequence_type": forms.Select(attrs={"class": "form-control"}),
            "prefix": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., STU, EMP, INV")}
            ),
            "suffix": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("e.g., -2024, /FY")}
            ),
            "last_number": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "padding": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "max": 10}
            ),
            "reset_frequency": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }
        help_texts = {
            "last_number": _(
                "The last generated number. Next number will be this + 1."
            ),
            "padding": _("Number of digits to pad with leading zeros (1-10)."),
        }

    def clean_padding(self):
        padding = self.cleaned_data.get("padding")
        if padding and (padding < 1 or padding > 10):
            raise ValidationError(_("Padding must be between 1 and 10 digits."))
        return padding

    def clean_last_number(self):
        last_number = self.cleaned_data.get("last_number")
        if last_number is not None and last_number < 0:
            raise ValidationError(_("Last number cannot be negative."))
        return last_number


class BulkNotificationForm(forms.Form):
    """
    Form for sending bulk notifications to multiple users.
    """

    NOTIFICATION_TYPES = [
        ("info", _("Information")),
        ("success", _("Success")),
        ("warning", _("Warning")),
        ("error", _("Error")),
    ]

    PRIORITY_CHOICES = [
        ("low", _("Low")),
        ("medium", _("Medium")),
        ("high", _("High")),
        ("urgent", _("Urgent")),
    ]

    user_roles = forms.MultipleChoiceField(
        choices=[],  # Will be populated in __init__
        required=False,
        label=_("Target User Roles"),
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
    )
    specific_users = forms.ModelMultipleChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        label=_("Specific Users"),
        widget=forms.SelectMultiple(attrs={"class": "form-control"}),
    )
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": _("Notification title")}
        ),
    )
    message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": _("Notification message"),
            }
        )
    )
    notification_type = forms.ChoiceField(
        choices=NOTIFICATION_TYPES,
        initial="info",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        initial="medium",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    action_url = forms.URLField(
        required=False,
        widget=forms.URLInput(
            attrs={"class": "form-control", "placeholder": _("Optional action URL")}
        ),
    )
    send_email = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Send as email"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    send_sms = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Send as SMS"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Filter users by institution
        from apps.core.middleware import get_user_accessible_institutions
        from apps.users.models import User, Role

        accessible_institutions = (
            get_user_accessible_institutions(user)
            if user
            else Institution.objects.none()
        )
        self.fields["specific_users"].queryset = User.objects.filter(
            is_active=True, institution_user__institution__in=accessible_institutions
        ).distinct()

        self.fields["user_roles"].choices = [
            (role.role_type, role.name) for role in Role.objects.filter(status="active")
        ]

    def clean(self):
        cleaned_data = super().clean()
        user_roles = cleaned_data.get("user_roles")
        specific_users = cleaned_data.get("specific_users")

        if not user_roles and not specific_users:
            raise ValidationError(
                _(
                    "You must select either user roles or specific users to send notifications."
                )
            )

        return cleaned_data


class SystemConfigBulkUpdateForm(forms.Form):
    """
    Form for bulk updating multiple system configurations.
    """

    def __init__(self, *args, **kwargs):
        configs = kwargs.pop("configs", None)
        super().__init__(*args, **kwargs)

        if configs:
            for config in configs:
                field_name = f"config_{config.id}"
                self.fields[field_name] = forms.CharField(
                    initial=config.value,
                    label=config.key,
                    help_text=config.description,
                    widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
                )


class DateRangeForm(forms.Form):
    """
    Generic form for selecting date ranges.
    """

    DATE_RANGE_CHOICES = [
        ("today", _("Today")),
        ("week", _("This Week")),
        ("month", _("This Month")),
        ("quarter", _("This Quarter")),
        ("year", _("This Year")),
        ("custom", _("Custom Range")),
    ]

    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        initial="month",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        date_range = cleaned_data.get("date_range")
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if date_range == "custom":
            if not start_date or not end_date:
                raise ValidationError(
                    _(
                        "Both start date and end date are required for custom date range."
                    )
                )
            if start_date > end_date:
                raise ValidationError(_("Start date cannot be after end date."))

        return cleaned_data
