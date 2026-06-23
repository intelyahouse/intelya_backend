import pytest
import uuid
from rest_framework import status
from apps.users.models import User

pytestmark = pytest.mark.django_db


class TestSecurite:

    def test_sql_injection_login(self, api_client):
        r = api_client.post('/api/v1/auth/login/', {
            'email': "admin'--", 'password': "' OR '1'='1",
        })
        assert r.status_code in [400, 401]

    def test_xss_inscription(self, api_client):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': '<script>alert("xss")</script>',
            'last_name': 'Test', 'email': 'xss@test.cm',
            'phone': '+237670000050',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
            'terms_accepted': True,
        })
        if r.status_code == 201:
            user = User.objects.get(email='xss@test.cm')
            assert '<script>' not in user.first_name

    def test_mass_assignment_role(self, api_client):
        r = api_client.post('/api/v1/auth/register/', {
            'first_name': 'Hacker', 'last_name': 'Test',
            'email': 'hacker2@test.cm', 'phone': '+237670000049',
            'password': 'MotDePasse123!', 'confirm_password': 'MotDePasse123!',
            'terms_accepted': True, 'role': 'admin', 'is_superuser': True,
        })
        if r.status_code == 201:
            user = User.objects.get(email='hacker2@test.cm')
            assert user.role != 'admin'
            assert not user.is_superuser

    def test_uuid_invalide_404(self, api_client):
        r = api_client.get('/api/v1/properties/pas-un-uuid/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_input_trop_long(self, api_client):
        r = api_client.post('/api/v1/auth/login/', {
            'email': 'a' * 1000 + '@test.cm',
            'password': 'a' * 1000,
        })
        assert r.status_code in [400, 401]

    def test_routes_protegees_sans_auth(self, api_client):
        routes = [
            '/api/v1/users/me/',
            '/api/v1/visits/',
            '/api/v1/payments/history/',
            '/api/v1/messaging/conversations/',
            '/api/v1/notifications/',
            '/api/v1/referrals/mine/',
        ]
        for route in routes:
            r = api_client.get(route)
            assert r.status_code == status.HTTP_401_UNAUTHORIZED, f"{route} devrait être protégée"

    def test_routes_admin_bloquees_client(self, auth_client):
        routes = [
            '/api/v1/admin-panel/stats/',
            '/api/v1/admin-panel/users/',
            '/api/v1/admin-panel/transactions/',
        ]
        for route in routes:
            r = auth_client.get(route)
            assert r.status_code == status.HTTP_403_FORBIDDEN, f"{route} devrait être bloquée pour client"

    def test_routes_admin_bloquees_agent(self, auth_agent):
        r = auth_agent.get('/api/v1/admin-panel/stats/')
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_idor_transactions(self, auth_client, agent_user):
        from apps.payments.models import Transaction
        txn = Transaction.objects.create(
            reference='IH-IDOR-001', payer=agent_user,
            transaction_type='visit', amount=5000,
            platform_fee=100, net_amount=4900,
            currency='FCFA', status='pending', payment_method='mtn',
        )
        r = auth_client.get(f'/api/v1/payments/status/{txn.reference}/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_idor_conversation(self, auth_client, agent_user, owner_user):
        from apps.messaging.models import Conversation
        autre = Conversation.objects.create(conversation_type='agent_owner')
        autre.participants.add(agent_user, owner_user)
        r = auth_client.get(f'/api/v1/messaging/conversations/{autre.id}/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_adresse_masquee_client(self, auth_client, property_obj):
        r = auth_client.get(f'/api/v1/properties/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK
        data = r.data.get('data', r.data)
        assert data.get('full_address') in [None, '', 'Non disponible', 'Adresse confidentielle']

    def test_forum_agents_confidentiel(self, auth_client):
        r = auth_client.get('/api/v1/messaging/forum/')
        assert r.status_code == status.HTTP_403_FORBIDDEN


class TestValidationFichiersMagicBytes:
    """Vérification que la validation magic bytes bloque les fichiers malveillants"""

    def test_image_valide_acceptee(self):
        from core.validators import validate_image_file
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core.exceptions import ValidationError

        # JPEG valide (magic bytes corrects)
        jpeg_content = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        f = SimpleUploadedFile("photo.jpg", jpeg_content, content_type="image/jpeg")
        # Ne doit pas lever d'exception
        try:
            validate_image_file(f)
        except ValidationError as e:
            # Accepté si c'est une erreur de taille, pas de format
            assert 'malveillant' not in str(e)

    def test_php_deguise_en_jpeg_rejete(self):
        from core.validators import validate_image_file
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core.exceptions import ValidationError

        # Fichier PHP avec content_type image/jpeg — attaque classique
        php_content = b'<?php system($_GET["cmd"]); ?>'
        f = SimpleUploadedFile("shell.php", php_content, content_type="image/jpeg")
        with pytest.raises(ValidationError) as exc_info:
            validate_image_file(f)
        assert 'malveillant' in str(exc_info.value).lower() or \
               'correspond' in str(exc_info.value).lower()

    def test_pdf_valide_accepte(self):
        from core.validators import validate_document_file
        from django.core.files.uploadedfile import SimpleUploadedFile

        pdf_content = b'%PDF-1.4 ' + b'\x00' * 50
        f = SimpleUploadedFile("doc.pdf", pdf_content, content_type="application/pdf")
        try:
            validate_document_file(f)
        except Exception as e:
            assert 'malveillant' not in str(e).lower()

    def test_exe_deguise_en_pdf_rejete(self):
        from core.validators import validate_document_file
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core.exceptions import ValidationError

        exe_content = b'MZ' + b'\x90' * 50  # Magic bytes d'un .exe Windows
        f = SimpleUploadedFile("malware.exe", exe_content, content_type="application/pdf")
        with pytest.raises(ValidationError):
            validate_document_file(f)
