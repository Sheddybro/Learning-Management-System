# apps/hostels/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from .models import (
    Hostel, Room, Bed, HostelAllocation, HostelFee,
    VisitorLog, MaintenanceRequest, InventoryItem
)
from apps.users.models import User
from apps.academics.models import Student, Class, ParentGuardian
from apps.academics.models import AcademicSession


class HostelForm(forms.ModelForm):
    """Form for creating and updating hostels."""
    
    class Meta:
        model = Hostel
        fields = [
            'name', 'code', 'hostel_type', 'category', 'total_floors',
            'total_rooms', 'capacity', 'warden', 'assistant_warden',
            'monthly_rent', 'security_deposit', 'amenities', 'rules',
            'description', 'allowed_classes', 'is_active',
            'address_line_1', 'address_line_2', 'city', 'state',
            'postal_code', 'country', 'phone', 'mobile', 'email',
            'emergency_contact', 'emergency_phone'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter hostel name')
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Enter hostel code')
            }),
            'hostel_type': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'total_floors': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'total_rooms': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'warden': forms.Select(attrs={'class': 'form-control'}),
            'assistant_warden': forms.Select(attrs={'class': 'form-control'}),
            'monthly_rent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'security_deposit': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'amenities': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('WiFi, Laundry, AC, Gym, etc.')
            }),
            'rules': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Enter hostel rules and regulations')
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Enter hostel description')
            }),
            'allowed_classes': forms.SelectMultiple(attrs={
                'class': 'form-control select2-multiple'
            }),
            'address_line_1': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Street address, P.O. Box')
            }),
            'address_line_2': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Apartment, suite, unit, building, floor, etc.')
            }),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_phone': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['warden'].queryset = User.objects.filter(is_active=True, is_staff=True)
        self.fields['assistant_warden'].queryset = User.objects.filter(is_active=True, is_staff=True)
        self.fields['allowed_classes'].queryset = Class.objects.filter(status='active')
    
    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity and capacity < 0:
            raise ValidationError(_('Capacity cannot be negative.'))
        return capacity
    
    def clean(self):
        cleaned_data = super().clean()
        total_rooms = cleaned_data.get('total_rooms')
        capacity = cleaned_data.get('capacity')
        
        if total_rooms and capacity and total_rooms > capacity:
            raise ValidationError(_('Total rooms cannot exceed total capacity.'))
        
        return cleaned_data


class RoomForm(forms.ModelForm):
    """Form for creating and updating rooms."""
    
    class Meta:
        model = Room
        fields = [
            'hostel', 'room_number', 'floor', 'room_type', 'capacity',
            'rent', 'amenities', 'preferred_class', 'is_available',
            'maintenance_required', 'maintenance_notes'
        ]
        widgets = {
            'hostel': forms.Select(attrs={'class': 'form-control'}),
            'room_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., 101, 201A')
            }),
            'floor': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'room_type': forms.Select(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'rent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'amenities': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Room-specific amenities')
            }),
            'preferred_class': forms.Select(attrs={'class': 'form-control'}),
            'maintenance_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hostel'].queryset = Hostel.objects.filter(is_active=True, status='active')
        self.fields['preferred_class'].queryset = Class.objects.filter(status='active')
    
    def clean_room_number(self):
        room_number = self.cleaned_data.get('room_number')
        hostel = self.cleaned_data.get('hostel')
        
        if room_number and hostel:
            # Check for duplicate room number in the same hostel
            existing = Room.objects.filter(
                hostel=hostel,
                room_number=room_number
            )
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(
                    _('Room number %(room_number)s already exists in %(hostel)s.'),
                    params={'room_number': room_number, 'hostel': hostel.name}
                )
        
        return room_number
    
    def clean(self):
        cleaned_data = super().clean()
        capacity = cleaned_data.get('capacity')
        room_type = cleaned_data.get('room_type')
        
        # Validate capacity based on room type
        if room_type and capacity:
            expected_capacity = {
                'single': 1,
                'double': 2,
                'triple': 3,
                'quad': 4,
                'dormitory': 8  # Minimum for dormitory
            }
            
            min_capacity = expected_capacity.get(room_type, 1)
            if capacity < min_capacity:
                raise ValidationError(
                    _('%(room_type)s rooms must have at least %(min_capacity)d capacity.'),
                    params={'room_type': room_type, 'min_capacity': min_capacity}
                )
        
        return cleaned_data


class BedForm(forms.ModelForm):
    """Form for creating and updating beds."""
    
    class Meta:
        model = Bed
        fields = [
            'room', 'bed_number', 'bed_type', 'features',
            'last_maintenance_date', 'next_maintenance_date'
        ]
        widgets = {
            'room': forms.Select(attrs={'class': 'form-control'}),
            'bed_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., A, B, 1, 2')
            }),
            'bed_type': forms.Select(attrs={'class': 'form-control'}),
            'features': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Study table, cupboard, reading light, etc.')
            }),
            'last_maintenance_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'next_maintenance_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['room'].queryset = Room.objects.filter(
            hostel__is_active=True,
            status='active'
        )
    
    def clean_bed_number(self):
        bed_number = self.cleaned_data.get('bed_number')
        room = self.cleaned_data.get('room')
        
        if bed_number and room:
            # Check for duplicate bed number in the same room
            existing = Bed.objects.filter(room=room, bed_number=bed_number)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(
                    _('Bed number %(bed_number)s already exists in room %(room)s.'),
                    params={'bed_number': bed_number, 'room': room.room_number}
                )
        
        return bed_number
    
    def clean(self):
        cleaned_data = super().clean()
        last_maintenance_date = cleaned_data.get('last_maintenance_date')
        next_maintenance_date = cleaned_data.get('next_maintenance_date')
        
        if last_maintenance_date and next_maintenance_date:
            if next_maintenance_date <= last_maintenance_date:
                raise ValidationError(_('Next maintenance date must be after last maintenance date.'))
        
        return cleaned_data


class HostelAllocationForm(forms.ModelForm):
    """Form for allocating students to hostel beds."""
    
    search_student = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search student by name or ID...')
        }),
        label=_('Search Student')
    )
    
    class Meta:
        model = HostelAllocation
        fields = [
            'student', 'bed', 'academic_session', 'class_enrolled',
            'allocation_date', 'expected_departure_date', 'status',
            'allocated_by', 'rent_amount', 'security_deposit_paid',
            'special_requirements', 'emergency_contact', 'medical_information',
            'notes'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'bed': forms.Select(attrs={'class': 'form-control'}),
            'academic_session': forms.Select(attrs={'class': 'form-control'}),
            'class_enrolled': forms.Select(attrs={'class': 'form-control'}),
            'allocation_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'expected_departure_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'allocated_by': forms.Select(attrs={'class': 'form-control'}),
            'rent_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'security_deposit_paid': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'special_requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Any special needs or requirements')
            }),
            'medical_information': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': _('Any medical conditions or allergies')
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.filter(status='active')
        self.fields['academic_session'].queryset = AcademicSession.objects.filter(status='active')
        self.fields['allocated_by'].queryset = User.objects.filter(is_active=True, is_staff=True)
        self.fields['emergency_contact'].queryset = ParentGuardian.objects.filter(status='active')
        
        # Filter available beds
        self.fields['bed'].queryset = Bed.objects.filter(
            is_available=True,
            room__hostel__is_active=True,
            status='active'
        )
        
        # Auto-set current class if student is selected
        if self.instance and self.instance.student_id:
            current_class = self.instance.student.current_class
            if current_class:
                self.fields['class_enrolled'].initial = current_class
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        bed = cleaned_data.get('bed')
        academic_session = cleaned_data.get('academic_session')
        allocation_date = cleaned_data.get('allocation_date')
        expected_departure_date = cleaned_data.get('expected_departure_date')
        status = cleaned_data.get('status')
        
        # Check if bed is available
        if bed and status == 'active':
            active_allocations = HostelAllocation.objects.filter(
                bed=bed,
                academic_session=academic_session,
                status='active'
            )
            if self.instance and self.instance.pk:
                active_allocations = active_allocations.exclude(pk=self.instance.pk)
            
            if active_allocations.exists():
                raise ValidationError(_('This bed is already allocated to another student.'))
        
        # Check if student already has active allocation in same session
        if student and academic_session and status == 'active':
            existing_allocations = HostelAllocation.objects.filter(
                student=student,
                academic_session=academic_session,
                status='active'
            )
            if self.instance and self.instance.pk:
                existing_allocations = existing_allocations.exclude(pk=self.instance.pk)
            
            if existing_allocations.exists():
                raise ValidationError(_('This student already has an active hostel allocation for this academic session.'))
        
        # Validate dates
        if allocation_date and expected_departure_date:
            if expected_departure_date <= allocation_date:
                raise ValidationError(_('Expected departure date must be after allocation date.'))
        
        return cleaned_data


class HostelFeeForm(forms.ModelForm):
    """Form for managing hostel fee payments."""
    
    class Meta:
        model = HostelFee
        fields = [
            'allocation', 'month', 'year', 'due_date', 'amount',
            'paid_amount', 'paid_date', 'status', 'late_fee',
            'discount', 'payment_method', 'transaction_id',
            'receipt_number', 'notes'
        ]
        widgets = {
            'allocation': forms.Select(attrs={'class': 'form-control'}),
            'month': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '12'
            }),
            'year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2020',
                'max': '2030'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'paid_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'paid_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'late_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'discount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'payment_method': forms.TextInput(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['allocation'].queryset = HostelAllocation.objects.filter(
            status='active'
        )
    
    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        paid_amount = cleaned_data.get('paid_amount')
        discount = cleaned_data.get('discount', 0)
        late_fee = cleaned_data.get('late_fee', 0)
        
        total_payable = (amount or 0) + (late_fee or 0) - (discount or 0)
        
        if paid_amount and paid_amount > total_payable:
            raise ValidationError(_('Paid amount cannot exceed total payable amount.'))
        
        return cleaned_data


class VisitorLogForm(forms.ModelForm):
    """Form for managing visitor logs."""
    
    class Meta:
        model = VisitorLog
        fields = [
            'hostel', 'visitor_name', 'visitor_phone', 'visitor_id_type',
            'visitor_id_number', 'visiting_student', 'is_parent_guardian',
            'parent_guardian', 'purpose', 'check_in_time', 'check_out_time',
            'items_carried', 'authorized_by', 'notes', 'photo_id_verified',
            'allowed_items_only'
        ]
        widgets = {
            'hostel': forms.Select(attrs={'class': 'form-control'}),
            'visitor_name': forms.TextInput(attrs={'class': 'form-control'}),
            'visitor_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'visitor_id_type': forms.TextInput(attrs={'class': 'form-control'}),
            'visitor_id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'visiting_student': forms.Select(attrs={'class': 'form-control'}),
            'parent_guardian': forms.Select(attrs={'class': 'form-control'}),
            'purpose': forms.Select(attrs={'class': 'form-control'}),
            'check_in_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'check_out_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'items_carried': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'authorized_by': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hostel'].queryset = Hostel.objects.filter(is_active=True)
        self.fields['visiting_student'].queryset = Student.objects.filter(status='active')
        self.fields['parent_guardian'].queryset = ParentGuardian.objects.filter(status='active')
        self.fields['authorized_by'].queryset = User.objects.filter(is_active=True, is_staff=True)
    
    def clean(self):
        cleaned_data = super().clean()
        check_in_time = cleaned_data.get('check_in_time')
        check_out_time = cleaned_data.get('check_out_time')
        is_parent_guardian = cleaned_data.get('is_parent_guardian')
        parent_guardian = cleaned_data.get('parent_guardian')
        
        if check_out_time and check_in_time:
            if check_out_time <= check_in_time:
                raise ValidationError(_('Check-out time must be after check-in time.'))
        
        if is_parent_guardian and not parent_guardian:
            raise ValidationError(_('Please select a parent/guardian when marking visitor as parent/guardian.'))
        
        return cleaned_data


class MaintenanceRequestForm(forms.ModelForm):
    """Form for submitting maintenance requests."""
    
    class Meta:
        model = MaintenanceRequest
        fields = [
            'hostel', 'room', 'bed', 'title', 'description', 'priority',
            'assigned_to', 'estimated_cost', 'scheduled_date', 'notes'
        ]
        widgets = {
            'hostel': forms.Select(attrs={'class': 'form-control'}),
            'room': forms.Select(attrs={'class': 'form-control'}),
            'bed': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Describe the issue in detail...')
            }),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'estimated_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'scheduled_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hostel'].queryset = Hostel.objects.filter(is_active=True)
        self.fields['room'].queryset = Room.objects.none()
        self.fields['bed'].queryset = Bed.objects.none()
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True, is_staff=True)
        
        # Dynamic filtering for rooms and beds
        if 'hostel' in self.data:
            try:
                hostel_id = int(self.data.get('hostel'))
                self.fields['room'].queryset = Room.objects.filter(hostel_id=hostel_id)
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.hostel_id:
            self.fields['room'].queryset = Room.objects.filter(hostel_id=self.instance.hostel_id)

        if 'room' in self.data:
            try:
                room_id = int(self.data.get('room'))
                self.fields['bed'].queryset = Bed.objects.filter(room_id=room_id)
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.room_id:
            self.fields['bed'].queryset = Bed.objects.filter(room_id=self.instance.room_id)


class InventoryItemForm(forms.ModelForm):
    """Form for managing hostel inventory."""
    
    class Meta:
        model = InventoryItem
        fields = [
            'hostel', 'room', 'name', 'category', 'serial_number',
            'quantity', 'condition', 'status', 'purchase_date',
            'purchase_cost', 'warranty_expiry', 'description', 'notes'
        ]
        widgets = {
            'hostel': forms.Select(attrs={'class': 'form-control'}),
            'room': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'purchase_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'warranty_expiry': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hostel'].queryset = Hostel.objects.filter(is_active=True)
        self.fields['room'].queryset = Room.objects.filter(hostel__is_active=True)
        
        # Dynamic room filtering
        if 'hostel' in self.data:
            try:
                hostel_id = int(self.data.get('hostel'))
                self.fields['room'].queryset = Room.objects.filter(hostel_id=hostel_id)
            except (ValueError, TypeError):
                pass
        elif self.instance and self.instance.hostel_id:
            self.fields['room'].queryset = Room.objects.filter(hostel_id=self.instance.hostel_id)


class BulkAllocationForm(forms.Form):
    """Form for bulk allocation of students to hostel beds."""
    
    academic_session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Session')
    )
    
    hostel = forms.ModelChoiceField(
        queryset=Hostel.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Hostel')
    )
    
    student_class = forms.ModelChoiceField(
        queryset=Class.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Student Class'),
        required=False
    )
    
    allocation_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_('Allocation Date')
    )
    
    allocate_by = forms.ChoiceField(
        choices=[
            ('gender', _('By Gender')),
            ('class', _('By Class')),
            ('random', _('Random Allocation')),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Allocation Method')
    )
    
    def clean(self):
        cleaned_data = super().clean()
        allocation_date = cleaned_data.get('allocation_date')
        
        if allocation_date and allocation_date > timezone.now().date():
            raise ValidationError(_('Allocation date cannot be in the future.'))
        
        return cleaned_data


class HostelSearchForm(forms.Form):
    """Form for searching and filtering hostel allocations."""
    
    hostel = forms.ModelChoiceField(
        queryset=Hostel.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Hostel')
    )
    
    academic_session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.filter(status='active'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Academic Session')
    )
    
    student_class = forms.ModelChoiceField(
        queryset=Class.objects.filter(status='active'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Class')
    )
    
    allocation_status = forms.ChoiceField(
        choices=[('', _('All Status'))] + list(HostelAllocation.AllocationStatus.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Allocation Status')
    )
    
    search_query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by student name or ID...')
        }),
        label=_('Search')
    )


class FeePaymentForm(forms.Form):
    """Form for processing hostel fee payments."""
    
    allocation = forms.ModelChoiceField(
        queryset=HostelAllocation.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Student Allocation')
    )
    
    month = forms.IntegerField(
        min_value=1,
        max_value=12,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label=_('Month')
    )
    
    year = forms.IntegerField(
        min_value=2020,
        max_value=2030,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label=_('Year')
    )
    
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label=_('Amount')
    )
    
    payment_method = forms.ChoiceField(
        choices=HostelFee._meta.get_field('payment_method').choices,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Payment Method')
    )
    
    transaction_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label=_('Transaction ID')
    )
    
    receipt_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label=_('Receipt Number')
    )
    
    def clean(self):
        cleaned_data = super().clean()
        allocation = cleaned_data.get('allocation')
        month = cleaned_data.get('month')
        year = cleaned_data.get('year')
        
        if allocation and month and year:
            # Check if fee already exists for this period
            existing_fee = HostelFee.objects.filter(
                allocation=allocation,
                month=month,
                year=year
            )
            if existing_fee.exists():
                raise ValidationError(
                    _('Fee already exists for %(student)s for %(month)d/%(year)d.'),
                    params={
                        'student': allocation.student,
                        'month': month,
                        'year': year
                    }
                )
        
        return cleaned_data


class RoomTransferForm(forms.Form):
    """Form for transferring students between rooms."""
    
    allocation = forms.ModelChoiceField(
        queryset=HostelAllocation.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('Current Allocation')
    )
    
    new_bed = forms.ModelChoiceField(
        queryset=Bed.objects.filter(is_available=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label=_('New Bed')
    )
    
    transfer_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_('Transfer Date')
    )
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Reason for transfer...')
        }),
        label=_('Reason')
    )
    
    def clean(self):
        cleaned_data = super().clean()
        allocation = cleaned_data.get('allocation')
        new_bed = cleaned_data.get('new_bed')
        transfer_date = cleaned_data.get('transfer_date')
        
        if allocation and new_bed:
            if allocation.bed == new_bed:
                raise ValidationError(_('Student is already allocated to this bed.'))
            
            # Check if new bed is in the same hostel
            if allocation.bed.room.hostel != new_bed.room.hostel:
                raise ValidationError(_('Cannot transfer between different hostels using this form.'))
        
        if transfer_date and transfer_date > timezone.now().date():
            raise ValidationError(_('Transfer date cannot be in the future.'))
        
        return cleaned_data


# Custom widgets
class DatePicker(forms.DateInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'class': 'form-control', 'type': 'date'})


class DateTimePicker(forms.DateTimeInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'class': 'form-control', 'type': 'datetime-local'})


class CurrencyInput(forms.NumberInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        })
