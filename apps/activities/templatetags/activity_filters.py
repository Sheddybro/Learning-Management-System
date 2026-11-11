from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def active_count(activities):
    """
    Count the number of active activities in a queryset.
    """
    if hasattr(activities, 'filter'):
        return activities.filter(status='active').count()
    return 0


@register.filter
def enrolled_count(activities):
    """
    Sum the enrolled participants across all activities in a queryset.
    """
    if hasattr(activities, 'all'):
        return sum(activity.enrolled_count for activity in activities.all())
    return 0


@register.filter
def completed_count(items):
    if hasattr(items, 'filter'):
        return items.filter(status='completed').count()
    return sum(1 for item in (items or []) if getattr(item, 'status', None) == 'completed')


@register.filter
def pending_count(items):
    if hasattr(items, 'filter'):
        return items.filter(status='pending').count()
    return sum(1 for item in (items or []) if getattr(item, 'status', None) == 'pending')


@register.filter
def upcoming_count(items):
    today = timezone.localdate()
    if hasattr(items, 'filter'):
        return items.filter(start_date__gte=today).count()
    return sum(1 for item in (items or []) if getattr(item, 'start_date', today) >= today)


@register.filter
def average_attendance(enrollments):
    values = [item.attendance_percentage for item in (enrollments or [])]
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else 0


@register.filter
def recent_count(reports):
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=30)
    if hasattr(reports, 'filter'):
        return reports.filter(created_at__gte=cutoff).count()
    return sum(1 for item in (reports or []) if getattr(item, 'created_at', cutoff) >= cutoff)
