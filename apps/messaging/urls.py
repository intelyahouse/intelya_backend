from django.urls import path
from .views import (
    MyConversationsView, ConversationMessagesView,
    StartConversationView, ForumConversationsView,
    StartForumNegotiationView, ForumReplyView
)

urlpatterns = [
    path('conversations/', MyConversationsView.as_view(), name='my-conversations'),
    path('conversations/start/', StartConversationView.as_view(), name='start-conversation'),
    path('conversations/<uuid:conversation_id>/', ConversationMessagesView.as_view(), name='conversation-messages'),
    path('forum/', ForumConversationsView.as_view(), name='forum'),
    path('forum/negotiate/', StartForumNegotiationView.as_view(), name='forum-negotiate'),
    path('forum/<uuid:message_id>/reply/', ForumReplyView.as_view(), name='forum-reply'),
]
