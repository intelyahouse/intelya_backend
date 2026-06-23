import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from apps.users.models import User, OTPVerification, Blacklist

pytestmark = pytest.mark.django_db


class TestInscription:

    def test_inscription_succes(self, api_client):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Jean', 'last_name': 'Dupont',
            'email': 'jean@test.cm', 'phone': '+237670000099',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
        })
        assert r.status_code == status.HTTP_201_CREATED

    def test_inscription_genere_referral_code(self, api_client):
        api_client.post('/api/v1/auth/register/', {
            'first_name': 'Marie', 'last_name': 'Tabi',
            'email': 'marie@test.cm', 'phone': '+237670000098',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
        })
        user = User.objects.get(email='marie@test.cm')
        assert user.referral_code is not None
        assert len(user.referral_code) >= 6

    def test_inscription_avec_code_parrainage(self, api_client, client_user):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Paul', 'last_name': 'Biya',
            'email': 'paul@test.cm', 'phone': '+237670000097',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
            'referral_code': client_user.referral_code,
        })
        assert r.status_code == status.HTTP_201_CREATED

    def test_inscription_email_duplique(self, api_client, client_user):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test', 'last_name': 'User',
            'email': client_user.email, 'phone': '+237670000096',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_inscription_telephone_duplique(self, api_client, client_user):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test', 'last_name': 'User',
            'email': 'nouveau@test.cm', 'phone': client_user.phone,
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_inscription_mot_de_passe_trop_court(self, api_client):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test', 'last_name': 'User',
            'email': 'test@test.cm', 'phone': '+237670000095',
            'password': '123', 'confirm_password': '123',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_inscription_mots_de_passe_differents(self, api_client):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test', 'last_name': 'User',
            'email': 'test2@test.cm', 'phone': '+237670000094',
            'password': 'MotDePasse123!', 'confirm_password': 'Autre456!',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_inscription_champs_manquants(self, api_client):
        r = api_client.post('/api/v1/auth/register/', {})
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_inscription_telephone_blackliste(self, api_client):
        Blacklist.objects.create(phone='+237670000092', reason='Fraude')
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test', 'last_name': 'User',
            'email': 'test5@test.cm', 'phone': '+237670000092',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_mass_assignment_role_bloque(self, api_client):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Hacker', 'last_name': 'Test',
            'email': 'hacker@test.cm', 'phone': '+237670000091',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
            'role': 'admin', 'is_superuser': True,
        })
        if r.status_code == 201:
            user = User.objects.get(email='hacker@test.cm')
            assert user.role != 'admin'
            assert not user.is_superuser


class TestConnexion:

    def test_connexion_succes(self, api_client, client_user):
        r = api_client.post('/api/v1/auth/login/', {
            'email': client_user.email, 'password': 'TestPass123!',
        })
        assert r.status_code == status.HTTP_200_OK
        assert 'access' in r.data['data']
        assert 'refresh' in r.data['data']

    def test_connexion_mauvais_mot_de_passe(self, api_client, client_user):
        r = api_client.post('/api/v1/auth/login/', {
            'email': client_user.email, 'password': 'MauvaisMDP!',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_connexion_utilisateur_bloque(self, api_client, client_user):
        client_user.is_blocked = True
        client_user.save()
        r = api_client.post('/api/v1/auth/login/', {
            'email': client_user.email, 'password': 'TestPass123!',
        })
        assert r.status_code in [401, 403]

    def test_connexion_email_inexistant(self, api_client):
        r = api_client.post('/api/v1/auth/login/', {
            'email': 'inexistant@test.cm', 'password': 'TestPass123!',
        })
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_connexion_remet_compteur_zero(self, api_client, client_user):
        client_user.login_attempts = 3
        client_user.save()
        api_client.post('/api/v1/auth/login/', {
            'email': client_user.email, 'password': 'TestPass123!',
        })
        client_user.refresh_from_db()
        assert client_user.login_attempts == 0

    def test_refresh_token(self, api_client, client_user):
        token = RefreshToken.for_user(client_user)
        r = api_client.post('/api/v1/auth/token/refresh/', {
            'refresh': str(token)
        })
        assert r.status_code == status.HTTP_200_OK
        assert 'access' in r.data

    def test_refresh_token_invalide(self, api_client):
        r = api_client.post('/api/v1/auth/token/refresh/', {
            'refresh': 'token_bidon_invalide'
        })
        assert r.status_code in [400, 401]

    def test_deconnexion(self, api_client, client_user):
        login = api_client.post('/api/v1/auth/login/', {
            'email': client_user.email, 'password': 'TestPass123!',
        })
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['data']['access']}")
        r = api_client.post('/api/v1/auth/logout/', {
            'refresh': login.data['data']['refresh']
        })
        assert r.status_code in [200, 205]

    def test_connexion_champs_vides(self, api_client):
        r = api_client.post('/api/v1/auth/login/', {
            'email': '', 'password': '',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST


class TestOTP:

    def test_otp_valide(self, api_client, client_user):
        OTPVerification.objects.create(
            user=client_user, phone=client_user.phone,
            code='123456',
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        r = api_client.post('/api/v1/auth/verify-otp/', {
            'phone': client_user.phone, 'code': '123456',
        })
        assert r.status_code == status.HTTP_200_OK

    def test_otp_expire_rejete(self, api_client, client_user):
        OTPVerification.objects.create(
            user=client_user, phone=client_user.phone,
            code='999999',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        r = api_client.post('/api/v1/auth/verify-otp/', {
            'phone': client_user.phone, 'code': '999999',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_otp_deja_utilise(self, api_client, client_user):
        OTPVerification.objects.create(
            user=client_user, phone=client_user.phone,
            code='111111', is_used=True,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        r = api_client.post('/api/v1/auth/verify-otp/', {
            'phone': client_user.phone, 'code': '111111',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_renvoyer_otp(self, api_client, client_user):
        r = api_client.post('/api/v1/auth/resend-otp/', {
            'phone': client_user.phone,
        })
        assert r.status_code in [200, 201]


class TestProfil:

    def test_voir_profil(self, auth_client, client_user):
        r = auth_client.get('/api/v1/users/me/')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['data']['email'] == client_user.email

    def test_modifier_profil(self, auth_client):
        r = auth_client.patch('/api/v1/users/me/', {'first_name': 'Nouveau'})
        assert r.status_code == status.HTTP_200_OK

    def test_profil_non_authentifie(self, api_client):
        r = api_client.get('/api/v1/users/me/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_mot_de_passe_oublie(self, api_client, client_user):
        r = api_client.post('/api/v1/auth/forgot-password/', {
            'email': client_user.email,
        })
        assert r.status_code == status.HTTP_200_OK
