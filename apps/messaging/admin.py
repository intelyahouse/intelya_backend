from django.contrib import admin
from .models import Conversation, Message, ForumMessage


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['conversation_type', 'is_active', 'last_message_at', 'created_at']
    list_filter  = ['conversation_type', 'is_active']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'conversation', 'message_type', 'is_read', 'created_at']
    list_filter  = ['message_type', 'is_read']


@admin.register(ForumMessage)
class ForumMessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'receiver', 'negotiation_status', 'created_at']
    list_filter  = ['negotiation_status']
