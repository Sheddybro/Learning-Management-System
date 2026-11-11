# apps/hostels/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import CoreBaseModel, AddressModel, ContactModel


class Hostel(CoreBaseModel, AddressModel, ContactModel):
    """
    Model for managing hostels and their basic information.
    """
    class HostelType(models.TextChoices):
        BOYS = 'boys', _('Boys Hostel')
        GIRLS = 'girls', _('Girls Hostel')
        COED = 'coed', _('Co-educational')
        STAFF = 'staff', _('Staff Quarters')
        GUEST = 'guest', _('Guest House')

    class HostelCategory(models.TextChoices):
        STANDARD = 'standard', _('Standard')
        DELUXE = 'deluxe', _('Deluxe')
        PREMIUM = 'premium', _('Premium')
        ECONOMY = 'economy', _('Economy')

    name = models.CharField(_('hostel name'), max_length=200)
    code = models.CharField(_('hostel code'), max_length=20, unique=True)
    hostel_type = models.CharField(
        _('hostel type'),
        max_length=20,
        choices=HostelType.choices,
        default=HostelType.BOYS
    )
    category = models.CharField(
        _('hostel category'),
        max_length=20,
        choices=HostelCategory.choices,
        default=HostelCategory.STANDARD
    )
    total_floors = models.PositiveIntegerField(_('total floors'), default=1)
    total_rooms = models.PositiveIntegerField(_('total rooms'), default=0)
    capacity = models.PositiveIntegerField(_('total capacity'), default=0)
    current_occupancy = models.PositiveIntegerField(_('current occupancy'), default=0)
    
    # Enhanced staff integration
    warden = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_hostels',
        verbose_name=_('warden')
    )
    assistant_warden = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assistant_managed_hostels',
        verbose_name=_('assistant warden')
    )
    
    # Financial integration
    monthly_rent = models.DecimalField(
        _('monthly rent'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    security_deposit = models.DecimalField(
        _('security deposit'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    
    # Enhanced features
    amenities = models.TextField(
        _('amenities'),
        blank=True,
        help_text=_('Comma-separated list of amenities (WiFi, Laundry, AC, etc.)')
    )
    rules = models.TextField(_('hostel rules'), blank=True)
    description = models.TextField(_('description'), blank=True)
    
    # Academic integration
    allowed_classes = models.ManyToManyField(
        'academics.Class',
        blank=True,
        related_name='allowed_hostels',
        verbose_name=_('allowed classes'),
        help_text=_('Classes allowed to stay in this hostel')
    )
    
    is_active = models.BooleanField(_('is active'), default=True)

    class Meta:
        verbose_name = _('Hostel')
        verbose_name_plural = _('Hostels')
        ordering = ['name']
        indexes = [
            models.Index(fields=['hostel_type', 'is_active']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['current_occupancy', 'capacity']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        if self.current_occupancy > self.capacity:
            raise ValidationError(_('Current occupancy cannot exceed total capacity.'))

    @property
    def available_beds(self):
        """Calculate available beds in the hostel."""
        return self.capacity - self.current_occupancy

    @property
    def occupancy_percentage(self):
        """Calculate occupancy percentage."""
        if self.capacity > 0:
            return round((self.current_occupancy / self.capacity) * 100, 2)
        return 0

    @property
    def is_full(self):
        """Check if hostel is full."""
        return self.current_occupancy >= self.capacity

    def update_occupancy(self):
        """Update current occupancy based on active allocations."""
        active_allocations = self.rooms.filter(
            beds__allocations__status='active'
        ).distinct().count()
        self.current_occupancy = active_allocations
        self.save()

    def get_students_by_class(self, class_obj):
        """Get all students from a specific class allocated to this hostel."""
        from apps.academics.models import Enrollment
        active_allocations = self.allocations.filter(
            status='active',
            student__enrollments__class_enrolled=class_obj,
            student__enrollments__enrollment_status='active'
        ).select_related('student')
        return [alloc.student for alloc in active_allocations]


class Room(CoreBaseModel):
    """
    Model for individual rooms within hostels.
    """
    class RoomType(models.TextChoices):
        SINGLE = 'single', _('Single Occupancy')
        DOUBLE = 'double', _('Double Occupancy')
        TRIPLE = 'triple', _('Triple Occupancy')
        QUAD = 'quad', _('Four Occupancy')
        DORMITORY = 'dormitory', _('Dormitory')

    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name='rooms',
        verbose_name=_('hostel')
    )
    room_number = models.CharField(_('room number'), max_length=20)
    floor = models.PositiveIntegerField(_('floor number'), default=1)
    room_type = models.CharField(
        _('room type'),
        max_length=20,
        choices=RoomType.choices,
        default=RoomType.DOUBLE
    )
    capacity = models.PositiveIntegerField(_('capacity'), default=2)
    current_occupancy = models.PositiveIntegerField(_('current occupancy'), default=0)
    
    # Financial integration with fallback to hostel rent
    rent = models.DecimalField(
        _('monthly rent'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Leave blank to use hostel default rent')
    )
    
    amenities = models.TextField(
        _('room amenities'),
        blank=True,
        help_text=_('Room-specific amenities')
    )
    
    # Enhanced status tracking
    is_available = models.BooleanField(_('is available'), default=True)
    maintenance_required = models.BooleanField(_('maintenance required'), default=False)
    maintenance_notes = models.TextField(_('maintenance notes'), blank=True)
    
    # Academic integration
    preferred_class = models.ForeignKey(
        'academics.Class',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preferred_rooms',
        verbose_name=_('preferred class'),
        help_text=_('Preferred class for this room allocation')
    )

    class Meta:
        verbose_name = _('Room')
        verbose_name_plural = _('Rooms')
        ordering = ['hostel', 'floor', 'room_number']
        unique_together = ['hostel', 'room_number']
        indexes = [
            models.Index(fields=['hostel', 'floor']),
            models.Index(fields=['room_type', 'is_available']),
            models.Index(fields=['is_available', 'maintenance_required']),
            models.Index(fields=['preferred_class']),
        ]

    def __str__(self):
        return f"{self.hostel.name} - Room {self.room_number}"

    def clean(self):
        if self.capacity < 1:
            raise ValidationError(_('Room capacity must be at least 1.'))
        if self.current_occupancy > self.capacity:
            raise ValidationError(_('Current occupancy cannot exceed room capacity.'))

    @property
    def available_beds(self):
        """Calculate available beds in the room."""
        return self.capacity - self.current_occupancy

    @property
    def effective_rent(self):
        """Get effective rent (room-specific or hostel default)."""
        return self.rent or self.hostel.monthly_rent

    @property
    def is_full(self):
        """Check if room is full."""
        return self.current_occupancy >= self.capacity

    def update_occupancy(self):
        """Update current occupancy based on active bed allocations."""
        active_allocations = self.beds.filter(
            allocations__status='active'
        ).count()
        self.current_occupancy = active_allocations
        self.save()
        # Update hostel occupancy as well
        self.hostel.update_occupancy()

    def get_current_residents(self):
        """Get current residents of this room."""
        return [alloc.student for alloc in self.allocations.filter(status='active')]


class Bed(CoreBaseModel):
    """
    Model for individual beds within rooms.
    """
    class BedType(models.TextChoices):
        SINGLE = 'single', _('Single Bed')
        BUNK = 'bunk', _('Bunk Bed')
        DOUBLE = 'double', _('Double Bed')
        COT = 'cot', _('Cot')

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='beds',
        verbose_name=_('room')
    )
    bed_number = models.CharField(_('bed number'), max_length=10)
    bed_type = models.CharField(
        _('bed type'),
        max_length=20,
        choices=BedType.choices,
        default=BedType.SINGLE
    )
    is_available = models.BooleanField(_('is available'), default=True)
    features = models.TextField(
        _('bed features'),
        blank=True,
        help_text=_('Study table, cupboard, etc.')
    )
    
    # Maintenance tracking
    last_maintenance_date = models.DateField(
        _('last maintenance date'),
        null=True,
        blank=True
    )
    next_maintenance_date = models.DateField(
        _('next maintenance date'),
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = _('Bed')
        verbose_name_plural = _('Beds')
        ordering = ['room', 'bed_number']
        unique_together = ['room', 'bed_number']
        indexes = [
            models.Index(fields=['room', 'is_available']),
            models.Index(fields=['last_maintenance_date']),
        ]

    def __str__(self):
        return f"{self.room} - Bed {self.bed_number}"

    @property
    def is_occupied(self):
        """Check if bed is currently occupied."""
        return self.allocations.filter(status='active').exists()

    @property
    def requires_maintenance(self):
        """Check if bed requires maintenance."""
        if self.next_maintenance_date:
            return timezone.now().date() >= self.next_maintenance_date
        return False

    def get_current_allocation(self):
        """Get current active allocation for this bed."""
        return self.allocations.filter(status='active').first()


class HostelAllocation(CoreBaseModel):
    """
    Model for allocating students to hostel beds.
    """
    class AllocationStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        ACTIVE = 'active', _('Active')
        CANCELLED = 'cancelled', _('Cancelled')
        COMPLETED = 'completed', _('Completed')
        TRANSFERRED = 'transferred', _('Transferred')
        SUSPENDED = 'suspended', _('Suspended')

    student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='hostel_allocations',
        verbose_name=_('student')
    )
    bed = models.ForeignKey(
        Bed,
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name=_('bed')
    )
    academic_session = models.ForeignKey(
        'academics.AcademicSession',
        on_delete=models.CASCADE,
        related_name='hostel_allocations',
        verbose_name=_('academic session')
    )
    
    # Enhanced academic integration
    class_enrolled = models.ForeignKey(
        'academics.Class',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hostel_allocations',
        verbose_name=_('class enrolled'),
        help_text=_('Student\'s class at time of allocation')
    )
    
    # Date management
    allocation_date = models.DateField(_('allocation date'))
    expected_departure_date = models.DateField(
        _('expected departure date'),
        null=True,
        blank=True
    )
    actual_departure_date = models.DateField(
        _('actual departure date'),
        null=True,
        blank=True
    )
    
    status = models.CharField(
        _('allocation status'),
        max_length=20,
        choices=AllocationStatus.choices,
        default=AllocationStatus.PENDING
    )
    
    # Staff tracking
    allocated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='allocated_beds',
        verbose_name=_('allocated by')
    )
    
    # Financial integration
    rent_amount = models.DecimalField(
        _('monthly rent'),
        max_digits=10,
        decimal_places=2
    )
    security_deposit_paid = models.DecimalField(
        _('security deposit paid'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    deposit_refunded = models.DecimalField(
        _('deposit refunded'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    
    # Enhanced student information
    special_requirements = models.TextField(_('special requirements'), blank=True)
    emergency_contact = models.ForeignKey(
        'academics.ParentGuardian',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hostel_emergency_contacts',
        verbose_name=_('emergency contact')
    )
    medical_information = models.TextField(_('medical information'), blank=True)
    notes = models.TextField(_('allocation notes'), blank=True)

    class Meta:
        verbose_name = _('Hostel Allocation')
        verbose_name_plural = _('Hostel Allocations')
        ordering = ['-allocation_date', 'student']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['bed', 'academic_session']),
            models.Index(fields=['allocation_date', 'status']),
            models.Index(fields=['academic_session', 'status']),
            models.Index(fields=['class_enrolled', 'status']),
        ]

    def __str__(self):
        return f"{self.student} - {self.bed} ({self.status})"

    def clean(self):
        if self.expected_departure_date and self.allocation_date:
            if self.expected_departure_date <= self.allocation_date:
                raise ValidationError(_('Expected departure date must be after allocation date.'))

        # Check if bed is already allocated to another active student
        if self.status == 'active' and self.pk:
            active_allocations = HostelAllocation.objects.filter(
                bed=self.bed,
                status='active',
                academic_session=self.academic_session
            ).exclude(pk=self.pk)
            if active_allocations.exists():
                raise ValidationError(_('This bed is already allocated to another student.'))

        # Auto-set class enrolled if not provided
        if not self.class_enrolled and self.student:
            current_class = self.student.current_class
            if current_class:
                self.class_enrolled = current_class

    def save(self, *args, **kwargs):
        """Update bed and room availability when allocation status changes."""
        # Auto-set class enrolled before saving
        if not self.class_enrolled and self.student:
            current_class = self.student.current_class
            if current_class:
                self.class_enrolled = current_class
        
        # Auto-set rent amount if not provided
        if not self.rent_amount and self.bed:
            self.rent_amount = self.bed.room.effective_rent
        
        if self.pk:
            original = HostelAllocation.objects.get(pk=self.pk)
            if original.status != self.status:
                if self.status == 'active':
                    self.bed.is_available = False
                    self.bed.save()
                elif self.status in ['completed', 'cancelled', 'transferred']:
                    self.bed.is_available = True
                    self.bed.save()
        
        super().save(*args, **kwargs)
        
        # Update room and hostel occupancy
        if self.bed.room:
            self.bed.room.update_occupancy()

    @property
    def duration_days(self):
        """Calculate allocation duration in days."""
        from datetime import date
        end_date = self.actual_departure_date or date.today()
        if self.allocation_date:
            delta = end_date - self.allocation_date
            return delta.days
        return 0

    @property
    def is_current(self):
        """Check if this is a current allocation."""
        return self.status == 'active' and not self.actual_departure_date

    @property
    def outstanding_balance(self):
        """Calculate outstanding fee balance."""
        total_due = self.fees.filter(status__in=['pending', 'partial']).aggregate(
            total=models.Sum(models.F('amount') + models.F('late_fee') - models.F('discount') - models.F('paid_amount'))
        )['total'] or 0
        return total_due

    def transfer_bed(self, new_bed, transferred_by, notes=""):
        """Transfer student to a new bed."""
        if self.status != 'active':
            raise ValidationError(_('Only active allocations can be transferred.'))
        
        # Create new allocation
        new_allocation = HostelAllocation.objects.create(
            student=self.student,
            bed=new_bed,
            academic_session=self.academic_session,
            class_enrolled=self.class_enrolled,
            allocation_date=timezone.now().date(),
            rent_amount=new_bed.room.effective_rent,
            security_deposit_paid=self.security_deposit_paid,
            allocated_by=transferred_by,
            special_requirements=self.special_requirements,
            emergency_contact=self.emergency_contact,
            medical_information=self.medical_information,
            notes=f"Transferred from {self.bed}. {notes}"
        )
        
        # Mark old allocation as transferred
        self.status = self.AllocationStatus.TRANSFERRED
        self.actual_departure_date = timezone.now().date()
        self.save()
        
        return new_allocation


class HostelFee(CoreBaseModel):
    """
    Model for managing hostel fee payments.
    """
    class FeeStatus(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PAID = 'paid', _('Paid')
        OVERDUE = 'overdue', _('Overdue')
        WAIVED = 'waived', _('Waived')
        PARTIAL = 'partial', _('Partial Payment')
        REFUNDED = 'refunded', _('Refunded')

    allocation = models.ForeignKey(
        HostelAllocation,
        on_delete=models.CASCADE,
        related_name='fees',
        verbose_name=_('hostel allocation')
    )
    month = models.PositiveIntegerField(
        _('month'),
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    year = models.PositiveIntegerField(_('year'))
    due_date = models.DateField(_('due date'))
    amount = models.DecimalField(
        _('amount'),
        max_digits=10,
        decimal_places=2
    )
    paid_amount = models.DecimalField(
        _('paid amount'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    paid_date = models.DateField(_('paid date'), null=True, blank=True)
    status = models.CharField(
        _('fee status'),
        max_length=20,
        choices=FeeStatus.choices,
        default=FeeStatus.PENDING
    )
    
    # Enhanced financial tracking
    late_fee = models.DecimalField(
        _('late fee'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    discount = models.DecimalField(
        _('discount'),
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    
    # Payment integration
    payment_method = models.CharField(
        _('payment method'),
        max_length=50,
        blank=True,
        help_text=_('Cash, Card, Bank Transfer, etc.')
    )
    transaction_id = models.CharField(
        _('transaction ID'),
        max_length=100,
        blank=True
    )
    receipt_number = models.CharField(_('receipt number'), max_length=50, blank=True)
    
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('Hostel Fee')
        verbose_name_plural = _('Hostel Fees')
        ordering = ['-year', '-month', 'allocation']
        unique_together = ['allocation', 'month', 'year']
        indexes = [
            models.Index(fields=['allocation', 'status']),
            models.Index(fields=['due_date', 'status']),
            models.Index(fields=['month', 'year', 'status']),
            models.Index(fields=['transaction_id']),
        ]

    def __str__(self):
        return f"{self.allocation.student} - {self.month}/{self.year} - {self.amount}"

    def clean(self):
        if self.paid_amount > (self.amount + self.late_fee - self.discount):
            raise ValidationError(_('Paid amount cannot exceed total payable amount.'))

    @property
    def total_payable(self):
        """Calculate total payable amount."""
        return self.amount + self.late_fee - self.discount

    @property
    def balance_amount(self):
        """Calculate balance amount."""
        return self.total_payable - self.paid_amount

    @property
    def is_overdue(self):
        """Check if fee is overdue."""
        from datetime import date
        return self.status in ['pending', 'partial'] and self.due_date < date.today()

    def mark_as_paid(self, paid_amount, paid_date=None, payment_method="", transaction_id="", receipt_number=""):
        """Mark fee as paid."""
        from datetime import date
        self.paid_amount = paid_amount
        self.paid_date = paid_date or date.today()
        self.payment_method = payment_method
        self.transaction_id = transaction_id
        self.receipt_number = receipt_number
        
        if self.paid_amount >= self.total_payable:
            self.status = self.FeeStatus.PAID
        elif self.paid_amount > 0:
            self.status = self.FeeStatus.PARTIAL
        self.save()

    def apply_late_fee(self, late_fee_amount):
        """Apply late fee to the payment."""
        self.late_fee = late_fee_amount
        if self.status == self.FeeStatus.PENDING:
            self.status = self.FeeStatus.OVERDUE
        self.save()


class VisitorLog(CoreBaseModel):
    """
    Model for tracking visitors to hostels.
    """
    class VisitPurpose(models.TextChoices):
        MEETING = 'meeting', _('Meeting')
        DELIVERY = 'delivery', _('Delivery')
        MAINTENANCE = 'maintenance', _('Maintenance')
        OFFICIAL = 'official', _('Official Work')
        PARENT_VISIT = 'parent_visit', _('Parent Visit')
        OTHER = 'other', _('Other')

    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name='visitors',
        verbose_name=_('hostel')
    )
    visitor_name = models.CharField(_('visitor name'), max_length=100)
    visitor_phone = models.CharField(_('visitor phone'), max_length=20, blank=True)
    visitor_id_type = models.CharField(_('ID type'), max_length=50, blank=True)
    visitor_id_number = models.CharField(_('ID number'), max_length=50, blank=True)
    
    # Enhanced visitor-student relationship
    visiting_student = models.ForeignKey(
        'academics.Student',
        on_delete=models.CASCADE,
        related_name='visitors',
        verbose_name=_('visiting student')
    )
    
    # Parent/Guardian integration
    is_parent_guardian = models.BooleanField(_('is parent/guardian'), default=False)
    parent_guardian = models.ForeignKey(
        'academics.ParentGuardian',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hostel_visits',
        verbose_name=_('parent/guardian')
    )
    
    purpose = models.CharField(
        _('visit purpose'),
        max_length=20,
        choices=VisitPurpose.choices,
        default=VisitPurpose.MEETING
    )
    check_in_time = models.DateTimeField(_('check in time'), default=timezone.now)
    check_out_time = models.DateTimeField(_('check out time'), null=True, blank=True)
    items_carried = models.TextField(_('items carried'), blank=True)
    
    # Enhanced authorization
    authorized_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authorized_visits',
        verbose_name=_('authorized by')
    )
    
    notes = models.TextField(_('notes'), blank=True)
    
    # Security features
    photo_id_verified = models.BooleanField(_('photo ID verified'), default=False)
    allowed_items_only = models.BooleanField(_('allowed items only'), default=True)

    class Meta:
        verbose_name = _('Visitor Log')
        verbose_name_plural = _('Visitor Logs')
        ordering = ['-check_in_time']
        indexes = [
            models.Index(fields=['hostel', 'check_in_time']),
            models.Index(fields=['visiting_student', 'check_in_time']),
            models.Index(fields=['is_parent_guardian']),
        ]

    def __str__(self):
        return f"{self.visitor_name} visiting {self.visiting_student}"

    def clean(self):
        if self.check_out_time and self.check_out_time <= self.check_in_time:
            raise ValidationError(_('Check-out time must be after check-in time.'))
        
        # Auto-set parent_guardian if visitor is parent
        if self.is_parent_guardian and not self.parent_guardian:
            # Try to find parent by name and student relationship
            from apps.academics.models import StudentParentRelationship
            relationships = StudentParentRelationship.objects.filter(
                student=self.visiting_student
            ).select_related('parent')
            
            for relationship in relationships:
                if (relationship.parent.first_name in self.visitor_name or 
                    relationship.parent.last_name in self.visitor_name):
                    self.parent_guardian = relationship.parent
                    break

    @property
    def duration_minutes(self):
        """Calculate visit duration in minutes."""
        if self.check_out_time:
            duration = self.check_out_time - self.check_in_time
            return int(duration.total_seconds() / 60)
        return None

    @property
    def is_checked_out(self):
        """Check if visitor has checked out."""
        return self.check_out_time is not None

    def check_out(self, check_out_time=None):
        """Check out visitor."""
        self.check_out_time = check_out_time or timezone.now()
        self.save()


# ... (MaintenanceRequest and InventoryItem models remain largely the same with similar enhancements)
# ... (Signal handlers remain the same)

class MaintenanceRequest(CoreBaseModel):
    """
    Model for managing hostel maintenance requests.
    """
    class Priority(models.TextChoices):
        LOW = 'low', _('Low')
        MEDIUM = 'medium', _('Medium')
        HIGH = 'high', _('High')
        URGENT = 'urgent', _('Urgent')

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')

    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name='maintenance_requests',
        verbose_name=_('hostel')
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='maintenance_requests',
        verbose_name=_('room'),
        null=True,
        blank=True
    )
    bed = models.ForeignKey(
        Bed,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='maintenance_requests',
        verbose_name=_('bed')
    )
    requested_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='maintenance_requests',
        verbose_name=_('requested by')
    )
    title = models.CharField(_('issue title'), max_length=200)
    description = models.TextField(_('description'))
    priority = models.CharField(
        _('priority'),
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    assigned_to = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_maintenance',
        verbose_name=_('assigned to')
    )
    estimated_cost = models.DecimalField(
        _('estimated cost'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    actual_cost = models.DecimalField(
        _('actual cost'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    requested_date = models.DateTimeField(_('requested date'), auto_now_add=True)
    scheduled_date = models.DateTimeField(_('scheduled date'), null=True, blank=True)
    completed_date = models.DateTimeField(_('completed date'), null=True, blank=True)
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('Maintenance Request')
        verbose_name_plural = _('Maintenance Requests')
        ordering = ['-requested_date', 'priority']
        indexes = [
            models.Index(fields=['hostel', 'status']),
            models.Index(fields=['priority', 'status']),
            models.Index(fields=['assigned_to', 'status']),
        ]

    def __str__(self):
        hostel_name = self.hostel.name if self.hostel_id else "No Hostel Assigned"
        return f"{self.title} - {hostel_name}"

    @property
    def is_overdue(self):
        """Check if maintenance is overdue."""
        if self.scheduled_date and self.status in ['pending', 'in_progress']:
            return timezone.now() > self.scheduled_date
        return False

    @property
    def resolution_time(self):
        """Calculate time taken to resolve the request."""
        if self.completed_date:
            duration = self.completed_date - self.requested_date
            return duration
        return None


class InventoryItem(CoreBaseModel):
    """
    Model for managing hostel inventory and assets.
    """
    class ItemCondition(models.TextChoices):
        EXCELLENT = 'excellent', _('Excellent')
        GOOD = 'good', _('Good')
        FAIR = 'fair', _('Fair')
        POOR = 'poor', _('Poor')
        DAMAGED = 'damaged', _('Damaged')

    class ItemStatus(models.TextChoices):
        AVAILABLE = 'available', _('Available')
        IN_USE = 'in_use', _('In Use')
        UNDER_MAINTENANCE = 'under_maintenance', _('Under Maintenance')
        DISCARDED = 'discarded', _('Discarded')

    hostel = models.ForeignKey(
        Hostel,
        on_delete=models.CASCADE,
        related_name='inventory',
        verbose_name=_('hostel')
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory',
        verbose_name=_('room')
    )
    name = models.CharField(_('item name'), max_length=200)
    category = models.CharField(_('category'), max_length=100)
    serial_number = models.CharField(_('serial number'), max_length=100, blank=True)
    quantity = models.PositiveIntegerField(_('quantity'), default=1)
    condition = models.CharField(
        _('condition'),
        max_length=20,
        choices=ItemCondition.choices,
        default=ItemCondition.GOOD
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=ItemStatus.choices,
        default=ItemStatus.AVAILABLE
    )
    purchase_date = models.DateField(_('purchase date'), null=True, blank=True)
    purchase_cost = models.DecimalField(
        _('purchase cost'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    warranty_expiry = models.DateField(_('warranty expiry'), null=True, blank=True)
    description = models.TextField(_('description'), blank=True)
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('Inventory Item')
        verbose_name_plural = _('Inventory Items')
        ordering = ['hostel', 'category', 'name']
        indexes = [
            models.Index(fields=['hostel', 'status']),
            models.Index(fields=['category', 'condition']),
            models.Index(fields=['status', 'condition']),
        ]

    def __str__(self):
        return f"{self.name} - {self.hostel.name}"

    @property
    def is_warranty_valid(self):
        """Check if item is under warranty."""
        from datetime import date
        return self.warranty_expiry and self.warranty_expiry >= date.today()

    @property
    def age_years(self):
        """Calculate age of item in years."""
        from datetime import date
        if self.purchase_date:
            today = date.today()
            return today.year - self.purchase_date.year - (
                (today.month, today.day) < (self.purchase_date.month, self.purchase_date.day)
            )
        return None


# Signal handlers for automatic updates
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


@receiver(post_save, sender=HostelAllocation)
@receiver(post_delete, sender=HostelAllocation)
def update_hostel_occupancy(sender, instance, **kwargs):
    """
    Update hostel and room occupancy when allocations change.
    """
    if instance.bed and instance.bed.room:
        instance.bed.room.update_occupancy()


@receiver(post_save, sender=Room)
def update_room_availability(sender, instance, **kwargs):
    """
    Update room availability based on maintenance status.
    """
    if instance.maintenance_required:
        instance.is_available = False
        instance.save(update_fields=['is_available'])
