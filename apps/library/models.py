# apps/library/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator,FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


from apps.core.models import CoreBaseModel, AddressModel, ContactModel
from apps.users.models import User
from apps.academics.models import Student, Teacher


class Library(CoreBaseModel):
    """
    Main library entity representing a physical or logical library.
    """
    name = models.CharField(_('library name'), max_length=200)
    code = models.CharField(_('library code'), max_length=20, unique=True)
    description = models.TextField(_('description'), blank=True)
    opening_time = models.TimeField(_('opening time'))
    closing_time = models.TimeField(_('closing time'))
    max_borrow_days = models.PositiveIntegerField(
        _('maximum borrow days'),
        default=14,
        validators=[MinValueValidator(1), MaxValueValidator(365)]
    )
    max_books_per_user = models.PositiveIntegerField(
        _('maximum books per user'),
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    fine_per_day = models.DecimalField(
        _('fine per day'),
        max_digits=8,
        decimal_places=2,
        default=5.00,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = _('Library')
        verbose_name_plural = _('Libraries')
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def operating_hours(self):
        return f"{self.opening_time.strftime('%H:%M')} - {self.closing_time.strftime('%H:%M')}"

    @property
    def is_open_now(self):
        """Check if library is currently open."""
        now = timezone.now().time()
        return self.opening_time <= now <= self.closing_time


class Author(CoreBaseModel):
    """
    Model for book authors.
    """
    first_name = models.CharField(_('first name'), max_length=100)
    last_name = models.CharField(_('last name'), max_length=100)
    bio = models.TextField(_('biography'), blank=True)
    date_of_birth = models.DateField(_('date of birth'), null=True, blank=True)
    date_of_death = models.DateField(_('date of death'), null=True, blank=True)
    nationality = models.CharField(_('nationality'), max_length=100, blank=True)

    class Meta:
        verbose_name = _('Author')
        verbose_name_plural = _('Authors')
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Publisher(CoreBaseModel):
    """
    Model for book publishers.
    """
    name = models.CharField(_('publisher name'), max_length=200)
    contact_person = models.CharField(_('contact person'), max_length=100, blank=True)
    email = models.EmailField(_('email'), blank=True)
    phone = models.CharField(_('phone'), max_length=20, blank=True)
    website = models.URLField(_('website'), blank=True)

    class Meta:
        verbose_name = _('Publisher')
        verbose_name_plural = _('Publishers')
        ordering = ['name']

    def __str__(self):
        return self.name


class BookCategory(CoreBaseModel):
    """
    Hierarchical categorization for books.
    """
    name = models.CharField(_('category name'), max_length=100)
    code = models.CharField(_('category code'), max_length=20, unique=True)
    description = models.TextField(_('description'), blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        verbose_name=_('parent category')
    )

    class Meta:
        verbose_name = _('Book Category')
        verbose_name_plural = _('Book Categories')
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def hierarchy_path(self):
        """Return full category hierarchy path."""
        path = []
        current = self
        while current:
            path.append(current.name)
            current = current.parent
        return ' > '.join(reversed(path))


class Book(CoreBaseModel):
    """
    Main book model representing a title in the library.
    """
    class BookType(models.TextChoices):
        TEXTBOOK = 'textbook', _('Textbook')
        REFERENCE = 'reference', _('Reference Book')
        FICTION = 'fiction', _('Fiction')
        NON_FICTION = 'non_fiction', _('Non-Fiction')
        MAGAZINE = 'magazine', _('Magazine')
        JOURNAL = 'journal', _('Journal')
        NEWSPAPER = 'newspaper', _('Newspaper')
        EBOOK = 'ebook', _('E-Book')
        AUDIOBOOK = 'audiobook', _('Audiobook')

    class BookStatus(models.TextChoices):
        AVAILABLE = 'available', _('Available')
        BORROWED = 'borrowed', _('Borrowed')
        RESERVED = 'reserved', _('Reserved')
        LOST = 'lost', _('Lost')
        DAMAGED = 'damaged', _('Damaged')
        UNDER_MAINTENANCE = 'under_maintenance', _('Under Maintenance')

    title = models.CharField(_('book title'), max_length=500)
    isbn = models.CharField(_('ISBN'), max_length=20, blank=True, db_index=True)
    edition = models.CharField(_('edition'), max_length=50, blank=True)
    book_type = models.CharField(
        _('book type'),
        max_length=20,
        choices=BookType.choices,
        default=BookType.TEXTBOOK
    )
    book_status = models.CharField(
        _('book status'),
        max_length=20,
        choices=BookStatus.choices,
        default=BookStatus.AVAILABLE
    )
    
    # Relationships
    authors = models.ManyToManyField(Author, related_name='books', verbose_name=_('authors'))
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='books',
        verbose_name=_('publisher')
    )
    category = models.ForeignKey(
        BookCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='books',
        verbose_name=_('category')
    )
    library = models.ForeignKey(
        Library,
        on_delete=models.CASCADE,
        related_name='books',
        verbose_name=_('library')
    )
    
    # Book details
    publication_year = models.PositiveIntegerField(
        _('publication year'),
        validators=[MinValueValidator(1000), MaxValueValidator(2100)],
        null=True,
        blank=True
    )
    pages = models.PositiveIntegerField(_('number of pages'), null=True, blank=True)
    language = models.CharField(_('language'), max_length=50, default='English')
    description = models.TextField(_('description'), blank=True)
    cover_image = models.ImageField(
        _('cover image'),
        upload_to='library/covers/',
        null=True,
        blank=True
    )
    
    # Acquisition details
    acquisition_date = models.DateField(_('acquisition date'), default=timezone.now)
    acquisition_price = models.DecimalField(
        _('acquisition price'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    source = models.CharField(_('acquisition source'), max_length=200, blank=True)
    
    # Metadata
    total_copies = models.PositiveIntegerField(
        _('total copies'),
        default=1,
        validators=[MinValueValidator(1)]
    )
    available_copies = models.PositiveIntegerField(_('available copies'), default=1)
    location = models.CharField(_('shelf location'), max_length=100, blank=True)
    keywords = models.CharField(_('keywords'), max_length=500, blank=True)

    class Meta:
        verbose_name = _('Book')
        verbose_name_plural = _('Books')
        ordering = ['title']
        indexes = [
            models.Index(fields=['title', 'book_status']),
            models.Index(fields=['isbn']),
            models.Index(fields=['book_status', 'available_copies']),
        ]

    def __str__(self):
        return f"{self.title} ({self.edition})" if self.edition else self.title

    def save(self, *args, **kwargs):
        """Ensure available copies don't exceed total copies."""
        if self.available_copies > self.total_copies:
            self.available_copies = self.total_copies
        super().save(*args, **kwargs)

    @property
    def is_available(self):
        return self.book_status == self.BookStatus.AVAILABLE and self.available_copies > 0

    @property
    def author_names(self):
        return ", ".join([str(author) for author in self.authors.all()])

    def update_available_copies(self):
        """Recalculate available copies based on current borrows."""
        from .models import BorrowRecord
        borrowed_count = self.borrow_records.filter(
            status__in=[BorrowRecord.Status.BORROWED, BorrowRecord.Status.OVERDUE]
        ).count()
        self.available_copies = self.total_copies - borrowed_count
        self.save()


class BookCopy(CoreBaseModel):
    """
    Individual copy of a book for tracking specific physical items.
    """
    class CopyStatus(models.TextChoices):
        AVAILABLE = 'available', _('Available')
        BORROWED = 'borrowed', _('Borrowed')
        RESERVED = 'reserved', _('Reserved')
        LOST = 'lost', _('Lost')
        DAMAGED = 'damaged', _('Damaged')
        UNDER_MAINTENANCE = 'under_maintenance', _('Under Maintenance')
        WITHDRAWN = 'withdrawn', _('Withdrawn')

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='copies',
        verbose_name=_('book')
    )
    copy_number = models.PositiveIntegerField(_('copy number'), default=1)
    barcode = models.CharField(_('barcode'), max_length=100, unique=True, db_index=True)
    copy_status = models.CharField(
        _('copy status'),
        max_length=20,
        choices=CopyStatus.choices,
        default=CopyStatus.AVAILABLE
    )
    acquisition_date = models.DateField(_('acquisition date'), default=timezone.now)
    condition_notes = models.TextField(_('condition notes'), blank=True)
    purchase_price = models.DecimalField(
        _('purchase price'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    last_maintenance_date = models.DateField(_('last maintenance date'), null=True, blank=True)
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('Book Copy')
        verbose_name_plural = _('Book Copies')
        unique_together = ['book', 'copy_number']
        ordering = ['book__title', 'copy_number']

    def __str__(self):
        return f"{self.book.title} - Copy {self.copy_number}"

    @property
    def is_available_for_borrow(self):
        return self.copy_status in [self.CopyStatus.AVAILABLE, self.CopyStatus.RESERVED]


class LibraryMember(CoreBaseModel):
    """
    Library membership information for users.
    """
    class MemberType(models.TextChoices):
        STUDENT = 'student', _('Student')
        TEACHER = 'teacher', _('Teacher')
        STAFF = 'staff', _('Staff')
        PARENT = 'parent', _('Parent')
        EXTERNAL = 'external', _('External')

    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='library_member',
        verbose_name=_('user')
    )
    member_id = models.CharField(_('member ID'), max_length=50, unique=True, db_index=True)
    member_type = models.CharField(
        _('member type'),
        max_length=20,
        choices=MemberType.choices
    )
    membership_date = models.DateField(_('membership date'), default=timezone.now)
    expiry_date = models.DateField(_('membership expiry date'))
    max_borrow_limit = models.PositiveIntegerField(_('maximum borrow limit'), default=5)
    current_borrow_count = models.PositiveIntegerField(_('current borrow count'), default=0)
    
    student = models.ForeignKey( 
        'academics.Student',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='library_members',
        verbose_name=_('student')
    )
    teacher = models.ForeignKey( 
        'academics.Teacher', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='library_members',
        verbose_name=_('teacher')
    )
    class Meta:
        verbose_name = _('Library Member')
        verbose_name_plural = _('Library Members')
        ordering = ['member_id']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.member_id})"

    @property
    def can_borrow_more(self):
        return self.current_borrow_count < self.max_borrow_limit

    @property
    def is_membership_active(self):
        return self.expiry_date >= timezone.now().date()

    def update_borrow_count(self):
        """Update current borrow count based on active borrow records."""
        active_borrows = self.borrow_records.filter(
            status__in=[BorrowRecord.Status.BORROWED, BorrowRecord.Status.OVERDUE]
        ).count()
        self.current_borrow_count = active_borrows
        self.save()


class BorrowRecord(CoreBaseModel):
    """
    Track book borrowing and returning operations.
    """
    class Status(models.TextChoices):
        BORROWED = 'borrowed', _('Borrowed')
        RETURNED = 'returned', _('Returned')
        OVERDUE = 'overdue', _('Overdue')
        LOST = 'lost', _('Lost')
        RESERVED = 'reserved', _('Reserved')
        CANCELLED = 'cancelled', _('Cancelled')

    member = models.ForeignKey(
        LibraryMember,
        on_delete=models.CASCADE,
        related_name='borrow_records',
        verbose_name=_('member')
    )
    book_copy = models.ForeignKey(
        BookCopy,
        on_delete=models.CASCADE,
        related_name='borrow_records',
        verbose_name=_('book copy')
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.BORROWED
    )
    
    # Borrow details
    borrow_date = models.DateField(_('borrow date'), default=timezone.now)
    due_date = models.DateField(_('due date'))
    return_date = models.DateField(_('return date'), null=True, blank=True)
    
    # Renewal tracking
    renewal_count = models.PositiveIntegerField(_('renewal count'), default=0)
    max_renewals = models.PositiveIntegerField(_('maximum renewals'), default=1)
    
    # Fine tracking
    fine_amount = models.DecimalField(
        _('fine amount'),
        max_digits=8,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)]
    )
    fine_paid = models.BooleanField(_('fine paid'), default=False)
    fine_paid_date = models.DateField(_('fine paid date'), null=True, blank=True)
    
    # Staff actions
    issued_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='issued_books',
        verbose_name=_('issued by')
    )
    received_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_books',
        verbose_name=_('received by')
    )
    
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('Borrow Record')
        verbose_name_plural = _('Borrow Records')
        ordering = ['-borrow_date']
        indexes = [
            models.Index(fields=['member', 'status']),
            models.Index(fields=['due_date', 'status']),
            models.Index(fields=['book_copy', 'status']),
        ]

    def __str__(self):
        return f"{self.member.member_id} - {self.book_copy.book.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        
        from django.db import transaction
        if self.member and hasattr(self.member, 'update_borrow_count'):
            transaction.on_commit(lambda: self.member.update_borrow_count())

        # Update book's available copies
        if self.book_copy and hasattr(self.book_copy.book, 'update_available_copies'):
            transaction.on_commit(lambda: self.book_copy.book.update_available_copies())

    @property
    def is_overdue(self):
        if self.status in [self.Status.RETURNED, self.Status.CANCELLED]:
            return False
        return timezone.now().date() > self.due_date

    @property
    def days_overdue(self):
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days

    @property
    def calculated_fine(self):
        """Calculate fine based on overdue days."""
        if not self.is_overdue:
            return 0
        library = self.book_copy.book.library
        return self.days_overdue * library.fine_per_day

    def can_renew(self):
        """Check if this borrow record can be renewed."""
        return (
            self.status == self.Status.BORROWED and
            self.renewal_count < self.max_renewals and
            not self.is_overdue
        )

    def renew(self, renewed_by):
        """Renew the book borrowing."""
        if not self.can_renew():
            return False
        
        self.renewal_count += 1
        self.due_date += timezone.timedelta(days=self.book_copy.book.library.max_borrow_days)
        self.issued_by = renewed_by
        self.save()
        return True

    def return_book(self, returned_by, notes=''):
        """Process book return."""
        self.status = self.Status.RETURNED
        self.return_date = timezone.now().date()
        self.received_by = returned_by
        self.notes = notes
        
        # Calculate and set fine if overdue
        if self.is_overdue:
            self.fine_amount = self.calculated_fine
        
        self.save()


class Reservation(CoreBaseModel):
    """
    Book reservation system for members.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        FULFILLED = 'fulfilled', _('Fulfilled')
        CANCELLED = 'cancelled', _('Cancelled')
        EXPIRED = 'expired', _('Expired')

    member = models.ForeignKey(
        LibraryMember,
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name=_('member')
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name=_('book')
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    reserve_date = models.DateField(_('reserve date'), default=timezone.now)
    expiry_date = models.DateField(_('expiry date'))
    priority = models.PositiveIntegerField(_('priority'), default=1)
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('Reservation')
        verbose_name_plural = _('Reservations')
        ordering = ['priority', 'reserve_date']
        unique_together = ['member', 'book', 'status']

    def __str__(self):
        return f"{self.member.member_id} - {self.book.title}"

    def save(self, *args, **kwargs):
        """Set expiry date if not provided."""
        if not self.expiry_date and not self.pk:
            self.expiry_date = self.reserve_date + timezone.timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now().date() > self.expiry_date

    def fulfill(self):
        """Mark reservation as fulfilled."""
        self.status = self.Status.FULFILLED
        self.save()


class FinePayment(CoreBaseModel):
    """
    Track fine payments for overdue books.
    """
    borrow_record = models.ForeignKey(
        BorrowRecord,
        on_delete=models.CASCADE,
        related_name='fine_payments',
        verbose_name=_('borrow record')
    )
    amount_paid = models.DecimalField(
        _('amount paid'),
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    payment_date = models.DateField(_('payment date'), default=timezone.now)
    payment_method = models.CharField(
        _('payment method'),
        max_length=20,
        choices=[
            ('cash', _('Cash')),
            ('card', _('Card')),
            ('online', _('Online')),
            ('transfer', _('Bank Transfer')),
        ],
        default='cash'
    )
    received_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='collected_fines',
        verbose_name=_('received by')
    )
    receipt_number = models.CharField(_('receipt number'), max_length=50, unique=True)
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('Fine Payment')
        verbose_name_plural = _('Fine Payments')
        ordering = ['-payment_date']

    def __str__(self):
        return f"Fine Payment - {self.receipt_number}"

    def save(self, *args, **kwargs):
        """Update borrow record when fine is paid."""
        super().save(*args, **kwargs)
        
        # Update borrow record
        if self.borrow_record:
            self.borrow_record.fine_paid = True
            self.borrow_record.fine_paid_date = self.payment_date
            self.borrow_record.save()