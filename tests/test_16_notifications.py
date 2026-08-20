import pytest
from unittest.mock import patch
from django.core import mail
from rest_framework import status
from apps.users.models import UserDevice
from apps.notifications.utils import notify, notify_account_validated, notify_payment_success
from apps.payments.models import Transaction

pytestmark = pytest.mark.django_db


class TestOTPDelivery:

    def test_register_sends_otp_via_sms(self, api_client):
        with patch('apps.users.views.sms_service.send_otp') as mock_send:
            r = api_client.post('/api/v1/auth/register/', {
                'email': 'newuser_otp@test.com', 'phone': '+237670000400',
                'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
                'first_name': 'Jean', 'last_name': 'Test',
            })
        assert r.status_code == status.HTTP_201_CREATED
        mock_send.assert_called_once()
        assert mock_send.call_args[0][0] == '+237670000400'

    def test_resend_otp_via_sms(self, api_client, client_user):
        with patch('apps.users.views.sms_service.send_otp') as mock_send:
            r = api_client.post('/api/v1/auth/resend-otp/', {'phone': client_user.phone})
        assert r.status_code == status.HTTP_200_OK
        mock_send.assert_called_once()

    def test_forgot_password_sends_sms_and_email(self, api_client, client_user):
        with patch('apps.users.views.sms_service.send_otp') as mock_sms, \
             patch('apps.users.views.email_service.send_otp') as mock_email:
            r = api_client.post('/api/v1/auth/forgot-password/', {'email': client_user.email})
        assert r.status_code == status.HTTP_200_OK
        mock_sms.assert_called_once()
        mock_email.assert_called_once()

    def test_google_complete_phone_sends_otp_via_sms(self, api_client, create_user):
        user = create_user(email='googleuser_otp@test.com', phone='+237670000401', role='client')
        user.is_phone_verified = False
        user.phone = ''
        user.save(update_fields=['is_phone_verified', 'phone'])

        with patch('apps.users.views.sms_service.send_otp') as mock_send:
            r = api_client.post('/api/v1/auth/google/complete-phone/', {
                'user_id': str(user.id), 'phone': '+237670000402',
            })
        assert r.status_code == status.HTTP_200_OK
        mock_send.assert_called_once()


class TestDeviceRegistration:

    def test_register_device(self, auth_client, client_user):
        r = auth_client.post('/api/v1/users/me/device/', {
            'device_token': 'fcm-token-abc', 'device_type': 'android',
        })
        assert r.status_code == status.HTTP_201_CREATED
        assert UserDevice.objects.filter(user=client_user, device_token='fcm-token-abc', is_active=True).exists()

    def test_register_device_missing_fields_rejected(self, auth_client):
        r = auth_client.post('/api/v1/users/me/device/', {'device_token': 'abc'})
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_reregister_same_token_updates_not_duplicates(self, auth_client, client_user):
        auth_client.post('/api/v1/users/me/device/', {'device_token': 'fcm-dup', 'device_type': 'ios'})
        auth_client.post('/api/v1/users/me/device/', {'device_token': 'fcm-dup', 'device_type': 'ios'})
        assert UserDevice.objects.filter(user=client_user, device_token='fcm-dup').count() == 1

    def test_unregister_device(self, auth_client, client_user):
        UserDevice.objects.create(user=client_user, device_token='fcm-to-remove', device_type='web')
        r = auth_client.delete('/api/v1/users/me/device/', {'device_token': 'fcm-to-remove'}, format='json')
        assert r.status_code == status.HTTP_200_OK
        device = UserDevice.objects.get(user=client_user, device_token='fcm-to-remove')
        assert device.is_active is False

    def test_unauthenticated_cannot_register_device(self, api_client):
        r = api_client.post('/api/v1/users/me/device/', {'device_token': 'x', 'device_type': 'web'})
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


class TestEmailChannel:

    def test_notify_with_send_email_delivers_to_outbox(self, client_user):
        mail.outbox = []
        notify(client_user, 'system', "Titre test", "Corps du message", send_email=True)
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [client_user.email]
        assert "Titre test" in mail.outbox[0].subject

    def test_notify_without_send_email_does_not_send(self, client_user):
        mail.outbox = []
        notify(client_user, 'system', "Titre test", "Corps du message")
        assert len(mail.outbox) == 0

    def test_account_validated_sends_email(self, agent_user):
        mail.outbox = []
        notify_account_validated(agent_user)
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [agent_user.email]

    def test_payment_success_sends_email(self, client_user):
        mail.outbox = []
        notify_payment_success(client_user, 5000)
        assert len(mail.outbox) == 1


class TestAdminValidationMultiChannel:

    def test_approve_sends_email_and_sms(self, auth_admin, create_user):
        pending_agent = create_user(
            email='pending_agent_notif@test.com', phone='+237670000410',
            role='agent', is_validated=False,
        )
        mail.outbox = []
        with patch('apps.notifications.services.sms.sms_service.send_account_validated') as mock_sms:
            r = auth_admin.post(f'/api/v1/admin-panel/users/{pending_agent.id}/validate/', {
                'action': 'approve',
            })
        assert r.status_code == status.HTTP_200_OK
        assert len(mail.outbox) == 1
        mock_sms.assert_called_once_with(pending_agent.phone, 'agent')


class TestPaymentCompletionNotification:

    def test_rent_payment_completion_notifies_payer(self, client_user):
        from apps.payments.services.disbursement import notify_payment_completed
        txn = Transaction.objects.create(
            reference='IH-NOTIF-001', payer=client_user,
            transaction_type='visit_fee', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='completed', payment_method='mtn',
        )
        mail.outbox = []
        with patch('apps.notifications.services.sms.sms_service.send_payment_received') as mock_sms:
            notify_payment_completed(txn)
        assert len(mail.outbox) == 1
        mock_sms.assert_called_once_with(client_user.phone, 5000)

    def test_webhook_success_triggers_notification(self, api_client, client_user):
        txn = Transaction.objects.create(
            reference='IH-NOTIF-002', payer=client_user,
            transaction_type='visit_fee', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='processing', payment_method='mtn',
        )
        mail.outbox = []
        api_client.post('/api/v1/payments/webhook/kpay/', {
            'tid': 'KPAY-NOTIF', 'refid': 'IH-NOTIF-002',
            'statusid': '01', 'statusdesc': 'Success',
        }, format='json')
        assert len(mail.outbox) == 1
