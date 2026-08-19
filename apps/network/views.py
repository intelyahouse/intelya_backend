from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema

from core.permissions import IsAgent
from core.utils import success_response, error_response
from apps.agencies.models import Agency
from apps.agents.models import ClientAgentRelation
from apps.properties.models import Property
from apps.notifications.utils import (
    notify_collaboration_proposed, notify_collaboration_countered,
    notify_collaboration_accepted, notify_collaboration_rejected,
)
from .models import Collaboration
from .serializers import NetworkAgencySerializer, CollaborationSerializer
from .services import create_collaboration, counter_propose, respond_collaboration


def _agent_agency(user):
    return getattr(getattr(user, 'agent_profile', None), 'agency', None)


def _parse_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None
    if amount < 0:
        return None
    return amount


class AgencySearchView(APIView):
    """Recherche d'agences pour collaboration -- reserve aux agents (le Network
    est un espace professionnel, aucun acces client/proprietaire)."""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Network'], summary="Rechercher une agence")
    def get(self, request):
        my_agency = _agent_agency(request.user)
        search = request.query_params.get('search', '')
        city = request.query_params.get('city', '')

        agencies = Agency.objects.exclude(id=my_agency.id if my_agency else None)
        if search:
            agencies = agencies.filter(name__icontains=search)
        if city:
            agencies = agencies.filter(agents__working_city__icontains=city)

        agencies = agencies.annotate(member_count=Count('agents', distinct=True)).distinct()[:50]

        data = [
            NetworkAgencySerializer({
                'id': a.id, 'name': a.name,
                'member_count': a.member_count, 'is_solo': a.is_solo,
            }).data
            for a in agencies
        ]
        return Response(success_response(data))


class CollaborationListCreateView(APIView):
    """Lister mes collaborations (mon agence, cote client ou cote bien), ou
    en proposer une nouvelle sur un bien detenu par une autre agence."""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Network'], summary="Mes collaborations")
    def get(self, request):
        my_agency = _agent_agency(request.user)
        if not my_agency:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)

        collaborations = Collaboration.objects.filter(
            Q(client_agency=my_agency) | Q(property_agency=my_agency)
        ).select_related(
            'property', 'client', 'client_agency', 'property_agency',
            'initiated_by', 'last_proposed_by_agency', 'responded_by',
        ).prefetch_related('proposals__proposed_by', 'proposals__proposed_by_agency').order_by('-updated_at')

        prop_status = request.query_params.get('status')
        if prop_status:
            collaborations = collaborations.filter(status=prop_status)

        return Response(success_response(CollaborationSerializer(collaborations, many=True).data))

    @extend_schema(tags=['Network'], summary="Proposer une collaboration")
    def post(self, request):
        my_agency = _agent_agency(request.user)
        if not my_agency:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)

        property_id = request.data.get('property_id')
        try:
            prop = Property.objects.select_related('agent__agent_profile__agency').get(id=property_id)
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=status.HTTP_404_NOT_FOUND)

        property_agency = _agent_agency(prop.agent) if prop.agent else None
        if property_agency is None:
            return Response(error_response("Ce bien n'a pas d'agence gestionnaire"), status=status.HTTP_400_BAD_REQUEST)
        if property_agency.id == my_agency.id:
            return Response(
                error_response("Ce bien appartient deja a votre agence"),
                status=status.HTTP_400_BAD_REQUEST
            )

        client = None
        client_id = request.data.get('client_id')
        if client_id:
            relation = ClientAgentRelation.objects.filter(
                client_id=client_id, agency=my_agency, is_active=True
            ).select_related('client').first()
            if not relation:
                return Response(
                    error_response("Ce client n'est pas lie a votre agence"),
                    status=status.HTTP_400_BAD_REQUEST
                )
            client = relation.client

        client_amount = _parse_amount(request.data.get('client_agency_amount'))
        property_amount = _parse_amount(request.data.get('property_agency_amount'))
        if client_amount is None or property_amount is None:
            return Response(
                error_response("client_agency_amount et property_agency_amount doivent etre des montants valides"),
                status=status.HTTP_400_BAD_REQUEST
            )

        collaboration = create_collaboration(
            initiator=request.user, property_obj=prop,
            client_agency=my_agency, property_agency=property_agency,
            client_agency_amount=client_amount, property_agency_amount=property_amount,
            client=client,
        )

        other_agents = [a.user for a in property_agency.agents.select_related('user').all()]
        notify_collaboration_proposed(other_agents, prop.title, my_agency.name)

        return Response(success_response(
            CollaborationSerializer(collaboration).data, "Collaboration proposee"
        ), status=status.HTTP_201_CREATED)


class CollaborationRespondView(APIView):
    """Accepter ou refuser une collaboration -- reserve a l'agence qui n'est
    pas a l'origine de la derniere proposition."""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Network'], summary="Repondre a une collaboration")
    def post(self, request, collaboration_id):
        my_agency = _agent_agency(request.user)
        if not my_agency:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)

        try:
            collaboration = Collaboration.objects.select_related(
                'client_agency', 'property_agency', 'property', 'last_proposed_by_agency'
            ).get(id=collaboration_id, status='proposed')
        except (Collaboration.DoesNotExist, ValueError):
            return Response(error_response("Collaboration introuvable"), status=status.HTTP_404_NOT_FOUND)

        if my_agency.id not in (collaboration.client_agency_id, collaboration.property_agency_id):
            return Response(error_response("Cette collaboration ne concerne pas votre agence"), status=status.HTTP_403_FORBIDDEN)
        if collaboration.last_proposed_by_agency_id == my_agency.id:
            return Response(
                error_response("Vous ne pouvez pas repondre a votre propre proposition"),
                status=status.HTTP_400_BAD_REQUEST
            )

        action = request.data.get('action')
        if action not in ('accept', 'reject'):
            return Response(error_response("Action invalide. Utilisez 'accept' ou 'reject'"), status=status.HTTP_400_BAD_REQUEST)

        collaboration = respond_collaboration(collaboration, request.user, accept=(action == 'accept'))

        if collaboration.initiated_by_id:
            if action == 'accept':
                notify_collaboration_accepted(collaboration.initiated_by, collaboration.property.title, my_agency.name)
            else:
                notify_collaboration_rejected(collaboration.initiated_by, collaboration.property.title, my_agency.name)

        return Response(success_response(CollaborationSerializer(collaboration).data))


class CollaborationCounterProposeView(APIView):
    """Contre-proposer une nouvelle repartition sur une collaboration en cours."""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Network'], summary="Contre-proposer une repartition")
    def post(self, request, collaboration_id):
        my_agency = _agent_agency(request.user)
        if not my_agency:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)

        try:
            collaboration = Collaboration.objects.select_related(
                'client_agency', 'property_agency', 'property'
            ).get(id=collaboration_id, status='proposed')
        except (Collaboration.DoesNotExist, ValueError):
            return Response(error_response("Collaboration introuvable"), status=status.HTTP_404_NOT_FOUND)

        if my_agency.id not in (collaboration.client_agency_id, collaboration.property_agency_id):
            return Response(error_response("Cette collaboration ne concerne pas votre agence"), status=status.HTTP_403_FORBIDDEN)

        client_amount = _parse_amount(request.data.get('client_agency_amount'))
        property_amount = _parse_amount(request.data.get('property_agency_amount'))
        if client_amount is None or property_amount is None:
            return Response(
                error_response("client_agency_amount et property_agency_amount doivent etre des montants valides"),
                status=status.HTTP_400_BAD_REQUEST
            )

        collaboration = counter_propose(
            collaboration, proposer=request.user, proposer_agency=my_agency,
            client_agency_amount=client_amount, property_agency_amount=property_amount,
        )

        other_agency = (
            collaboration.property_agency if my_agency.id == collaboration.client_agency_id
            else collaboration.client_agency
        )
        other_agents = [a.user for a in other_agency.agents.select_related('user').all()]
        notify_collaboration_countered(other_agents, collaboration.property.title, my_agency.name)

        return Response(success_response(CollaborationSerializer(collaboration).data))


class CollaborationCancelView(APIView):
    """Annuler une collaboration encore en negociation (n'importe quelle
    agence partie prenante peut annuler)."""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Network'], summary="Annuler une collaboration")
    def post(self, request, collaboration_id):
        my_agency = _agent_agency(request.user)
        if not my_agency:
            return Response(error_response("Profil agent introuvable"), status=status.HTTP_404_NOT_FOUND)

        try:
            collaboration = Collaboration.objects.get(id=collaboration_id, status='proposed')
        except (Collaboration.DoesNotExist, ValueError):
            return Response(error_response("Collaboration introuvable"), status=status.HTTP_404_NOT_FOUND)

        if my_agency.id not in (collaboration.client_agency_id, collaboration.property_agency_id):
            return Response(error_response("Cette collaboration ne concerne pas votre agence"), status=status.HTTP_403_FORBIDDEN)

        collaboration.status = 'cancelled'
        collaboration.responded_by = request.user
        from django.utils import timezone
        collaboration.responded_at = timezone.now()
        collaboration.save(update_fields=['status', 'responded_by', 'responded_at', 'updated_at'])

        return Response(success_response(message="Collaboration annulee"))
