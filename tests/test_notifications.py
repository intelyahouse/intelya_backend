import pytest
from rest_framework import status
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


class TestNotifications:

    def test_get_notifications(self, auth_client, client_user):
        Notification.objects.create(
            recipient=client_user,
            notification_type='system',
            title='Test',
            body='Message de test',
        )
        response = auth_client.get('/api/v1/notifications/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data'] if 'data' in response.data else response.data
        assert data['unread_count'] >= 1

    def test_mark_all_read(self, auth_client, client_user):
        Notification.objects.create(
            recipient=client_user,
            notification_type='system',
            title='Non lu',
            body='Corps du message',
            is_read=False,
        )
        response = auth_client.post('/api/v1/notifications/mark-read/')
        assert response.status_code == status.HTTP_200_OK
        assert Notification.objects.filter(recipient=client_user, is_read=False).count() == 0

    def test_unauthenticated_cannot_see_notifications(self, api_client):
        response = api_client.get('/api/v1/notifications/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
