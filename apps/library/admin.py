# apps/library/admin.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.db.models import Count, Sum, Q
from django.contrib.auth.models import User
from apps.core.admin import InstitutionModelAdmin

from .models import (
    Library,
    Author,
    Publisher,
    BookCategory,
    Book,
    BookCopy,
    LibraryMember,
    BorrowRecord,
    Reservation,
    FinePayment,
)


class LibraryAdmin(InstitutionModelAdmin):
    list_display = (
        "name",
        "code",
        "operating_hours",
        "max_books_per_user",
        "fine_per_day",
        "is_open_now_display",
    )
    list_filter = ("max_books_per_user",)
    search_fields = ("name", "code", "description")
    readonly_fields = ("operating_hours", "is_open_now_display")
    fieldsets = (
        (_("Basic Information"), {"fields": ("name", "code", "description")}),
        (
            _("Operating Hours"),
            {
                "fields": (
                    "opening_time",
                    "closing_time",
                    "operating_hours",
                    "is_open_now_display",
                )
            },
        ),
        (
            _("Borrowing Policies"),
            {"fields": ("max_borrow_days", "max_books_per_user", "fine_per_day")},
        ),
    )

    def is_open_now_display(self, obj):
        if obj.is_open_now:
            return format_html(
                '<span style="color: green; font-weight: bold;">●</span> {}', _("Open")
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">●</span> {}', _("Closed")
            )

    is_open_now_display.short_description = _("Current Status")


class AuthorAdmin(InstitutionModelAdmin):
    list_display = (
        "last_name",
        "first_name",
        "nationality",
        "date_of_birth",
        "date_of_death",
        "book_count",
    )
    list_filter = ("nationality",)
    search_fields = ("first_name", "last_name", "bio")
    readonly_fields = ("book_count",)
    fieldsets = (
        (
            _("Personal Information"),
            {"fields": ("first_name", "last_name", "nationality")},
        ),
        (
            _("Biographical Information"),
            {"fields": ("date_of_birth", "date_of_death", "bio")},
        ),
        (_("Statistics"), {"fields": ("book_count",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_book_count=Count("books"))

    def book_count(self, obj):
        return obj._book_count

    book_count.short_description = _("Number of Books")
    book_count.admin_order_field = "_book_count"


class PublisherAdmin(InstitutionModelAdmin):
    list_display = ("name", "contact_person", "email", "phone", "book_count")
    search_fields = ("name", "contact_person", "email")
    readonly_fields = ("book_count",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_book_count=Count("books"))

    def book_count(self, obj):
        return obj._book_count

    book_count.short_description = _("Number of Books")
    book_count.admin_order_field = "_book_count"


class BookCategoryInline(admin.TabularInline):
    model = BookCategory
    fk_name = "parent"
    extra = 1
    fields = ("name", "code", "description")


@admin.register(BookCategory)
class BookCategoryAdmin(InstitutionModelAdmin):
    list_display = ("name", "code", "parent", "hierarchy_path", "book_count")
    list_filter = ("parent",)
    search_fields = ("name", "code", "description")
    readonly_fields = ("hierarchy_path", "book_count")
    inlines = [BookCategoryInline]
    fieldsets = (
        (
            _("Category Information"),
            {"fields": ("name", "code", "description", "parent")},
        ),
        (_("Hierarchy"), {"fields": ("hierarchy_path",)}),
        (_("Statistics"), {"fields": ("book_count",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_book_count=Count("books"))

    def book_count(self, obj):
        return obj._book_count

    book_count.short_description = _("Number of Books")
    book_count.admin_order_field = "_book_count"


class BookCopyInline(admin.TabularInline):
    model = BookCopy
    extra = 0
    readonly_fields = ("copy_status", "barcode", "acquisition_date")
    fields = (
        "copy_number",
        "barcode",
        "copy_status",
        "acquisition_date",
        "condition_notes",
    )
    can_delete = False


@admin.register(Book)
class BookAdmin(InstitutionModelAdmin):
    list_display = (
        "title",
        "isbn",
        "book_type",
        "book_status",
        "available_copies",
        "total_copies",
        "library",
    )
    list_filter = ("book_type", "book_status", "library", "category")
    search_fields = ("title", "isbn", "authors__first_name", "authors__last_name")
    readonly_fields = ("available_copies", "author_names", "is_available_display")
    filter_horizontal = ("authors",)
    inlines = [BookCopyInline]
    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("title", "isbn", "edition", "book_type", "book_status")},
        ),
        (
            _("Relationships"),
            {"fields": ("authors", "publisher", "category", "library")},
        ),
        (
            _("Book Details"),
            {
                "fields": (
                    "publication_year",
                    "pages",
                    "language",
                    "description",
                    "cover_image",
                )
            },
        ),
        (
            _("Acquisition Details"),
            {"fields": ("acquisition_date", "acquisition_price", "source")},
        ),
        (
            _("Inventory Management"),
            {"fields": ("total_copies", "available_copies", "location", "keywords")},
        ),
        (_("Availability"), {"fields": ("is_available_display", "author_names")}),
    )

    def is_available_display(self, obj):
        if obj.is_available:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Available"),
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗</span> {}',
                _("Not Available"),
            )

    is_available_display.short_description = _("Available for Borrow")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("authors")


@admin.register(BookCopy)
class BookCopyAdmin(InstitutionModelAdmin):
    list_display = (
        "book_title",
        "copy_number",
        "barcode",
        "copy_status",
        "acquisition_date",
        "is_available_for_borrow_display",
    )
    list_filter = ("copy_status", "book__library")
    search_fields = ("book__title", "barcode", "copy_number")
    readonly_fields = ("book_title", "is_available_for_borrow_display")
    fieldsets = (
        (
            _("Copy Information"),
            {"fields": ("book", "copy_number", "barcode", "copy_status")},
        ),
        (
            _("Acquisition & Condition"),
            {
                "fields": (
                    "acquisition_date",
                    "purchase_price",
                    "condition_notes",
                    "last_maintenance_date",
                )
            },
        ),
        (_("Additional Information"), {"fields": ("notes",)}),
        (_("Availability"), {"fields": ("is_available_for_borrow_display",)}),
    )

    def book_title(self, obj):
        return obj.book.title

    book_title.short_description = _("Book Title")

    def is_available_for_borrow_display(self, obj):
        if obj.is_available_for_borrow:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Available"),
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗</span> {}',
                _("Not Available"),
            )

    is_available_for_borrow_display.short_description = _("Available for Borrow")


@admin.register(LibraryMember)
class LibraryMemberAdmin(InstitutionModelAdmin):
    list_display = (
        "member_id",
        "user_name",
        "member_type",
        "membership_date",
        "expiry_date",
        "is_membership_active_display",
        "current_borrow_count",
        "can_borrow_more_display",
    )
    list_filter = ("member_type", "membership_date", "expiry_date")
    search_fields = ("member_id", "user__first_name", "user__last_name", "user__email")
    readonly_fields = (
        "user_name",
        "is_membership_active_display",
        "can_borrow_more_display",
        "current_borrow_count",
    )
    fieldsets = (
        (_("Member Information"), {"fields": ("user", "member_id", "member_type")}),
        (
            _("Membership Details"),
            {
                "fields": (
                    "membership_date",
                    "expiry_date",
                    "is_membership_active_display",
                )
            },
        ),
        (
            _("Borrowing Limits"),
            {
                "fields": (
                    "max_borrow_limit",
                    "current_borrow_count",
                    "can_borrow_more_display",
                )
            },
        ),
        (
            _("Academic Relationships"),
            {"fields": ("student", "teacher"), "classes": ("collapse",)},
        ),
    )

    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    user_name.short_description = _("User Name")

    def is_membership_active_display(self, obj):
        if obj.is_membership_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Active"),
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗</span> {}', _("Expired")
            )

    is_membership_active_display.short_description = _("Membership Status")

    def can_borrow_more_display(self, obj):
        if obj.can_borrow_more:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Can Borrow"),
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗</span> {}',
                _("Limit Reached"),
            )

    can_borrow_more_display.short_description = _("Borrowing Status")


class FinePaymentInline(admin.TabularInline):
    model = FinePayment
    extra = 0
    readonly_fields = (
        "amount_paid",
        "payment_date",
        "payment_method",
        "receipt_number",
    )
    fields = ("amount_paid", "payment_date", "payment_method", "receipt_number")
    can_delete = False


@admin.register(BorrowRecord)
class BorrowRecordAdmin(InstitutionModelAdmin):
    list_display = (
        "id",
        "member_id",
        "book_title",
        "borrow_date",
        "due_date",
        "return_date",
        "status",
        "is_overdue_display",
        "fine_amount",
        "fine_paid",
    )
    list_filter = ("status", "borrow_date", "due_date", "fine_paid")
    search_fields = (
        "member__member_id",
        "book_copy__book__title",
        "book_copy__barcode",
    )
    readonly_fields = (
        "member_id",
        "book_title",
        "is_overdue_display",
        "days_overdue",
        "calculated_fine",
        "can_renew_display",
    )
    inlines = [FinePaymentInline]
    fieldsets = (
        (_("Borrow Information"), {"fields": ("member", "book_copy", "status")}),
        (_("Dates"), {"fields": ("borrow_date", "due_date", "return_date")}),
        (
            _("Renewal Information"),
            {"fields": ("renewal_count", "max_renewals", "can_renew_display")},
        ),
        (
            _("Fine Information"),
            {
                "fields": (
                    "fine_amount",
                    "fine_paid",
                    "fine_paid_date",
                    "calculated_fine",
                )
            },
        ),
        (_("Staff Information"), {"fields": ("issued_by", "received_by")}),
        (_("Overdue Status"), {"fields": ("is_overdue_display", "days_overdue")}),
        (_("Additional Information"), {"fields": ("notes",)}),
    )

    def member_id(self, obj):
        return obj.member.member_id

    member_id.short_description = _("Member ID")

    def book_title(self, obj):
        return obj.book_copy.book.title

    book_title.short_description = _("Book Title")

    def is_overdue_display(self, obj):
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠</span> {}', _("Overdue")
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("On Time"),
            )

    is_overdue_display.short_description = _("Overdue Status")

    def can_renew_display(self, obj):
        if obj.can_renew():
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Can Renew"),
            )
        else:
            return format_html(
                '<span style="color: red; font-weight: bold;">✗</span> {}',
                _("Cannot Renew"),
            )

    can_renew_display.short_description = _("Renewal Status")


@admin.register(Reservation)
class ReservationAdmin(InstitutionModelAdmin):
    list_display = (
        "member_id",
        "book_title",
        "reserve_date",
        "expiry_date",
        "status",
        "is_expired_display",
        "priority",
    )
    list_filter = ("status", "reserve_date", "expiry_date")
    search_fields = ("member__member_id", "book__title")
    readonly_fields = ("member_id", "book_title", "is_expired_display")
    fieldsets = (
        (
            _("Reservation Information"),
            {"fields": ("member", "book", "status", "priority")},
        ),
        (_("Dates"), {"fields": ("reserve_date", "expiry_date", "is_expired_display")}),
        (_("Additional Information"), {"fields": ("notes",)}),
    )

    def member_id(self, obj):
        return obj.member.member_id

    member_id.short_description = _("Member ID")

    def book_title(self, obj):
        return obj.book.title

    book_title.short_description = _("Book Title")

    def is_expired_display(self, obj):
        if obj.is_expired:
            return format_html(
                '<span style="color: red; font-weight: bold;">⚠</span> {}', _("Expired")
            )
        else:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> {}',
                _("Active"),
            )

    is_expired_display.short_description = _("Expiry Status")


@admin.register(FinePayment)
class FinePaymentAdmin(InstitutionModelAdmin):
    list_display = (
        "receipt_number",
        "borrow_record_info",
        "amount_paid",
        "payment_date",
        "payment_method",
        "received_by_name",
    )
    list_filter = ("payment_method", "payment_date")
    search_fields = (
        "receipt_number",
        "borrow_record__member__member_id",
        "borrow_record__book_copy__book__title",
    )
    readonly_fields = ("borrow_record_info", "received_by_name")
    fieldsets = (
        (
            _("Payment Information"),
            {
                "fields": (
                    "borrow_record",
                    "amount_paid",
                    "payment_date",
                    "payment_method",
                )
            },
        ),
        (_("Receipt Information"), {"fields": ("receipt_number", "received_by")}),
        (_("Additional Information"), {"fields": ("notes",)}),
    )

    def borrow_record_info(self, obj):
        return f"{obj.borrow_record.member.member_id} - {obj.borrow_record.book_copy.book.title}"

    borrow_record_info.short_description = _("Borrow Record")

    def received_by_name(self, obj):
        if obj.received_by:
            return obj.received_by.get_full_name() or obj.received_by.username
        return _("Not specified")

    received_by_name.short_description = _("Received By")


# Custom admin site header and title
admin.site.site_header = _("Library Management System")
admin.site.site_title = _("Library Admin")
admin.site.index_title = _("Library Administration")
