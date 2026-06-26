import pytest
from rest_framework import status
from apps.messaging.models import Conversation, Message

pytestmark = pytest.mark.django_db


class TestConversations:

    def test_start_conversation_client_to_agent(self, auth_client_with_agent, agent_user):
        response = auth_client_with_agent.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(agent_user.id),
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data['data']

    def test_start_conversation_creates_once(self, auth_client_with_agent, agent_user):
        auth_client_with_agent.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(agent_user.id),
        })
        response = auth_client_with_agent.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(agent_user.id),
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Conversation existante'

    def test_start_conversation_without_relation_fails(self, auth_client, agent_user):
        response = auth_client.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(agent_user.id),
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_start_conversation_with_self_fails(self, auth_client, client_user):
        response = auth_client.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(client_user.id),
        })
        assert response.status_code in [400, 403]

    def test_start_conversation_invalid_user(self, auth_client):
        import uuid
        response = auth_client.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(uuid.uuid4()),
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_my_conversations_empty(self, auth_client):
        response = auth_client.get('/api/v1/messaging/conversations/')
        assert response.status_code == status.HTTP_200_OK

    def test_get_my_conversations_shows_mine(self, auth_client_with_agent, agent_user, client_with_agent):
        """Créer une conv directement et vérifier qu'elle apparaît"""
        conv = Conversation.objects.create(conversation_type='client_agent')
        conv.participants.add(client_with_agent, agent_user)
        response = auth_client_with_agent.get('/api/v1/messaging/conversations/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) >= 1

    def test_unauthenticated_cannot_access_conversations(self, api_client):
        response = api_client.get('/api/v1/messaging/conversations/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_start_conversation(self, api_client, agent_user):
        response = api_client.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(agent_user.id),
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMessages:

    @pytest.fixture
    def conversation(self, client_with_agent, agent_user):
        conv = Conversation.objects.create(conversation_type='client_agent')
        conv.participants.add(client_with_agent, agent_user)
        return conv

    def test_send_message(self, auth_client_with_agent, conversation):
        response = auth_client_with_agent.post(
            f'/api/v1/messaging/conversations/{conversation.id}/',
            {'content': 'Bonjour, je suis intéressé par le bien.', 'message_type': 'text'}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['data']['content'] == 'Bonjour, je suis intéressé par le bien.'

    def test_get_messages(self, auth_client_with_agent, conversation, client_with_agent):
        Message.objects.create(
            conversation=conversation,
            sender=client_with_agent,
            content='Premier message',
            message_type='text'
        )
        response = auth_client_with_agent.get(
            f'/api/v1/messaging/conversations/{conversation.id}/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] >= 1

    def test_cannot_access_other_conversation(self, auth_client, agent_user, owner_user):
        other_conv = Conversation.objects.create(conversation_type='agent_owner')
        other_conv.participants.add(agent_user, owner_user)
        response = auth_client.get(f'/api/v1/messaging/conversations/{other_conv.id}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_send_to_other_conversation(self, auth_client, agent_user, owner_user):
        other_conv = Conversation.objects.create(conversation_type='agent_owner')
        other_conv.participants.add(agent_user, owner_user)
        response = auth_client.post(
            f'/api/v1/messaging/conversations/{other_conv.id}/',
            {'content': 'Intrusion !', 'message_type': 'text'}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_messages_marked_as_read(self, auth_client_with_agent, conversation, agent_user):
        msg = Message.objects.create(
            conversation=conversation,
            sender=agent_user,
            content='Message non lu',
            message_type='text',
            is_read=False
        )
        auth_client_with_agent.get(f'/api/v1/messaging/conversations/{conversation.id}/')
        msg.refresh_from_db()
        assert msg.is_read is True

    def test_conversation_not_found(self, auth_client):
        import uuid
        response = auth_client.get(f'/api/v1/messaging/conversations/{uuid.uuid4()}/')
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestForumAgents:

    def test_client_cannot_access_forum(self, auth_client):
        response = auth_client.get('/api/v1/messaging/forum/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_cannot_access_forum(self, auth_owner):
        response = auth_owner.get('/api/v1/messaging/forum/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_agent_can_access_forum(self, auth_agent):
        response = auth_agent.get('/api/v1/messaging/forum/')
        assert response.status_code == status.HTTP_200_OK

    def test_agent_cannot_contact_non_agent(self, auth_agent, client_user, property_obj):
        response = auth_agent.post('/api/v1/messaging/forum/negotiate/', {
            'receiver_agent_id': str(client_user.id),
            'property_id': str(property_obj.id),
            'message': 'Je suis intéressé par ce bien pour mon client.',
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_agent_cannot_negotiate_own_property(self, auth_agent, property_obj, agent_user):
        response = auth_agent.post('/api/v1/messaging/forum/negotiate/', {
            'receiver_agent_id': str(agent_user.id),
            'property_id': str(property_obj.id),
            'message': 'Je veux mon propre bien.',
        })
        assert response.status_code in [400, 403]

    def test_unauthenticated_cannot_use_forum(self, api_client):
        response = api_client.get('/api/v1/messaging/forum/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
