"""
WebSocket routing configuration for the school management system.
"""

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import path
from django.core.asgi import get_asgi_application

# Import consumers
from apps.communication.consumers import ChatConsumer, NotificationConsumer, BulkNotificationConsumer

# Define WebSocket URL patterns
websocket_urlpatterns = [
    # Chat WebSocket
    path('ws/chat/<int:room_id>/', ChatConsumer.as_asgi()),

    # Real-time notifications WebSocket
    path('ws/notifications/', NotificationConsumer.as_asgi()),

    # Bulk notifications WebSocket (for admins/staff)
    path('ws/bulk-notifications/', BulkNotificationConsumer.as_asgi()),
]

# Protocol type router
application = ProtocolTypeRouter({
    # Django's ASGI application for HTTP requests
    'http': get_asgi_application(),

    # WebSocket connections with authentication
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
