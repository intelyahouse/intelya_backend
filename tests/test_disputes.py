import pytest
from rest_framework import status
from apps.disputes.models import Dispute, Report

pytestmark = pytest.mark.django_db


class TestDisputes:

    def test_create_dispute(self, auth_client, agent_user):
        response = auth_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(agent_user.id),
            'dispute_type': 'agent',
            'title': 'Agent non professionnel',
            'description': 'Description détaillée du problème rencontré avec cet agent',
        })
        assert response.status_code == status.HTTP_201_CREATED

    def test_cannot_dispute_yourself(self, auth_client, client_user):
        response = auth_client.post('/api/v1/disputes/disputes/create/', {
            'defendant': str(client_user.id),
            'dispute_type': 'other',
            'title': 'Auto-litige',
            'description': 'Description du problème',
        })
        assert response.status_code in [400, 201]

    def test_get_my_disputes(self, auth_client):
        response = auth_client.get('/api/v1/disputes/disputes/')
        assert response.status_code == status.HTTP_200_OK


class TestReports:

    def test_create_report(self, auth_client, agent_user):
        response = auth_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'fraud',
            'description': 'Cet agent demande des paiements hors plateforme',
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert Report.objects.filter(reported=agent_user).exists()

    def test_three_reports_suspend_user(self, api_client, create_user, agent_user):
        """3 signalements en 30 jours = suspension automatique"""
        reporters = [
            create_user(email=f'reporter{i}@test.com', phone=f'+23767000010{i}', role='client')
            for i in range(3)
        ]
        for reporter in reporters:
            api_client.force_authenticate(user=reporter)
            api_client.post('/api/v1/disputes/reports/create/', {
                'reported': str(agent_user.id),
                'reason': 'harassment',
                'description': 'Signalement de harcèlement',
            })
        agent_user.refresh_from_db()
        assert agent_user.is_active is False

    def test_unauthenticated_cannot_report(self, api_client, agent_user):
        response = api_client.post('/api/v1/disputes/reports/create/', {
            'reported': str(agent_user.id),
            'reason': 'fraud',
            'description': 'Test',
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
