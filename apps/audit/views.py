# apps/audit/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, TemplateView
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.db import connection,ProgrammingError
import sys

from .models import AuditLog
from apps.core.models import SystemConfig
from apps.core.middleware import filter_queryset_by_institution


class AuditLogListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for Audit Logs with filtering and search capabilities.
    """
    model = AuditLog
    template_name = 'audit/logs/auditlog_list.html'
    context_object_name = 'audit_logs'
    paginate_by = 50
    permission_required = 'audit.view_auditlog'
    
    def get_queryset(self):
        queryset = AuditLog.objects.select_related('user').all()

        # Apply institution-based filtering for security
        queryset = filter_queryset_by_institution(queryset, self.request.user)

        # Apply filters from GET parameters
        action = self.request.GET.get('action')
        model_name = self.request.GET.get('model_name')
        user_id = self.request.GET.get('user')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        search = self.request.GET.get('search')

        if action and action != 'all':
            queryset = queryset.filter(action=action)

        if model_name and model_name != 'all':
            queryset = queryset.filter(model_name=model_name)

        if user_id and user_id != 'all':
            queryset = queryset.filter(user_id=user_id)

        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)

        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(model_name__icontains=search) |
                Q(object_id__icontains=search) |
                Q(details__icontains=search)
            )

        return queryset.order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options to context
        context['action_types'] = AuditLog.ActionType.choices
        context['model_names'] = AuditLog.objects.values_list(
            'model_name', flat=True
        ).distinct().order_by('model_name')
        
        # Add current filter values for template
        context['current_filters'] = {
            'action': self.request.GET.get('action', ''),
            'model_name': self.request.GET.get('model_name', ''),
            'user': self.request.GET.get('user', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
            'search': self.request.GET.get('search', ''),
        }
        
        # Add stats
        unfiltered_queryset = AuditLog.objects.all()
        filtered_queryset = filter_queryset_by_institution(unfiltered_queryset, self.request.user)
        context['total_logs'] = filtered_queryset.count()
        context['today_logs'] = filtered_queryset.filter(
            timestamp__date=timezone.now().date()
        ).count()
        
        return context


class AuditLogDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detail view for individual Audit Log entries.
    """
    model = AuditLog
    template_name = 'audit/logs/auditlog_detail.html'
    context_object_name = 'audit_log'
    permission_required = 'audit.view_auditlog'
    
    def get_queryset(self):
        queryset = AuditLog.objects.select_related('user').all()
        return filter_queryset_by_institution(queryset, self.request.user)


class AuditLogDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Dashboard view for Audit Logs with statistics and charts.
    """
    template_name = 'audit/dashboard/auditlog_dashboard.html'
    permission_required = 'audit.view_auditlog'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filtered queryset for the current user
        filtered_queryset = filter_queryset_by_institution(AuditLog.objects.all(), self.request.user)

        # Apply institution filter if specified
        selected_institution_id = self.request.GET.get('institution', '')
        if selected_institution_id and selected_institution_id != 'all':
            try:
                from apps.core.models import Institution
                selected_institution = Institution.objects.get(
                    id=selected_institution_id,
                    is_active=True
                )
                filtered_queryset = filtered_queryset.filter(institution=selected_institution)
                context['selected_institution'] = selected_institution
            except Institution.DoesNotExist:
                pass  # Ignore invalid institution selection

        # Time period for statistics (last 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)

        # Basic statistics
        context['total_actions'] = filtered_queryset.filter(
            timestamp__gte=thirty_days_ago
        ).count()

        context['unique_users'] = filtered_queryset.filter(
            timestamp__gte=thirty_days_ago
        ).values('user').distinct().count()

        context['unique_models'] = filtered_queryset.filter(
            timestamp__gte=thirty_days_ago
        ).values('model_name').distinct().count()

        # Action type breakdown
        action_stats = filtered_queryset.filter(
            timestamp__gte=thirty_days_ago
        ).values('action').annotate(
            count=Count('id')
        ).order_by('-count')

        context['action_stats'] = list(action_stats)

        # Daily activity data (last 30 days)
        daily_data = filtered_queryset.filter(
            timestamp__gte=thirty_days_ago
        ).extra(
            {'date': "DATE(timestamp)"}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')

        context['daily_activity'] = list(daily_data)

        # Model activity distribution
        model_data = filtered_queryset.filter(
            timestamp__gte=thirty_days_ago
        ).values('model_name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        context['model_activity'] = list(model_data)

        # Recent activities (also filtered by selected institution if any)
        recent_queryset = filter_queryset_by_institution(AuditLog.objects.select_related('user').all(), self.request.user)
        if 'selected_institution' in context:
            recent_queryset = recent_queryset.filter(institution=context['selected_institution'])
        context['recent_activities'] = recent_queryset.order_by('-timestamp')[:10]

        # Most active users
        active_users = filtered_queryset.filter(
            timestamp__gte=thirty_days_ago,
            user__isnull=False
        ).values('user_id', 'user__email', 'user__first_name', 'user__last_name').annotate(
            activity_count=Count('id')
        ).order_by('-activity_count')[:10]

        context['active_users'] = list(active_users)

        # Add available institutions for filtering
        from apps.core.middleware import get_user_accessible_institutions
        context['available_institutions'] = get_user_accessible_institutions(self.request.user)

        return context


class AuditLogExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    View for exporting audit logs in various formats.
    """
    permission_required = 'audit.view_auditlog'
    
    def get(self, request, *args, **kwargs):
        format_type = request.GET.get('format', 'csv')
        queryset = self.get_export_queryset()
        
        if format_type == 'csv':
            return self.export_csv(queryset)
        elif format_type == 'json':
            return self.export_json(queryset)
        else:
            messages.error(request, _('Unsupported export format'))
            from django.shortcuts import redirect
            return redirect('audit:auditlog_list')
    
    def get_export_queryset(self):
        # Apply same filters as list view
        queryset = AuditLog.objects.select_related('user').all()
        queryset = filter_queryset_by_institution(queryset, self.request.user)

        action = self.request.GET.get('action')
        model_name = self.request.GET.get('model_name')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')

        if action and action != 'all':
            queryset = queryset.filter(action=action)

        if model_name and model_name != 'all':
            queryset = queryset.filter(model_name=model_name)

        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)

        return queryset.order_by('-timestamp')
    
    def export_csv(self, queryset):
        import csv
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'User', 'Action', 'Model', 'Object ID', 
            'IP Address', 'User Agent'
        ])
        
        for log in queryset:
            writer.writerow([
                log.timestamp,
                log.user.email if log.user else 'System',
                log.get_action_display(),
                log.model_name,
                log.object_id,
                log.ip_address or '',
                log.user_agent[:100] if log.user_agent else ''  # Truncate for CSV
            ])
        
        return response
    
    def export_json(self, queryset):
        import json
        
        data = []
        for log in queryset:
            data.append({
                'timestamp': log.timestamp.isoformat(),
                'user': log.user.email if log.user else None,
                'action': log.action,
                'action_display': log.get_action_display(),
                'model_name': log.model_name,
                'object_id': log.object_id,
                'details': log.details,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
            })
        
        response = JsonResponse(data, safe=False)
        response['Content-Disposition'] = 'attachment; filename="audit_logs.json"'
        return response


class AuditLogStatisticsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API view for audit log statistics (used for charts).
    """
    permission_required = 'audit.view_auditlog'

    def get(self, request, *args, **kwargs):
        period = request.GET.get('period', '7days')  # 7days, 30days, 90days

        if period == '7days':
            days = 7
        elif period == '30days':
            days = 30
        else:  # 90days
            days = 90

        start_date = timezone.now() - timezone.timedelta(days=days)

        # Get filtered queryset for current user
        filtered_queryset = filter_queryset_by_institution(AuditLog.objects.all(), request.user)

        # Daily activity data
        daily_data = filtered_queryset.filter(
            timestamp__gte=start_date
        ).extra(
            {'date': "DATE(timestamp)"}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')

        # Action type distribution
        action_data = filtered_queryset.filter(
            timestamp__gte=start_date
        ).values('action').annotate(
            count=Count('id')
        ).order_by('-count')

        # Model activity distribution
        model_data = filtered_queryset.filter(
            timestamp__gte=start_date
        ).values('model_name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]  # Top 10 models

        return JsonResponse({
            'daily_activity': list(daily_data),
            'action_distribution': list(action_data),
            'model_activity': list(model_data),
        })


# Utility functions for audit logging
class AuditLogMixin:
    """
    Mixin to add audit logging capabilities to other views.
    """
    
    def log_action(self, action, model_name, object_id, details=None, request=None):
        """
        Helper method to create audit log entries.
        """
        if request is None:
            request = getattr(self, 'request', None)
        
        if request and _can_create_audit_log():
            try:
                AuditLog.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    action=action,
                    model_name=model_name,
                    object_id=str(object_id),
                    details=details or {},
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            except Exception as e:
                # Log error but don't break the application
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to create audit log: {e}")
    
    def get_client_ip(self, request):
        """
        Get client IP address from request.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Signal handler utilities
def _is_migration_running():
    """
    Check if migrations are currently running
    """
    return 'migrate' in sys.argv or 'makemigrations' in sys.argv or 'showmigrations' in sys.argv

def _audit_log_table_exists():
    """
    Check if the audit_auditlog table exists
    """
    try:
        with connection.cursor() as cursor:
            table_names = connection.introspection.table_names()
            return 'audit_auditlog' in table_names
    except (ProgrammingError, Exception):
        return False

def _can_create_audit_log():
    """
    Check if it's safe to create audit logs
    """
    from apps.core.middleware import get_current_institution
    return not _is_migration_running() and _audit_log_table_exists() and get_current_institution() is not None


# Signal handlers for automatic audit logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    """
    Automatically log model save operations.
    """
    # Skip if we can't create audit logs
    if not _can_create_audit_log():
        return
    
    # Skip if it's the AuditLog model itself to avoid recursion
    if sender == AuditLog:
        return
    
    # Skip if it's a model we don't want to audit
    excluded_models = [
        'Session', 'LogEntry', 'ContentType', 'Migration', 
        'Permission', 'Group'
    ]
    
    if sender.__name__ in excluded_models:
        return
    
    # Skip if this is a raw save (during fixtures loading)
    if kwargs.get('raw', False):
        return
    
    action = 'create' if created else 'update'
    
    # Get request from thread local if available
    import threading
    
    request = None
    thread_local = threading.current_thread()
    if hasattr(thread_local, 'request'):
        request = thread_local.request
    
    try:
        # Create audit log entry
        AuditLog.objects.create(
            user=request.user if request and hasattr(request, 'user') and request.user.is_authenticated else None,
            action=action,
            model_name=sender.__name__,
            object_id=str(instance.pk),
            details={
                'fields_changed': getattr(instance, '_changed_fields', []),
                'new_values': _get_changed_field_values(instance) if not created else _get_all_field_values(instance)
            },
            ip_address=_get_client_ip(request) if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else ''
        )
    except Exception as e:
        # Log the error but don't break the application
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to create audit log for {sender.__name__}: {e}")

@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    """
    Automatically log model delete operations.
    """
    # Skip if we can't create audit logs
    if not _can_create_audit_log():
        return
    
    if sender == AuditLog:
        return
    
    excluded_models = [
        'Session', 'LogEntry', 'ContentType', 'Migration',
        'Permission', 'Group'
    ]
    
    if sender.__name__ in excluded_models:
        return
    
    # Skip if this is a raw delete
    if kwargs.get('raw', False):
        return
    
    import threading
    
    request = None
    thread_local = threading.current_thread()
    if hasattr(thread_local, 'request'):
        request = thread_local.request
    
    try:
        AuditLog.objects.create(
            user=request.user if request and hasattr(request, 'user') and request.user.is_authenticated else None,
            action='delete',
            model_name=sender.__name__,
            object_id=str(instance.pk),
            details={
                'deleted_data': _get_all_field_values(instance)
            },
            ip_address=_get_client_ip(request) if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else ''
        )
    except Exception as e:
        # Log the error but don't break the application
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to create audit log for {sender.__name__}: {e}")


# Helper functions for signal handlers
def _get_changed_field_values(instance):
    """
    Get values of changed fields for update operations.
    """
    changed_data = {}
    if hasattr(instance, '_changed_fields'):
        for field in instance._changed_fields:
            try:
                changed_data[field] = str(getattr(instance, field, ''))
            except (AttributeError, ValueError):
                changed_data[field] = '[Unable to serialize]'
    return changed_data

def _get_all_field_values(instance):
    """
    Get all field values for create/delete operations.
    """
    data = {}
    for field in instance._meta.fields:
        if field.name not in ['password', 'verification_token']:  # Exclude sensitive fields
            try:
                data[field.name] = str(getattr(instance, field.name, ''))
            except (AttributeError, ValueError):
                data[field.name] = '[Unable to serialize]'
    return data

def _get_client_ip(request):
    """
    Extract client IP from request.
    """
    if not request:
        return None
    
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# Middleware to make request available in signals
class AuditLogMiddleware:
    """
    Middleware to make request available in model signals for audit logging.
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Store request in thread local
        import threading
        thread_local = threading.current_thread()
        thread_local.request = request
        
        response = self.get_response(request)
        
        # Clean up
        if hasattr(thread_local, 'request'):
            del thread_local.request
        
        return response


# Optional: Function to temporarily disable audit logging
def disable_audit_logging():
    """
    Temporarily disable audit logging signals.
    Useful for bulk operations or data migrations.
    """
    post_save.disconnect(receiver=log_model_save)
    post_delete.disconnect(receiver=log_model_delete)

def enable_audit_logging():
    """
    Re-enable audit logging signals.
    """
    post_save.connect(receiver=log_model_save)
    post_delete.connect(receiver=log_model_delete)
