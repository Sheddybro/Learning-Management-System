from django import template
from django.db.models import Q
from django.utils import timezone
from ..models import Announcement

register = template.Library()


@register.simple_tag(takes_context=True)
def get_recent_announcements(context, user, request, limit=5):
    """
    Template tag to get recent announcements for the dashboard.

    Args:
        context: Template context
        user: User object
        request: HttpRequest object
        limit: Number of announcements to return (default: 5)

    Returns:
        QuerySet of Announcement objects
    """
    if not user or not user.is_authenticated:
        return Announcement.objects.none()

    # Base queryset for active announcements
    announcements = Announcement.objects.filter(
        is_published=True, status="active", expires_at__isnull=True
    ) | Announcement.objects.filter(
        is_published=True, status="active", expires_at__gt=timezone.now()
    )

    # Filter by audience permissions
    if (
        hasattr(user, "student_profile")
        or user.has_perm("academics.view_enrollment")
        or user.user_roles.filter(role__role_type="student").exists()
    ):
        # Students see general, student-specific, and class-specific announcements
        student_profile = getattr(user, "student_profile", None)
        class_ids = []
        if student_profile:
            class_ids = list(
                student_profile.enrollments.values_list("class_enrolled", flat=True)
            )

        announcements = announcements.filter(
            Q(target_audience="all")
            | Q(target_audience="students")
            | Q(specific_users=user)
            | Q(specific_classes__in=class_ids)
        ).distinct()

    elif (
        user.has_perm("academics.view_class")
        or user.user_roles.filter(role__role_type="teacher").exists()
    ):
        # Teachers see teacher-specific and general announcements
        announcements = announcements.filter(
            Q(target_audience="all")
            | Q(target_audience="teachers")
            | Q(specific_users=user)
        ).distinct()

    elif (
        user.has_perm("academics.view_student")
        or user.user_roles.filter(role__role_type="parent").exists()
    ):
        # Parents see parent-specific and general announcements
        announcements = announcements.filter(
            Q(target_audience="all")
            | Q(target_audience="parents")
            | Q(specific_users=user)
        ).distinct()

    elif (
        user.is_staff
        or user.user_roles.filter(
            role__role_type__in=["admin", "principal", "school_admin", "super_admin"]
        ).exists()
    ):
        # Staff/admin see all announcements
        announcements = announcements.filter(
            Q(target_audience="all") | Q(specific_users=user)
        ).distinct()

    else:
        # Default to general announcements only
        announcements = announcements.filter(
            Q(target_audience="all") | Q(specific_users=user)
        ).distinct()

    # Order by pinned status, urgent priority, then by creation date
    announcements = announcements.order_by(
        "-is_pinned", "-priority", "-created_at"
    ).select_related("author")[:limit]

    return announcements


@register.simple_tag(takes_context=True)
def get_upcoming_events(context, user, request, limit=5):
    """
    Template tag to get upcoming events for the dashboard.

    Args:
        context: Template context
        user: User object
        request: HttpRequest object
        limit: Number of events to return (default: 5)

    Returns:
        QuerySet of Announcement objects with announcement_type='event'
    """
    if not user or not user.is_authenticated:
        return Announcement.objects.none()

    # Base queryset for upcoming events (announcement_type='event')
    now = timezone.now()
    events = Announcement.objects.filter(
        announcement_type="event",
        is_published=True,
        status="active",
        # Must have a scheduled date (event date)
        schedule_publish__isnull=False,
        # Event date is today or in the future
        schedule_publish__gte=now.date(),
    ).filter(
        # Either no expiration or expiration is in future
        Q(expires_at__isnull=True)
        | Q(expires_at__gt=now)
    )

    # Filter by audience permissions (same logic as announcements)
    if (
        hasattr(user, "student_profile")
        or user.has_perm("academics.view_enrollment")
        or user.user_roles.filter(role__role_type="student").exists()
    ):
        # Students see general, student-specific, and class-specific events
        student_profile = getattr(user, "student_profile", None)
        class_ids = []
        if student_profile:
            class_ids = list(
                student_profile.enrollments.values_list("class_enrolled", flat=True)
            )

        events = events.filter(
            Q(target_audience="all")
            | Q(target_audience="students")
            | Q(specific_users=user)
            | Q(specific_classes__in=class_ids)
        ).distinct()

    elif (
        user.has_perm("academics.view_class")
        or user.user_roles.filter(role__role_type="teacher").exists()
    ):
        # Teachers see teacher-specific and general events
        events = events.filter(
            Q(target_audience="all")
            | Q(target_audience="teachers")
            | Q(specific_users=user)
        ).distinct()

    elif (
        user.has_perm("academics.view_student")
        or user.user_roles.filter(role__role_type="parent").exists()
    ):
        # Parents see parent-specific and general events
        events = events.filter(
            Q(target_audience="all")
            | Q(target_audience="parents")
            | Q(specific_users=user)
        ).distinct()

    elif (
        user.is_staff
        or user.user_roles.filter(
            role__role_type__in=["admin", "principal", "school_admin", "super_admin"]
        ).exists()
    ):
        # Staff/admin see all events
        events = events.filter(
            Q(target_audience="all") | Q(specific_users=user)
        ).distinct()

    else:
        # Default to general events only
        events = events.filter(
            Q(target_audience="all") | Q(specific_users=user)
        ).distinct()

    # Order by event date (schedule_publish), then by pinned status and priority
    events = events.order_by(
        "schedule_publish", "-is_pinned", "-priority"
    ).select_related("author")[:limit]

    return events
