from django import template

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
