"""
Routing WebSocket pour le chat en temps réel.
URL: ws://localhost:8000/ws/chat/<conversation_id>/
Activé avec Django Channels + Redis.
"""
from django.urls import re_path
from .consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<conversation_id>[0-9a-f-]+)/$', ChatConsumer.as_asgi()),
]
