from rest_framework import serializers
from .models import Conversation, Message, ForumMessage


class MessageSerializer(serializers.ModelSerializer):
    sender_name  = serializers.CharField(source='sender.get_full_name', read_only=True)
    sender_role  = serializers.CharField(source='sender.role', read_only=True)
    is_mine      = serializers.SerializerMethodField()

    class Meta:
        model  = Message
        fields = [
            'id', 'sender_name', 'sender_role', 'is_mine',
            'message_type', 'content', 'file',
            'is_read', 'read_at', 'created_at'
        ]

    def get_is_mine(self, obj):
        request = self.context.get('request')
        return request and request.user == obj.sender


class ConversationSerializer(serializers.ModelSerializer):
    last_message    = serializers.SerializerMethodField()
    unread_count    = serializers.SerializerMethodField()
    other_participant = serializers.SerializerMethodField()

    class Meta:
        model  = Conversation
        fields = [
            'id', 'conversation_type', 'title',
            'last_message', 'unread_count',
            'other_participant', 'last_message_at', 'created_at'
        ]

    def get_last_message(self, obj):
        msg = obj.messages.filter(is_deleted=False).last()
        if msg:
            return {
                'content': msg.content,
                'sender': msg.sender.get_full_name(),
                'created_at': msg.created_at
            }
        return None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request:
            return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        return 0

    def get_other_participant(self, obj):
        request = self.context.get('request')
        if request:
            other = obj.participants.exclude(id=request.user.id).first()
            if other:
                return {
                    'id': str(other.id),
                    'name': other.get_full_name(),
                    'role': other.role,
                }
        return None


class ForumMessageSerializer(serializers.ModelSerializer):
    sender_name   = serializers.CharField(source='sender.get_full_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.get_full_name', read_only=True)
    property_title = serializers.CharField(source='related_property.title', read_only=True)

    class Meta:
        model  = ForumMessage
        fields = [
            'id', 'sender_name', 'receiver_name',
            'property_title', 'content', 'is_read',
            'negotiation_status', 'created_at'
        ]


class SendMessageSerializer(serializers.Serializer):
    content      = serializers.CharField(required=False, allow_blank=True)
    message_type = serializers.ChoiceField(
        choices=[('text', 'Texte'), ('image', 'Image'), ('document', 'Document')],
        default='text'
    )
    file         = serializers.FileField(required=False)


class StartForumNegotiationSerializer(serializers.Serializer):
    receiver_agent_id = serializers.UUIDField()
    property_id       = serializers.UUIDField()
    message           = serializers.CharField()


class ForumReplySerializer(serializers.Serializer):
    content            = serializers.CharField()
    negotiation_status = serializers.ChoiceField(
        choices=[('pending', 'En attente'), ('accepted', 'Accepté'), ('refused', 'Refusé')],
        required=False
    )
