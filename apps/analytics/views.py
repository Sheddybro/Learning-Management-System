# apps/analytics/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Max, Min
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy

# REST Framework imports
try:
    from rest_framework import viewsets, permissions, status
    from rest_framework.decorators import action
    from rest_framework.response import Response
    from .serializers import (
        ReportSerializer, KPISerializer, DashboardSerializer
    )
    REST_FRAMEWORK_AVAILABLE = True
except ImportError:
    REST_FRAMEWORK_AVAILABLE = False

from .models import (
    ReportType, Report, Dashboard, KPI, KPIMeasurement, 
    DataExport, AnalyticsCache, TrendAnalysis
)
from .forms import (
    ReportSearchForm, KPISearchForm, DataExportRequestForm,
    AnalyticsSettingsForm, ReportGenerationForm
)
from apps.academics.models import AcademicSession


@login_required
def analytics_dashboard(request):
    """
    Main analytics dashboard view.
    """
    # Get user's default dashboard or create one
    user_dashboard, created = Dashboard.objects.get_or_create(
        owner=request.user,
        is_default=True,
        defaults={
            'name': f"{request.user.get_full_name()}'s Dashboard",
            'description': _('Your personal analytics dashboard'),
            'dashboard_type': 'user',
            'layout_config': {'widgets': []},
            'widget_config': {},
            'refresh_interval': 15
        }
    )
    
    # Get recent reports
    recent_reports = Report.objects.filter(
        Q(generated_by=request.user) | 
        Q(report_type__access_roles__contains=[request.user.role_type()])
    ).select_related('report_type', 'academic_session')[:5]
    
    # Get active KPIs - prioritize system performance KPIs for super admin
    if request.user.role_type() == 'super_admin':
        # Show system KPIs first, then other KPIs
        system_kpis = KPI.objects.filter(
            status='active',
            category='system',
            is_trending=True
        ).order_by('name')
        other_kpis = KPI.objects.filter(
            status='active',
            is_trending=True
        ).exclude(category='system')[:4]
        active_kpis = list(system_kpis) + list(other_kpis)
    else:
        active_kpis = KPI.objects.filter(status='active', is_trending=True)[:6]
    
    # Get recent measurements for trending KPIs
    kpi_measurements = {}
    for kpi in active_kpis:
        recent_measurement = KPIMeasurement.objects.filter(
            kpi=kpi
        ).select_related('academic_session').order_by('-measured_at').first()
        if recent_measurement:
            kpi_measurements[kpi.id] = recent_measurement
    
    context = {
        'dashboard': user_dashboard,
        'recent_reports': recent_reports,
        'active_kpis': active_kpis,
        'kpi_measurements': kpi_measurements,
        'page_title': _('Analytics Dashboard'),
    }
    
    return render(request, 'analytics/dashboard/dashboard.html', context)


@login_required
def report_list(request):
    """
    List and filter reports.
    """
    form = ReportSearchForm(request.GET or None)
    reports = Report.objects.select_related(
        'report_type', 'academic_session', 'generated_by'
    ).filter(
        Q(generated_by=request.user) | 
        Q(report_type__access_roles__contains=[request.user.role_type()])
    ).order_by('-created_at')
    
    if form.is_valid():
        name = form.cleaned_data.get('name')
        report_type = form.cleaned_data.get('report_type')
        category = form.cleaned_data.get('category')
        academic_session = form.cleaned_data.get('academic_session')
        status = form.cleaned_data.get('status')
        date_range = form.cleaned_data.get('date_range')
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
        
        if name:
            reports = reports.filter(name__icontains=name)
        if report_type:
            reports = reports.filter(report_type=report_type)
        if category:
            reports = reports.filter(report_type__category=category)
        if academic_session:
            reports = reports.filter(academic_session=academic_session)
        if status:
            reports = reports.filter(status=status)
        
        # Date range filtering
        if date_range:
            today = timezone.now().date()
            if date_range == 'today':
                reports = reports.filter(created_at__date=today)
            elif date_range == 'week':
                start_of_week = today - timezone.timedelta(days=today.weekday())
                reports = reports.filter(created_at__date__gte=start_of_week)
            elif date_range == 'month':
                reports = reports.filter(
                    created_at__year=today.year,
                    created_at__month=today.month
                )
            elif date_range == 'year':
                reports = reports.filter(created_at__year=today.year)
            elif date_range == 'custom' and start_date and end_date:
                reports = reports.filter(
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date
                )
    
    # Pagination
    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'form': form,
        'page_obj': page_obj,
        'total_reports': reports.count(),
        'page_title': _('Reports'),
    }
    
    return render(request, 'analytics/reports/list.html', context)


@login_required
def report_detail(request, report_id):
    """
    View report details and content.
    """
    report = get_object_or_404(
        Report.objects.select_related('report_type', 'academic_session', 'generated_by'),
        id=report_id
    )
    
    # Check access permissions
    if (report.generated_by != request.user and 
        request.user.role_type() not in report.report_type.access_roles):
        messages.error(request, _('You do not have permission to view this report.'))
        return redirect('analytics:report_list')
    
    # Mark as accessed
    report.mark_accessed()
    
    context = {
        'report': report,
        'page_title': f"{report.name}",
    }
    
    return render(request, 'analytics/reports/detail.html', context)


@login_required
def generate_report(request, report_type_id):
    """
    Generate a new report with parameters.
    """
    report_type = get_object_or_404(ReportType, id=report_type_id)
    
    # Check access permissions
    if request.user.role_type() not in report_type.access_roles:
        messages.error(request, _('You do not have permission to generate this report type.'))
        return redirect('analytics:report_list')
    
    if request.method == 'POST':
        form = ReportGenerationForm(request.POST, report_type=report_type)
        if form.is_valid():
            # Create report instance
            report = Report(
                report_type=report_type,
                name=f"{report_type.name} - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                academic_session=AcademicSession.get_current(),
                generated_by=request.user,
                parameters=form.cleaned_data,
                status='pending'
            )
            report.save()
            
            # Trigger report generation (this would typically be a background task)
            # For now, we'll simulate immediate generation
            report.generation_started_at = timezone.now()
            report.status = 'generating'
            report.save()
            
            # Simulate report generation
            import time
            time.sleep(2)  # Simulate processing time
            
            report.generation_completed_at = timezone.now()
            report.status = 'completed'
            report.summary = _("Report generated successfully with provided parameters.")
            report.save()
            
            messages.success(request, _('Report generated successfully!'))
            return redirect('analytics:report_detail', report_id=report.id)
    else:
        form = ReportGenerationForm(report_type=report_type)
    
    context = {
        'report_type': report_type,
        'form': form,
        'page_title': _('Generate Report'),
    }
    
    return render(request, 'analytics/reports/generate.html', context)


@login_required
def download_report(request, report_id):
    """
    Download report file.
    """
    report = get_object_or_404(Report, id=report_id)
    
    # Check access permissions
    if (report.generated_by != request.user and 
        request.user.role_type() not in report.report_type.access_roles):
        messages.error(request, _('You do not have permission to download this report.'))
        return redirect('analytics:report_list')
    
    if not report.file:
        messages.error(request, _('Report file is not available.'))
        return redirect('analytics:report_detail', report_id=report.id)
    
    # Mark as accessed
    report.mark_accessed()
    
    response = HttpResponse(report.file.read(), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{report.name}.{report.format}"'
    return response


@login_required
def kpi_list(request):
    """
    List and filter KPIs.
    """
    form = KPISearchForm(request.GET or None)
    kpis = KPI.objects.filter(status='active').order_by('category', 'name')
    
    if form.is_valid():
        name = form.cleaned_data.get('name')
        category = form.cleaned_data.get('category')
        value_type = form.cleaned_data.get('value_type')
        refresh_frequency = form.cleaned_data.get('refresh_frequency')
        
        if name:
            kpis = kpis.filter(name__icontains=name)
        if category:
            kpis = kpis.filter(category=category)
        if value_type:
            kpis = kpis.filter(value_type=value_type)
        if refresh_frequency:
            kpis = kpis.filter(refresh_frequency=refresh_frequency)
    
    # Get latest measurements for each KPI
    kpi_measurements = {}
    for kpi in kpis:
        latest_measurement = KPIMeasurement.objects.filter(
            kpi=kpi
        ).order_by('-measured_at').first()
        if latest_measurement:
            kpi_measurements[kpi.id] = latest_measurement
    
    context = {
        'form': form,
        'kpis': kpis,
        'kpi_measurements': kpi_measurements,
        'page_title': _('Key Performance Indicators'),
    }
    
    return render(request, 'analytics/kpis/list.html', context)


@login_required
def kpi_detail(request, kpi_id):
    """
    View KPI details and historical measurements.
    """
    kpi = get_object_or_404(KPI, id=kpi_id)
    
    # Get measurements with pagination
    measurements = KPIMeasurement.objects.filter(
        kpi=kpi
    ).select_related('academic_session').order_by('-measured_at')
    
    paginator = Paginator(measurements, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get measurement statistics
    if measurements.exists():
        stats = measurements.aggregate(
            avg_value=Avg('value'),
            max_value=Max('value'),
            min_value=Min('value'),
            total_measurements=Count('id')
        )
    else:
        stats = None
    
    context = {
        'kpi': kpi,
        'page_obj': page_obj,
        'stats': stats,
        'page_title': f"KPI: {kpi.name}",
    }
    
    return render(request, 'analytics/kpis/detail.html', context)


@login_required
def kpi_trend_data(request, kpi_id):
    """
    API endpoint for KPI trend data (JSON).
    """
    kpi = get_object_or_404(KPI, id=kpi_id)
    
    # Get recent measurements for trend chart
    measurements = KPIMeasurement.objects.filter(
        kpi=kpi
    ).order_by('measured_at')[:30]  # Last 30 measurements
    
    data = {
        'labels': [m.measured_at.strftime('%Y-%m-%d') for m in measurements],
        'values': [float(m.value) for m in measurements],
        'change_percentages': [float(m.change_percentage) if m.change_percentage else 0 for m in measurements],
    }
    
    return JsonResponse(data)


@login_required
def request_data_export(request):
    """
    Request a new data export.
    """
    if request.method == 'POST':
        form = DataExportRequestForm(request.POST)
        if form.is_valid():
            # Create export instance
            export = DataExport(
                requested_by=request.user,
                name=form.cleaned_data['export_name'],
                data_source=form.cleaned_data['data_source'],
                format=form.cleaned_data['export_format'],
                status='pending',
                filters={}  # This would be populated based on form data
            )
            export.save()
            
            # Trigger export processing (this would typically be a background task)
            export.started_at = timezone.now()
            export.status = 'processing'
            export.save()
            
            # Simulate export processing
            import time
            time.sleep(3)  # Simulate processing time
            
            export.completed_at = timezone.now()
            export.status = 'completed'
            export.record_count = 100  # Simulated record count
            export.file_size = 1024 * 50  # Simulated file size (50KB)
            export.save()
            
            messages.success(request, _('Data export completed successfully!'))
            return redirect('analytics:export_list')
    else:
        form = DataExportRequestForm()
    
    context = {
        'form': form,
        'page_title': _('Request Data Export'),
    }
    
    return render(request, 'analytics/exports/request.html', context)


@login_required
def export_list(request):
    """
    List user's data exports.
    """
    exports = DataExport.objects.filter(
        requested_by=request.user
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(exports, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_exports': exports.count(),
        'page_title': _('Data Exports'),
    }
    
    return render(request, 'analytics/exports/list.html', context)


@login_required
def download_export(request, export_id):
    """
    Download exported data file.
    """
    export = get_object_or_404(DataExport, id=export_id, requested_by=request.user)
    
    if not export.file:
        messages.error(request, _('Export file is not available.'))
        return redirect('analytics:export_list')
    
    if export.status != 'completed':
        messages.error(request, _('Export is not ready for download.'))
        return redirect('analytics:export_list')
    
    response = HttpResponse(export.file.read(), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{export.name}.{export.format}"'
    return response


@login_required
def trend_analysis_list(request):
    """
    List trend analyses.
    """
    analyses = TrendAnalysis.objects.filter(
        Q(generated_by=request.user) | 
        Q(status='active')
    ).select_related('generated_by').order_by('-generated_at')
    
    # Pagination
    paginator = Paginator(analyses, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'page_title': _('Trend Analyses'),
    }
    
    return render(request, 'analytics/reports/trends/list.html', context)


@login_required
def trend_analysis_detail(request, analysis_id):
    """
    View trend analysis details.
    """
    analysis = get_object_or_404(
        TrendAnalysis.objects.select_related('generated_by'),
        id=analysis_id
    )
    
    context = {
        'analysis': analysis,
        'page_title': f"Analysis: {analysis.name}",
    }
    
    return render(request, 'analytics/reports/trends/detail.html', context)


@login_required
def analytics_settings(request):
    """
    Analytics settings and configuration.
    """
    if request.method == 'POST':
        form = AnalyticsSettingsForm(request.POST)
        if form.is_valid():
            # Save settings to SystemConfig or user preferences
            # This is a simplified implementation
            messages.success(request, _('Analytics settings updated successfully!'))
            return redirect('analytics:dashboard')
    else:
        form = AnalyticsSettingsForm()
    
    context = {
        'form': form,
        'page_title': _('Analytics Settings'),
    }
    
    return render(request, 'analytics/config/settings.html', context)


@login_required
def api_kpi_measurements(request, kpi_code):
    """
    API endpoint for KPI measurements data.
    """
    try:
        kpi = KPI.objects.get(code=kpi_code, status='active')
    except KPI.DoesNotExist:
        return JsonResponse({'error': 'KPI not found'}, status=404)
    
    # Get date range from query parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    limit = int(request.GET.get('limit', 50))
    
    measurements = KPIMeasurement.objects.filter(kpi=kpi)
    
    if start_date:
        measurements = measurements.filter(measured_at__date__gte=start_date)
    if end_date:
        measurements = measurements.filter(measured_at__date__lte=end_date)
    
    measurements = measurements.order_by('-measured_at')[:limit]
    
    data = {
        'kpi': {
            'name': kpi.name,
            'code': kpi.code,
            'value_type': kpi.value_type,
            'target_value': float(kpi.target_value) if kpi.target_value else None,
        },
        'measurements': [
            {
                'measured_at': m.measured_at.isoformat(),
                'value': float(m.value),
                'change_percentage': float(m.change_percentage) if m.change_percentage else None,
                'academic_session': m.academic_session.name if m.academic_session else None,
            }
            for m in measurements
        ]
    }
    
    return JsonResponse(data)


@login_required
def api_report_types(request):
    """
    API endpoint for available report types.
    """
    report_types = ReportType.objects.filter(
        status='active',
        access_roles__contains=[request.user.role_type()]
    ).values('id', 'name', 'code', 'category', 'description')
    
    return JsonResponse({'report_types': list(report_types)})


@login_required
def clear_analytics_cache(request):
    """
    Clear user's analytics cache.
    """
    if request.method == 'POST':
        # Clear expired cache entries
        expired_entries = AnalyticsCache.objects.filter(expires_at__lt=timezone.now())
        count = expired_entries.count()
        expired_entries.delete()

        messages.success(request, _(f'Cleared {count} expired cache entries.'))
        return redirect('analytics:dashboard')

    return redirect('analytics:dashboard')


@login_required
def collect_system_metrics(request):
    """
    AJAX endpoint to trigger system metrics collection.
    """
    from django.http import JsonResponse
    from django.core.management import call_command
    from io import StringIO

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'})

    # Check if user has permission (super admin only)
    if request.user.role_type() != 'super_admin':
        return JsonResponse({'success': False, 'error': 'Permission denied'})

    try:
        # Run the collect_system_metrics management command
        stdout = StringIO()
        call_command('collect_system_metrics', stdout=stdout, verbosity=1)

        # Parse the output to get the count
        output = stdout.getvalue()
        if 'System metrics collection complete' in output:
            return JsonResponse({
                'success': True,
                'message': 'System metrics collected successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to collect metrics'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# Class-Based Views for CRUD operations

class DashboardCreateView(CreateView):
    """
    Create a new dashboard.
    """
    model = Dashboard
    template_name = 'analytics/dashboards/form.html'
    fields = ['name', 'description', 'layout_config', 'widget_config', 'refresh_interval']
    
    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.dashboard_type = 'user'
        messages.success(self.request, _('Dashboard created successfully!'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('analytics:dashboard')


class DashboardUpdateView(UpdateView):
    """
    Update an existing dashboard.
    """
    model = Dashboard
    template_name = 'analytics/dashboards/form.html'
    fields = ['name', 'description', 'layout_config', 'widget_config', 'refresh_interval']
    
    def get_queryset(self):
        return Dashboard.objects.filter(owner=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, _('Dashboard updated successfully!'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('analytics:dashboard')


class DashboardDeleteView(DeleteView):
    """
    Delete a dashboard.
    """
    model = Dashboard
    template_name = 'analytics/dashboards/confirm_delete.html'
    
    def get_queryset(self):
        return Dashboard.objects.filter(owner=self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, _('Dashboard deleted successfully!'))
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('analytics:dashboard')


def analytics_overview_api(request):
    """
    API endpoint for analytics overview data.
    """
    # This would typically return aggregated data for dashboard widgets
    data = {
        'total_reports': Report.objects.filter(status='completed').count(),
        'active_kpis': KPI.objects.filter(status='active').count(),
        'pending_exports': DataExport.objects.filter(status='pending').count(),
        'cache_entries': AnalyticsCache.objects.count(),
        'recent_analyses': TrendAnalysis.objects.count(),
    }

    return JsonResponse(data)


# REST API ViewSets
if REST_FRAMEWORK_AVAILABLE:
    class ReportViewSet(viewsets.ModelViewSet):
        """
        ViewSet for Report model.
        """
        queryset = Report.objects.all()
        serializer_class = ReportSerializer
        permission_classes = [permissions.IsAuthenticated]

        def get_queryset(self):
            queryset = Report.objects.select_related('report_type', 'academic_session', 'generated_by')
            user = self.request.user

            # Filter based on user permissions
            if not user.is_superuser:
                queryset = queryset.filter(
                    Q(generated_by=user) |
                    Q(report_type__access_roles__contains=[user.role_type()])
                )

            return queryset

        @action(detail=True, methods=['post'])
        def regenerate(self, request, pk=None):
            """Regenerate a report."""
            report = self.get_object()
            # Trigger regeneration logic here
            return Response({'status': 'Report regeneration triggered'})

    class KPIViewSet(viewsets.ModelViewSet):
        """
        ViewSet for KPI model.
        """
        queryset = KPI.objects.filter(status='active')
        serializer_class = KPISerializer
        permission_classes = [permissions.IsAuthenticated]

        @action(detail=True, methods=['get'])
        def measurements(self, request, pk=None):
            """Get KPI measurements."""
            kpi = self.get_object()
            measurements = KPIMeasurement.objects.filter(kpi=kpi).order_by('-measured_at')[:50]

            data = {
                'kpi': KPISerializer(kpi).data,
                'measurements': [
                    {
                        'measured_at': m.measured_at.isoformat(),
                        'value': float(m.value),
                        'change_percentage': float(m.change_percentage) if m.change_percentage else None,
                    }
                    for m in measurements
                ]
            }

            return Response(data)

        @action(detail=True, methods=['post'])
        def measure(self, request, pk=None):
            """Trigger KPI measurement."""
            kpi = self.get_object()
            # Trigger measurement logic here
            return Response({'status': 'KPI measurement triggered'})

    class DashboardViewSet(viewsets.ModelViewSet):
        """
        ViewSet for Dashboard model.
        """
        queryset = Dashboard.objects.all()
        serializer_class = DashboardSerializer
        permission_classes = [permissions.IsAuthenticated]

        def get_queryset(self):
            user = self.request.user
            if user.is_superuser:
                return Dashboard.objects.all()
            else:
                return Dashboard.objects.filter(
                    Q(owner=user) |
                    Q(is_public=True)
                )

        def perform_create(self, serializer):
            serializer.save(owner=self.request.user)

        @action(detail=True, methods=['post'])
        def clone(self, request, pk=None):
            """Clone a dashboard."""
            dashboard = self.get_object()
            cloned_dashboard = Dashboard.objects.create(
                name=f"{dashboard.name} (Copy)",
                description=dashboard.description,
                owner=request.user,
                dashboard_type='user',
                layout_config=dashboard.layout_config,
                widget_config=dashboard.widget_config,
                refresh_interval=dashboard.refresh_interval,
                is_default=False
            )

            serializer = self.get_serializer(cloned_dashboard)
            return Response(serializer.data)
