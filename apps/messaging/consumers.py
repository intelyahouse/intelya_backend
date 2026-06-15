"""
Consumer WebSocket sécurisé avec authentification JWT
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # Authentification JWT obligatoire
        user = await self.get_authenticated_user()
        if not user:
            logger.warning("[WS] Connexion refusée — non authentifié")
            await self.close(code=4001)
            return

        self.user = user
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        # Vérifier que l'utilisateur a accès à cette conversation
        has_access = await self.check_access()
        if not has_access:
            logger.warning(f"[WS] {user.email} n'a pas accès à la conversation {self.conversation_id}")
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info(f"[WS] {user.email} connecté à la conversation {self.conversation_id}")

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            # Vérifier que l'utilisateur n'est pas bloqué
            is_still_active = await self.check_user_still_active()
            if not is_still_active:
                await self.close(code=4003)
                return

            data = json.loads(text_data)
            content = data.get('content', '').strip()
            if not content:
                return
            if len(content) > 4000:
                await self.send(json.dumps({'error': 'Message trop long (max 4000 caractères)'}))
                return
            if len(content) < 1:
                return

            message = await self.save_message(self.user, content)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': str(message.id),
                        'sender_name': self.user.get_full_name(),
                        'sender_role': self.user.role,
                        'content': content,
                        'created_at': message.created_at.isoformat(),
                    }
                }
            )
        except json.JSONDecodeError:
            await self.send(json.dumps({'error': 'Format JSON invalide'}))
        except Exception as e:
            logger.error(f"[WS] Erreur: {e}")

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['message']))

    @database_sync_to_async
    def get_authenticated_user(self):
        """Authentification via JWT dans le header ou query param"""
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from django.contrib.auth import get_user_model
            User = get_user_model()

            # Token dans query string: ws://...?token=xxx
            token_key = self.scope.get('query_string', b'').decode()
            token_str = None
            for param in token_key.split('&'):
                if param.startswith('token='):
                    token_str = param.split('=')[1]
                    break

            if not token_str:
                # Token dans les headers
                headers = dict(self.scope.get('headers', []))
                auth = headers.get(b'authorization', b'').decode()
                if auth.startswith('Bearer '):
                    token_str = auth.split(' ')[1]

            if not token_str:
                return None

            token = AccessToken(token_str)
            user = User.objects.get(id=token['user_id'])
            return user if user.is_active and not user.is_blocked else None
        except Exception:
            return None

    @database_sync_to_async
    def check_user_still_active(self):
        """Vérifie que l'utilisateur est toujours actif et non bloqué"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=self.user.id)
            return user.is_active and not user.is_blocked
        except Exception:
            return False

    @database_sync_to_async
    def check_access(self):
        """Vérifie que l'utilisateur peut accéder à cette conversation"""
        from .models import Conversation
        return Conversation.objects.filter(
            id=self.conversation_id,
            participants=self.user,
            is_active=True
        ).exists()

    @database_sync_to_async
    def save_message(self, user, content):
        from .models import Message, Conversation
        conv = Conversation.objects.get(id=self.conversation_id, participants=user)
        msg = Message.objects.create(conversation=conv, sender=user, content=content, message_type='text')
        conv.last_message_at = timezone.now()
        conv.save(update_fields=['last_message_at'])
        return msg
