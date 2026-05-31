from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from .models import Conversation, Message, ForumMessage
from .serializers import (
    ConversationSerializer, MessageSerializer,
    SendMessageSerializer, ForumMessageSerializer,
    StartForumNegotiationSerializer, ForumReplySerializer
)
from core.permissions import IsAgent
from core.utils import success_response, error_response


class MyConversationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Messaging'], summary="Mes conversations")
    def get(self, request):
        conversations = Conversation.objects.filter(
            participants=request.user, is_active=True
        ).prefetch_related('participants', 'messages')
        serializer = ConversationSerializer(
            conversations, many=True, context={'request': request}
        )
        return Response(success_response(serializer.data))


class ConversationMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Messaging'], summary="Messages d'une conversation")
    def get(self, request, conversation_id):
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                participants=request.user
            )
        except Conversation.DoesNotExist:
            return Response(error_response("Conversation introuvable"), status=status.HTTP_404_NOT_FOUND)

        messages = conversation.messages.filter(is_deleted=False)

        # Marquer les messages non lus comme lus
        messages.exclude(sender=request.user).filter(is_read=False).update(
            is_read=True, read_at=timezone.now()
        )

        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(success_response(serializer.data))

    @extend_schema(
        tags=['Messaging'],
        summary="Envoyer un message",
        request=SendMessageSerializer
    )
    def post(self, request, conversation_id):
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                participants=request.user
            )
        except Conversation.DoesNotExist:
            return Response(error_response("Conversation introuvable"), status=status.HTTP_404_NOT_FOUND)

        serializer = SendMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            message_type=serializer.validated_data.get('message_type', 'text'),
            content=serializer.validated_data.get('content', ''),
            file=serializer.validated_data.get('file'),
        )

        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['last_message_at'])

        return Response(
            success_response(
                MessageSerializer(message, context={'request': request}).data,
                "Message envoyé"
            ),
            status=status.HTTP_201_CREATED
        )


class StartConversationView(APIView):
    """Démarrer une conversation avec l'agent"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Messaging'], summary="Démarrer une conversation")
    def post(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        other_id = request.data.get('user_id')
        try:
            other_user = User.objects.get(id=other_id)
        except User.DoesNotExist:
            return Response(error_response("Utilisateur introuvable"), status=status.HTTP_404_NOT_FOUND)

        # Déterminer le type de conversation
        roles = sorted([request.user.role, other_user.role])
        conv_type = 'client_agent'
        if 'agent' in roles and 'owner' in roles:
            conv_type = 'agent_owner'
        elif 'owner' in roles and 'tenant' in roles:
            conv_type = 'owner_tenant'

        # Chercher une conversation existante
        existing = Conversation.objects.filter(
            conversation_type=conv_type,
            participants=request.user
        ).filter(participants=other_user).first()

        if existing:
            return Response(success_response(
                ConversationSerializer(existing, context={'request': request}).data,
                "Conversation existante"
            ))

        conversation = Conversation.objects.create(conversation_type=conv_type)
        conversation.participants.add(request.user, other_user)

        return Response(
            success_response(
                ConversationSerializer(conversation, context={'request': request}).data,
                "Conversation créée"
            ),
            status=status.HTTP_201_CREATED
        )


class ForumConversationsView(APIView):
    """Forum inter-agents — liste des négociations"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Messaging'], summary="Forum agents — mes négociations")
    def get(self, request):
        messages = ForumMessage.objects.filter(
            sender=request.user
        ) | ForumMessage.objects.filter(
            receiver=request.user
        )
        messages = messages.order_by('-created_at')
        serializer = ForumMessageSerializer(messages, many=True)
        return Response(success_response(serializer.data))


class StartForumNegotiationView(APIView):
    """Agent démarre une négociation dans le forum"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(
        tags=['Messaging'],
        summary="Démarrer une négociation forum (agent)",
        description="Agent A contacte Agent B pour un bien. Le client ne sait pas.",
        request=StartForumNegotiationSerializer
    )
    def post(self, request):
        serializer = StartForumNegotiationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        from django.contrib.auth import get_user_model
        from apps.properties.models import Property
        User = get_user_model()

        try:
            receiver = User.objects.get(
                id=serializer.validated_data['receiver_agent_id'],
                role='agent'
            )
        except User.DoesNotExist:
            return Response(error_response("Agent introuvable"), status=status.HTTP_404_NOT_FOUND)

        try:
            prop = Property.objects.get(id=serializer.validated_data['property_id'])
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=status.HTTP_404_NOT_FOUND)

        if receiver == request.user:
            return Response(error_response("Vous ne pouvez pas vous contacter vous-même"), status=status.HTTP_400_BAD_REQUEST)

        forum_msg = ForumMessage.objects.create(
            sender=request.user,
            receiver=receiver,
            related_property=prop,
            content=serializer.validated_data['message'],
            negotiation_status='pending'
        )

        return Response(
            success_response(
                ForumMessageSerializer(forum_msg).data,
                f"Message envoyé à {receiver.get_full_name()}"
            ),
            status=status.HTTP_201_CREATED
        )


class ForumReplyView(APIView):
    """Agent répond à une négociation"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(
        tags=['Messaging'],
        summary="Répondre à une négociation forum",
        request=ForumReplySerializer
    )
    def post(self, request, message_id):
        try:
            original = ForumMessage.objects.get(
                id=message_id, receiver=request.user
            )
        except ForumMessage.DoesNotExist:
            return Response(error_response("Message introuvable"), status=status.HTTP_404_NOT_FOUND)

        serializer = ForumReplySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        # Mettre à jour le statut de négociation
        neg_status = serializer.validated_data.get('negotiation_status', 'pending')
        original.negotiation_status = neg_status
        original.is_read = True
        original.read_at = timezone.now()
        original.save()

        # Créer la réponse
        reply = ForumMessage.objects.create(
            sender=request.user,
            receiver=original.sender,
            related_property=original.related_property,
            content=serializer.validated_data['content'],
            negotiation_status=neg_status
        )

        return Response(success_response(
            ForumMessageSerializer(reply).data,
            f"Réponse envoyée — Négociation : {neg_status}"
        ))
