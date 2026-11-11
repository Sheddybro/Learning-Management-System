# apps/analytics/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import (
    ReportType, Report, Dashboard, KPI, KPIMeasurement, DataExport,
    AnalyticsCache, TrendAnalysis
)


class ReportTypeForm(forms.ModelForm):
    """
    Form for creating and updating ReportType instances.
    """
    class Meta:
        model = ReportType
        fields = [
            'name', 'code', 'category', 'description', 'data_source',
            'is_standard', 'parameters_schema', 'refresh_frequency',
            'access_roles', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Student Performance Report, Financial Summary')
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., student_performance, financial_summary')
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Report type description and purpose')
            }),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., academics.Student, finance.Invoice')
            }),
            'is_standard': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'parameters_schema': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('JSON schema for report parameters')
            }),
            'refresh_frequency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'access_roles': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('JSON array of allowed role types')
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
        help_texts = {
            'code': _('Unique slug identifier for this report type'),
            'parameters_schema': _('Define the parameters this report accepts in JSON schema format'),
            'access_roles': _('List of role types that can access this report (e.g., ["admin", "teacher"])'),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.lower().strip().replace(' ', '_')
            # Check for duplicate codes
            duplicate_report_types = ReportType.objects.filter(code=code)
            if self.instance.pk:
                duplicate_report_types = duplicate_report_types.exclude(pk=self.instance.pk)
            
            if duplicate_report_types.exists():
                raise ValidationError(
                    _("A report type with this code already exists.")
                )
        return code

    def clean_parameters_schema(self):
        parameters_schema = self.cleaned_data.get('parameters_schema')
        if parameters_schema:
            try:
                import json
                json.loads(parameters_schema)
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Parameters schema must be valid JSON.")
                )
        return parameters_schema

    def clean_access_roles(self):
        access_roles = self.cleaned_data.get('access_roles')
        if access_roles:
            try:
                import json
                roles = json.loads(access_roles)
                if not isinstance(roles, list):
                    raise ValidationError(
                        _("Access roles must be a JSON array.")
                    )
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Access roles must be valid JSON.")
                )
        return access_roles


class ReportForm(forms.ModelForm):
    """
    Form for creating and updating Report instances.
    """
    class Meta:
        model = Report
        fields = [
            'report_type', 'name', 'academic_session', 'parameters',
            'format', 'status'
        ]
        widgets = {
            'report_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Report name')
            }),
            'academic_session': forms.Select(attrs={
                'class': 'form-control'
            }),
            'parameters': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Report parameters in JSON format')
            }),
            'format': forms.Select(attrs={
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
        help_texts = {
            'parameters': _('Parameters for this report in JSON format'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.models import AcademicSession
        self.fields['academic_session'].queryset = AcademicSession.objects.filter(status='active')

    def clean_parameters(self):
        parameters = self.cleaned_data.get('parameters')
        if parameters:
            try:
                import json
                json.loads(parameters)
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Parameters must be valid JSON.")
                )
        return parameters


class ReportGenerationForm(forms.Form):
    """
    Form for generating reports with dynamic parameters.
    """
    def __init__(self, *args, **kwargs):
        self.report_type = kwargs.pop('report_type', None)
        super().__init__(*args, **kwargs)
        
        if self.report_type and self.report_type.parameters_schema:
            try:
                import json
                schema = json.loads(self.report_type.parameters_schema)
                self._build_dynamic_fields(schema)
            except json.JSONDecodeError:
                pass

    def _build_dynamic_fields(self, schema):
        """
        Build form fields dynamically based on JSON schema.
        """
        properties = schema.get('properties', {})
        required_fields = schema.get('required', [])

        for field_name, field_config in properties.items():
            field_type = field_config.get('type', 'string')
            field_title = field_config.get('title', field_name.replace('_', ' ').title())
            field_description = field_config.get('description', '')
            
            if field_type == 'string':
                self.fields[field_name] = forms.CharField(
                    label=field_title,
                    help_text=field_description,
                    required=field_name in required_fields,
                    widget=forms.TextInput(attrs={'class': 'form-control'})
                )
            elif field_type == 'number':
                self.fields[field_name] = forms.FloatField(
                    label=field_title,
                    help_text=field_description,
                    required=field_name in required_fields,
                    widget=forms.NumberInput(attrs={'class': 'form-control'})
                )
            elif field_type == 'integer':
                self.fields[field_name] = forms.IntegerField(
                    label=field_title,
                    help_text=field_description,
                    required=field_name in required_fields,
                    widget=forms.NumberInput(attrs={'class': 'form-control'})
                )
            elif field_type == 'boolean':
                self.fields[field_name] = forms.BooleanField(
                    label=field_title,
                    help_text=field_description,
                    required=field_name in required_fields,
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )
            elif field_type == 'array':
                self.fields[field_name] = forms.MultipleChoiceField(
                    label=field_title,
                    help_text=field_description,
                    required=field_name in required_fields,
                    choices=[(opt, opt) for opt in field_config.get('enum', [])],
                    widget=forms.SelectMultiple(attrs={'class': 'form-control'})
                )


class DashboardForm(forms.ModelForm):
    """
    Form for creating and updating Dashboard instances.
    """
    class Meta:
        model = Dashboard
        fields = [
            'name', 'description', 'dashboard_type', 'owner',
            'layout_config', 'widget_config', 'is_default',
            'refresh_interval', 'access_roles', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Dashboard name')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Dashboard description and purpose')
            }),
            'dashboard_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'owner': forms.Select(attrs={
                'class': 'form-control'
            }),
            'layout_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': _('Dashboard layout configuration in JSON')
            }),
            'widget_config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': _('Widget configuration in JSON')
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'refresh_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 1440
            }),
            'access_roles': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('JSON array of allowed role types')
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
        help_texts = {
            'refresh_interval': _('Dashboard refresh interval in minutes (1-1440)'),
            'layout_config': _('Grid layout configuration for dashboard widgets'),
            'widget_config': _('Configuration for each widget on the dashboard'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.users.models import User
        self.fields['owner'].queryset = User.objects.filter(is_active=True)

    def clean_layout_config(self):
        layout_config = self.cleaned_data.get('layout_config')
        if layout_config:
            try:
                import json
                json.loads(layout_config)
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Layout configuration must be valid JSON.")
                )
        return layout_config

    def clean_widget_config(self):
        widget_config = self.cleaned_data.get('widget_config')
        if widget_config:
            try:
                import json
                json.loads(widget_config)
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Widget configuration must be valid JSON.")
                )
        return widget_config

    def clean_access_roles(self):
        access_roles = self.cleaned_data.get('access_roles')
        if access_roles:
            try:
                import json
                roles = json.loads(access_roles)
                if not isinstance(roles, list):
                    raise ValidationError(
                        _("Access roles must be a JSON array.")
                    )
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Access roles must be valid JSON.")
                )
        return access_roles


class KPIForm(forms.ModelForm):
    """
    Form for creating and updating KPI instances.
    """
    class Meta:
        model = KPI
        fields = [
            'name', 'code', 'category', 'description', 'value_type',
            'target_value', 'min_value', 'max_value', 'calculation_query',
            'data_source', 'refresh_frequency', 'is_trending',
            'display_format', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Student Attendance Rate, Revenue Growth')
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., student_attendance, revenue_growth')
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('KPI description and calculation method')
            }),
            'value_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'target_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'min_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'max_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'calculation_query': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('SQL query or calculation logic for this KPI')
            }),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Data source for this KPI')
            }),
            'refresh_frequency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_trending': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'display_format': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., {value}%, ${value:,}')
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
        help_texts = {
            'code': _('Unique identifier for this KPI'),
            'display_format': _('Format string for displaying KPI values'),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.lower().strip().replace(' ', '_')
            # Check for duplicate codes
            duplicate_kpis = KPI.objects.filter(code=code)
            if self.instance.pk:
                duplicate_kpis = duplicate_kpis.exclude(pk=self.instance.pk)
            
            if duplicate_kpis.exists():
                raise ValidationError(
                    _("A KPI with this code already exists.")
                )
        return code

    def clean(self):
        cleaned_data = super().clean()
        target_value = cleaned_data.get('target_value')
        min_value = cleaned_data.get('min_value')
        max_value = cleaned_data.get('max_value')

        # Validate value ranges
        if min_value is not None and max_value is not None:
            if min_value >= max_value:
                raise ValidationError({
                    'max_value': _('Maximum value must be greater than minimum value.')
                })

        if target_value is not None:
            if min_value is not None and target_value < min_value:
                raise ValidationError({
                    'target_value': _('Target value cannot be less than minimum value.')
                })
            if max_value is not None and target_value > max_value:
                raise ValidationError({
                    'target_value': _('Target value cannot be greater than maximum value.')
                })

        return cleaned_data


class KPIMeasurementForm(forms.ModelForm):
    """
    Form for creating and updating KPI Measurement instances.
    """
    class Meta:
        model = KPIMeasurement
        fields = [
            'kpi', 'academic_session', 'measured_at', 'value',
            'previous_value', 'metadata'
        ]
        widgets = {
            'kpi': forms.Select(attrs={
                'class': 'form-control'
            }),
            'academic_session': forms.Select(attrs={
                'class': 'form-control'
            }),
            'measured_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'previous_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'metadata': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Additional measurement metadata in JSON')
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.models import AcademicSession
        self.fields['academic_session'].queryset = AcademicSession.objects.filter(status='active')

    def clean_measured_at(self):
        measured_at = self.cleaned_data.get('measured_at')
        if measured_at:
            if measured_at > timezone.now():
                raise ValidationError(
                    _("Measurement date cannot be in the future.")
                )
        return measured_at

    def clean_metadata(self):
        metadata = self.cleaned_data.get('metadata')
        if metadata:
            try:
                import json
                json.loads(metadata)
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Metadata must be valid JSON.")
                )
        return metadata

    def clean(self):
        cleaned_data = super().clean()
        kpi = cleaned_data.get('kpi')
        value = cleaned_data.get('value')
        measured_at = cleaned_data.get('measured_at')

        if kpi and measured_at:
            # Check for duplicate measurements for the same KPI and timestamp
            duplicate_measurements = KPIMeasurement.objects.filter(
                kpi=kpi,
                measured_at=measured_at
            )
            if self.instance.pk:
                duplicate_measurements = duplicate_measurements.exclude(pk=self.instance.pk)
            
            if duplicate_measurements.exists():
                raise ValidationError(
                    _("A measurement for this KPI already exists at the specified time.")
                )

        # Validate value against KPI constraints
        if kpi and value is not None:
            if kpi.min_value is not None and value < kpi.min_value:
                raise ValidationError({
                    'value': _("Value cannot be less than the KPI's minimum value ({min}).").format(
                        min=kpi.min_value
                    )
                })
            if kpi.max_value is not None and value > kpi.max_value:
                raise ValidationError({
                    'value': _("Value cannot be greater than the KPI's maximum value ({max}).").format(
                        max=kpi.max_value
                    )
                })

        return cleaned_data


class DataExportForm(forms.ModelForm):
    """
    Form for creating and updating DataExport instances.
    """
    class Meta:
        model = DataExport
        fields = [
            'name', 'description', 'data_source', 'filters',
            'columns', 'format', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Export name')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Export description and purpose')
            }),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., academics.Student, finance.Invoice')
            }),
            'filters': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Export filters in JSON format')
            }),
            'columns': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Columns to include in JSON array format')
            }),
            'format': forms.Select(attrs={
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }

    def clean_filters(self):
        filters = self.cleaned_data.get('filters')
        if filters:
            try:
                import json
                json.loads(filters)
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Filters must be valid JSON.")
                )
        return filters

    def clean_columns(self):
        columns = self.cleaned_data.get('columns')
        if columns:
            try:
                import json
                cols = json.loads(columns)
                if not isinstance(cols, list):
                    raise ValidationError(
                        _("Columns must be a JSON array.")
                    )
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Columns must be valid JSON.")
                )
        return columns


class AnalyticsCacheForm(forms.ModelForm):
    """
    Form for creating and updating AnalyticsCache instances.
    """
    class Meta:
        model = AnalyticsCache
        fields = [
            'cache_key', 'data', 'data_source', 'expires_at', 'status'
        ]
        widgets = {
            'cache_key': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Cache key identifier')
            }),
            'data': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': _('Cached data in JSON format')
            }),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Data source for this cache')
            }),
            'expires_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }

    def clean_data(self):
        data = self.cleaned_data.get('data')
        if data:
            try:
                import json
                json.loads(data)
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Cached data must be valid JSON.")
                )
        return data

    def clean_expires_at(self):
        expires_at = self.cleaned_data.get('expires_at')
        if expires_at:
            if expires_at <= timezone.now():
                raise ValidationError(
                    _("Expiration date must be in the future.")
                )
        return expires_at


class TrendAnalysisForm(forms.ModelForm):
    """
    Form for creating and updating TrendAnalysis instances.
    """
    class Meta:
        model = TrendAnalysis
        fields = [
            'name', 'description', 'data_source', 'analysis_period',
            'start_date', 'end_date', 'trend_direction', 'confidence_score',
            'key_findings', 'recommendations', 'data_points', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Trend analysis name')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Analysis description and methodology')
            }),
            'data_source': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Data source for analysis')
            }),
            'analysis_period': forms.Select(attrs={
                'class': 'form-control'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'trend_direction': forms.Select(attrs={
                'class': 'form-control'
            }),
            'confidence_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': 0,
                'max': 100
            }),
            'key_findings': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Key findings from the analysis in JSON format')
            }),
            'recommendations': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Recommendations based on analysis in JSON format')
            }),
            'data_points': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': _('Analysis data points in JSON format')
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        confidence_score = cleaned_data.get('confidence_score')

        # Validate date range
        if start_date and end_date:
            if start_date >= end_date:
                raise ValidationError({
                    'end_date': _('End date must be after start date.')
                })

            # Validate analysis period is reasonable
            days_diff = (end_date - start_date).days
            if days_diff < 1:
                raise ValidationError({
                    'end_date': _('Analysis period must be at least 1 day.')
                })

        # Validate confidence score
        if confidence_score:
            if confidence_score < 0 or confidence_score > 100:
                raise ValidationError({
                    'confidence_score': _('Confidence score must be between 0 and 100.')
                })

        return cleaned_data

    def clean_key_findings(self):
        key_findings = self.cleaned_data.get('key_findings')
        if key_findings:
            try:
                import json
                json.loads(key_findings)
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Key findings must be valid JSON.")
                )
        return key_findings

    def clean_recommendations(self):
        recommendations = self.cleaned_data.get('recommendations')
        if recommendations:
            try:
                import json
                json.loads(recommendations)
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Recommendations must be valid JSON.")
                )
        return recommendations

    def clean_data_points(self):
        data_points = self.cleaned_data.get('data_points')
        if data_points:
            try:
                import json
                json.loads(data_points)
            except json.JSONDecodeError:
                raise ValidationError(
                    _("Data points must be valid JSON.")
                )
        return data_points


class ReportSearchForm(forms.Form):
    """
    Form for searching and filtering reports.
    """
    CATEGORY_CHOICES = [('', _('All Categories'))] + list(ReportType.ReportCategory.choices)
    STATUS_CHOICES = [('', _('All Status'))] + list(Report.ReportStatus.choices)

    name = forms.CharField(
        required=False,
        label=_('Report Name'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by report name')
        })
    )
    report_type = forms.ModelChoiceField(
        queryset=ReportType.objects.filter(status='active'),
        required=False,
        label=_('Report Type'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        required=False,
        label=_('Category'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    academic_session = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        label=_('Academic Session'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        label=_('Status'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_range = forms.ChoiceField(
        choices=[
            ('', _('Any Time')),
            ('today', _('Today')),
            ('week', _('This Week')),
            ('month', _('This Month')),
            ('year', _('This Year')),
            ('custom', _('Custom Range')),
        ],
        required=False,
        label=_('Date Range'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        required=False,
        label=_('From Date'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    end_date = forms.DateField(
        required=False,
        label=_('To Date'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.models import AcademicSession
        self.fields['academic_session'].queryset = AcademicSession.objects.filter(status='active')

    def clean(self):
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if date_range == 'custom':
            if not start_date or not end_date:
                raise ValidationError(
                    _('Both start date and end date are required for custom date range.')
                )
            if start_date > end_date:
                raise ValidationError(
                    _('Start date cannot be after end date.')
                )

        return cleaned_data


class KPISearchForm(forms.Form):
    """
    Form for searching and filtering KPIs.
    """
    name = forms.CharField(
        required=False,
        label=_('KPI Name'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by KPI name')
        })
    )
    category = forms.ChoiceField(
        choices=[('', _('All Categories'))] + list(KPI.KPICategory.choices),
        required=False,
        label=_('Category'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    value_type = forms.ChoiceField(
        choices=[('', _('All Types'))] + list(KPI.ValueType.choices),
        required=False,
        label=_('Value Type'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    refresh_frequency = forms.ChoiceField(
        choices=[('', _('All Frequencies'))] + [
            ('realtime', _('Real-time')),
            ('hourly', _('Hourly')),
            ('daily', _('Daily')),
            ('weekly', _('Weekly')),
            ('monthly', _('Monthly'))
        ],
        required=False,
        label=_('Refresh Frequency'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class DataExportRequestForm(forms.Form):
    """
    Form for requesting data exports with filters.
    """
    FORMAT_CHOICES = [
        ('excel', _('Excel')),
        ('csv', _('CSV')),
        ('json', _('JSON')),
    ]

    export_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Name for this export')
        })
    )
    data_source = forms.ChoiceField(
        choices=[
            ('students', _('Students Data')),
            ('teachers', _('Teachers Data')),
            ('attendance', _('Attendance Records')),
            ('grades', _('Academic Records')),
            ('financial', _('Financial Data')),
            ('library', _('Library Records')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    export_format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        initial='excel',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_range = forms.ChoiceField(
        choices=[
            ('all', _('All Time')),
            ('current_session', _('Current Academic Session')),
            ('last_month', _('Last Month')),
            ('last_quarter', _('Last Quarter')),
            ('last_year', _('Last Year')),
            ('custom', _('Custom Range')),
        ],
        initial='current_session',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    include_sensitive_data = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Include sensitive data'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean(self):
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if date_range == 'custom':
            if not start_date or not end_date:
                raise ValidationError(
                    _('Both start date and end date are required for custom date range.')
                )
            if start_date > end_date:
                raise ValidationError(
                    _('Start date cannot be after end date.')
                )

        return cleaned_data


class AnalyticsSettingsForm(forms.Form):
    """
    Form for configuring analytics settings.
    """
    cache_duration = forms.IntegerField(
        min_value=1,
        max_value=1440,
        initial=60,
        label=_('Cache Duration (minutes)'),
        help_text=_('How long to cache analytics data (1-1440 minutes)'),
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    auto_refresh_interval = forms.IntegerField(
        min_value=1,
        max_value=120,
        initial=15,
        label=_('Auto-refresh Interval (minutes)'),
        help_text=_('Dashboard auto-refresh interval (1-120 minutes)'),
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    data_retention_months = forms.IntegerField(
        min_value=1,
        max_value=60,
        initial=24,
        label=_('Data Retention (months)'),
        help_text=_('How long to keep analytics data (1-60 months)'),
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    enable_real_time_analytics = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Enable Real-time Analytics'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    enable_anonymized_data = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Enable Anonymized Data Collection'),
        help_text=_('Collect anonymized data for system improvement'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    max_export_records = forms.IntegerField(
        min_value=100,
        max_value=100000,
        initial=10000,
        label=_('Maximum Export Records'),
        help_text=_('Maximum number of records allowed in a single export'),
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )