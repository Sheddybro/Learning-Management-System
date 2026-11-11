# apps/library/urls.py

from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

app_name = 'library'

urlpatterns = [
    # Dashboard and Home
    path('', views.library_dashboard, name='dashboard'),
    path('member-dashboard/', views.member_dashboard, name='member_dashboard'),
    
    # Library URLs
    path('libraries/', views.LibraryListView.as_view(), name='library_list'),
    path('libraries/<uuid:pk>/', views.LibraryDetailView.as_view(), name='library_detail'),
    path('libraries/create/', views.LibraryCreateView.as_view(), name='library_create'),
    path('libraries/<uuid:pk>/update/', views.LibraryUpdateView.as_view(), name='library_update'),
    
    # Author URLs
    path('authors/', views.AuthorListView.as_view(), name='author_list'),
    path('authors/<uuid:pk>/', views.AuthorDetailView.as_view(), name='author_detail'),
    path('authors/create/', views.AuthorCreateView.as_view(), name='author_create'),
    path('authors/<uuid:pk>/update/', views.AuthorUpdateView.as_view(), name='author_update'),
    
    # Publisher URLs
    path('publishers/', views.PublisherListView.as_view(), name='publisher_list'),
    path('publishers/<uuid:pk>/', views.PublisherDetailView.as_view(), name='publisher_detail'),
    path('publishers/create/', views.PublisherCreateView.as_view(), name='publisher_create'),
    path('publishers/<uuid:pk>/update/', views.PublisherUpdateView.as_view(), name='publisher_update'),
    
    # BookCategory URLs
    path('categories/', views.BookCategoryListView.as_view(), name='bookcategory_list'),
    path('categories/<uuid:pk>/', views.BookCategoryDetailView.as_view(), name='bookcategory_detail'),
    path('categories/create/', views.BookCategoryCreateView.as_view(), name='bookcategory_create'),
    path('categories/<uuid:pk>/update/', views.BookCategoryUpdateView.as_view(), name='bookcategory_update'),
    
    # Book URLs
    path('books/', views.BookListView.as_view(), name='book_list'),
    path('books/<uuid:pk>/', views.BookDetailView.as_view(), name='book_detail'),
    path('books/create/', views.BookCreateView.as_view(), name='book_create'),
    path('books/<uuid:pk>/update/', views.BookUpdateView.as_view(), name='book_update'),
    
    # BookCopy URLs
    path('copies/', views.BookCopyListView.as_view(), name='bookcopy_list'),
    path('copies/create/', views.BookCopyCreateView.as_view(), name='bookcopy_create'),
    path('copies/<uuid:pk>/update/', views.BookCopyUpdateView.as_view(), name='bookcopy_update'),
    
    # LibraryMember URLs
    path('members/', views.LibraryMemberListView.as_view(), name='librarymember_list'),
    path('members/<uuid:pk>/', views.LibraryMemberDetailView.as_view(), name='librarymember_detail'),
    path('members/create/', views.LibraryMemberCreateView.as_view(), name='librarymember_create'),
    path('members/<uuid:pk>/update/', views.LibraryMemberUpdateView.as_view(), name='librarymember_update'),
    
    # BorrowRecord URLs
    path('borrows/', views.BorrowRecordListView.as_view(), name='borrowrecord_list'),
    path('borrows/create/', views.BorrowRecordCreateView.as_view(), name='borrowrecord_create'),
    path('borrows/<uuid:pk>/update/', views.BorrowRecordUpdateView.as_view(), name='borrowrecord_update'),
    path('borrows/<uuid:pk>/return/', views.return_book, name='return_book'),
    path('borrows/<uuid:pk>/renew/', views.renew_book, name='renew_book'),
    
    # Reservation URLs
    path('reservations/', views.ReservationListView.as_view(), name='reservation_list'),
    path('reservations/create/', views.ReservationCreateView.as_view(), name='reservation_create'),
    path('reservations/<uuid:pk>/fulfill/', views.fulfill_reservation, name='fulfill_reservation'),
    
    # FinePayment URLs
    path('fines/', views.FinePaymentListView.as_view(), name='finepayment_list'),
    path('fines/create/', views.FinePaymentCreateView.as_view(), name='finepayment_create'),
    
    # AJAX/API URLs
    path('ajax/book/<uuid:book_id>/', views.get_book_details, name='ajax_book_details'),
    path('ajax/member/<uuid:member_id>/', views.get_member_details, name='ajax_member_details'),
    path('ajax/search-books/', views.search_books_ajax, name='ajax_search_books'),
    path('ajax/reserve-book/<uuid:book_id>/', views.reserve_book_ajax, name='ajax_reserve_book'),
    path('ajax/borrow-book/<uuid:book_copy_id>/', views.borrow_book_ajax, name='ajax_borrow_book'),
    path('ajax/return-book/<uuid:borrow_record_id>/', views.return_book_ajax, name='ajax_return_book'),
    path('ajax/renew-book/<uuid:borrow_record_id>/', views.renew_book_ajax, name='ajax_renew_book'),
    path('ajax/cancel-reservation/<uuid:reservation_id>/', views.cancel_reservation_ajax, name='ajax_cancel_reservation'),
    
    # Export URLs
    path('export/borrow-records/', views.export_borrow_records, name='export_borrow_records'),
    path('export/books/', views.export_books, name='export_books'),
    path('export/reservations/', views.export_reservations, name='export_reservations'),
    path('export/overdue-books/', views.export_overdue_books, name='export_overdue_books'),

    # Bulk Import URLs
    path('bulk-import/', views.bulk_import_books, name='bulk_import_books'),
    path('download-template/<str:file_type>/', views.download_import_template, name='download_import_template'),
    
    # Reports URLs
    path('reports/overdue-books/', views.OverdueBooksReportView.as_view(), name='report_overdue_books'),
    path('reports/popular-books/', views.PopularBooksReportView.as_view(), name='report_popular_books'),
    path('reports/member-activity/', views.MemberActivityReportView.as_view(), name='report_member_activity'),
    path('reports/fine-collection/', views.FineCollectionReportView.as_view(), name='report_fine_collection'),
    
    # Authentication URLs (for library-specific login if needed)
    path('login/', auth_views.LoginView.as_view(template_name='library/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='library:login'), name='logout'),
]

# Additional URL patterns for REST API (if using Django REST Framework)
api_urlpatterns = [
    path('api/books/', views.BookListAPIView.as_view(), name='api_book_list'),
    path('api/books/<uuid:pk>/', views.BookDetailAPIView.as_view(), name='api_book_detail'),
    path('api/members/', views.MemberListAPIView.as_view(), name='api_member_list'),
    path('api/members/<uuid:pk>/', views.MemberDetailAPIView.as_view(), name='api_member_detail'),
    path('api/borrows/', views.BorrowRecordListAPIView.as_view(), name='api_borrow_list'),
    path('api/borrows/<uuid:pk>/', views.BorrowRecordDetailAPIView.as_view(), name='api_borrow_detail'),
]

# Include API URLs if needed
urlpatterns += [
    path('api/', include(api_urlpatterns)),
]

# Error handlers
handler404 = views.handler404
handler500 = views.handler500
