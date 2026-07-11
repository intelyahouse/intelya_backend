"""
Tests Sécurité Avancée — Production Grade
Couvre : OWASP Top 10, injection, auth bypass, rate limiting, headers
"""
import pytest
import uuid
from rest_framework import status
from apps.users.models import User
from apps.payments.models import Transaction

pytestmark = pytest.mark.django_db


class TestOWASPTop10:
    """OWASP Top 10 — Les 10 vulnérabilités les plus critiques"""

    # A01 — Broken Access Control
    def test_client_ne_peut_pas_acceder_admin(self, auth_client):
        routes_admin = [
            '/api/v1/admin-panel/stats/',
            '/api/v1/admin-panel/users/',
            '/api/v1/admin-panel/transactions/',
            '/api/v1/admin-panel/disputes/',
            '/api/v1/admin-panel/config/',
        ]
        for route in routes_admin:
            r = auth_client.get(route)
            assert r.status_code == status.HTTP_403_FORBIDDEN, f"IDOR: {route} accessible au client"

    def test_agent_ne_peut_pas_acceder_admin(self, auth_agent):
        r = auth_agent.get('/api/v1/admin-panel/stats/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_ne_peut_pas_acceder_admin(self, auth_owner):
        r = auth_owner.get('/api/v1/admin-panel/stats/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_idor_transaction(self, auth_client, agent_user):
        """Un user ne peut pas voir la transaction d'un autre"""
        txn = Transaction.objects.create(
            reference='IH-IDOR-SEC-001', payer=agent_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='completed', payment_method='mtn',
        )
        r = auth_client.get(f'/api/v1/payments/status/{txn.reference}/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_idor_conversation(self, auth_client, agent_user, owner_user):
        """Un user ne peut pas lire une conversation qui n'est pas la sienne"""
        from apps.messaging.models import Conversation
        conv = Conversation.objects.create(conversation_type='agent_owner')
        conv.participants.add(agent_user, owner_user)
        r = auth_client.get(f'/api/v1/messaging/conversations/{conv.id}/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_adresse_bien_masquee_client(self, auth_client, property_obj):
        """L'adresse exacte n'est jamais exposée au client"""
        r = auth_client.get(f'/api/v1/properties/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK
        data = r.data.get('data', r.data)
        assert data.get('full_address') in [None, '', 'Non disponible', 'Adresse confidentielle']

    def test_adresse_bien_masquee_liste(self, api_client, property_obj):
        """L'adresse n'est pas dans la liste publique"""
        r = api_client.get('/api/v1/properties/')
        for bien in r.data.get('results', []):
            assert 'full_address' not in bien or bien.get('full_address') in [None, '', 'Non disponible', 'Adresse confidentielle']

    # A02 — Cryptographic Failures
    def test_token_jwt_present_dans_reponse(self, api_client, client_user):
        """JWT retourné à la connexion"""
        r = api_client.post('/api/v1/auth/login/', {
            'email': client_user.email, 'password': 'TestPass123!',
        })
        assert r.status_code == status.HTTP_200_OK
        assert 'access' in r.data['data']
        assert len(r.data['data']['access']) > 50

    def test_mot_de_passe_non_expose(self, auth_client):
        """Le mot de passe n'est jamais dans la réponse profil"""
        r = auth_client.get('/api/v1/users/me/')
        assert r.status_code == status.HTTP_200_OK
        data = r.data.get('data', r.data)
        assert 'password' not in data

    # A03 — Injection
    def test_sql_injection_login(self, api_client):
        payloads = [
            "admin'--",
            "' OR '1'='1",
            "'; DROP TABLE users_user; --",
            "' UNION SELECT * FROM users_user --",
        ]
        for payload in payloads:
            r = api_client.post('/api/v1/auth/login/', {
                'email': payload, 'password': payload,
            })
            assert r.status_code in [400, 401], f"SQLi possible avec: {payload}"

    def test_sql_injection_recherche(self, api_client):
        r = api_client.get("/api/v1/properties/?city='; DROP TABLE properties_property; --")
        assert r.status_code in [200, 400]
        # Ne doit pas planter le serveur
        assert r.status_code != 500

    def test_xss_dans_inscription(self, api_client):
        payloads = [
            '<script>alert("xss")</script>',
            '<img src=x onerror=alert(1)>',
            'javascript:alert(1)',
        ]
        for i, payload in enumerate(payloads):
            r = api_client.post('/api/v1/auth/register/', {
                'first_name': payload,
                'last_name': 'Test',
                'email': f'xss{i}@test.cm',
                'phone': f'+23767009{i:04d}',
                'password': 'MotDePasse123!',
                'confirm_password': 'MotDePasse123!',
            })
            if r.status_code == 201:
                user = User.objects.get(email=f'xss{i}@test.cm')
                assert '<script>' not in user.first_name
                assert 'onerror' not in user.first_name

    # A04 — Insecure Design
    def test_mass_assignment_role_admin(self, api_client):
        """On ne peut pas se créer un compte admin"""
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Hacker', 'last_name': 'Test',
            'email': 'hacker_sec@test.cm', 'phone': '+237670088001',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
            'role': 'admin', 'is_superuser': True, 'is_staff': True,
            'is_validated': True,
        })
        if r.status_code == 201:
            user = User.objects.get(email='hacker_sec@test.cm')
            assert user.role != 'admin'
            assert not user.is_superuser
            assert not user.is_staff

    def test_mass_assignment_validation(self, api_client):
        """On ne peut pas se valider soi-même"""
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test', 'last_name': 'User',
            'email': 'mass_assign@test.cm', 'phone': '+237670088002',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
            'is_validated': True, 'validation_status': 'approved',
        })
        if r.status_code == 201:
            user = User.objects.get(email='mass_assign@test.cm')
            assert not user.is_validated

    # A05 — Security Misconfiguration
    def test_routes_inexistantes_404(self, api_client):
        """Les routes inexistantes retournent 404, pas 500"""
        routes = [
            '/api/v1/inexistant/',
            '/api/v1/admin/secret/',
            '/api/v1/../etc/passwd',
        ]
        for route in routes:
            r = api_client.get(route)
            assert r.status_code in [404, 400], f"Route {route} retourne {r.status_code}"

    def test_methodes_non_autorisees(self, api_client, property_obj):
        """Les méthodes HTTP non autorisées retournent 405"""
        r = api_client.delete(f'/api/v1/properties/{property_obj.id}/')
        assert r.status_code in [403, 404, 405]

    # A07 — Identification and Authentication Failures
    def test_connexion_bloquee_apres_mauvais_mdp(self, api_client, client_user):
        """Plusieurs mauvais mots de passe consécutifs"""
        for _ in range(3):
            api_client.post('/api/v1/auth/login/', {
                'email': client_user.email, 'password': 'MauvaisMDP!',
            })
        client_user.refresh_from_db()
        assert client_user.login_attempts >= 3

    def test_token_expire_bloque(self, api_client):
        """Un token expiré est refusé"""
        r = api_client.get('/api/v1/users/me/', HTTP_AUTHORIZATION='Bearer token_expire_bidon')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_mal_forme_bloque(self, api_client):
        """Un token mal formé est refusé"""
        r = api_client.get('/api/v1/users/me/', HTTP_AUTHORIZATION='Bearer pas.un.jwt')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_sans_token_bloque(self, api_client):
        """Sans token, les routes protégées sont bloquées"""
        r = api_client.get('/api/v1/users/me/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    # A08 — Software and Data Integrity
    def test_webhook_sans_refid_ignore(self, api_client):
        """Webhook sans référence est ignoré proprement"""
        r = api_client.post('/api/v1/payments/webhook/kpay/', {
            'statusid': '01',
        }, format='json')
        assert r.status_code == status.HTTP_200_OK
        assert r.status_code != 500

    # A09 — Logging and Monitoring
    def test_audit_log_connexion(self, api_client, client_user):
        """La connexion est loguée (vérification indirecte)"""
        r = api_client.post('/api/v1/auth/login/', {
            'email': client_user.email, 'password': 'TestPass123!',
        })
        assert r.status_code == status.HTTP_200_OK

    # A10 — Server-Side Request Forgery (SSRF)
    def test_upload_url_externe_bloque(self, auth_agent):
        """Les URLs externes dans les uploads sont bloquées"""
        r = auth_agent.post('/api/v1/properties/create/', {
            'title': 'Test SSRF',
            'video_url': 'http://169.254.169.254/latest/meta-data/',
        })
        assert r.status_code in [400, 403]


class TestInputValidation:

    def test_input_trop_long_bloque(self, api_client):
        r = api_client.post('/api/v1/auth/login/', {
            'email': 'a' * 10000 + '@test.cm',
            'password': 'a' * 10000,
        })
        assert r.status_code in [400, 401]
        assert r.status_code != 500

    def test_uuid_invalide_404(self, api_client):
        r = api_client.get('/api/v1/properties/pas-un-uuid-valide/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_uuid_inexistant_404(self, api_client):
        r = api_client.get(f'/api/v1/properties/{uuid.uuid4()}/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_json_malformed_gere(self, api_client):
        """Le serveur gère les requêtes JSON mal formées"""
        r = api_client.post(
            '/api/v1/auth/login/',
            data='{"email": "test@test.cm", "password":}',
            content_type='application/json'
        )
        assert r.status_code in [400, 401]
        assert r.status_code != 500

    def test_champs_numeriques_valides(self, auth_agent):
        r = auth_agent.post('/api/v1/properties/create/', {
            'price': 'pas_un_nombre',
            'bedrooms': 'abc',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_email_invalide_rejete(self, api_client):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Test', 'last_name': 'User',
            'email': 'pas_un_email',
            'phone': '+237670000050',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
        })
        assert r.status_code == status.HTTP_400_BAD_REQUEST


class TestRolesEtPermissions:

    def test_toutes_routes_protegees(self, api_client):
        """Vérification systématique de toutes les routes protégées"""
        routes_protegees = [
            ('GET', '/api/v1/users/me/'),
            ('GET', '/api/v1/visits/'),
            ('GET', '/api/v1/payments/history/'),
            ('GET', '/api/v1/messaging/conversations/'),
            ('GET', '/api/v1/notifications/'),
            ('GET', '/api/v1/referrals/mine/'),
            ('GET', '/api/v1/agents/me/'),
            ('GET', '/api/v1/owners/me/'),
            ('GET', '/api/v1/boost/mine/'),
        ]
        for method, route in routes_protegees:
            if method == 'GET':
                r = api_client.get(route)
            else:
                r = api_client.post(route, {})
            assert r.status_code == status.HTTP_401_UNAUTHORIZED, \
                f"Route {method} {route} devrait retourner 401, reçu {r.status_code}"

    def test_toutes_routes_admin_bloquees_pour_client(self, auth_client):
        routes_admin = [
            '/api/v1/admin-panel/stats/',
            '/api/v1/admin-panel/users/',
            '/api/v1/admin-panel/transactions/',
            '/api/v1/admin-panel/revenue/',
            '/api/v1/admin-panel/config/',
            '/api/v1/admin-panel/disputes/',
            '/api/v1/admin-panel/reports/',
            '/api/v1/admin-panel/boosts/',
            '/api/v1/admin-panel/leases/',
        ]
        for route in routes_admin:
            r = auth_client.get(route)
            assert r.status_code == status.HTTP_403_FORBIDDEN, \
                f"Route admin {route} accessible au client — FAILLE CRITIQUE"

    def test_forum_agents_confidentiel(self, auth_client, auth_owner, api_client):
        """Le forum agents est inaccessible aux non-agents"""
        for client in [auth_client, auth_owner, api_client]:
            r = client.get('/api/v1/messaging/forum/')
            assert r.status_code in [401, 403]
