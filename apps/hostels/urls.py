# apps/hostels/urls.py

from django.urls import path, include
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'hostels'

urlpatterns = [
    # Dashboard and Overview
    path('', views.hostel_dashboard, name='dashboard'),
    
    # Hostel Management URLs
    path('hostels/', views.HostelListView.as_view(), name='hostel_list'),
    path('hostels/create/', views.HostelCreateView.as_view(), name='hostel_create'),
    path('hostels/<uuid:pk>/', views.HostelDetailView.as_view(), name='hostel_detail'),
    path('hostels/<uuid:pk>/update/', views.HostelUpdateView.as_view(), name='hostel_update'),
    path('hostels/<uuid:pk>/delete/', views.HostelDeleteView.as_view(), name='hostel_delete'),
    
    # Room Management URLs
    path('rooms/', views.RoomListView.as_view(), name='room_list'),
    path('rooms/create/', views.RoomCreateView.as_view(), name='room_create'),
    path('rooms/<uuid:pk>/', views.RoomDetailView.as_view(), name='room_detail'),
    path('rooms/<uuid:pk>/update/', views.RoomUpdateView.as_view(), name='room_update'),
    
    # Bed Management URLs
    path('beds/', views.BedListView.as_view(), name='bed_list'),
    path('beds/create/', views.BedCreateView.as_view(), name='bed_create'),
    path('beds/<uuid:pk>/update/', views.BedUpdateView.as_view(), name='bed_update'),
    
    # Hostel Allocation URLs
    path('allocations/', views.HostelAllocationListView.as_view(), name='allocation_list'),
    path('allocations/<uuid:pk>/', views.HostelAllocationDetailView.as_view(), name='allocation_detail'),
    path('allocations/create/', views.HostelAllocationCreateView.as_view(), name='allocation_create'),
    path('allocations/<uuid:pk>/update/', views.HostelAllocationUpdateView.as_view(), name='allocation_update'),
    path('allocations/<uuid:pk>/transfer/', views.transfer_allocation, name='allocation_transfer'),
    path('allocations/<uuid:pk>/checkout/', views.check_out_student, name='allocation_checkout'),
    
    # Hostel Fee URLs
    path('fees/', views.HostelFeeListView.as_view(), name='fee_list'),
    path('fees/<uuid:pk>/', views.HostelFeeDetailView.as_view(), name='fee_detail'),
    path('fees/<uuid:pk>/pay/', views.mark_fee_paid, name='fee_mark_paid'),

    # Visitor Log URLs
    path('visitors/', views.VisitorLogListView.as_view(), name='visitor_list'),
    path('visitors/<uuid:pk>/', views.VisitorLogDetailView.as_view(), name='visitor_detail'),
    path('visitors/create/', views.VisitorLogCreateView.as_view(), name='visitor_create'),
    path('visitors/<uuid:pk>/checkout/', views.check_out_visitor, name='visitor_checkout'),

    # Maintenance Request URLs
    path('maintenance/', views.MaintenanceRequestListView.as_view(), name='maintenance_list'),
    path('maintenance/<uuid:pk>/', views.MaintenanceRequestDetailView.as_view(), name='maintenance_detail'),
    path('maintenance/create/', views.MaintenanceRequestCreateView.as_view(), name='maintenance_create'),
    path('maintenance/<uuid:pk>/update/', views.MaintenanceRequestUpdateView.as_view(), name='maintenance_update'),
    path('maintenance/<uuid:pk>/complete/', views.complete_maintenance, name='maintenance_complete'),

    # Inventory Management URLs
    path('inventory/', views.InventoryItemListView.as_view(), name='inventory_list'),
    path('inventory/<uuid:pk>/', views.InventoryItemDetailView.as_view(), name='inventory_detail'),
    path('inventory/create/', views.InventoryItemCreateView.as_view(), name='inventory_create'),
    path('inventory/<uuid:pk>/update/', views.InventoryItemUpdateView.as_view(), name='inventory_update'),
    
    # AJAX URLs for dynamic filtering
    path('ajax/rooms-by-hostel/', views.get_rooms_by_hostel, name='ajax_rooms_by_hostel'),
    path('ajax/beds-by-room/', views.get_beds_by_room, name='ajax_beds_by_room'),
    path('ajax/available-beds/', views.get_available_beds, name='ajax_available_beds'),
    
    # Report URLs
    path('reports/occupancy/', views.occupancy_report, name='occupancy_report'),
    path('reports/fee-collection/', views.fee_collection_report, name='fee_collection_report'),
    
    # API URLs for mobile app integration
    path('api/hostels/', views.api_hostel_list, name='api_hostel_list'),
    path('api/search-students/', views.api_search_students, name='api_search_students'),
    path('api/student-allocation/<uuid:student_id>/', views.api_student_allocation, name='api_student_allocation'),
]

# Additional URL patterns for different user roles
staff_urlpatterns = [
    path('staff/', include([
        path('dashboard/', views.hostel_dashboard, name='staff_dashboard'),
        path('allocations/', views.HostelAllocationListView.as_view(), name='staff_allocation_list'),
        path('visitors/', views.VisitorLogListView.as_view(), name='staff_visitor_list'),
        path('visitors/create/', views.VisitorLogCreateView.as_view(), name='staff_visitor_create'),
        path('maintenance/create/', views.MaintenanceRequestCreateView.as_view(), name='staff_maintenance_create'),
    ]))
]

student_urlpatterns = [
    path('student/', include([
        path('my-allocation/', views.api_student_allocation, name='student_my_allocation'),
        path('maintenance/create/', views.MaintenanceRequestCreateView.as_view(), name='student_maintenance_create'),
    ]))
]

# Include additional URL patterns
urlpatterns += staff_urlpatterns
urlpatterns += student_urlpatterns

# Export functionality URLs (placeholder for future implementation)
urlpatterns += [
    path('export/allocations/', views.HostelAllocationListView.as_view(), name='export_allocations'),
    path('export/fees/', views.HostelFeeListView.as_view(), name='export_fees'),
    path('export/visitors/', views.VisitorLogListView.as_view(), name='export_visitors'),
]
