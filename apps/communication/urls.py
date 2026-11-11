from django.urls import path
from . import views

app_name = 'communication'

urlpatterns = [
    # Announcements
    path('announcements/', views.AnnouncementListView.as_view(), name='announcement_list'),
    path('announcements/<uuid:pk>/', views.AnnouncementDetailView.as_view(), name='announcement_detail'),
    path('announcements/create/', views.AnnouncementCreateView.as_view(), name='announcement_create'),
    path('announcements/<uuid:pk>/update/', views.AnnouncementUpdateView.as_view(), name='announcement_update'),
    path('announcements/<uuid:pk>/delete/', views.AnnouncementDeleteView.as_view(), name='announcement_delete'),



    # Notice Boards
    path('noticeboards/', views.NoticeBoardListView.as_view(), name='noticeboard_list'),
    path('noticeboards/public/', views.public_noticeboard_portal, name='public_noticeboard_portal'),
    path('noticeboards/<uuid:pk>/', views.NoticeBoardDetailView.as_view(), name='noticeboard_detail'),
    path('noticeboards/<uuid:pk>/display/', views.NoticeBoardDisplayView.as_view(), name='noticeboard_display'),
    path('noticeboards/create/', views.NoticeBoardCreateView.as_view(), name='noticeboard_create'),
    path('noticeboards/<uuid:pk>/update/', views.NoticeBoardUpdateView.as_view(), name='noticeboard_update'),
    path('noticeboards/<uuid:pk>/delete/', views.NoticeBoardDeleteView.as_view(), name='noticeboard_delete'),

    # Notice Board Items
    path('noticeboards/<uuid:board_pk>/add/<uuid:announcement_pk>/', views.add_announcement_to_board, name='add_to_board'),
    path('noticeboards/<uuid:board_pk>/remove/<uuid:item_pk>/', views.remove_announcement_from_board, name='remove_from_board'),
    path('noticeboards/<uuid:board_pk>/reorder/', views.reorder_notice_board_items, name='reorder_board_items'),
    path('noticeboards/items/<uuid:item_pk>/toggle/', views.toggle_notice_board_item, name='toggle_board_item'),

    # Email Templates
    path('emails/templates/', views.EmailTemplateListView.as_view(), name='emailtemplate_list'),
    path('emails/templates/create/', views.EmailTemplateCreateView.as_view(), name='emailtemplate_create'),
    path('emails/templates/<uuid:pk>/update/', views.EmailTemplateUpdateView.as_view(), name='emailtemplate_update'),
    path('emails/templates/<uuid:pk>/delete/', views.EmailTemplateDeleteView.as_view(), name='emailtemplate_delete'),
    path('emails/templates/<uuid:pk>/test/', views.send_test_email_view, name='send_test_email'),
    path('emails/templates/<uuid:pk>/toggle/', views.toggle_emailtemplate_status, name='toggle_emailtemplate'),
    path('emails/templates/bulk-update/', views.bulk_update_template_status, name='bulk_update_templates'),
    path('emails/templates/<uuid:pk>/duplicate/', views.duplicate_emailtemplate, name='duplicate_emailtemplate'),
    path('emails/templates/<uuid:pk>/export/', views.export_emailtemplate, name='export_emailtemplate'),

    # SMS Templates
    path('sms/templates/', views.SMSTemplateListView.as_view(), name='smstemplate_list'),
    path('sms/templates/create/', views.SMSTemplateCreateView.as_view(), name='smstemplate_create'),
    path('sms/templates/<uuid:pk>/update/', views.SMSTemplateUpdateView.as_view(), name='smstemplate_update'),
    path('sms/templates/<uuid:pk>/delete/', views.SMSTemplateDeleteView.as_view(), name='smstemplate_delete'),

    # Dashboard and Analytics
    path('dashboard/', views.communication_dashboard, name='dashboard'),

    # Messages
    path('messages/create/', views.MessageCreateView.as_view(), name='message_create'),

    # Bulk actions
    path('announcements/bulk-publish/', views.bulk_publish_announcements, name='bulk_publish_announcements'),
    path('announcements/bulk-delete/', views.bulk_delete_announcements, name='bulk_delete_announcements'),
    path('emails/templates/bulk-delete/', views.bulk_delete_templates, name='bulk_delete_templates'),

    # Parent Calendar
    path('calendar/parent/', views.ParentCalendarView.as_view(), name='parent_calendar'),

    # ===== NOTIFICATION URLS =====

    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('notifications/unread/', views.UnreadNotificationListView.as_view(), name='unread_notifications'),
    path('notifications/<uuid:pk>/', views.NotificationDetailView.as_view(), name='notification_detail'),
    path('notifications/<uuid:pk>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/<uuid:pk>/delete/', views.delete_notification, name='delete_notification'),
    path('notifications/clear-all/', views.clear_all_notifications, name='clear_all_notifications'),
    path('notifications/unread-count/', views.get_unread_notification_count, name='get_unread_notification_count'),
    path('notifications/preferences/', views.notification_preferences, name='notification_preferences'),
    path('notifications/api/', views.NotificationAPIView.as_view(), name='notification_api'),

    # Real-time Notifications (using same templates as regular notifications)
    path('realtime-notifications/', views.RealTimeNotificationListView.as_view(), name='realtime_notification_list'),
    path('realtime-notifications/<uuid:pk>/', views.RealTimeNotificationDetailView.as_view(), name='realtime_notification_detail'),
    path('realtime-notifications/preferences/', views.realtime_notification_preferences, name='realtime_notification_preferences'),

    # ===== CHAT URLS =====

    # Inbox - unified messages view
    path('inbox/', views.ChatRoomListView.as_view(), name='inbox'),

    # Chat Rooms
    path('chat/', views.ChatRoomListView.as_view(), name='chat_room_list'),
    path('chat/<int:pk>/', views.ChatRoomDetailView.as_view(), name='chat_room_detail'),
    path('chat/create/', views.ChatRoomCreateView.as_view(), name='chat_room_create'),

    # Chat Messages (AJAX)
    path('chat/<int:room_pk>/send/', views.send_chat_message, name='send_chat_message'),
    path('chat/<int:room_pk>/messages/', views.get_chat_messages, name='get_chat_messages'),
    path('chat/<int:room_pk>/mark-read/', views.mark_chat_messages_read, name='mark_chat_messages_read'),
]
