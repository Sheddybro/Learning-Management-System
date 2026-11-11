# apps/transport/urls.py
from django.urls import path
from . import views

app_name = 'transport'

# Dashboard & Analytics
dashboard_urls = [
    path('', views.TransportDashboardView.as_view(), name='dashboard'),
    path('analytics/', views.TransportAnalyticsView.as_view(), name='analytics'),
    path('reports/', views.TransportReportView.as_view(), name='reports'),
]

# Vehicle Management
vehicle_urls = [
    path('vehicles/', views.VehicleListView.as_view(), name='vehicle_list'),
    path('vehicles/create/', views.VehicleCreateView.as_view(), name='vehicle_create'),
    path('vehicles/<uuid:pk>/', views.VehicleDetailView.as_view(), name='vehicle_detail'),
    path('vehicles/<uuid:pk>/update/', views.VehicleUpdateView.as_view(), name='vehicle_update'),
    path('vehicles/<uuid:pk>/delete/', views.VehicleDeleteView.as_view(), name='vehicle_delete'),
    path('vehicles/maintenance-schedule/', views.VehicleMaintenanceScheduleView.as_view(), name='vehicle_maintenance_schedule'),
]

# Maintenance & Fuel
maintenance_urls = [
    path('maintenance/', views.MaintenanceRecordListView.as_view(), name='maintenancerecord_list'),
    path('maintenance/create/', views.MaintenanceRecordCreateView.as_view(), name='maintenancerecord_create'),
    path('maintenance/<uuid:pk>/update/', views.MaintenanceRecordUpdateView.as_view(), name='maintenancerecord_update'),
    path('maintenance/<uuid:pk>/delete/', views.MaintenanceRecordDeleteView.as_view(), name='maintenancerecord_delete'),
    
    path('fuel/', views.FuelRecordListView.as_view(), name='fuelrecord_list'),
    path('fuel/create/', views.FuelRecordCreateView.as_view(), name='fuelrecord_create'),
    path('fuel/<uuid:pk>/update/', views.FuelRecordUpdateView.as_view(), name='fuelrecord_update'),
    path('fuel/<uuid:pk>/delete/', views.FuelRecordDeleteView.as_view(), name='fuelrecord_delete'),
]

# Personnel Management
personnel_urls = [
    path('drivers/', views.DriverListView.as_view(), name='driver_list'),
    path('drivers/create/', views.DriverCreateView.as_view(), name='driver_create'),
    path('drivers/<uuid:pk>/', views.DriverDetailView.as_view(), name='driver_detail'),
    path('drivers/<uuid:pk>/update/', views.DriverUpdateView.as_view(), name='driver_update'),
    path('drivers/<uuid:pk>/delete/', views.DriverDeleteView.as_view(), name='driver_delete'),
    
    path('attendants/', views.AttendantListView.as_view(), name='attendant_list'),
    path('attendants/create/', views.AttendantCreateView.as_view(), name='attendant_create'),
    path('attendants/<uuid:pk>/', views.AttendantDetailView.as_view(), name='attendant_detail'),
    path('attendants/<uuid:pk>/update/', views.AttendantUpdateView.as_view(), name='attendant_update'),
    path('attendants/<uuid:pk>/delete/', views.AttendantDeleteView.as_view(), name='attendant_delete'),
]

# Route Management
route_urls = [
    path('routes/', views.RouteListView.as_view(), name='route_list'),
    path('routes/create/', views.RouteCreateView.as_view(), name='route_create'),
    path('routes/<uuid:pk>/', views.RouteDetailView.as_view(), name='route_detail'),
    path('routes/<uuid:pk>/update/', views.RouteUpdateView.as_view(), name='route_update'),
    path('routes/<uuid:pk>/delete/', views.RouteDeleteView.as_view(), name='route_delete'),
    path('routes/optimization/', views.RouteOptimizationView.as_view(), name='route_optimization'),
    
    path('routes/<uuid:route_id>/stops/create/', views.RouteStopCreateView.as_view(), name='routestop_create'),
    path('stops/<uuid:pk>/update/', views.RouteStopUpdateView.as_view(), name='routestop_update'),
    path('stops/<uuid:pk>/delete/', views.RouteStopDeleteView.as_view(), name='routestop_delete'),
]

# Operations
operation_urls = [
    path('schedules/', views.RouteScheduleListView.as_view(), name='routeschedule_list'),
    path('schedules/create/', views.RouteScheduleCreateView.as_view(), name='routeschedule_create'),
    path('schedules/<uuid:pk>/', views.RouteScheduleDetailView.as_view(), name='routeschedule_detail'),
    path('schedules/<uuid:pk>/update/', views.RouteScheduleUpdateView.as_view(), name='routeschedule_update'),
    path('schedules/<uuid:pk>/delete/', views.RouteScheduleDeleteView.as_view(), name='routeschedule_delete'),
    
    path('allocations/', views.TransportAllocationListView.as_view(), name='transportallocation_list'),
    path('allocations/create/', views.TransportAllocationCreateView.as_view(), name='transportallocation_create'),
    path('allocations/<uuid:pk>/', views.TransportAllocationDetailView.as_view(), name='transportallocation_detail'),
    path('allocations/<uuid:pk>/update/', views.TransportAllocationUpdateView.as_view(), name='transportallocation_update'),
    path('allocations/<uuid:pk>/delete/', views.TransportAllocationDeleteView.as_view(), name='transportallocation_delete'),
    
    path('incidents/', views.IncidentReportListView.as_view(), name='incidentreport_list'),
    path('incidents/create/', views.IncidentReportCreateView.as_view(), name='incidentreport_create'),
    path('incidents/<uuid:pk>/', views.IncidentReportDetailView.as_view(), name='incidentreport_detail'),
    path('incidents/<uuid:pk>/update/', views.IncidentReportUpdateView.as_view(), name='incidentreport_update'),
    path('incidents/<uuid:pk>/delete/', views.IncidentReportDeleteView.as_view(), name='incidentreport_delete'),
]

# API Endpoints
api_urls = [
    path('api/route-stops/<uuid:route_id>/', views.GetRouteStopsView.as_view(), name='api_route_stops'),
    path('api/vehicle-availability/<str:date>/', views.GetVehicleAvailabilityView.as_view(), name='api_vehicle_availability'),
    path('api/driver-schedule/<uuid:driver_id>/<str:date>/', views.GetDriverScheduleView.as_view(), name='api_driver_schedule'),
    path('api/send-parent-notification/', views.ParentNotificationView.as_view(), name='api_send_parent_notification'),
]

# Combine all URL patterns
urlpatterns = (
    dashboard_urls +
    vehicle_urls +
    maintenance_urls +
    personnel_urls +
    route_urls +
    operation_urls +
    api_urls
)
