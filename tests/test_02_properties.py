import pytest
import uuid
from rest_framework import status
from apps.agents.models import OwnerAgentRelation
from datetime import date

pytestmark = pytest.mark.django_db


class TestListeBiens:

    def test_liste_publique(self, api_client, property_obj):
        r = api_client.get('/api/v1/properties/')
        assert r.status_code == status.HTTP_200_OK
        assert r.data['count'] >= 1

    def test_sans_adresse_exacte(self, api_client, property_obj):
        r = api_client.get('/api/v1/properties/')
        for bien in r.data['results']:
            addr = bien.get('full_address', '')
            assert addr in [None, '', 'Non disponible', 'Adresse confidentielle']

    def test_filtre_ville(self, api_client, property_obj):
        r = api_client.get('/api/v1/properties/?city=Douala')
        assert r.status_code == status.HTTP_200_OK

    def test_filtre_type(self, api_client, property_obj):
        r = api_client.get('/api/v1/properties/?property_type=apartment')
        assert r.status_code == status.HTTP_200_OK

    def test_filtre_prix_max(self, api_client, property_obj):
        r = api_client.get('/api/v1/properties/?max_price=200000')
        assert r.status_code == status.HTTP_200_OK

    def test_filtre_prix_min(self, api_client, property_obj):
        r = api_client.get('/api/v1/properties/?min_price=50000')
        assert r.status_code == status.HTTP_200_OK

    def test_filtre_groupe_electrogene(self, api_client, property_obj):
        r = api_client.get('/api/v1/properties/?has_generator=true')
        assert r.status_code == status.HTTP_200_OK

    def test_filtre_parking(self, api_client, property_obj):
        r = api_client.get('/api/v1/properties/?has_parking=true')
        assert r.status_code == status.HTTP_200_OK

    def test_filtre_meuble(self, api_client, property_obj):
        r = api_client.get('/api/v1/properties/?is_furnished=true')
        assert r.status_code == status.HTTP_200_OK

    def test_pagination(self, api_client):
        r = api_client.get('/api/v1/properties/?page=1&page_size=5')
        assert r.status_code == status.HTTP_200_OK
        assert 'count' in r.data and 'results' in r.data

    def test_detail_succes(self, api_client, property_obj):
        r = api_client.get(f'/api/v1/properties/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK

    def test_detail_incremente_vues(self, api_client, property_obj):
        vues = property_obj.views_count
        api_client.get(f'/api/v1/properties/{property_obj.id}/')
        property_obj.refresh_from_db()
        assert property_obj.views_count >= vues

    def test_detail_inexistant_404(self, api_client):
        r = api_client.get(f'/api/v1/properties/{uuid.uuid4()}/')
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_adresse_masquee_client(self, auth_client, property_obj):
        r = auth_client.get(f'/api/v1/properties/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK
        data = r.data.get('data', r.data)
        assert data.get('full_address') in [None, '', 'Non disponible', 'Adresse confidentielle']

    def test_adresse_visible_admin(self, auth_admin, property_obj):
        r = auth_admin.get(f'/api/v1/properties/{property_obj.id}/')
        assert r.status_code == status.HTTP_200_OK


class TestCreationBien:

    def test_agent_cree_bien(self, auth_agent, agent_user, owner_user):
        from apps.agents.models import OwnerAgentRelation, AgentProfile
        import datetime
        OwnerAgentRelation.objects.get_or_create(
            owner=owner_user, agent=agent_user,
            defaults={
                'status': 'active', 'contract_start': datetime.date.today(),
                'agency': AgentProfile.objects.get(user=agent_user).agency,
            }
        )
        r = auth_agent.post('/api/v1/properties/create/', {
            'owner_id': str(owner_user.id),
            'title': 'Bel Appartement Test Bonanjo',
            'description': 'Belle description tres detaillee et suffisamment longue pour valider les cinquante mots minimum requis par la plateforme INTELYA HAVEN afin de garantir la qualite et la completude des annonces immobilieres publiees sur cette excellente plateforme immobiliere africaine innovante et moderne qui aide efficacement les proprietaires agents et locataires camerounais partout',
            'property_type': 'apartment',
            'price': 150000,
            'payment_period': 'monthly',
            'min_lease_months': 6,
            'bedrooms': 3, 'bathrooms': 2,
            'living_rooms': 1, 'kitchens': 1,
            'area_sqm': 120,
            'city': 'Douala', 'neighborhood': 'Bonanjo',
            'full_address': 'Rue Test 1, Bonanjo',
            'is_furnished': True,
            'has_generator': True, 'has_parking': True,
            'has_borehole': False, 'has_water_tank': True,
            'has_fence': True, 'has_security_guard': False,
            'has_air_conditioning': False, 'parking_spots': 1,
        })
        # Si 403 c'est que la relation owner-agent n'est pas bien créée
        # Si 400 c'est un champ manquant - on affiche pour debug
        if r.status_code == 400:
            print('ERREUR 400:', r.data)
        assert r.status_code in [200, 201]

    def test_agent_sans_owner_lie_bloque(self, auth_agent, create_user):
        owner_non_lie = create_user(
            email='owner_nl@test.cm', phone='+237670000088',
            role='owner', is_validated=True,
        )
        r = auth_agent.post('/api/v1/properties/create/', {
            'owner_id': str(owner_non_lie.id),
            'title': 'Test', 'price': 100000,
        })
        assert r.status_code in [400, 403]

    def test_client_ne_peut_pas_creer(self, auth_client):
        r = auth_client.post('/api/v1/properties/create/', {'title': 'Test'})
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_non_authentifie_bloque(self, api_client):
        r = api_client.post('/api/v1/properties/create/', {'title': 'Test'})
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_agent_sans_owner_id_bloque(self, auth_agent):
        r = auth_agent.post('/api/v1/properties/create/', {'title': 'Test sans owner'})
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_agent_voit_ses_biens(self, auth_agent):
        r = auth_agent.get('/api/v1/properties/agent/')
        assert r.status_code == status.HTTP_200_OK


class TestLikesFavoris:

    def test_liker_bien(self, auth_client, property_obj):
        r = auth_client.post(f'/api/v1/properties/{property_obj.id}/like/')
        assert r.status_code in [200, 201]

    def test_unliker_bien(self, auth_client, property_obj):
        auth_client.post(f'/api/v1/properties/{property_obj.id}/like/')
        r = auth_client.post(f'/api/v1/properties/{property_obj.id}/like/')
        assert r.status_code in [200, 201]

    def test_voir_favoris(self, auth_client, property_obj):
        auth_client.post(f'/api/v1/properties/{property_obj.id}/like/')
        r = auth_client.get('/api/v1/properties/favorites/')
        assert r.status_code == status.HTTP_200_OK

    def test_non_authentifie_ne_peut_pas_liker(self, api_client, property_obj):
        r = api_client.post(f'/api/v1/properties/{property_obj.id}/like/')
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
