# apps/library/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import FileExtensionValidator

from .models import (
    Library, Author, Publisher, BookCategory, Book, BookCopy,
    LibraryMember, BorrowRecord, Reservation, FinePayment
)


class LibraryForm(forms.ModelForm):
    """Form for Library model with enhanced validation."""
    
    class Meta:
        model = Library
        fields = [
            'name', 'code', 'description', 'opening_time', 'closing_time',
            'max_borrow_days', 'max_books_per_user', 'fine_per_day', 'status'
        ]
        widgets = {
            'opening_time': forms.TimeInput(attrs={'type': 'time'}),
            'closing_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'code': _('Unique library code identifier'),
            'max_borrow_days': _('Maximum number of days a book can be borrowed'),
            'max_books_per_user': _('Maximum number of books a user can borrow at once'),
            'fine_per_day': _('Fine amount per day for overdue books'),
        }

    def clean_closing_time(self):
        opening_time = self.cleaned_data.get('opening_time')
        closing_time = self.cleaned_data.get('closing_time')
        
        if opening_time and closing_time and closing_time <= opening_time:
            raise ValidationError(_('Closing time must be after opening time.'))
        
        return closing_time

    def clean_max_borrow_days(self):
        days = self.cleaned_data.get('max_borrow_days')
        if days and days > 365:
            raise ValidationError(_('Maximum borrow days cannot exceed 365.'))
        return days

    def clean_max_books_per_user(self):
        books = self.cleaned_data.get('max_books_per_user')
        if books and books > 20:
            raise ValidationError(_('Maximum books per user cannot exceed 20.'))
        return books

    def clean_fine_per_day(self):
        fine = self.cleaned_data.get('fine_per_day')
        if fine and fine < 0:
            raise ValidationError(_('Fine amount cannot be negative.'))
        return fine


class AuthorForm(forms.ModelForm):
    """Form for Author model."""
    
    class Meta:
        model = Author
        fields = [
            'first_name', 'last_name', 'bio', 'date_of_birth', 'date_of_death',
            'nationality', 'status'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'date_of_death': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        date_of_birth = cleaned_data.get('date_of_birth')
        date_of_death = cleaned_data.get('date_of_death')
        
        if date_of_birth and date_of_death and date_of_death <= date_of_birth:
            self.add_error(
                'date_of_death',
                _('Date of death cannot be before date of birth.')
            )
        
        if date_of_birth and date_of_birth > timezone.now().date():
            self.add_error(
                'date_of_birth',
                _('Date of birth cannot be in the future.')
            )
        
        if date_of_death and date_of_death > timezone.now().date():
            self.add_error(
                'date_of_death',
                _('Date of death cannot be in the future.')
            )
        
        return cleaned_data


class PublisherForm(forms.ModelForm):
    """Form for Publisher model."""
    
    class Meta:
        model = Publisher
        fields = [
            'name', 'contact_person', 'email', 'phone', 'website', 'status'
        ]
        widgets = {
            'website': forms.URLInput(attrs={'placeholder': 'https://nordalms.pythonanywhere.com'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and not forms.EmailField().clean(email):
            raise ValidationError(_('Enter a valid email address.'))
        return email

    def clean_website(self):
        website = self.cleaned_data.get('website')
        if website and not website.startswith(('http://', 'https://')):
            raise ValidationError(_('Enter a valid website URL starting with http:// or https://'))
        return website


class BookCategoryForm(forms.ModelForm):
    """Form for BookCategory model."""
    
    class Meta:
        model = BookCategory
        fields = ['name', 'code', 'description', 'parent', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'code': _('Unique category code identifier'),
            'parent': _('Select parent category for hierarchical structure'),
        }

    def clean_parent(self):
        parent = self.cleaned_data.get('parent')
        instance = self.instance
        
        # Prevent circular hierarchy
        if parent and instance:
            if parent == instance:
                raise ValidationError(_('A category cannot be its own parent.'))
            
            # Check for circular references
            current = parent
            while current:
                if current == instance:
                    raise ValidationError(_('Circular category hierarchy detected.'))
                current = current.parent
        
        return parent


class BookForm(forms.ModelForm):
    """Form for Book model with enhanced validation."""
    
    class Meta:
        model = Book
        fields = [
            'title', 'isbn', 'edition', 'book_type', 'book_status', 'authors',
            'publisher', 'category', 'library', 'publication_year', 'pages',
            'language', 'description', 'cover_image', 'acquisition_date',
            'acquisition_price', 'source', 'total_copies', 'available_copies',
            'location', 'keywords', 'status'
        ]
        widgets = {
            'acquisition_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'authors': forms.SelectMultiple(attrs={'class': 'select2'}),
            'keywords': forms.TextInput(attrs={
                'placeholder': _('Comma-separated keywords for search')
            }),
        }
        help_texts = {
            'isbn': _('International Standard Book Number'),
            'total_copies': _('Total number of copies available in library'),
            'available_copies': _('Number of copies currently available for borrowing'),
            'location': _('Shelf location in the library'),
        }

    def clean_publication_year(self):
        year = self.cleaned_data.get('publication_year')
        if year and (year < 1000 or year > timezone.now().year):
            raise ValidationError(_('Publication year must be between 1000 and current year.'))
        return year

    def clean_pages(self):
        pages = self.cleaned_data.get('pages')
        if pages and pages <= 0:
            raise ValidationError(_('Number of pages must be greater than 0.'))
        return pages

    def clean_acquisition_price(self):
        price = self.cleaned_data.get('acquisition_price')
        if price and price < 0:
            raise ValidationError(_('Acquisition price cannot be negative.'))
        return price

    def clean_available_copies(self):
        available_copies = self.cleaned_data.get('available_copies')
        total_copies = self.cleaned_data.get('total_copies')
        
        if available_copies and total_copies and available_copies > total_copies:
            raise ValidationError(_('Available copies cannot exceed total copies.'))
        
        return available_copies

    def clean_isbn(self):
        isbn = self.cleaned_data.get('isbn')
        if isbn:
            # Basic ISBN validation (can be enhanced with proper ISBN validation)
            isbn = isbn.replace('-', '').replace(' ', '')
            if not isbn.isdigit() and not (len(isbn) == 10 or len(isbn) == 13):
                raise ValidationError(_('Enter a valid ISBN (10 or 13 digits).'))
        return isbn


class BookCopyForm(forms.ModelForm):
    """Form for BookCopy model."""
    
    class Meta:
        model = BookCopy
        fields = [
            'book', 'copy_number', 'barcode', 'copy_status', 'acquisition_date',
            'condition_notes', 'purchase_price', 'last_maintenance_date', 'notes', 'status'
        ]
        widgets = {
            'acquisition_date': forms.DateInput(attrs={'type': 'date'}),
            'last_maintenance_date': forms.DateInput(attrs={'type': 'date'}),
            'condition_notes': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
        help_texts = {
            'barcode': _('Unique barcode for this copy'),
            'copy_number': _('Copy number for this book title'),
        }

    def clean_copy_number(self):
        copy_number = self.cleaned_data.get('copy_number')
        book = self.cleaned_data.get('book')
        
        if copy_number and book:
            existing = BookCopy.objects.filter(
                book=book, copy_number=copy_number
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise ValidationError(
                    _('Copy number must be unique for each book title.')
                )
        
        return copy_number

    def clean_barcode(self):
        barcode = self.cleaned_data.get('barcode')
        if barcode:
            existing = BookCopy.objects.filter(barcode=barcode).exclude(
                pk=self.instance.pk if self.instance else None
            )
            if existing.exists():
                raise ValidationError(_('Barcode must be unique.'))
        return barcode

    def clean_purchase_price(self):
        price = self.cleaned_data.get('purchase_price')
        if price and price < 0:
            raise ValidationError(_('Purchase price cannot be negative.'))
        return price

    def clean_last_maintenance_date(self):
        maintenance_date = self.cleaned_data.get('last_maintenance_date')
        if maintenance_date and maintenance_date > timezone.now().date():
            raise ValidationError(_('Maintenance date cannot be in the future.'))
        return maintenance_date


class LibraryMemberForm(forms.ModelForm):
    """Form for LibraryMember model."""
    
    class Meta:
        model = LibraryMember
        fields = [
            'user', 'member_id', 'member_type', 'membership_date', 'expiry_date',
            'max_borrow_limit', 'student', 'teacher', 'status'
        ]
        widgets = {
            'membership_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }
        help_texts = {
            'member_id': _('Unique library membership ID'),
            'max_borrow_limit': _('Maximum number of books member can borrow at once'),
        }

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        membership_date = self.cleaned_data.get('membership_date')
        
        if expiry_date and membership_date and expiry_date <= membership_date:
            raise ValidationError(_('Expiry date must be after membership date.'))
        
        return expiry_date

    def clean_max_borrow_limit(self):
        limit = self.cleaned_data.get('max_borrow_limit')
        if limit and limit > 20:
            raise ValidationError(_('Maximum borrow limit cannot exceed 20 books.'))
        return limit

    def clean(self):
        cleaned_data = super().clean()
        member_type = cleaned_data.get('member_type')
        student = cleaned_data.get('student')
        teacher = cleaned_data.get('teacher')
        
        # Validate member type consistency
        if member_type == LibraryMember.MemberType.STUDENT and not student:
            self.add_error('student', _('Student must be selected for student members.'))
        
        if member_type == LibraryMember.MemberType.TEACHER and not teacher:
            self.add_error('teacher', _('Teacher must be selected for teacher members.'))
        
        if member_type not in [LibraryMember.MemberType.STUDENT, LibraryMember.MemberType.TEACHER]:
            if student or teacher:
                self.add_error(
                    'member_type',
                    _('Student/Teacher fields should only be used for student/teacher members.')
                )
        
        return cleaned_data


class BorrowRecordForm(forms.ModelForm):
    """Form for BorrowRecord model with business logic validation."""
    
    class Meta:
        model = BorrowRecord
        fields = [
            'member', 'book_copy', 'status', 'borrow_date', 'due_date',
            'return_date', 'renewal_count', 'max_renewals', 'fine_amount',
            'fine_paid', 'fine_paid_date', 'issued_by', 'received_by', 'notes', 'status'
        ]
        widgets = {
            'borrow_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'return_date': forms.DateInput(attrs={'type': 'date'}),
            'fine_paid_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial due date based on library policy
        if not self.instance.pk and not self.initial.get('due_date'):
            # This would typically be set in the view based on library settings
            pass

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        borrow_date = self.cleaned_data.get('borrow_date')
        
        if due_date and borrow_date and due_date <= borrow_date:
            raise ValidationError(_('Due date must be after borrow date.'))
        
        return due_date

    def clean_return_date(self):
        return_date = self.cleaned_data.get('return_date')
        borrow_date = self.cleaned_data.get('borrow_date')
        
        if return_date and borrow_date and return_date < borrow_date:
            raise ValidationError(_('Return date cannot be before borrow date.'))
        
        return return_date

    def clean_renewal_count(self):
        renewal_count = self.cleaned_data.get('renewal_count')
        max_renewals = self.cleaned_data.get('max_renewals')
        
        if renewal_count and max_renewals and renewal_count > max_renewals:
            raise ValidationError(_('Renewal count cannot exceed maximum renewals.'))
        
        return renewal_count

    def clean_fine_amount(self):
        fine_amount = self.cleaned_data.get('fine_amount')
        if fine_amount and fine_amount < 0:
            raise ValidationError(_('Fine amount cannot be negative.'))
        return fine_amount

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        book_copy = cleaned_data.get('book_copy')
        status = cleaned_data.get('status')
        
        # Check member eligibility
        if member and not member.is_membership_active:
            self.add_error('member', _('Member\'s library membership has expired.'))
        
        if member and not member.can_borrow_more:
            self.add_error('member', _('Member has reached maximum borrow limit.'))
        
        # Check book copy availability
        if book_copy and not book_copy.is_available_for_borrow:
            self.add_error('book_copy', _('This book copy is not available for borrowing.'))
        
        # Validate fine payment
        fine_paid = cleaned_data.get('fine_paid')
        fine_amount = cleaned_data.get('fine_amount')
        
        if fine_paid and (not fine_amount or fine_amount == 0):
            self.add_error('fine_paid', _('Cannot mark fine as paid when fine amount is zero.'))
        
        return cleaned_data


class ReservationForm(forms.ModelForm):
    """Form for Reservation model."""
    
    class Meta:
        model = Reservation
        fields = [
            'member', 'book', 'status', 'reserve_date', 'expiry_date',
            'priority', 'notes', 'status'
        ]
        widgets = {
            'reserve_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        reserve_date = self.cleaned_data.get('reserve_date')
        
        if expiry_date and reserve_date and expiry_date <= reserve_date:
            raise ValidationError(_('Expiry date must be after reserve date.'))
        
        return expiry_date

    def clean_priority(self):
        priority = self.cleaned_data.get('priority')
        if priority and priority <= 0:
            raise ValidationError(_('Priority must be a positive number.'))
        return priority

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        book = cleaned_data.get('book')
        
        if member and book:
            # Check if member already has an active reservation for this book
            existing = Reservation.objects.filter(
                member=member,
                book=book,
                status=Reservation.Status.PENDING
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                self.add_error(
                    'book',
                    _('Member already has an active reservation for this book.')
                )
        
        return cleaned_data


class FinePaymentForm(forms.ModelForm):
    """Form for FinePayment model."""
    
    class Meta:
        model = FinePayment
        fields = [
            'borrow_record', 'amount_paid', 'payment_date', 'payment_method',
            'received_by', 'receipt_number', 'notes', 'status'
        ]
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }
        help_texts = {
            'receipt_number': _('Unique receipt number for this payment'),
        }

    def clean_amount_paid(self):
        amount_paid = self.cleaned_data.get('amount_paid')
        borrow_record = self.cleaned_data.get('borrow_record')
        
        if amount_paid and amount_paid <= 0:
            raise ValidationError(_('Payment amount must be greater than 0.'))
        
        if borrow_record and amount_paid:
            outstanding_fine = borrow_record.fine_amount - borrow_record.fine_payments.aggregate(
                total_paid=models.Sum('amount_paid')
            )['total_paid'] or 0
            
            if amount_paid > outstanding_fine:
                raise ValidationError(
                    _('Payment amount cannot exceed outstanding fine amount: %(outstanding)s') % {
                        'outstanding': outstanding_fine
                    }
                )
        
        return amount_paid

    def clean_receipt_number(self):
        receipt_number = self.cleaned_data.get('receipt_number')
        if receipt_number:
            existing = FinePayment.objects.filter(receipt_number=receipt_number).exclude(
                pk=self.instance.pk if self.instance else None
            )
            if existing.exists():
                raise ValidationError(_('Receipt number must be unique.'))
        return receipt_number


# Search and Filter Forms
class BookSearchForm(forms.Form):
    """Form for searching books."""
    
    title = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by title...')})
    )
    author = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by author...')})
    )
    isbn = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by ISBN...')})
    )
    category = forms.ModelChoiceField(
        required=False,
        queryset=BookCategory.objects.all(),
        empty_label=_('All Categories')
    )
    book_type = forms.ChoiceField(
        required=False,
        choices=[('', _('All Types'))] + list(Book.BookType.choices)
    )
    book_status = forms.ChoiceField(
        required=False,
        choices=[('', _('All Status'))] + list(Book.BookStatus.choices)
    )
    available_only = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Available Books Only')
    )


class MemberSearchForm(forms.Form):
    """Form for searching library members."""
    
    member_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by member ID...')})
    )
    user_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by user name...')})
    )
    member_type = forms.ChoiceField(
        required=False,
        choices=[('', _('All Types'))] + list(LibraryMember.MemberType.choices)
    )
    membership_active = forms.BooleanField(
        required=False,
        label=_('Active Membership Only')
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', _('All Status'))] + list(LibraryMember.Status.choices)
    )


class BorrowSearchForm(forms.Form):
    """Form for searching borrow records."""
    
    member_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by member ID...')})
    )
    book_title = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': _('Search by book title...')})
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', _('All Status'))] + list(BorrowRecord.Status.choices)
    )
    overdue_only = forms.BooleanField(
        required=False,
        label=_('Overdue Books Only')
    )
    borrow_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Borrow Date From')
    )
    borrow_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Borrow Date To')
    )


# Bulk Operations Forms
class BulkBookImportForm(forms.Form):
    """Form for bulk importing books from CSV/Excel."""
    
    file = forms.FileField(
        label=_('Import File'),
        help_text=_('CSV or Excel file containing book data'),
        validators=[FileExtensionValidator(allowed_extensions=['csv', 'xlsx', 'xls'])]
    )
    library = forms.ModelChoiceField(
        queryset=Library.objects.all(),
        label=_('Library'),
        help_text=_('Select library for imported books')
    )
    create_authors = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Create Missing Authors'),
        help_text=_('Create author records if they don\'t exist')
    )
    create_publishers = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Create Missing Publishers'),
        help_text=_('Create publisher records if they don\'t exist')
    )
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        label=_('Update Existing Books'),
        help_text=_('Update books that already exist based on ISBN')
    )


class BulkBookIssueForm(forms.Form):
    """Form for bulk book issuing."""
    
    member = forms.ModelChoiceField(
        queryset=LibraryMember.objects.filter(status='active'),
        label=_('Library Member')
    )
    books = forms.ModelMultipleChoiceField(
        queryset=BookCopy.objects.filter(copy_status='available'),
        widget=forms.SelectMultiple(attrs={'class': 'select2'}),
        label=_('Books to Issue')
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Due Date')
    )
    issued_by = forms.ModelChoiceField(
        queryset=None,  # Will be set in view to current user
        label=_('Issued By')
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['issued_by'].queryset = type(user).objects.filter(pk=user.pk)

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date <= timezone.now().date():
            raise ValidationError(_('Due date must be in the future.'))
        return due_date

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        books = cleaned_data.get('books')
        
        if member and books:
            # Check member's borrow limit
            current_borrows = BorrowRecord.objects.filter(
                member=member,
                status__in=[BorrowRecord.Status.BORROWED, BorrowRecord.Status.OVERDUE]
            ).count()
            
            if current_borrows + len(books) > member.max_borrow_limit:
                self.add_error(
                    'books',
                    _('Member can only borrow %(limit)s more books. Current selection: %(selected)s') % {
                        'limit': member.max_borrow_limit - current_borrows,
                        'selected': len(books)
                    }
                )
        
        return cleaned_data


# Report Generation Forms
class LibraryReportForm(forms.Form):
    """Form for generating library reports."""
    
    REPORT_TYPES = [
        ('book_inventory', _('Book Inventory Report')),
        ('borrowing_activity', _('Borrowing Activity Report')),
        ('overdue_books', _('Overdue Books Report')),
        ('member_activity', _('Member Activity Report')),
        ('fine_collection', _('Fine Collection Report')),
        ('popular_books', _('Popular Books Report')),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        label=_('Report Type')
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('Start Date')
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label=_('End Date')
    )
    library = forms.ModelChoiceField(
        required=False,
        queryset=Library.objects.all(),
        empty_label=_('All Libraries'),
        label=_('Library')
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


class BookReturnForm(forms.Form):
    """Form for returning books."""
    
    barcode = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': _('Scan or enter book barcode...'),
            'autofocus': True
        }),
        label=_('Book Barcode')
    )
    condition_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': _('Condition notes...')}),
        label=_('Condition Notes')
    )
    received_by = forms.ModelChoiceField(
        queryset=None,  # Will be set in view to current user
        label=_('Received By')
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['received_by'].queryset = type(user).objects.filter(pk=user.pk)

    def clean_barcode(self):
        barcode = self.cleaned_data.get('barcode')
        try:
            book_copy = BookCopy.objects.get(barcode=barcode)
            # Check if book is actually borrowed
            active_borrow = BorrowRecord.objects.filter(
                book_copy=book_copy,
                status__in=[BorrowRecord.Status.BORROWED, BorrowRecord.Status.OVERDUE]
            ).first()
            
            if not active_borrow:
                raise ValidationError(_('This book is not currently borrowed.'))
            
            self.book_copy = book_copy
            self.active_borrow = active_borrow
            
        except BookCopy.DoesNotExist:
            raise ValidationError(_('No book found with this barcode.'))
        
        return barcode


class RenewBookForm(forms.Form):
    """Form for renewing book borrowals."""
    
    borrow_record = forms.ModelChoiceField(
        queryset=BorrowRecord.objects.filter(
            status__in=[BorrowRecord.Status.BORROWED, BorrowRecord.Status.OVERDUE]
        ),
        label=_('Borrow Record')
    )
    renewed_by = forms.ModelChoiceField(
        queryset=None,  # Will be set in view to current user
        label=_('Renewed By')
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['renewed_by'].queryset = type(user).objects.filter(pk=user.pk)

    def clean_borrow_record(self):
        borrow_record = self.cleaned_data.get('borrow_record')
        if borrow_record and not borrow_record.can_renew():
            raise ValidationError(_('This book cannot be renewed.'))
        return borrow_record
