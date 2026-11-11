# apps/library/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy
from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    PermissionRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.auth.views import LoginView, LogoutView

from apps.core.mixins import InstitutionPermissionMixin
from apps.users.utils import has_role_or_perm

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
from .forms import (
    LibraryForm,
    AuthorForm,
    PublisherForm,
    BookCategoryForm,
    BookForm,
    BookCopyForm,
    LibraryMemberForm,
    BorrowRecordForm,
    ReservationForm,
    FinePaymentForm,
    BookSearchForm,
)


# Library Views
class LibraryAccessMixin:
    """Mixin to check library-related permissions"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Check if user has library-related role or is staff/admin
        user_roles = request.user.user_roles.all()
        library_roles = ["librarian", "admin", "principal", "super_admin"]

        if not any(role.role.role_type in library_roles for role in user_roles):
            if not request.user.is_staff:
                # Students can access library but with limited permissions
                if not hasattr(request.user, "student_profile"):
                    messages.error(
                        request,
                        _("You don't have permission to access library resources."),
                    )
                    return redirect("users:dashboard")

        return super().dispatch(request, *args, **kwargs)


class LibrarianRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure user is a librarian, staff, or admin."""

    def test_func(self):
        user = self.request.user
        if user.is_staff:
            return True

        # Check if user has librarian role
        return has_role_or_perm(user, perm="library.change_book", role_type="librarian")


class LibraryListView(LoginRequiredMixin, LibraryAccessMixin, ListView):
    model = Library
    template_name = "library/libraries/library_list.html"
    context_object_name = "libraries"
    paginate_by = 20

    def get_queryset(self):
        queryset = Library.objects.filter(status="active")

        # Search functionality
        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(code__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = BookSearchForm(self.request.GET)
        return context


class LibraryDetailView(LoginRequiredMixin, DetailView):
    model = Library
    template_name = "library/libraries/library_detail.html"
    context_object_name = "library"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        library = self.get_object()

        # Statistics
        context["total_books"] = Book.objects.filter(
            library=library, status="active"
        ).count()
        context["total_members"] = LibraryMember.objects.filter(status="active").count()
        context["active_borrows"] = BorrowRecord.objects.filter(
            book_copy__book__library=library, status__in=["borrowed", "overdue"]
        ).count()

        return context


class LibraryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Library
    form_class = LibraryForm
    template_name = "library/libraries/library_form.html"
    permission_required = "library.add_library"
    success_url = reverse_lazy("library:library_list")

    def form_valid(self, form):
        messages.success(self.request, _("Library created successfully."))
        return super().form_valid(form)


class LibraryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Library
    form_class = LibraryForm
    template_name = "library/libraries/library_form.html"
    permission_required = "library.change_library"
    success_url = reverse_lazy("library:library_list")

    def form_valid(self, form):
        messages.success(self.request, _("Library updated successfully."))
        return super().form_valid(form)


# Author Views
class AuthorListView(InstitutionPermissionMixin, ListView):
    model = Author
    template_name = "library/authors/author_list.html"
    context_object_name = "authors"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .filter(status="active")
            .annotate(book_count=Count("books"))
        )

        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
                | Q(nationality__icontains=search_query)
            )

        return queryset.order_by("pk")


class AuthorDetailView(LoginRequiredMixin, DetailView):
    model = Author
    template_name = "library/authors/author_detail.html"
    context_object_name = "author"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        author = self.get_object()

        # Get author's books
        context["books"] = Book.objects.filter(
            authors=author, status="active"
        ).select_related("publisher", "category")

        return context


class AuthorCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Author
    form_class = AuthorForm
    template_name = "library/authors/author_form.html"
    permission_required = "library.add_author"
    success_url = reverse_lazy("library:author_list")

    def form_valid(self, form):
        messages.success(self.request, _("Author created successfully."))
        return super().form_valid(form)


class AuthorUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Author
    form_class = AuthorForm
    template_name = "library/authors/author_form.html"
    permission_required = "library.change_author"
    success_url = reverse_lazy("library:author_list")

    def form_valid(self, form):
        messages.success(self.request, _("Author updated successfully."))
        return super().form_valid(form)


# Book Views
class BookListView(InstitutionPermissionMixin, ListView):
    model = Book
    template_name = "library/books/book_list.html"
    context_object_name = "books"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .filter(status="active")
            .select_related("publisher", "category", "library")
            .prefetch_related("authors")
        )

        # Search functionality
        search_query = self.request.GET.get("search", "")
        category_filter = self.request.GET.get("category", "")
        book_type_filter = self.request.GET.get("book_type", "")

        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(isbn__icontains=search_query)
                | Q(authors__first_name__icontains=search_query)
                | Q(authors__last_name__icontains=search_query)
            ).distinct()

        if category_filter:
            queryset = queryset.filter(category_id=category_filter)

        if book_type_filter:
            queryset = queryset.filter(book_type=book_type_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_form"] = BookSearchForm(self.request.GET)
        try:
            from apps.core.middleware import get_user_accessible_institutions

            if self.request.user.is_superuser:
                context["categories"] = BookCategory.objects.filter(status="active")
            else:
                accessible_insts = get_user_accessible_institutions(self.request.user)
                context["categories"] = BookCategory.objects.filter(
                    status="active", institution__in=accessible_insts
                )
        except Exception:
            context["categories"] = BookCategory.objects.filter(status="active")
        return context


class BookDetailView(LoginRequiredMixin, DetailView):
    model = Book
    template_name = "library/books/book_detail.html"
    context_object_name = "book"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book = self.get_object()

        # Get available copies
        context["available_copies"] = book.copies.filter(
            copy_status="available", status="active"
        )

        # Get current reservations
        context["reservations"] = Reservation.objects.filter(
            book=book, status="pending"
        ).select_related("member__user")

        # Get borrow history
        context["borrow_history"] = BorrowRecord.objects.filter(
            book_copy__book=book
        ).select_related("member__user", "book_copy")[:10]

        return context


class BookCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = "library/books/book_form.html"
    permission_required = "library.add_book"
    success_url = reverse_lazy("library:book_list")

    def form_valid(self, form):
        messages.success(self.request, _("Book created successfully."))
        return super().form_valid(form)


class BookUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = "library/books/book_form.html"
    permission_required = "library.change_book"
    success_url = reverse_lazy("library:book_list")

    def form_valid(self, form):
        messages.success(self.request, _("Book updated successfully."))
        return super().form_valid(form)


# BookCopy Views
class BookCopyListView(InstitutionPermissionMixin, ListView):
    model = BookCopy
    template_name = "library/bookcopies/bookcopy_list.html"
    context_object_name = "copies"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .filter(status="active")
            .select_related("book", "book__library")
        )

        search_query = self.request.GET.get("search", "")
        status_filter = self.request.GET.get("status", "")

        if search_query:
            queryset = queryset.filter(
                Q(book__title__icontains=search_query)
                | Q(barcode__icontains=search_query)
            )

        if status_filter:
            queryset = queryset.filter(copy_status=status_filter)

        return queryset


class BookCopyCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = BookCopy
    form_class = BookCopyForm
    template_name = "library/bookcopies/bookcopy_form.html"
    permission_required = "library.add_bookcopy"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        book_id = self.request.GET.get("book")
        if book_id:
            try:
                book = Book.objects.get(pk=book_id)
                context["initial_book"] = book
                # Initialize the form with the book
                context["form"].initial = {"book": book}
            except Book.DoesNotExist:
                pass
        return context

    def get_success_url(self):
        return reverse_lazy("library:book_detail", kwargs={"pk": self.object.book.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Book copy created successfully."))
        return super().form_valid(form)


class BookCopyUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = BookCopy
    form_class = BookCopyForm
    template_name = "library/bookcopies/bookcopy_form.html"
    permission_required = "library.change_bookcopy"

    def get_success_url(self):
        return reverse_lazy("library:book_detail", kwargs={"pk": self.object.book.pk})

    def form_valid(self, form):
        messages.success(self.request, _("Book copy updated successfully."))
        return super().form_valid(form)


# LibraryMember Views
class LibraryMemberListView(InstitutionPermissionMixin, ListView):
    model = LibraryMember
    template_name = "library/librarymembers/librarymember_list.html"
    context_object_name = "members"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .filter(status="active")
            .select_related("user", "student", "teacher")
            .annotate(
                active_borrows=Count(
                    "borrow_records",
                    filter=Q(borrow_records__status__in=["borrowed", "overdue"]),
                )
            )
        )

        search_query = self.request.GET.get("search", "")
        member_type_filter = self.request.GET.get("member_type", "")

        if search_query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(member_id__icontains=search_query)
                | Q(user__email__icontains=search_query)
            )

        if member_type_filter:
            queryset = queryset.filter(member_type=member_type_filter)

        return queryset.order_by("pk")


class LibraryMemberDetailView(LoginRequiredMixin, DetailView):
    model = LibraryMember
    template_name = "library/librarymembers/librarymember_detail.html"
    context_object_name = "member"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member = self.get_object()

        # Get current borrows
        context["current_borrows"] = BorrowRecord.objects.filter(
            member=member, status__in=["borrowed", "overdue"]
        ).select_related("book_copy__book")

        # Get borrow history
        context["borrow_history"] = (
            BorrowRecord.objects.filter(member=member)
            .select_related("book_copy__book")
            .order_by("-borrow_date")[:20]
        )

        # Get reservations
        context["reservations"] = Reservation.objects.filter(
            member=member, status="pending"
        ).select_related("book")

        # Get fine history
        context["fine_history"] = FinePayment.objects.filter(
            borrow_record__member=member
        ).select_related("borrow_record__book_copy__book")

        return context


class LibraryMemberCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = LibraryMember
    form_class = LibraryMemberForm
    template_name = "library/librarymembers/librarymember_form.html"
    permission_required = "library.add_librarymember"
    success_url = reverse_lazy("library:librarymember_list")

    def form_valid(self, form):
        messages.success(self.request, _("Library member created successfully."))
        return super().form_valid(form)


class LibraryMemberUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = LibraryMember
    form_class = LibraryMemberForm
    template_name = "library/librarymembers/librarymember_form.html"
    permission_required = "library.change_librarymember"
    success_url = reverse_lazy("library:librarymember_list")

    def form_valid(self, form):
        messages.success(self.request, _("Library member updated successfully."))
        return super().form_valid(form)


# BorrowRecord Views
class BorrowRecordListView(LoginRequiredMixin, ListView):
    model = BorrowRecord
    template_name = "library/borrowrecords/borrowrecord_list.html"
    context_object_name = "borrow_records"
    paginate_by = 20

    def get_queryset(self):
        queryset = BorrowRecord.objects.select_related(
            "member__user", "book_copy__book", "issued_by"
        ).order_by("-borrow_date")

        status_filter = self.request.GET.get("status", "")
        overdue_filter = self.request.GET.get("overdue", "")

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if overdue_filter == "true":
            queryset = queryset.filter(is_overdue=True)

        return queryset


class BorrowRecordCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = BorrowRecord
    form_class = BorrowRecordForm
    template_name = "library/borrowrecords/borrowrecord_form.html"
    permission_required = "library.add_borrowrecord"

    def get_success_url(self):
        return reverse_lazy("library:borrowrecord_list")

    def form_valid(self, form):
        form.instance.issued_by = self.request.user
        form.instance.borrow_date = timezone.now().date()

        # Set due date based on library policy
        book_copy = form.cleaned_data["book_copy"]
        library = book_copy.book.library
        form.instance.due_date = timezone.now().date() + timezone.timedelta(
            days=library.max_borrow_days
        )

        messages.success(self.request, _("Book borrowed successfully."))
        return super().form_valid(form)


class BorrowRecordUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = BorrowRecord
    form_class = BorrowRecordForm
    template_name = "library/borrowrecords/borrowrecord_form.html"
    permission_required = "library.change_borrowrecord"

    def get_success_url(self):
        return reverse_lazy("library:borrowrecord_list")

    def form_valid(self, form):
        messages.success(self.request, _("Borrow record updated successfully."))
        return super().form_valid(form)


@login_required
@permission_required("library.change_borrowrecord")
def return_book(request, pk):
    """
    View for returning a borrowed book.
    """
    borrow_record = get_object_or_404(BorrowRecord, pk=pk)

    if request.method == "POST":
        borrow_record.return_book(
            returned_by=request.user, notes=request.POST.get("notes", "")
        )
        messages.success(request, _("Book returned successfully."))
        return redirect("library:borrowrecord_list")

    context = {
        "borrow_record": borrow_record,
        "calculated_fine": borrow_record.calculated_fine,
    }
    return render(request, "library/borrowrecords/return_book.html", context)


@login_required
@permission_required("library.change_borrowrecord")
def renew_book(request, pk):
    """
    View for renewing a borrowed book.
    """
    borrow_record = get_object_or_404(BorrowRecord, pk=pk)

    if borrow_record.can_renew():
        if borrow_record.renew(request.user):
            messages.success(request, _("Book renewed successfully."))
        else:
            messages.error(request, _("Cannot renew this book."))
    else:
        messages.error(request, _("This book cannot be renewed."))

    return redirect("library:borrowrecord_list")


# Reservation Views
class ReservationListView(LoginRequiredMixin, ListView):
    model = Reservation
    template_name = "library/reservations/reservation_list.html"
    context_object_name = "reservations"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            Reservation.objects.filter(status="pending")
            .select_related("member__user", "book")
            .order_by("priority", "reserve_date")
        )

        return queryset


class ReservationCreateView(LoginRequiredMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = "library/reservations/reservation_form.html"

    def get_success_url(self):
        return reverse_lazy("library:reservation_list")

    def form_valid(self, form):
        # Check if member can make reservation
        member = form.cleaned_data["member"]
        if not member.is_membership_active:
            messages.error(self.request, _("Member membership is not active."))
            return self.form_invalid(form)

        messages.success(self.request, _("Book reserved successfully."))
        return super().form_valid(form)


@login_required
@permission_required("library.change_reservation")
def fulfill_reservation(request, pk):
    """
    View for fulfilling a reservation when book becomes available.
    """
    reservation = get_object_or_404(Reservation, pk=pk)

    if reservation.status == "pending":
        reservation.fulfill()
        messages.success(request, _("Reservation fulfilled successfully."))
    else:
        messages.error(request, _("Reservation cannot be fulfilled."))

    return redirect("library:reservation_list")


# FinePayment Views
class FinePaymentListView(LoginRequiredMixin, ListView):
    model = FinePayment
    template_name = "library/finepayments/finepayment_list.html"
    context_object_name = "fine_payments"
    paginate_by = 20

    def get_queryset(self):
        queryset = FinePayment.objects.select_related(
            "borrow_record__member__user",
            "borrow_record__book_copy__book",
            "received_by",
        ).order_by("-payment_date")

        return queryset


class FinePaymentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = FinePayment
    form_class = FinePaymentForm
    template_name = "library/finepayments/finepayment_form.html"
    permission_required = "library.add_finepayment"

    def get_success_url(self):
        return reverse_lazy("library:finepayment_list")

    def form_valid(self, form):
        form.instance.received_by = self.request.user
        messages.success(self.request, _("Fine payment recorded successfully."))
        return super().form_valid(form)


# Dashboard and Reports
@login_required
def library_dashboard(request):
    """
    Main dashboard view for library management.
    """
    from apps.core.middleware import get_current_institution

    current_institution = get_current_institution()

    if not current_institution:
        messages.warning(request, _("Please select an institution to continue."))
        return redirect("core:institution_select")

    # Basic statistics
    total_books = Book.objects.filter(
        status="active", institution=current_institution
    ).count()
    total_members = LibraryMember.objects.filter(
        status="active", institution=current_institution
    ).count()
    active_borrows = BorrowRecord.objects.filter(
        status__in=["borrowed", "overdue"],
        book_copy__book__institution=current_institution,
    ).count()
    overdue_books = BorrowRecord.objects.filter(
        status="overdue", book_copy__book__institution=current_institution
    ).count()
    pending_reservations = Reservation.objects.filter(
        status="pending", book__institution=current_institution
    ).count()

    # Recent activities
    recent_borrows = (
        BorrowRecord.objects.select_related("member__user", "book_copy__book")
        .filter(book_copy__book__institution=current_institution)
        .order_by("-borrow_date")[:10]
    )

    recent_returns = (
        BorrowRecord.objects.filter(
            status="returned", book_copy__book__institution=current_institution
        )
        .select_related("member__user", "book_copy__book")
        .order_by("-return_date")[:10]
    )

    # Popular books (most borrowed)
    popular_books = (
        Book.objects.annotate(borrow_count=Count("copies__borrow_records"))
        .filter(borrow_count__gt=0, institution=current_institution)
        .order_by("-borrow_count")[:10]
    )

    context = {
        "total_books": total_books,
        "total_members": total_members,
        "active_borrows": active_borrows,
        "overdue_books": overdue_books,
        "pending_reservations": pending_reservations,
        "recent_borrows": recent_borrows,
        "recent_returns": recent_returns,
        "popular_books": popular_books,
    }

    return render(request, "library/dashboard/dashboard.html", context)


@login_required
def member_dashboard(request):
    """
    Dashboard view for library members.
    """
    if not hasattr(request.user, "library_member"):
        messages.error(request, _("You are not registered as a library member."))
        return redirect("library:library_list")

    member = request.user.library_member

    # Current borrows
    current_borrows = BorrowRecord.objects.filter(
        member=member, status__in=["borrowed", "overdue"]
    ).select_related("book_copy__book")

    # Reservations
    reservations = Reservation.objects.filter(
        member=member, status="pending"
    ).select_related("book")

    # Borrow history
    borrow_history = (
        BorrowRecord.objects.filter(member=member)
        .select_related("book_copy__book")
        .order_by("-borrow_date")[:10]
    )

    # Fines
    unpaid_fines = BorrowRecord.objects.filter(
        member=member, fine_amount__gt=0, fine_paid=False
    ).select_related("book_copy__book")

    context = {
        "member": member,
        "current_borrows": current_borrows,
        "reservations": reservations,
        "borrow_history": borrow_history,
        "unpaid_fines": unpaid_fines,
    }

    return render(request, "library/dashboard/member_dashboard.html", context)


# AJAX Views for dynamic functionality
@login_required
def get_book_details(request, book_id):
    """
    AJAX view to get book details for borrowing/reservation.
    """
    book = get_object_or_404(Book, pk=book_id)

    available_copies = book.copies.filter(
        copy_status="available", status="active"
    ).count()

    data = {
        "title": book.title,
        "authors": book.author_names,
        "isbn": book.isbn,
        "available_copies": available_copies,
        "is_available": book.is_available,
    }

    return JsonResponse(data)


@login_required
def get_member_details(request, member_id):
    """
    AJAX view to get member details for borrowing.
    """
    member = get_object_or_404(LibraryMember, pk=member_id)

    current_borrows = BorrowRecord.objects.filter(
        member=member, status__in=["borrowed", "overdue"]
    ).count()

    data = {
        "full_name": member.user.get_full_name(),
        "member_type": member.get_member_type_display(),
        "membership_status": "Active" if member.is_membership_active else "Expired",
        "current_borrows": current_borrows,
        "can_borrow_more": member.can_borrow_more,
        "max_borrow_limit": member.max_borrow_limit,
    }

    return JsonResponse(data)


@login_required
def search_books_ajax(request):
    """
    AJAX view for book search with autocomplete.
    """
    query = request.GET.get("q", "")

    if query:
        books = (
            Book.objects.filter(
                Q(title__icontains=query)
                | Q(isbn__icontains=query)
                | Q(authors__first_name__icontains=query)
                | Q(authors__last_name__icontains=query)
            )
            .filter(status="active")
            .distinct()[:10]
        )

        results = []
        for book in books:
            results.append(
                {
                    "id": book.id,
                    "title": book.title,
                    "authors": book.author_names,
                    "isbn": book.isbn,
                    "available": book.is_available,
                }
            )
    else:
        results = []

    return JsonResponse({"results": results})


@login_required
def reserve_book_ajax(request, book_id):
    """
    AJAX view for reserving a book.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"})

    try:
        book = Book.objects.get(pk=book_id, status="active")
        member = request.user.library_member

        # Check if member can make reservation
        if not member.is_membership_active:
            return JsonResponse({"success": False, "error": "Membership is not active"})

        # Check if member already has an active reservation for this book
        existing_reservation = Reservation.objects.filter(
            member=member, book=book, status="pending"
        ).exists()

        if existing_reservation:
            return JsonResponse(
                {
                    "success": False,
                    "error": "You already have a pending reservation for this book",
                }
            )

        # Create reservation
        reservation = Reservation.objects.create(
            member=member,
            book=book,
            reserve_date=timezone.now().date(),
            expiry_date=timezone.now().date() + timezone.timedelta(days=7),
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Book reserved successfully",
                "reservation_id": str(reservation.id),
            }
        )

    except Book.DoesNotExist:
        return JsonResponse({"success": False, "error": "Book not found"})
    except AttributeError:
        return JsonResponse(
            {"success": False, "error": "You are not registered as a library member"}
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def borrow_book_ajax(request, book_copy_id):
    """
    AJAX view for borrowing a book copy.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"})

    try:
        book_copy = BookCopy.objects.get(pk=book_copy_id, status="active")
        member = request.user.library_member

        # Check if member can borrow
        if not member.is_membership_active:
            return JsonResponse({"success": False, "error": "Membership is not active"})

        if not member.can_borrow_more:
            return JsonResponse({"success": False, "error": "Borrow limit reached"})

        # Check if copy is available
        if not book_copy.is_available_for_borrow:
            return JsonResponse(
                {"success": False, "error": "Book copy is not available"}
            )

        # Create borrow record
        library = book_copy.book.library
        borrow_record = BorrowRecord.objects.create(
            member=member,
            book_copy=book_copy,
            borrow_date=timezone.now().date(),
            due_date=timezone.now().date()
            + timezone.timedelta(days=library.max_borrow_days),
            issued_by=request.user,
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Book borrowed successfully",
                "borrow_record_id": str(borrow_record.id),
                "due_date": borrow_record.due_date.strftime("%Y-%m-%d"),
            }
        )

    except BookCopy.DoesNotExist:
        return JsonResponse({"success": False, "error": "Book copy not found"})
    except AttributeError:
        return JsonResponse(
            {"success": False, "error": "You are not registered as a library member"}
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def return_book_ajax(request, borrow_record_id):
    """
    AJAX view for returning a borrowed book.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"})

    try:
        borrow_record = BorrowRecord.objects.get(pk=borrow_record_id)
        notes = request.POST.get("notes", "")

        # Check if user has permission to return this book
        if borrow_record.member.user != request.user and not request.user.has_perm(
            "library.change_borrowrecord"
        ):
            return JsonResponse({"success": False, "error": "Permission denied"})

        # Process return
        borrow_record.return_book(returned_by=request.user, notes=notes)

        return JsonResponse(
            {
                "success": True,
                "message": "Book returned successfully",
                "fine_amount": str(borrow_record.fine_amount),
            }
        )

    except BorrowRecord.DoesNotExist:
        return JsonResponse({"success": False, "error": "Borrow record not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def renew_book_ajax(request, borrow_record_id):
    """
    AJAX view for renewing a book borrowing.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"})

    try:
        borrow_record = BorrowRecord.objects.get(pk=borrow_record_id)

        # Check if user has permission to renew this book
        if borrow_record.member.user != request.user and not request.user.has_perm(
            "library.change_borrowrecord"
        ):
            return JsonResponse({"success": False, "error": "Permission denied"})

        # Attempt renewal
        if borrow_record.renew(request.user):
            return JsonResponse(
                {
                    "success": True,
                    "message": "Book renewed successfully",
                    "new_due_date": borrow_record.due_date.strftime("%Y-%m-%d"),
                }
            )
        else:
            return JsonResponse({"success": False, "error": "Book cannot be renewed"})

    except BorrowRecord.DoesNotExist:
        return JsonResponse({"success": False, "error": "Borrow record not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@login_required
def cancel_reservation_ajax(request, reservation_id):
    """
    AJAX view for canceling a reservation.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"})

    try:
        reservation = Reservation.objects.get(pk=reservation_id)

        # Check if user has permission to cancel this reservation
        if reservation.member.user != request.user and not request.user.has_perm(
            "library.change_reservation"
        ):
            return JsonResponse({"success": False, "error": "Permission denied"})

        # Cancel reservation
        reservation.status = Reservation.Status.CANCELLED
        reservation.save()

        return JsonResponse(
            {"success": True, "message": "Reservation cancelled successfully"}
        )

    except Reservation.DoesNotExist:
        return JsonResponse({"success": False, "error": "Reservation not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


# Export Views
@login_required
@permission_required("library.view_borrowrecord")
def export_borrow_records(request):
    """
    View to export borrow records to CSV.
    """
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="borrow_records.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Member ID",
            "Book Title",
            "Borrow Date",
            "Due Date",
            "Return Date",
            "Status",
            "Fine Amount",
        ]
    )

    borrow_records = BorrowRecord.objects.select_related(
        "member", "book_copy__book"
    ).all()

    for record in borrow_records:
        writer.writerow(
            [
                record.member.member_id,
                record.book_copy.book.title,
                record.borrow_date,
                record.due_date,
                record.return_date or "",
                record.get_status_display(),
                record.fine_amount,
            ]
        )

    return response


@login_required
@permission_required("library.view_book")
def export_books(request):
    """
    View to export books to CSV.
    """
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="books.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Title",
            "ISBN",
            "Authors",
            "Publisher",
            "Category",
            "Total Copies",
            "Available Copies",
        ]
    )

    books = Book.objects.filter(status="active").prefetch_related("authors")

    for book in books:
        writer.writerow(
            [
                book.title,
                book.isbn,
                book.author_names,
                book.publisher.name if book.publisher else "",
                book.category.name if book.category else "",
                book.total_copies,
                book.available_copies,
            ]
        )

    return response


@login_required
@permission_required("library.add_book")
def bulk_import_books(request):
    """
    View to handle bulk import of books from CSV/Excel.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"})

    import_file = request.FILES.get("file")
    library_id = request.POST.get("library")
    create_authors = request.POST.get("create_authors") == "true"
    create_publishers = request.POST.get("create_publishers") == "true"
    update_existing = request.POST.get("update_existing") == "true"

    if not import_file:
        return JsonResponse({"success": False, "error": "No file provided"})

    if not library_id:
        return JsonResponse({"success": False, "error": "No library selected"})

    try:
        library = Library.objects.get(pk=library_id, status="active")
    except Library.DoesNotExist:
        return JsonResponse({"success": False, "error": "Library not found"})

    # Process the file
    import pandas as pd
    import io

    try:
        if import_file.name.endswith(".csv"):
            df = pd.read_csv(io.StringIO(import_file.read().decode("utf-8")))
        elif import_file.name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(import_file)
        else:
            return JsonResponse({"success": False, "error": "Unsupported file format"})

        success_count = 0
        error_count = 0
        errors = []

        for index, row in df.iterrows():
            try:
                # Extract data from row
                title = row.get("Title", row.get("title", ""))
                isbn = row.get("ISBN", row.get("isbn", ""))
                authors_str = row.get("Authors", row.get("authors", ""))
                publisher_name = row.get("Publisher", row.get("publisher", ""))
                category_name = row.get("Category", row.get("category", ""))
                total_copies = int(row.get("Total Copies", row.get("total_copies", 1)))
                book_type = row.get("Book Type", row.get("book_type", "textbook"))

                if not title:
                    error_count += 1
                    errors.append(f"Row {index + 2}: Missing title")
                    continue

                # Handle existing book
                book = None
                if isbn and update_existing:
                    book = Book.objects.filter(isbn=isbn, library=library).first()

                if not book:
                    book = Book.objects.create(
                        title=title,
                        isbn=isbn if isbn else None,
                        book_type=book_type,
                        library=library,
                        total_copies=total_copies,
                        available_copies=total_copies,
                    )

                # Handle authors
                if authors_str:
                    author_names = [name.strip() for name in authors_str.split(",")]
                    for author_name in author_names:
                        if author_name:
                            first_name, last_name = (
                                author_name.split(" ", 1)
                                if " " in author_name
                                else (author_name, "")
                            )
                            author, created = Author.objects.get_or_create(
                                first_name=first_name,
                                last_name=last_name,
                                defaults={"status": "active"},
                            )
                            book.authors.add(author)

                # Handle publisher
                if publisher_name and create_publishers:
                    publisher, created = Publisher.objects.get_or_create(
                        name=publisher_name, defaults={"status": "active"}
                    )
                    book.publisher = publisher

                # Handle category
                if category_name:
                    category, created = BookCategory.objects.get_or_create(
                        name=category_name, defaults={"status": "active"}
                    )
                    book.category = category

                book.save()
                success_count += 1

            except Exception as e:
                error_count += 1
                errors.append(f"Row {index + 2}: {str(e)}")

        return JsonResponse(
            {
                "success": True,
                "message": f"Successfully imported {success_count} books",
                "success_count": success_count,
                "error_count": error_count,
                "errors": errors[:10],  # Limit errors shown
            }
        )

    except Exception as e:
        return JsonResponse(
            {"success": False, "error": f"File processing error: {str(e)}"}
        )


@login_required
def download_import_template(request, file_type):
    """
    View to download import template.
    """
    import csv
    from django.http import HttpResponse

    if file_type == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="book_import_template.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Title",
                "ISBN",
                "Authors",
                "Publisher",
                "Category",
                "Total Copies",
                "Book Type",
            ]
        )
        writer.writerow(
            [
                "Sample Book Title",
                "978-0-123456-78-9",
                "John Doe, Jane Smith",
                "Sample Publisher",
                "Fiction",
                "5",
                "textbook",
            ]
        )

    else:
        return JsonResponse({"success": False, "error": "Invalid file type"})

    return response


@login_required
@permission_required("library.view_reservation")
def export_reservations(request):
    """
    View to export reservations to CSV.
    """
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="reservations.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Member ID",
            "Member Name",
            "Book Title",
            "Reserve Date",
            "Expiry Date",
            "Priority",
            "Status",
        ]
    )

    reservations = Reservation.objects.select_related("member__user", "book")

    # Apply current filters
    status_filter = request.GET.get("status", "")
    search_filter = request.GET.get("search", "")

    if status_filter:
        reservations = reservations.filter(status=status_filter)

    if search_filter:
        reservations = reservations.filter(
            Q(member__user__first_name__icontains=search_filter)
            | Q(member__user__last_name__icontains=search_filter)
            | Q(book__title__icontains=search_filter)
        )

    for reservation in reservations:
        writer.writerow(
            [
                reservation.member.member_id,
                reservation.member.user.get_full_name(),
                reservation.book.title,
                reservation.reserve_date,
                reservation.expiry_date,
                (
                    "High"
                    if reservation.priority == 1
                    else "Medium" if reservation.priority == 2 else "Low"
                ),
                reservation.get_status_display(),
            ]
        )

    return response


@login_required
@permission_required("library.view_borrowrecord")
def export_overdue_books(request):
    """
    View to export overdue books to CSV.
    """
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="overdue_books.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Member ID",
            "Member Name",
            "Book Title",
            "Borrow Date",
            "Due Date",
            "Days Overdue",
            "Fine Amount",
        ]
    )

    overdue_records = BorrowRecord.objects.filter(status="overdue").select_related(
        "member__user", "book_copy__book"
    )

    for record in overdue_records:
        writer.writerow(
            [
                record.member.member_id,
                record.member.user.get_full_name(),
                record.book_copy.book.title,
                record.borrow_date,
                record.due_date,
                record.days_overdue,
                record.fine_amount,
            ]
        )

    return response


# Add these to your existing views.py file

# API Views (if using Django REST Framework)
try:
    from rest_framework import generics, permissions
    from .serializers import (
        BookSerializer,
        LibraryMemberSerializer,
        BorrowRecordSerializer,
        AuthorSerializer,
    )

    REST_FRAMEWORK_AVAILABLE = True
except ImportError:
    REST_FRAMEWORK_AVAILABLE = False


class BookListAPIView(generics.ListCreateAPIView):
    def get_queryset(self):
        from apps.core.middleware import get_user_accessible_institutions

        request = self.request
        if request.user.is_superuser:
            return Book.objects.filter(status="active")
        accessible_insts = get_user_accessible_institutions(request.user)
        return Book.objects.filter(status="active", institution__in=accessible_insts)

    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticated]


class BookDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    def get_queryset(self):
        from apps.core.middleware import get_user_accessible_institutions

        request = self.request
        if request.user.is_superuser:
            return Book.objects.all()
        accessible_insts = get_user_accessible_institutions(request.user)
        return Book.objects.filter(institution__in=accessible_insts)

    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticated]


class MemberListAPIView(generics.ListCreateAPIView):
    def get_queryset(self):
        from apps.core.middleware import get_user_accessible_institutions

        request = self.request
        if request.user.is_superuser:
            return LibraryMember.objects.filter(status="active")
        accessible_insts = get_user_accessible_institutions(request.user)
        return LibraryMember.objects.filter(
            status="active", institution__in=accessible_insts
        )

    serializer_class = LibraryMemberSerializer
    permission_classes = [permissions.IsAuthenticated]


class MemberDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    def get_queryset(self):
        from apps.core.middleware import get_user_accessible_institutions

        request = self.request
        if request.user.is_superuser:
            return LibraryMember.objects.all()
        accessible_insts = get_user_accessible_institutions(request.user)
        return LibraryMember.objects.filter(institution__in=accessible_insts)

    serializer_class = LibraryMemberSerializer
    permission_classes = [permissions.IsAuthenticated]


class BorrowRecordListAPIView(generics.ListCreateAPIView):
    def get_queryset(self):
        from apps.core.middleware import get_user_accessible_institutions

        request = self.request
        if request.user.is_superuser:
            return BorrowRecord.objects.all()
        accessible_insts = get_user_accessible_institutions(request.user)
        return BorrowRecord.objects.filter(institution__in=accessible_insts)

    serializer_class = BorrowRecordSerializer
    permission_classes = [permissions.IsAuthenticated]


class BorrowRecordDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    def get_queryset(self):
        from apps.core.middleware import get_user_accessible_institutions

        request = self.request
        if request.user.is_superuser:
            return BorrowRecord.objects.all()
        accessible_insts = get_user_accessible_institutions(request.user)
        return BorrowRecord.objects.filter(institution__in=accessible_insts)

    serializer_class = BorrowRecordSerializer
    permission_classes = [permissions.IsAuthenticated]


# Report Views
class OverdueBooksReportView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = BorrowRecord
    template_name = "library/reports/overdue_books.html"
    permission_required = "library.view_borrowrecord"

    def get_queryset(self):
        return BorrowRecord.objects.filter(status="overdue").select_related(
            "member__user", "book_copy__book"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_overdue"] = self.get_queryset().count()
        context["total_fines"] = (
            self.get_queryset().aggregate(total=Sum("fine_amount"))["total"] or 0
        )
        return context


class PopularBooksReportView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Book
    template_name = "library/reports/popular_books.html"
    permission_required = "library.view_book"

    def get_queryset(self):
        return (
            Book.objects.annotate(borrow_count=Count("copies__borrow_records"))
            .filter(borrow_count__gt=0)
            .order_by("-borrow_count")[:50]
        )


class MemberActivityReportView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LibraryMember
    template_name = "library/reports/member_activity.html"
    permission_required = "library.view_librarymember"

    def get_queryset(self):
        return (
            LibraryMember.objects.annotate(
                total_borrows=Count("borrow_records"),
                current_borrows=Count(
                    "borrow_records",
                    filter=Q(borrow_records__status__in=["borrowed", "overdue"]),
                ),
            )
            .filter(total_borrows__gt=0)
            .order_by("-total_borrows")
        )


class FineCollectionReportView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = FinePayment
    template_name = "library/reports/fine_collection.html"
    permission_required = "library.view_finepayment"

    def get_queryset(self):
        # Get fines by month
        return (
            FinePayment.objects.extra(
                select={"month": "EXTRACT(month FROM payment_date)"}
            )
            .values("month")
            .annotate(total_amount=Sum("amount_paid"), payment_count=Count("id"))
            .order_by("month")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_collected"] = (
            FinePayment.objects.aggregate(total=Sum("amount_paid"))["total"] or 0
        )
        return context


# Publisher and BookCategory List Views (missing from previous views)
class PublisherListView(LoginRequiredMixin, ListView):
    model = Publisher
    template_name = "library/publishers/publisher_list.html"
    context_object_name = "publishers"
    paginate_by = 20

    def get_queryset(self):
        queryset = Publisher.objects.filter(status="active").annotate(
            book_count=Count("books")
        )

        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query)
                | Q(contact_person__icontains=search_query)
                | Q(email__icontains=search_query)
            )

        return queryset.order_by("pk")


class PublisherDetailView(LoginRequiredMixin, DetailView):
    model = Publisher
    template_name = "library/publishers/publisher_detail.html"
    context_object_name = "publisher"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        publisher = self.get_object()
        context["books"] = Book.objects.filter(publisher=publisher, status="active")
        return context


class PublisherCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Publisher
    form_class = PublisherForm
    template_name = "library/publishers/publisher_form.html"
    permission_required = "library.add_publisher"
    success_url = reverse_lazy("library:publisher_list")

    def form_valid(self, form):
        messages.success(self.request, _("Publisher created successfully."))
        return super().form_valid(form)


class PublisherUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Publisher
    form_class = PublisherForm
    template_name = "library/publishers/publisher_form.html"
    permission_required = "library.change_publisher"
    success_url = reverse_lazy("library:publisher_list")

    def form_valid(self, form):
        messages.success(self.request, _("Publisher updated successfully."))
        return super().form_valid(form)


class BookCategoryListView(LoginRequiredMixin, ListView):
    model = BookCategory
    template_name = "library/bookcategories/bookcategory_list.html"
    context_object_name = "categories"
    paginate_by = 20

    def get_queryset(self):
        queryset = BookCategory.objects.filter(status="active").annotate(
            book_count=Count("books")
        )

        search_query = self.request.GET.get("search", "")
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | Q(code__icontains=search_query)
            )

        return queryset.order_by("pk")


class BookCategoryDetailView(LoginRequiredMixin, DetailView):
    model = BookCategory
    template_name = "library/bookcategories/bookcategory_detail.html"
    context_object_name = "category"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = self.get_object()
        context["books"] = Book.objects.filter(category=category, status="active")
        context["subcategories"] = BookCategory.objects.filter(
            parent=category, status="active"
        )
        return context


class BookCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = BookCategory
    form_class = BookCategoryForm
    template_name = "library/bookcategories/bookcategory_form.html"
    permission_required = "library.add_bookcategory"
    success_url = reverse_lazy("library:bookcategory_list")

    def form_valid(self, form):
        messages.success(self.request, _("Book category created successfully."))
        return super().form_valid(form)


class BookCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = BookCategory
    form_class = BookCategoryForm
    template_name = "library/bookcategories/bookcategory_form.html"
    permission_required = "library.change_bookcategory"
    success_url = reverse_lazy("library:bookcategory_list")

    def form_valid(self, form):
        messages.success(self.request, _("Book category updated successfully."))
        return super().form_valid(form)


# Custom error views
def handler404(request, exception):
    return render(request, "errors/404.html", status=404)


def handler500(request):
    return render(request, "errors/500.html", status=500)
