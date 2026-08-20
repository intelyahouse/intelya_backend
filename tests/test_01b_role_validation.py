import datetime
import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.users.tasks import remind_pending_validations

pytestmark = pytest.mark.django_db

User = get_user_model()


def _auth_as(user):
    """Client HTTP dedie, authentifie comme `user` -- necessaire des qu'un
    test manipule plus d'un role (auth_client/auth_admin partagent le meme
    api_client sous-jacent : le second force_authenticate() ecrase le premier)."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _cni_payload(role='agent'):
    import io
    from PIL import Image
    from django.core.files.uploadedfile import SimpleUploadedFile

    def img(name):
        buf = io.BytesIO()
        Image.new('RGB', (100, 100)).save(buf, format='JPEG')
        buf.seek(0)
        return SimpleUploadedFile(name, buf.read(), content_type='image/jpeg')

    return {
        'requested_role': role, 'cni_number': f'CM{role}12345',
        'cni_front_photo': img('front.jpg'), 'cni_back_photo': img('back.jpg'),
        'selfie_photo': img('selfie.jpg'),
    }


class TestRoleRequestSetsRole:

    def test_request_role_sets_user_role(self, client_user):
        r = _auth_as(client_user).post('/api/v1/auth/request-role/', _cni_payload('agent'), format='multipart')
        assert r.status_code == status.HTTP_200_OK
        client_user.refresh_from_db()
        assert client_user.role == 'agent'
        assert client_user.validation_status == 'pending'
        assert client_user.role_requested_at is not None

    def test_request_role_appears_in_admin_pending_list(self, client_user, admin_user):
        _auth_as(client_user).post('/api/v1/auth/request-role/', _cni_payload('owner'), format='multipart')
        r = _auth_as(admin_user).get('/api/v1/admin-panel/users/pending/')
        assert r.status_code == status.HTTP_200_OK
        ids = [u['id'] for u in r.data['data']]
        assert str(client_user.id) in ids

    def test_admins_notified_on_new_request(self, client_user, admin_user):
        from apps.notifications.models import Notification
        _auth_as(client_user).post('/api/v1/auth/request-role/', _cni_payload('agent'), format='multipart')
        assert Notification.objects.filter(recipient=admin_user, notification_type='system').exists()


class TestValidationApproveReject:

    def test_approve_agent_request(self, client_user, admin_user):
        _auth_as(client_user).post('/api/v1/auth/request-role/', _cni_payload('agent'), format='multipart')
        r = _auth_as(admin_user).post(f'/api/v1/admin-panel/users/{client_user.id}/validate/', {'action': 'approve'})
        assert r.status_code == status.HTTP_200_OK
        client_user.refresh_from_db()
        assert client_user.is_validated is True
        assert client_user.role == 'agent'
        from apps.agents.models import AgentProfile
        assert AgentProfile.objects.filter(user=client_user).exists()

    def test_reject_reverts_role_to_client(self, client_user, admin_user):
        _auth_as(client_user).post('/api/v1/auth/request-role/', _cni_payload('owner'), format='multipart')
        r = _auth_as(admin_user).post(f'/api/v1/admin-panel/users/{client_user.id}/validate/', {
            'action': 'reject', 'note': 'Documents illisibles',
        })
        assert r.status_code == status.HTTP_200_OK
        client_user.refresh_from_db()
        assert client_user.role == 'client'
        assert client_user.validation_status == 'rejected'
        assert client_user.is_validated is False

    def test_rejected_user_can_still_use_client_features(self, client_user, admin_user):
        auth_client = _auth_as(client_user)
        auth_client.post('/api/v1/auth/request-role/', _cni_payload('agent'), format='multipart')
        _auth_as(admin_user).post(f'/api/v1/admin-panel/users/{client_user.id}/validate/', {'action': 'reject'})
        r = auth_client.get('/api/v1/properties/')
        assert r.status_code == status.HTTP_200_OK

    def test_user_notified_on_rejection(self, client_user, admin_user):
        mail.outbox = []
        _auth_as(client_user).post('/api/v1/auth/request-role/', _cni_payload('agent'), format='multipart')
        _auth_as(admin_user).post(f'/api/v1/admin-panel/users/{client_user.id}/validate/', {
            'action': 'reject', 'note': 'CNI expirée',
        })
        assert len(mail.outbox) == 1

    def test_pending_agent_has_no_dashboard_access(self, client_user):
        auth_client = _auth_as(client_user)
        auth_client.post('/api/v1/auth/request-role/', _cni_payload('agent'), format='multipart')
        r = auth_client.get('/api/v1/agencies/me/')
        assert r.status_code == status.HTTP_403_FORBIDDEN


class TestPendingValidationReminder:

    def test_stale_request_triggers_admin_reminder(self, client_user, admin_user):
        client_user.role = 'agent'
        client_user.validation_status = 'pending'
        client_user.role_requested_at = timezone.now() - datetime.timedelta(hours=49)
        client_user.save()

        remind_pending_validations()

        from apps.notifications.models import Notification
        assert Notification.objects.filter(recipient=admin_user, notification_type='system').exists()
        client_user.refresh_from_db()
        assert client_user.validation_reminder_sent is True

    def test_reminder_not_sent_twice(self, client_user, admin_user):
        from apps.notifications.models import Notification
        client_user.role = 'agent'
        client_user.validation_status = 'pending'
        client_user.role_requested_at = timezone.now() - datetime.timedelta(hours=49)
        client_user.save()

        remind_pending_validations()
        count_after_first = Notification.objects.filter(recipient=admin_user).count()
        remind_pending_validations()
        count_after_second = Notification.objects.filter(recipient=admin_user).count()
        assert count_after_first == count_after_second

    def test_fresh_request_not_reminded(self, client_user, admin_user):
        client_user.role = 'agent'
        client_user.validation_status = 'pending'
        client_user.role_requested_at = timezone.now() - datetime.timedelta(hours=10)
        client_user.save()

        remind_pending_validations()

        from apps.notifications.models import Notification
        assert not Notification.objects.filter(recipient=admin_user, notification_type='system').exists()
