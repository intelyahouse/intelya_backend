import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from apps.users.models import OTPVerification
from django.utils import timezone
from datetime import timedelta

User = get_user_model()
pytestmark = pytest.mark.django_db


class TestRegistration:

    def test_register_success(self, api_client):
        response = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Shalom',
            'last_name': 'Intelya',
            'email': 'shalom@intelya.com',
            'phone': '+237670000010',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!',
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True
        assert User.objects.filter(email='shalom@intelya.com').exists()

    def test_register_creates_client_role(self, api_client):
        api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test',
            'last_name': 'Role',
            'email': 'role@test.com',
            'phone': '+237670000011',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!',
        })
        user = User.objects.get(email='role@test.com')
        assert user.role == 'client'

    def test_register_generates_referral_code(self, api_client):
        api_client.post('/api/v1/auth/register/', {
            'first_name': 'Ref',
            'last_name': 'Code',
            'email': 'ref@test.com',
            'phone': '+237670000012',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!',
        })
        user = User.objects.get(email='ref@test.com')
        assert user.referral_code is not None
        assert len(user.referral_code) == 8

    def test_register_duplicate_email_fails(self, api_client, client_user):
        response = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Other',
            'last_name': 'User',
            'email': 'client@test.com',
            'phone': '+237670000099',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_phone_fails(self, api_client, client_user):
        response = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Other',
            'last_name': 'User',
            'email': 'other@test.com',
            'phone': '+237670000001',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_password_mismatch_fails(self, api_client):
        response = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'mismatch@test.com',
            'phone': '+237670000013',
            'password': 'TestPass123!',
            'confirm_password': 'Different123!',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_invalid_phone_format_fails(self, api_client):
        """Numéro invalide — pas le format camerounais +237"""
        response = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'phone@test.com',
            'phone': '0670000014',
            'password': 'TestPass123!',
            'confirm_password': 'TestPass123!',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_short_password_fails(self, api_client):
        response = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'short@test.com',
            'phone': '+237670000015',
            'password': 'abc',
            'confirm_password': 'abc',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_missing_fields_fails(self, api_client):
        response = api_client.post('/api/v1/auth/register/', {
            'email': 'incomplete@test.com',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestLogin:

    def test_login_success_returns_tokens(self, api_client, client_user):
        response = api_client.post('/api/v1/auth/login/', {
            'email': 'client@test.com',
            'password': 'TestPass123!',
        })
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data['data']
        assert 'refresh' in response.data['data']
        assert 'user' in response.data['data']

    def test_login_wrong_password_fails(self, api_client, client_user):
        response = api_client.post('/api/v1/auth/login/', {
            'email': 'client@test.com',
            'password': 'WrongPass!',
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user_fails(self, api_client):
        response = api_client.post('/api/v1/auth/login/', {
            'email': 'nobody@test.com',
            'password': 'TestPass123!',
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_blocked_user_fails(self, api_client, client_user):
        client_user.is_blocked = True
        client_user.save()
        response = api_client.post('/api/v1/auth/login/', {
            'email': 'client@test.com',
            'password': 'TestPass123!',
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_login_increments_attempts_on_failure(self, api_client, client_user):
        initial_attempts = client_user.login_attempts
        api_client.post('/api/v1/auth/login/', {
            'email': 'client@test.com',
            'password': 'WrongPass!',
        })
        client_user.refresh_from_db()
        assert client_user.login_attempts == initial_attempts + 1

    def test_login_resets_attempts_on_success(self, api_client, client_user):
        client_user.login_attempts = 3
        client_user.save()
        api_client.post('/api/v1/auth/login/', {
            'email': 'client@test.com',
            'password': 'TestPass123!',
        })
        client_user.refresh_from_db()
        assert client_user.login_attempts == 0

    def test_login_empty_fields_fails(self, api_client):
        response = api_client.post('/api/v1/auth/login/', {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestOTP:

    def test_verify_otp_success(self, api_client, client_user):
        otp = OTPVerification.objects.create(
            user=client_user,
            code='123456',
            phone=client_user.phone,
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        response = api_client.post('/api/v1/auth/verify-otp/', {
            'phone': client_user.phone,
            'code': '123456',
        })
        assert response.status_code == status.HTTP_200_OK
        client_user.refresh_from_db()
        assert client_user.is_phone_verified is True

    def test_verify_otp_expired_fails(self, api_client, client_user):
        OTPVerification.objects.create(
            user=client_user,
            code='654321',
            phone=client_user.phone,
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        response = api_client.post('/api/v1/auth/verify-otp/', {
            'phone': client_user.phone,
            'code': '654321',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_otp_wrong_code_fails(self, api_client, client_user):
        OTPVerification.objects.create(
            user=client_user,
            code='111111',
            phone=client_user.phone,
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        response = api_client.post('/api/v1/auth/verify-otp/', {
            'phone': client_user.phone,
            'code': '999999',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_resend_otp_success(self, api_client, client_user):
        response = api_client.post('/api/v1/auth/resend-otp/', {
            'phone': client_user.phone,
        })
        assert response.status_code == status.HTTP_200_OK
        assert OTPVerification.objects.filter(user=client_user, is_used=False).exists()

    def test_resend_otp_invalid_phone_fails(self, api_client):
        response = api_client.post('/api/v1/auth/resend-otp/', {
            'phone': '+237699999999',
        })
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestLogout:

    def test_logout_success(self, auth_client, client_user):
        login = auth_client.post('/api/v1/auth/login/', {
            'email': 'client@test.com',
            'password': 'TestPass123!',
        })
        if login.status_code == 200:
            refresh = login.data['data']['refresh']
            response = auth_client.post('/api/v1/auth/logout/', {'refresh': refresh})
            assert response.status_code == status.HTTP_200_OK


class TestProfile:

    def test_get_my_profile_authenticated(self, auth_client, client_user):
        response = auth_client.get('/api/v1/users/me/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['email'] == 'client@test.com'
        assert response.data['data']['role'] == 'client'

    def test_get_profile_unauthenticated_fails(self, api_client):
        response = api_client.get('/api/v1/users/me/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_profile_success(self, auth_client, client_user):
        response = auth_client.patch('/api/v1/users/me/', {
            'first_name': 'NouveauPrénom',
        })
        assert response.status_code == status.HTTP_200_OK
        client_user.refresh_from_db()
        assert client_user.first_name == 'NouveauPrénom'

    def test_mass_assignment_role_blocked(self, auth_client, client_user):
        """Le rôle ne peut pas être changé via le profil"""
        auth_client.patch('/api/v1/users/me/', {
            'role': 'admin',
            'is_validated': True,
        })
        client_user.refresh_from_db()
        assert client_user.role == 'client'
        assert client_user.is_validated is False

    def test_change_password_success(self, auth_client, client_user):
        response = auth_client.post('/api/v1/auth/change-password/', {
            'old_password': 'TestPass123!',
            'new_password': 'NewPass123!',
            'confirm_password': 'NewPass123!',
        })
        assert response.status_code == status.HTTP_200_OK

    def test_change_password_wrong_old_fails(self, auth_client):
        response = auth_client.post('/api/v1/auth/change-password/', {
            'old_password': 'WrongOld!',
            'new_password': 'NewPass123!',
            'confirm_password': 'NewPass123!',
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_forgot_password_success(self, api_client, client_user):
        response = api_client.post('/api/v1/auth/forgot-password/', {
            'email': 'client@test.com',
        })
        assert response.status_code == status.HTTP_200_OK

    def test_forgot_password_unknown_email_safe(self, api_client):
        """Ne révèle pas si l'email existe ou non"""
        response = api_client.post('/api/v1/auth/forgot-password/', {
            'email': 'nobody@test.com',
        })
        assert response.status_code == status.HTTP_200_OK
