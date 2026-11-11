from django.db import models
from .models import RealTimeNotification, NoticeBoard, NoticeBoardItem, Announcement


def notification_count(request):
    """
    Context processor to add notification count to all templates.
    """
    if request.user.is_authenticated:
        unread_count = RealTimeNotification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        return {'unread_notification_count': unread_count}
    return {'unread_notification_count': 0}


def noticeboard_data(request):
    """
    Context processor to add noticeboard data to all templates.
    Makes noticeboards very visible to all authenticated users.
    """
    if not request.user.is_authenticated:
        return {}
    
    # Get active noticeboards that user can access
    noticeboards = NoticeBoard.objects.filter(is_active=True)
    
    # Filter based on user permissions/access
    accessible_boards = []
    urgent_announcements = []
    recent_announcements = []
    
    for board in noticeboards:
        # Check if user has specific access to this board
        if board.allowed_users.filter(id=request.user.id).exists():
            accessible_boards.append(board)
        elif not board.allowed_users.exists():
            # Public boards (no specific user restrictions)
            accessible_boards.append(board)
    
    # Get recent announcements from accessible noticeboards
    if accessible_boards:
        board_ids = [board.id for board in accessible_boards]
        
        # Recent announcements (last 7 days)
        from django.utils import timezone
        week_ago = timezone.now() - timezone.timedelta(days=7)
        recent_announcements = Announcement.objects.filter(
            noticeboarditem__notice_board_id__in=board_ids,
            noticeboarditem__is_active=True,
            noticeboarditem__notice_board__is_active=True,
            is_published=True,
            created_at__gte=week_ago
        ).select_related('author').distinct()[:6]  # Last 6 announcements
        
        # Urgent announcements
        urgent_announcements = Announcement.objects.filter(
            noticeboarditem__notice_board_id__in=board_ids,
            noticeboarditem__is_active=True,
            noticeboarditem__notice_board__is_active=True,
            is_published=True,
            priority__in=['urgent', 'high']
        ).select_related('author').distinct()[:3]  # Top 3 urgent
    
    return {
        'accessible_noticeboards': accessible_boards,
        'noticeboard_count': len(accessible_boards),
        'recent_noticeboard_announcements': recent_announcements,
        'urgent_noticeboard_announcements': urgent_announcements,
        'has_urgent_announcements': len(urgent_announcements) > 0,
    }


def active_announcements(request):
    """
    Context processor to show any active emergency or urgent announcements.
    """
    if not request.user.is_authenticated:
        return {}
    
    # Get urgent announcements that apply to this user
    urgent_announcements = Announcement.objects.filter(
        is_published=True,
        priority='urgent',
        status='active'
    ).filter(
        # Show to all users or specifically targeted users
        models.Q(target_audience='all') |
        models.Q(specific_users=request.user) |
        # Add more audience filtering based on user role if needed
        models.Q(target_audience__in=['students', 'teachers', 'parents'])
    )[:2]  # Limit to 2 most recent urgent announcements
    
    return {
        'urgent_site_announcements': urgent_announcements,
        'show_urgent_banner': len(urgent_announcements) > 0,
    }
