"""
Consumer WebSocket pour le chat en temps réel
Chaque utilisateur se connecte via ws://localhost:8000/ws/chat/CONVERSATION_ID/
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        # Rejoindre le groupe de la conversation
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Reçoit un message du client WebSocket"""
        try:
            data    = json.loads(text_data)
            content = data.get('content', '')
            user    = self.scope.get('user')

            if not user or not user.is_authenticated:
                await self.send(json.dumps({'error': 'Non authentifié'}))
                return

            # Sauvegarder en base
            message = await self.save_message(user, content)

            # Diffuser à tous dans le groupe
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': str(message.id),
                        'sender_name': user.get_full_name(),
                        'sender_role': user.role,
                        'content': content,
                        'created_at': message.created_at.isoformat(),
                        'is_mine': False,
                    }
                }
            )
        except Exception as e:
            await self.send(json.dumps({'error': str(e)}))

    async def chat_message(self, event):
        """Envoie le message au client WebSocket"""
        await self.send(text_data=json.dumps(event['message']))

    @database_sync_to_async
    def save_message(self, user, content):
        from .models import Message, Conversation
        try:
            conv = Conversation.objects.get(
                id=self.conversation_id,
                participants=user
            )
            msg = Message.objects.create(
                conversation=conv,
                sender=user,
                content=content,
                message_type='text'
            )
            conv.last_message_at = timezone.now()
            conv.save(update_fields=['last_message_at'])
            return msg
        except Conversation.DoesNotExist:
            raise Exception("Conversation introuvable")
