"""
ASGI config for school management system project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Import routing configuration
from config.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

# Application definition
application = ProtocolTypeRouter(
    {
        # Django's ASGI application for HTTP requests
        "http": get_asgi_application(),
        # WebSocket connections with authentication
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
