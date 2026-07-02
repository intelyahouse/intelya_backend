from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from .models import AgentProfile, ClientAgentRelation, AgentAvailabilitySlot
from .serializers import (
    AgentProfileSerializer, PublicAgentSerializer,
    AvailabilitySlotSerializer
)
from core.permissions import IsAgent
from core.utils import success_response, error_response

User = get_user_model()


class AgentListView(APIView):
    """Liste des agents pour clients et propriétaires sans agent — classés par boost puis score"""
    permission_classes = [AllowAny]

    @extend_schema(tags=['Agents'], summary="Liste des agents disponibles")
    def get(self, request):
        city = request.query_params.get('city', '')
        agents = AgentProfile.objects.select_related('user').filter(
            user__is_validated=True,
            user__role='agent'
        )
        if city:
            agents = agents.filter(working_city__icontains=city)

        from django.utils import timezone
        from apps.boost.models import Boost
        from django.db.models import Case, When, IntegerField, Value

        now = timezone.now()

        # Annoter chaque agent avec son niveau de boost actif
        active_boosts = Boost.objects.filter(
            is_active=True,
            end_date__gte=now
        ).filter(
            target_city__icontains=city if city else ''
        )

        gold_agents   = active_boosts.filter(level='gold').values_list('agent_id', flat=True)
        silver_agents = active_boosts.filter(level='silver').values_list('agent_id', flat=True)
        bronze_agents = active_boosts.filter(level='bronze').values_list('agent_id', flat=True)

        agents = agents.annotate(
            boost_priority=Case(
                When(user_id__in=gold_agents,   then=Value(3)),
                When(user_id__in=silver_agents, then=Value(2)),
                When(user_id__in=bronze_agents, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).order_by('-boost_priority', '-reliability_score')

        serializer = PublicAgentSerializer(agents, many=True)
        return Response(success_response(serializer.data))


class AgentProfileView(APIView):
    """Mon profil agent — voir et modifier"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agents'], summary="Mon profil agent")
    def get(self, request):
        try:
            profile = AgentProfile.objects.get(user=request.user)
        except AgentProfile.DoesNotExist:
            return Response(
                error_response("Profil agent introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(success_response(AgentProfileSerializer(profile).data))

    @extend_schema(tags=['Agents'], summary="Modifier mon profil agent")
    def patch(self, request):
        try:
            profile = AgentProfile.objects.get(user=request.user)
        except AgentProfile.DoesNotExist:
            return Response(
                error_response("Profil agent introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = AgentProfileSerializer(profile, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer.save()
        return Response(success_response(serializer.data, "Profil mis à jour"))


class AgentPublicProfileView(APIView):
    """Page publique d'un agent"""
    permission_classes = [AllowAny]

    @extend_schema(tags=['Agents'], summary="Profil public d'un agent")
    def get(self, request, agent_id):
        try:
            profile = AgentProfile.objects.get(id=agent_id, user__is_validated=True)
        except AgentProfile.DoesNotExist:
            return Response(
                error_response("Agent introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(success_response(PublicAgentSerializer(profile).data))


class AgentClientsView(APIView):
    """Liste des clients de l'agent"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agents'], summary="Mes clients")
    def get(self, request):
        relations = ClientAgentRelation.objects.filter(
            agent=request.user, is_active=True
        ).select_related('client')
        clients = [{
            'id': str(r.client.id),
            'full_name': r.client.get_full_name(),
            'email': r.client.email,
            'phone': r.client.phone,
            'role': r.client.role,
            'is_phone_verified': r.client.is_phone_verified,
            'since': r.created_at,
        } for r in relations]
        return Response(success_response(clients))


class AgentAvailabilityView(APIView):
    """Créneaux de disponibilité de l'agent"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agents'], summary="Mes créneaux de disponibilité")
    def get(self, request):
        slots = AgentAvailabilitySlot.objects.filter(agent=request.user, is_active=True)
        return Response(success_response(AvailabilitySlotSerializer(slots, many=True).data))

    @extend_schema(tags=['Agents'], summary="Ajouter un créneau", request=AvailabilitySlotSerializer)
    def post(self, request):
        serializer = AvailabilitySlotSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer.save(agent=request.user)
        return Response(
            success_response(serializer.data, "Créneau ajouté"),
            status=status.HTTP_201_CREATED
        )

    @extend_schema(tags=['Agents'], summary="Supprimer un créneau")
    def delete(self, request, slot_id):
        try:
            slot = AgentAvailabilitySlot.objects.get(id=slot_id, agent=request.user)
            slot.delete()
            return Response(success_response(message="Créneau supprimé"))
        except AgentAvailabilitySlot.DoesNotExist:
            return Response(
                error_response("Créneau introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )


class ChooseAgentView(APIView):
    """Client ou propriétaire choisit un agent"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Agents'], summary="Choisir mon agent")
    def post(self, request):
        user = request.user
        if user.role not in ['client', 'tenant', 'owner']:
            return Response(
                error_response("Seuls les clients et propriétaires peuvent choisir un agent"),
                status=status.HTTP_400_BAD_REQUEST
            )

        agent_id = request.data.get('agent_id')
        if not agent_id:
            return Response(
                error_response("agent_id est requis"),
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            agent_profile = AgentProfile.objects.get(id=agent_id, user__is_validated=True)
        except AgentProfile.DoesNotExist:
            return Response(
                error_response("Agent introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )

        if user.role in ['client', 'tenant']:
            if ClientAgentRelation.objects.filter(client=user, is_active=True).exists():
                return Response(
                    error_response("Vous avez déjà un agent."),
                    status=status.HTTP_400_BAD_REQUEST
                )
            ClientAgentRelation.objects.create(client=user, agent=agent_profile.user)
            return Response(success_response(
                message=f"Vous êtes maintenant lié à l'agent {agent_profile.user.get_full_name()}"
            ))

        return Response(error_response("Action non autorisée"), status=status.HTTP_400_BAD_REQUEST)
