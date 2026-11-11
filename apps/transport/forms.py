# apps/transport/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    Vehicle, Driver, Attendant, Route, RouteStop, RouteSchedule,
    TransportAllocation, MaintenanceRecord, FuelRecord, IncidentReport
)


class VehicleForm(forms.ModelForm):
    """Form for Vehicle model with enhanced validation."""
    
    class Meta:
        model = Vehicle
        fields = [
            'vehicle_number', 'registration_number', 'vehicle_type', 'make', 'model',
            'year', 'color', 'seating_capacity', 'fuel_type', 'insurance_number',
            'insurance_expiry', 'fitness_certificate_number', 'fitness_expiry',
            'purchase_date', 'purchase_price', 'current_mileage', 'notes', 'status'
        ]
        widgets = {
            'insurance_expiry': forms.DateInput(attrs={'type': 'date'}),
            'fitness_expiry': forms.DateInput(attrs={'type': 'date'}),
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'color': forms.TextInput(attrs={'type': 'color'}),
        }
        help_texts = {
            'vehicle_number': _('Unique identifier for the vehicle'),
            'registration_number': _('Official registration number'),
            'current_mileage': _('Current mileage in kilometers'),
        }

    def clean_year(self):
        year = self.cleaned_data.get('year')
        if year and (year < 2000 or year > 2030):
            raise ValidationError(_('Manufacturing year must be between 2000 and 2030.'))
        return year

    def clean_insurance_expiry(self):
        expiry = self.cleaned_data.get('insurance_expiry')
        if expiry and expiry < timezone.now().date():
            raise ValidationError(_('Insurance expiry date cannot be in the past.'))
        return expiry

    def clean_fitness_expiry(self):
        expiry = self.cleaned_data.get('fitness_expiry')
        if expiry and expiry < timezone.now().date():
            raise ValidationError(_('Fitness expiry date cannot be in the past.'))
        return expiry


class DriverForm(forms.ModelForm):
    """Form for Driver model with enhanced validation."""
    
    class Meta:
        model = Driver
        fields = [
            'user', 'employee_id', 'license_number', 'license_type', 'license_expiry',
            'date_of_birth', 'date_of_joining', 'salary', 'phone', 'email',
            'emergency_contact_name', 'emergency_contact_relation', 'status'
        ]
        widgets = {
            'license_expiry': forms.DateInput(attrs={'type': 'date'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'date_of_joining': forms.DateInput(attrs={'type': 'date'}),
        }
        help_texts = {
            'employee_id': _('Unique employee identifier'),
            'license_number': _('Valid driving license number'),
        }

    def clean_license_expiry(self):
        expiry = self.cleaned_data.get('license_expiry')
        if expiry and expiry < timezone.now().date():
            raise ValidationError(_('License has expired. Please renew.'))
        return expiry

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            age = (timezone.now().date() - dob).days // 365
            if age < 18:
                raise ValidationError(_('Driver must be at least 18 years old.'))
            if age > 70:
                raise ValidationError(_('Driver cannot be older than 70 years.'))
        return dob


class AttendantForm(forms.ModelForm):
    """Form for Attendant model."""
    
    class Meta:
        model = Attendant
        fields = [
            'user', 'employee_id', 'date_of_birth', 'date_of_joining', 'salary',
            'phone', 'email', 'responsibilities', 'emergency_contact_name',
            'emergency_contact_relation', 'status'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'date_of_joining': forms.DateInput(attrs={'type': 'date'}),
            'responsibilities': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            age = (timezone.now().date() - dob).days // 365
            if age < 18:
                raise ValidationError(_('Attendant must be at least 18 years old.'))
        return dob


class RouteForm(forms.ModelForm):
    """Form for Route model."""
    
    class Meta:
        model = Route
        fields = [
            'name', 'code', 'start_point', 'end_point', 'total_distance',
            'estimated_duration', 'description', 'is_active', 'status'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'code': _('Unique route code identifier'),
            'total_distance': _('Total distance in kilometers'),
            'estimated_duration': _('Estimated travel time in minutes'),
        }

    def clean_total_distance(self):
        distance = self.cleaned_data.get('total_distance')
        if distance and distance <= 0:
            raise ValidationError(_('Distance must be greater than 0.'))
        return distance

    def clean_estimated_duration(self):
        duration = self.cleaned_data.get('estimated_duration')
        if duration and duration <= 0:
            raise ValidationError(_('Duration must be greater than 0 minutes.'))
        return duration


class RouteStopForm(forms.ModelForm):
    """Form for RouteStop model."""
    
    class Meta:
        model = RouteStop
        fields = [
            'route', 'name', 'sequence', 'address', 'latitude', 'longitude',
            'estimated_arrival_time', 'pickup_time', 'drop_time', 'status'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'estimated_arrival_time': forms.TimeInput(attrs={'type': 'time'}),
            'pickup_time': forms.TimeInput(attrs={'type': 'time'}),
            'drop_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean_sequence(self):
        sequence = self.cleaned_data.get('sequence')
        route = self.cleaned_data.get('route')
        
        if route and sequence:
            # Check if sequence is unique for this route
            existing = RouteStop.objects.filter(
                route=route, sequence=sequence
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise ValidationError(
                    _('Stop sequence must be unique for each route.')
                )
        
        return sequence

    def clean_latitude(self):
        latitude = self.cleaned_data.get('latitude')
        if latitude is not None:
            if latitude < -90 or latitude > 90:
                raise ValidationError(_('Latitude must be between -90 and 90.'))
        return latitude

    def clean_longitude(self):
        longitude = self.cleaned_data.get('longitude')
        if longitude is not None:
            if longitude < -180 or longitude > 180:
                raise ValidationError(_('Longitude must be between -180 and 180.'))
        return longitude


class RouteScheduleForm(forms.ModelForm):
    """Form for RouteSchedule model with complex validation."""
    
    class Meta:
        model = RouteSchedule
        fields = [
            'route', 'vehicle', 'driver', 'attendant', 'academic_session',
            'morning_start_time', 'morning_end_time', 'evening_start_time',
            'evening_end_time', 'days_of_week', 'status'
        ]
        widgets = {
            'morning_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'morning_end_time': forms.TimeInput(attrs={'type': 'time'}),
            'evening_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'evening_end_time': forms.TimeInput(attrs={'type': 'time'}),
            'days_of_week': forms.TextInput(attrs={
                'placeholder': 'e.g., 1,2,3,4,5 for Monday-Friday'
            }),
        }
        help_texts = {
            'days_of_week': _('Comma separated: 1=Monday, 2=Tuesday, ..., 7=Sunday'),
        }

    def clean_days_of_week(self):
        days = self.cleaned_data.get('days_of_week')
        if days:
            try:
                day_list = [int(day.strip()) for day in days.split(',')]
                for day in day_list:
                    if day < 1 or day > 7:
                        raise ValueError
            except ValueError:
                raise ValidationError(
                    _('Days must be comma-separated numbers from 1 to 7.')
                )
        return days

    def clean(self):
        cleaned_data = super().clean()
        morning_start = cleaned_data.get('morning_start_time')
        morning_end = cleaned_data.get('morning_end_time')
        evening_start = cleaned_data.get('evening_start_time')
        evening_end = cleaned_data.get('evening_end_time')

        # Validate morning times
        if morning_start and morning_end and morning_end <= morning_start:
            self.add_error(
                'morning_end_time',
                _('Morning end time must be after start time.')
            )

        # Validate evening times if provided
        if evening_start and evening_end:
            if evening_end <= evening_start:
                self.add_error(
                    'evening_end_time',
                    _('Evening end time must be after start time.')
                )
            if morning_end and evening_start <= morning_end:
                self.add_error(
                    'evening_start_time',
                    _('Evening start time must be after morning end time.')
                )

        return cleaned_data


class TransportAllocationForm(forms.ModelForm):
    """Form for TransportAllocation model."""
    
    class Meta:
        model = TransportAllocation
        fields = [
            'student', 'route_schedule', 'pickup_stop', 'drop_stop',
            'allocation_type', 'start_date', 'end_date', 'monthly_fee', 'notes', 'status'
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        route_schedule = cleaned_data.get('route_schedule')
        pickup_stop = cleaned_data.get('pickup_stop')
        drop_stop = cleaned_data.get('drop_stop')

        # Validate date range
        if start_date and end_date and end_date <= start_date:
            self.add_error('end_date', _('End date must be after start date.'))

        # Validate stops belong to the same route
        if pickup_stop and drop_stop and route_schedule:
            if pickup_stop.route != route_schedule.route:
                self.add_error(
                    'pickup_stop',
                    _('Pickup stop must belong to the selected route.')
                )
            if drop_stop.route != route_schedule.route:
                self.add_error(
                    'drop_stop',
                    _('Drop stop must belong to the selected route.')
                )

        # Validate seating capacity
        if route_schedule and start_date:
            vehicle = route_schedule.vehicle
            if vehicle.available_seats <= 0:
                self.add_error(
                    'route_schedule',
                    _('Selected vehicle has no available seats.')
                )

        return cleaned_data


class MaintenanceRecordForm(forms.ModelForm):
    """Form for MaintenanceRecord model."""
    
    class Meta:
        model = MaintenanceRecord
        fields = [
            'vehicle', 'maintenance_type', 'date', 'odometer_reading',
            'description', 'work_done', 'parts_replaced', 'cost',
            'next_due_odometer', 'next_due_date', 'service_center',
            'invoice_number', 'status'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'next_due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'work_done': forms.Textarea(attrs={'rows': 3}),
            'parts_replaced': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise ValidationError(_('Maintenance date cannot be in the future.'))
        return date

    def clean_next_due_date(self):
        next_due_date = self.cleaned_data.get('next_due_date')
        maintenance_date = self.cleaned_data.get('date')
        
        if next_due_date and maintenance_date and next_due_date <= maintenance_date:
            raise ValidationError(_('Next due date must be after maintenance date.'))
        
        return next_due_date

    def clean_odometer_reading(self):
        reading = self.cleaned_data.get('odometer_reading')
        vehicle = self.cleaned_data.get('vehicle')
        
        if reading and vehicle and reading < vehicle.current_mileage:
            raise ValidationError(
                _('Odometer reading cannot be less than current vehicle mileage.')
            )
        
        return reading


class FuelRecordForm(forms.ModelForm):
    """Form for FuelRecord model."""
    
    class Meta:
        model = FuelRecord
        fields = [
            'vehicle', 'date', 'odometer_reading', 'fuel_quantity',
            'fuel_cost', 'fuel_station', 'invoice_number', 'notes', 'status'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise ValidationError(_('Fuel record date cannot be in the future.'))
        return date

    def clean_odometer_reading(self):
        reading = self.cleaned_data.get('odometer_reading')
        vehicle = self.cleaned_data.get('vehicle')
        
        if reading and vehicle:
            # Check if this is not the first record
            previous = FuelRecord.objects.filter(
                vehicle=vehicle
            ).exclude(pk=self.instance.pk if self.instance else None).order_by('-date').first()
            
            if previous and reading <= previous.odometer_reading:
                raise ValidationError(
                    _('Odometer reading must be greater than previous reading.')
                )
        
        return reading

    def clean_fuel_quantity(self):
        quantity = self.cleaned_data.get('fuel_quantity')
        if quantity and quantity <= 0:
            raise ValidationError(_('Fuel quantity must be greater than 0.'))
        return quantity

    def clean_fuel_cost(self):
        cost = self.cleaned_data.get('fuel_cost')
        if cost and cost < 0:
            raise ValidationError(_('Fuel cost cannot be negative.'))
        return cost


class IncidentReportForm(forms.ModelForm):
    """Form for IncidentReport model."""
    
    class Meta:
        model = IncidentReport
        fields = [
            'route_schedule', 'incident_type', 'severity', 'date', 'time',
            'location', 'description', 'action_taken', 'reported_by',
            'students_affected', 'follow_up_required', 'follow_up_notes', 'status'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'action_taken': forms.Textarea(attrs={'rows': 3}),
            'follow_up_notes': forms.Textarea(attrs={'rows': 2}),
            'students_affected': forms.SelectMultiple(attrs={'class': 'select2'}),
        }

    def clean_date(self):
        date = self.cleaned_data.get('date')
        if date and date > timezone.now().date():
            raise ValidationError(_('Incident date cannot be in the future.'))
        return date


# Bulk and Search Forms
class VehicleSearchForm(forms.Form):
    """Form for searching vehicles."""
    
    vehicle_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by vehicle number...')})
    )
    vehicle_type = forms.ChoiceField(
        required=False,
        choices=[('', _('All Types'))] + list(Vehicle.VehicleType.choices)
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', _('All Status'))] + list(Vehicle.Status.choices)
    )
    insurance_expired = forms.BooleanField(required=False, label=_('Insurance Expired'))
    fitness_expired = forms.BooleanField(required=False, label=_('Fitness Expired'))


class DriverSearchForm(forms.Form):
    """Form for searching drivers."""
    
    employee_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by employee ID...')})
    )
    license_type = forms.ChoiceField(
        required=False,
        choices=[('', _('All Types'))] + list(Driver.LicenseType.choices)
    )
    license_expired = forms.BooleanField(required=False, label=_('License Expired'))
    status = forms.ChoiceField(
        required=False,
        choices=[('', _('All Status'))] + list(Driver.Status.choices)
    )


class RouteSearchForm(forms.Form):
    """Form for searching routes."""
    
    code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by route code...')})
    )
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by route name...')})
    )
    is_active = forms.BooleanField(required=False, label=_('Active Routes Only'))
    status = forms.ChoiceField(
        required=False,
        choices=[('', _('All Status'))] + list(Route.Status.choices)
    )


class BulkAllocationForm(forms.Form):
    """Form for bulk transport allocation."""
    
    academic_session = forms.ModelChoiceField(
        queryset=None,
        label=_('Academic Session'),
        help_text=_('Select academic session for allocation')
    )
    route_schedule = forms.ModelChoiceField(
        queryset=None,
        label=_('Route Schedule'),
        help_text=_('Select route schedule')
    )
    students = forms.ModelMultipleChoiceField(
        queryset=None,
        label=_('Students'),
        widget=forms.SelectMultiple(attrs={'class': 'select2'}),
        help_text=_('Select students to allocate')
    )
    allocation_type = forms.ChoiceField(
        choices=TransportAllocation.AllocationType.choices,
        initial=TransportAllocation.AllocationType.BOTH,
        label=_('Allocation Type')
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Start Date')
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # These would be set in the view based on context
        from apps.core.models import AcademicSession
        from apps.academics.models import Student
        
        self.fields['academic_session'].queryset = AcademicSession.objects.all()
        self.fields['route_schedule'].queryset = RouteSchedule.objects.all()
        self.fields['students'].queryset = Student.objects.all()

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if start_date and start_date < timezone.now().date():
            raise ValidationError(_('Start date cannot be in the past.'))
        return start_date


class MaintenanceReminderForm(forms.Form):
    """Form for maintenance reminder settings."""
    
    days_before_due = forms.IntegerField(
        min_value=1,
        max_value=30,
        initial=7,
        label=_('Days Before Due'),
        help_text=_('Send reminder this many days before maintenance is due')
    )
    include_odometer = forms.BooleanField(
        initial=True,
        label=_('Include Odometer-based Maintenance'),
        help_text=_('Include maintenance based on odometer readings')
    )
    include_date_based = forms.BooleanField(
        initial=True,
        label=_('Include Date-based Maintenance'),
        help_text=_('Include maintenance based on scheduled dates')
    )


# File Import Forms
class VehicleImportForm(forms.Form):
    """Form for importing vehicles from CSV/Excel."""
    
    file = forms.FileField(
        label=_('Import File'),
        help_text=_('CSV or Excel file containing vehicle data')
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Update Existing Vehicles'),
        help_text=_('Update vehicles that already exist based on vehicle number')
    )


class RouteImportForm(forms.Form):
    """Form for importing routes from CSV/Excel."""
    
    file = forms.FileField(
        label=_('Import File'),
        help_text=_('CSV or Excel file containing route data')
    )
    import_stops = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Import Route Stops'),
        help_text=_('Import route stops along with routes')
    )


# Report Generation Forms
class TransportReportForm(forms.Form):
    """Form for generating transport reports."""

    REPORT_TYPES = [
        ('vehicle_utilization', _('Vehicle Utilization Report')),
        ('driver_performance', _('Driver Performance Report')),
        ('route_efficiency', _('Route Efficiency Report')),
        ('maintenance_summary', _('Maintenance Summary Report')),
        ('fuel_consumption', _('Fuel Consumption Report')),
    ]

    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        label=_('Report Type')
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Start Date')
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('End Date')
    )
    format = forms.ChoiceField(
        choices=[('pdf', 'PDF'), ('excel', 'Excel'), ('csv', 'CSV')],
        initial='pdf',
        label=_('Output Format')
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', _('End date must be after start date.'))

        return cleaned_data


class BulkTransportNotificationForm(forms.Form):
    """Form for sending bulk transport notifications to parents."""

    NOTIFICATION_TYPES = [
        ('allocation', _('Transport Allocation Details')),
        ('schedule_change', _('Schedule Change Notification')),
        ('emergency', _('Emergency/Incident Alert')),
        ('fee_reminder', _('Fee Payment Reminder')),
        ('general', _('General Transport Update')),
    ]

    notification_type = forms.ChoiceField(
        choices=NOTIFICATION_TYPES,
        label=_('Notification Type'),
        help_text=_('Select the type of notification to send')
    )

    recipients = forms.ModelMultipleChoiceField(
        queryset=None,
        label=_('Recipients'),
        widget=forms.SelectMultiple(attrs={'class': 'select2'}),
        help_text=_('Select students whose parents will receive the notification')
    )

    subject = forms.CharField(
        max_length=200,
        label=_('Subject'),
        help_text=_('Email/SMS subject line')
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 6}),
        label=_('Message'),
        help_text=_('The notification message to send to parents')
    )

    send_email = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Send Email'),
        help_text=_('Send notification via email')
    )

    send_sms = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Send SMS'),
        help_text=_('Send notification via SMS (additional charges may apply)')
    )

    priority = forms.ChoiceField(
        choices=[
            ('normal', _('Normal')),
            ('high', _('High')),
            ('urgent', _('Urgent')),
        ],
        initial='normal',
        label=_('Priority'),
        help_text=_('Message priority level')
    )

    schedule_send = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        label=_('Schedule Send'),
        help_text=_('Leave empty to send immediately, or set a future date/time')
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set recipients queryset to active transport allocations
        from .models import TransportAllocation
        self.fields['recipients'].queryset = TransportAllocation.objects.filter(
            status='active'
        ).select_related('student')

    def clean(self):
        cleaned_data = super().clean()
        send_email = cleaned_data.get('send_email')
        send_sms = cleaned_data.get('send_sms')

        if not send_email and not send_sms:
            raise forms.ValidationError(_('At least one delivery method (Email or SMS) must be selected.'))

        return cleaned_data
