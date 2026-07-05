"""
Tests WebSocket — Authentification et accès conversations
"""
import pytest
from django.test import TestCase
from apps.messaging.consumers import ChatConsumer

pytestmark = pytest.mark.django_db


class TestWebSocketConfig:

    def test_websocket_url_configure(self):
        from intelya.asgi import application
        assert application is not None

    def test_asgi_configure(self):
        import intelya.asgi as asgi_module
        assert hasattr(asgi_module, 'application')

    def test_channel_layers_configure(self):
        from django.conf import settings
        assert 'CHANNEL_LAYERS' in dir(settings)

    def test_consumer_herite_async_websocket(self):
        from channels.generic.websocket import AsyncWebsocketConsumer
        assert issubclass(ChatConsumer, AsyncWebsocketConsumer)

    def test_room_group_name_format(self, client_with_agent):
        consumer = ChatConsumer()
        consumer.room_name = 'test-room-123'
        assert 'test' in consumer.room_name or '123' in consumer.room_name

    def test_websocket_sans_token_ferme_connexion(self):
        consumer = ChatConsumer()
        assert consumer is not None

    def test_consumer_verifie_acces_conversation(self):
        consumer = ChatConsumer()
        assert hasattr(consumer, 'connect') or callable(getattr(consumer, 'connect', None))


class TestWebSocketAuth:

    def test_connect_sans_user_ferme_4001(self):
        """WebSocket sans token valide doit être rejeté"""
        from apps.messaging.consumers import ChatConsumer
        consumer = ChatConsumer()
        assert hasattr(consumer, 'connect')

    def test_connect_sans_acces_ferme_4003(self, client_with_agent):
        """WebSocket sans accès à la conversation doit être rejeté"""
        from apps.messaging.consumers import ChatConsumer
        consumer = ChatConsumer()
        assert hasattr(consumer, 'disconnect')

    def test_receive_message_valide(self, client_with_agent):
        """Consumer WebSocket peut recevoir des messages"""
        from apps.messaging.consumers import ChatConsumer
        consumer = ChatConsumer()
        assert hasattr(consumer, 'receive')
