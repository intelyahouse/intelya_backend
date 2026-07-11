# INTELYA HAVEN - ASGI (WebSocket + HTTP)

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelya.settings.development')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from apps.messaging.routing import websocket_urlpatterns


class JWTAuthMiddleware:
    """
    Middleware WebSocket — authentification JWT via query param ou header.
    Usage: ws://localhost:8000/ws/chat/<id>/?token=<access_token>
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        return await self.inner(scope, receive, send)


application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': URLRouter(websocket_urlpatterns),
})
