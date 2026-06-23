import pytest
import uuid
from rest_framework import status
from apps.messaging.models import Conversation, Message

pytestmark = pytest.mark.django_db


class TestConversations:

    def test_demarrer_conversation(self, auth_client_with_agent, agent_user):
        r = auth_client_with_agent.post('/api/v1/messaging/conversations/start/', {
            'user_id': str(agent_user.id),
        })
        assert r.status_code in [200, 201]

    def test_conversation_existante_retournee(self, auth_client_with_agent, agent_user):
        auth_client_with_agent.post('/api/v1/messaging/conversations/start/', {'user_id': str(agent_user.id)})
        r = auth_client_with_agent.post('/api/v1/messaging/conversations/start/', {'user_id': str(agent_user.id)})
        assert r.status_code == status.HTTP_200_OK
        assert r.data['message'] == 'Conversation existante'

    def test_client_sans_relation_bloque(self, auth_client, agent_user):
        r = auth_client.post('/api/v1/messaging/conversations/start/', {'user_id': str(agent_user.id)})
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_user_inexistant_404(self, auth_client):
        r = auth_client.post('/api/v1/messaging/conversations/start/', {'user_id': str(uuid.uuid4())})
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_voir_mes_conversations(self, auth_client_with_agent, client_with_agent, agent_user):
        conv = Conversation.objects.create(conversation_type='client_agent')
        conv.participants.add(client_with_agent, agent_user)
        r = auth_client_with_agent.get('/api/v1/messaging/conversations/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/messaging/conversations/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestMessages:

    @pytest.fixture
    def conv(self, client_with_agent, agent_user):
        c = Conversation.objects.create(conversation_type='client_agent')
        c.participants.add(client_with_agent, agent_user)
        return c

    def test_envoyer_message(self, auth_client_with_agent, conv):
        r = auth_client_with_agent.post(f'/api/v1/messaging/conversations/{conv.id}/', {
            'content': 'Bonjour agent !', 'message_type': 'text',
        })
        assert r.status_code in [200, 201]
        assert r.data['data']['content'] == 'Bonjour agent !'

    def test_lire_messages(self, auth_client_with_agent, conv, agent_user):
        Message.objects.create(
            conversation=conv, sender=agent_user,
            content='Bonjour !', message_type='text',
        )
        r = auth_client_with_agent.get(f'/api/v1/messaging/conversations/{conv.id}/')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['count'] >= 1

    def test_messages_marques_lus(self, auth_client_with_agent, conv, agent_user, client_with_agent):
        msg = Message.objects.create(
            conversation=conv, sender=agent_user,
            content='Test', message_type='text', is_read=False,
        )
        auth_client_with_agent.get(f'/api/v1/messaging/conversations/{conv.id}/')
        msg.refresh_from_db()
        assert msg.is_read is True

    def test_ne_peut_pas_acceder_autre_conv(self, auth_client, agent_user, owner_user):
        autre = Conversation.objects.create(conversation_type='agent_owner')
        autre.participants.add(agent_user, owner_user)
        r = auth_client.get(f'/api/v1/messaging/conversations/{autre.id}/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_ne_peut_pas_envoyer_autre_conv(self, auth_client, agent_user, owner_user):
        autre = Conversation.objects.create(conversation_type='agent_owner')
        autre.participants.add(agent_user, owner_user)
        r = auth_client.post(f'/api/v1/messaging/conversations/{autre.id}/', {
            'content': 'Intrusion', 'message_type': 'text',
        })
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_conv_inexistante_404(self, auth_client):
        r = auth_client.get(f'/api/v1/messaging/conversations/{uuid.uuid4()}/')
        assert r.status_code == status.HTTP_404_NOT_FOUND


class TestForumAgents:

    def test_agent_acces_forum(self, auth_agent):
        r = auth_agent.get('/api/v1/messaging/forum/')
        assert r.status_code == status.HTTP_200_OK

    def test_client_bloque_forum(self, auth_client):
        r = auth_client.get('/api/v1/messaging/forum/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_bloque_forum(self, auth_owner):
        r = auth_owner.get('/api/v1/messaging/forum/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.get('/api/v1/messaging/forum/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
