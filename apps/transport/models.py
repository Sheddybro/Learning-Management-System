# apps/transport/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from apps.core.models import CoreBaseModel, AddressModel, ContactModel


class Vehicle(CoreBaseModel):
    """
    Model for managing transport vehicles (buses, vans, etc.).
    """
    
    class VehicleType(models.TextChoices):
        BUS = 'bus', _('Bus')
        MINIBUS = 'minibus', _('Minibus')
        VAN = 'van', _('Van')
        CAR = 'car', _('Car')
        OTHER = 'other', _('Other')

    class FuelType(models.TextChoices):
        PETROL = 'petrol', _('Petrol')
        DIESEL = 'diesel', _('Diesel')
        ELECTRIC = 'electric', _('Electric')
        HYBRID = 'hybrid', _('Hybrid')
        CNG = 'cng', _('CNG')

    vehicle_number = models.CharField(_('vehicle number'), max_length=20, unique=True)
    registration_number = models.CharField(_('registration number'), max_length=20, unique=True)
    vehicle_type = models.CharField(
        _('vehicle type'),
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.BUS
    )
    make = models.CharField(_('make'), max_length=50)
    model = models.CharField(_('model'), max_length=50)
    year = models.PositiveIntegerField(
        _('manufacturing year'),
        validators=[MinValueValidator(2000), MaxValueValidator(2030)]
    )
    color = models.CharField(_('color'), max_length=30, blank=True)
    seating_capacity = models.PositiveIntegerField(
        _('seating capacity'),
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    fuel_type = models.CharField(
        _('fuel type'),
        max_length=20,
        choices=FuelType.choices,
        default=FuelType.DIESEL
    )
    insurance_number = models.CharField(_('insurance number'), max_length=50, blank=True)
    insurance_expiry = models.DateField(_('insurance expiry date'), null=True, blank=True)
    fitness_certificate_number = models.CharField(_('fitness certificate number'), max_length=50, blank=True)
    fitness_expiry = models.DateField(_('fitness expiry date'), null=True, blank=True)
    purchase_date = models.DateField(_('purchase date'), null=True, blank=True)
    purchase_price = models.DecimalField(
        _('purchase price'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    current_mileage = models.PositiveIntegerField(_('current mileage (km)'), default=0)
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('Vehicle')
        verbose_name_plural = _('Vehicles')
        ordering = ['vehicle_number']
        indexes = [
            models.Index(fields=['vehicle_type', 'status']),
            models.Index(fields=['insurance_expiry']),
            models.Index(fields=['fitness_expiry']),
        ]

    def __str__(self):
        return f"{self.vehicle_number} - {self.make} {self.model}"

    @property
    def available_seats(self):
        """Calculate available seats by subtracting allocated students."""
        allocated_count = self.route_schedules.filter(
            student_allocations__status='active',
            academic_session__is_current=True
        ).aggregate(
            total_allocated=models.Count('student_allocations', distinct=True)
        )['total_allocated'] or 0
        return max(0, self.seating_capacity - allocated_count)

    @property
    def is_insurance_expired(self):
        """Check if insurance is expired."""
        from django.utils import timezone
        if self.insurance_expiry:
            return self.insurance_expiry < timezone.now().date()
        return False

    @property
    def is_fitness_expired(self):
        """Check if fitness certificate is expired."""
        from django.utils import timezone
        if self.fitness_expiry:
            return self.fitness_expiry < timezone.now().date()
        return False


class Driver(CoreBaseModel, ContactModel):
    """
    Model for managing vehicle drivers.
    """
    
    class LicenseType(models.TextChoices):
        LMV = 'lmv', _('Light Motor Vehicle')
        HMV = 'hmv', _('Heavy Motor Vehicle')
        MCWG = 'mcwg', _('Motor Cycle With Gear')
        MCWOG = 'mcwog', _('Motor Cycle Without Gear')
        INTERNATIONAL = 'international', _('International')

    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='driver_profile',
        verbose_name=_('user account')
    )
    employee_id = models.CharField(_('employee ID'), max_length=20, unique=True)
    license_number = models.CharField(_('license number'), max_length=30, unique=True)
    license_type = models.CharField(
        _('license type'),
        max_length=20,
        choices=LicenseType.choices,
        default=LicenseType.LMV
    )
    license_expiry = models.DateField(_('license expiry date'))
    date_of_birth = models.DateField(_('date of birth'))
    date_of_joining = models.DateField(_('date of joining'))
    salary = models.DecimalField(
        _('salary'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    emergency_contact_name = models.CharField(_('emergency contact name'), max_length=100, blank=True)
    emergency_contact_relation = models.CharField(_('emergency contact relation'), max_length=50, blank=True)

    class Meta:
        verbose_name = _('Driver')
        verbose_name_plural = _('Drivers')
        ordering = ['employee_id']
        indexes = [
            models.Index(fields=['license_expiry', 'status']),
        ]

    def __str__(self):
        return f"{self.employee_id} - {self.user.get_full_name()}"

    @property
    def age(self):
        """Calculate driver's age."""
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def is_license_expired(self):
        """Check if driver's license is expired."""
        from django.utils import timezone
        return self.license_expiry < timezone.now().date()


class Attendant(CoreBaseModel, ContactModel):
    """
    Model for managing vehicle attendants/conductor.
    """
    
    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='attendant_profile',
        verbose_name=_('user account')
    )
    employee_id = models.CharField(_('employee ID'), max_length=20, unique=True)
    date_of_birth = models.DateField(_('date of birth'))
    date_of_joining = models.DateField(_('date of joining'))
    salary = models.DecimalField(
        _('salary'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    responsibilities = models.TextField(_('responsibilities'), blank=True)
    emergency_contact_name = models.CharField(_('emergency contact name'), max_length=100, blank=True)
    emergency_contact_relation = models.CharField(_('emergency contact relation'), max_length=50, blank=True)

    class Meta:
        verbose_name = _('Attendant')
        verbose_name_plural = _('Attendants')
        ordering = ['employee_id']

    def __str__(self):
        return f"{self.employee_id} - {self.user.get_full_name()}"

    @property
    def age(self):
        """Calculate attendant's age."""
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )


class Route(CoreBaseModel):
    """
    Model for managing transport routes.
    """
    
    name = models.CharField(_('route name'), max_length=100)
    code = models.CharField(_('route code'), max_length=20, unique=True)
    start_point = models.CharField(_('start point'), max_length=200)
    end_point = models.CharField(_('end point'), max_length=200)
    total_distance = models.DecimalField(
        _('total distance (km)'),
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    estimated_duration = models.PositiveIntegerField(
        _('estimated duration (minutes)'),
        help_text=_('Estimated travel time in minutes')
    )
    description = models.TextField(_('description'), blank=True)
    is_active = models.BooleanField(_('is active'), default=True)

    class Meta:
        verbose_name = _('Route')
        verbose_name_plural = _('Routes')
        ordering = ['name']
        indexes = [
            models.Index(fields=['code', 'is_active']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def current_students_count(self):
        """Count active students on this route for current academic session."""
        return self.route_schedules.filter(
            student_allocations__status='active',
            academic_session__is_current=True
        ).aggregate(
            total_student_count=models.Count('student_allocations', distinct=True)
        )['total_student_count'] or 0

    @property
    def current_vehicles_count(self):
        """Count active vehicles assigned to this route."""
        return self.route_schedules.filter(
            status='active',
            academic_session__is_current=True
        ).values('vehicle').distinct().count()


class RouteStop(CoreBaseModel):
    """
    Model for managing stops along a route.
    """
    
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='stops',
        verbose_name=_('route')
    )
    name = models.CharField(_('stop name'), max_length=100)
    sequence = models.PositiveIntegerField(
        _('sequence order'),
        validators=[MinValueValidator(1)]
    )
    address = models.TextField(_('address'))
    latitude = models.DecimalField(
        _('latitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        _('longitude'),
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    estimated_arrival_time = models.TimeField(_('estimated arrival time'))
    pickup_time = models.TimeField(_('pickup time'), null=True, blank=True)
    drop_time = models.TimeField(_('drop time'), null=True, blank=True)

    class Meta:
        verbose_name = _('Route Stop')
        verbose_name_plural = _('Route Stops')
        ordering = ['route', 'sequence']
        unique_together = ['route', 'sequence']
        indexes = [
            models.Index(fields=['route', 'sequence']),
        ]

    def __str__(self):
        return f"{self.route.code} - Stop {self.sequence}: {self.name}"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Ensure sequence is unique for this route
        if RouteStop.objects.filter(
            route=self.route, 
            sequence=self.sequence
        ).exclude(pk=self.pk).exists():
            raise ValidationError(_('Stop sequence must be unique for each route.'))


class RouteSchedule(CoreBaseModel):
    """
    Model for scheduling vehicles on routes.
    """
    
    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name='route_schedules',
        verbose_name=_('route')
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='route_schedules',
        verbose_name=_('vehicle')
    )
    driver = models.ForeignKey(
        Driver,
        on_delete=models.CASCADE,
        related_name='route_schedules',
        verbose_name=_('driver')
    )
    attendant = models.ForeignKey(
        Attendant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='route_schedules',
        verbose_name=_('attendant')
    )
    academic_session = models.ForeignKey(
        'academics.AcademicSession',
        on_delete=models.CASCADE,
        related_name='transport_schedules',
        verbose_name=_('academic session')
    )
    morning_start_time = models.TimeField(_('morning start time'))
    morning_end_time = models.TimeField(_('morning end time'))
    evening_start_time = models.TimeField(_('evening start time'), null=True, blank=True)
    evening_end_time = models.TimeField(_('evening end time'), null=True, blank=True)
    days_of_week = models.CharField(
        _('days of week'),
        max_length=50,
        default='1,2,3,4,5',
        help_text=_('Comma separated: 1=Monday, 2=Tuesday, ..., 7=Sunday')
    )

    class Meta:
        verbose_name = _('Route Schedule')
        verbose_name_plural = _('Route Schedules')
        ordering = ['route', 'morning_start_time']
        unique_together = ['route', 'vehicle', 'academic_session']
        indexes = [
            models.Index(fields=['route', 'academic_session']),
            models.Index(fields=['vehicle', 'status']),
            models.Index(fields=['driver', 'status']),
        ]

    def __str__(self):
        return f"{self.route.code} - {self.vehicle.vehicle_number} - {self.academic_session.name}"

    @property
    def current_students_count(self):
        """Count students allocated to this schedule."""
        return self.student_allocations.filter(status='active').count()

    @property
    def is_operational_today(self):
        """Check if this schedule operates today."""
        from django.utils import timezone
        today_weekday = timezone.now().isoweekday()
        return str(today_weekday) in self.days_of_week.split(',')


class TransportAllocation(CoreBaseModel):
    """
    Model for allocating students to transport routes.
    """
    
    class AllocationType(models.TextChoices):
        MORNING = 'morning', _('Morning Only')
        EVENING = 'evening', _('Evening Only')
        BOTH = 'both', _('Both Morning and Evening')

    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='transport_allocations',
        verbose_name=_('student')
    )
    route_schedule = models.ForeignKey(
        RouteSchedule,
        on_delete=models.CASCADE,
        related_name='student_allocations',
        verbose_name=_('route schedule')
    )
    pickup_stop = models.ForeignKey(
        RouteStop,
        on_delete=models.CASCADE,
        related_name='pickup_allocations',
        verbose_name=_('pickup stop')
    )
    drop_stop = models.ForeignKey(
        RouteStop,
        on_delete=models.CASCADE,
        related_name='drop_allocations',
        verbose_name=_('drop stop')
    )
    allocation_type = models.CharField(
        _('allocation type'),
        max_length=20,
        choices=AllocationType.choices,
        default=AllocationType.BOTH
    )
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'), null=True, blank=True)
    monthly_fee = models.DecimalField(
        _('monthly fee'),
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('Transport Allocation')
        verbose_name_plural = _('Transport Allocations')
        ordering = ['student', '-start_date']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['route_schedule', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.student} - {self.route_schedule.route.code}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.end_date and self.end_date <= self.start_date:
            raise ValidationError(_('End date must be after start date.'))

    @property
    def is_active_allocation(self):
        """Check if allocation is currently active."""
        from django.utils import timezone
        today = timezone.now().date()
        if self.end_date:
            return self.start_date <= today <= self.end_date
        return self.start_date <= today


class MaintenanceRecord(CoreBaseModel):
    """
    Model for tracking vehicle maintenance.
    """
    
    class MaintenanceType(models.TextChoices):
        ROUTINE = 'routine', _('Routine Maintenance')
        REPAIR = 'repair', _('Repair')
        BREAKDOWN = 'breakdown', _('Breakdown Repair')
        ACCIDENT = 'accident', _('Accident Repair')
        UPGRADE = 'upgrade', _('Upgrade')

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='maintenance_records',
        verbose_name=_('vehicle')
    )
    maintenance_type = models.CharField(
        _('maintenance type'),
        max_length=20,
        choices=MaintenanceType.choices,
        default=MaintenanceType.ROUTINE
    )
    date = models.DateField(_('maintenance date'))
    odometer_reading = models.PositiveIntegerField(_('odometer reading (km)'))
    description = models.TextField(_('description'))
    work_done = models.TextField(_('work performed'))
    parts_replaced = models.TextField(_('parts replaced'), blank=True)
    cost = models.DecimalField(
        _('cost'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    next_due_odometer = models.PositiveIntegerField(
        _('next due odometer reading'),
        null=True,
        blank=True
    )
    next_due_date = models.DateField(_('next due date'), null=True, blank=True)
    service_center = models.CharField(_('service center'), max_length=200, blank=True)
    invoice_number = models.CharField(_('invoice number'), max_length=50, blank=True)

    class Meta:
        verbose_name = _('Maintenance Record')
        verbose_name_plural = _('Maintenance Records')
        ordering = ['-date', 'vehicle']
        indexes = [
            models.Index(fields=['vehicle', 'date']),
            models.Index(fields=['maintenance_type', 'date']),
        ]

    def __str__(self):
        return f"{self.vehicle.vehicle_number} - {self.maintenance_type} - {self.date}"

    @property
    def is_overdue(self):
        """Check if next maintenance is overdue."""
        from django.utils import timezone
        if self.next_due_date:
            return self.next_due_date < timezone.now().date()
        return False


class FuelRecord(CoreBaseModel):
    """
    Model for tracking vehicle fuel consumption.
    """
    
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='fuel_records',
        verbose_name=_('vehicle')
    )
    date = models.DateField(_('fuel date'))
    odometer_reading = models.PositiveIntegerField(_('odometer reading (km)'))
    fuel_quantity = models.DecimalField(
        _('fuel quantity (liters)'),
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    fuel_cost = models.DecimalField(
        _('fuel cost'),
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    fuel_station = models.CharField(_('fuel station'), max_length=200, blank=True)
    invoice_number = models.CharField(_('invoice number'), max_length=50, blank=True)
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('Fuel Record')
        verbose_name_plural = _('Fuel Records')
        ordering = ['-date', 'vehicle']
        indexes = [
            models.Index(fields=['vehicle', 'date']),
        ]

    def __str__(self):
        return f"{self.vehicle.vehicle_number} - {self.date} - {self.fuel_quantity}L"

    @property
    def fuel_efficiency(self):
        """Calculate fuel efficiency if previous record exists."""
        previous_record = FuelRecord.objects.filter(
            vehicle=self.vehicle,
            date__lt=self.date
        ).order_by('-date').first()
        
        if previous_record and self.odometer_reading > previous_record.odometer_reading:
            distance = self.odometer_reading - previous_record.odometer_reading
            if self.fuel_quantity > 0:
                return distance / float(self.fuel_quantity)
        return None


class IncidentReport(CoreBaseModel):
    """
    Model for reporting transport-related incidents.
    """
    
    class IncidentType(models.TextChoices):
        ACCIDENT = 'accident', _('Accident')
        BREAKDOWN = 'breakdown', _('Vehicle Breakdown')
        DELAY = 'delay', _('Significant Delay')
        DISCIPLINE = 'discipline', _('Student Discipline Issue')
        OTHER = 'other', _('Other')

    class Severity(models.TextChoices):
        LOW = 'low', _('Low')
        MEDIUM = 'medium', _('Medium')
        HIGH = 'high', _('High')
        CRITICAL = 'critical', _('Critical')

    route_schedule = models.ForeignKey(
        RouteSchedule,
        on_delete=models.CASCADE,
        related_name='incident_reports',
        verbose_name=_('route schedule')
    )
    incident_type = models.CharField(
        _('incident type'),
        max_length=20,
        choices=IncidentType.choices,
        default=IncidentType.OTHER
    )
    severity = models.CharField(
        _('severity'),
        max_length=20,
        choices=Severity.choices,
        default=Severity.MEDIUM
    )
    date = models.DateField(_('incident date'))
    time = models.TimeField(_('incident time'))
    location = models.CharField(_('location'), max_length=200)
    description = models.TextField(_('description'))
    action_taken = models.TextField(_('action taken'))
    reported_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='reported_incidents',
        verbose_name=_('reported by')
    )
    students_affected = models.ManyToManyField(
        'academics.Student',
        related_name='transport_incidents',
        blank=True,
        verbose_name=_('students affected')
    )
    follow_up_required = models.BooleanField(_('follow up required'), default=False)
    follow_up_notes = models.TextField(_('follow up notes'), blank=True)

    class Meta:
        verbose_name = _('Incident Report')
        verbose_name_plural = _('Incident Reports')
        ordering = ['-date', '-time']
        indexes = [
            models.Index(fields=['incident_type', 'severity']),
            models.Index(fields=['date', 'route_schedule']),
        ]

    def __str__(self):
        return f"{self.incident_type} - {self.route_schedule} - {self.date}"
