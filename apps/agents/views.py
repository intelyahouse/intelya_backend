from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from .models import OwnerAgentRelation
from django.db.models import Count
from apps.properties.models import Property
from apps.visits.models import VisitRequest
from apps.contracts.models import LeaseContract
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

        serializer = PublicAgentSerializer(agents, many=True, context={'request': request})
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
        return Response(success_response(
            AgentProfileSerializer(profile, context={'request': request}).data
        ))

    @extend_schema(tags=['Agents'], summary="Modifier mon profil agent")
    def patch(self, request):
        try:
            profile = AgentProfile.objects.get(user=request.user)
        except AgentProfile.DoesNotExist:
            return Response(
                error_response("Profil agent introuvable"),
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = AgentProfileSerializer(
            profile, data=request.data, partial=True,
            context={'request': request}
        )
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
        return Response(success_response(PublicAgentSerializer(profile, context={'request': request}).data))


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

class AgentClientHistoryView(APIView):
    """Historique (visites + baux) d'un client, limité à ceux gérés par cet agent"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agents'], summary="Historique d'un client")
    def get(self, request, client_id):
        # Vérifie que ce client est bien lié à cet agent
        is_linked = ClientAgentRelation.objects.filter(
            agent=request.user, client_id=client_id, is_active=True
        ).exists()
        if not is_linked:
            return Response(
                error_response("Ce client n'est pas lié à votre compte"),
                status=status.HTTP_404_NOT_FOUND
            )

        visits = VisitRequest.objects.filter(
            agent=request.user, client_id=client_id
        ).select_related('visit_property').order_by('-created_at')

        contracts = LeaseContract.objects.filter(
            agent=request.user, tenant_id=client_id
        ).select_related('rental_property').order_by('-created_at')

        PAGE_SIZE = 10

        def paginate(queryset, page_param):
            try:
                page = max(1, int(request.query_params.get(page_param, 1)))
            except (TypeError, ValueError):
                page = 1
            count = queryset.count()
            total_pages = max(1, -(-count // PAGE_SIZE))  # ceil division
            start = (page - 1) * PAGE_SIZE
            return queryset[start:start + PAGE_SIZE], count, total_pages, page

        visits_page_qs, visits_count, visits_total_pages, visits_page = paginate(visits, 'visits_page')
        contracts_page_qs, contracts_count, contracts_total_pages, contracts_page = paginate(contracts, 'contracts_page')

        visits_data = [{
            'id': str(v.id),
            'property_title': v.visit_property.title,
            'property_id': str(v.visit_property.id),
            'status': v.status,
            'scheduled_date': v.scheduled_date,
            'scheduled_time': v.scheduled_time,
            'created_at': v.created_at,
        } for v in visits_page_qs]

        contracts_data = [{
            'id': str(c.id),
            'property_title': c.rental_property.title,
            'property_id': str(c.rental_property.id),
            'status': c.status,
            'monthly_rent': c.monthly_rent,
            'start_date': c.start_date,
            'end_date': c.end_date,
            'signed_at': c.signed_at,
        } for c in contracts_page_qs]

        return Response(success_response({
            'visits': {
                'results': visits_data,
                'count': visits_count,
                'total_pages': visits_total_pages,
                'current_page': visits_page,
            },
            'contracts': {
                'results': contracts_data,
                'count': contracts_count,
                'total_pages': contracts_total_pages,
                'current_page': contracts_page,
            },
        }))


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

class AgentOwnersView(APIView):
    """Liste des proprietaires geres par l'agence de l'agent (mandats actifs)"""
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Agents'], summary="Proprietaires geres par mon agence")
    def get(self, request):
        agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
        relations = OwnerAgentRelation.objects.filter(
            agency_id=agency_id, status="active"
        ).select_related('owner', 'agent')

        # Nombre de biens geres par l'agence, par proprietaire (1 seule requete)
        counts = dict(
            Property.objects.filter(agent__agent_profile__agency_id=agency_id)
            .values_list('owner_id')
            .annotate(count=Count('id'))
        )

        owners = [{
            'id': str(r.owner.id),
            'full_name': r.owner.get_full_name(),
            'email': r.owner.email,
            'phone': r.owner.phone,
            'since': r.contract_start,
            'assigned_agent_id': str(r.agent.id),
            'assigned_agent_name': r.agent.get_full_name(),
            'properties_count': counts.get(r.owner.id, 0),
        } for r in relations]
        return Response(success_response(owners))


class AgentReportsView(APIView):
    """Statistiques et rapports de l'agent (revenus, biens, transactions)"""
    permission_classes = [IsAuthenticated, IsAgent]

    @staticmethod
    def _add_months(date, n):
        month_index = date.month - 1 + n
        year  = date.year + month_index // 12
        month = month_index % 12 + 1
        return date.replace(year=year, month=month)

    @extend_schema(tags=['Agents'], summary="Mes rapports / statistiques")
    def get(self, request):
        from django.db.models import Sum
        from django.db.models.functions import TruncMonth
        from django.utils import timezone
        from apps.payments.models import Transaction

        try:
            months = min(max(int(request.query_params.get('months', 6)), 1), 24)
        except (TypeError, ValueError):
            months = 6

        now = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_start = self._add_months(now, -(months - 1))

        properties_qs   = Property.objects.filter(agent=request.user)
        transactions_qs = Transaction.objects.filter(receiver=request.user, status='completed')

        # ===== RÉSUMÉ =====

        total_properties = properties_qs.count()
        rented_count      = properties_qs.filter(status='rented').count()
        total_revenue      = transactions_qs.aggregate(total=Sum('net_amount'))['total'] or 0
        total_clients       = ClientAgentRelation.objects.filter(agent=request.user, is_active=True).count()
        total_owners         = OwnerAgentRelation.objects.filter(agent=request.user, status='active').count()

        summary = {
            'total_revenue': total_revenue,
            'total_properties': total_properties,
            'rented_properties': rented_count,
            'occupancy_rate': round((rented_count / total_properties) * 100, 1) if total_properties else 0,
            'total_clients': total_clients,
            'total_owners': total_owners,
        }

        # ===== BIENS PAR STATUT =====

        status_counts = dict(
            properties_qs.values_list('status').annotate(count=Count('id'))
        )
        properties_by_status = [{
            'status': key,
            'label': label,
            'count': status_counts.get(key, 0),
        } for key, label in Property.STATUS_CHOICES]

        # ===== REVENUS PAR MOIS =====

        monthly = (
            transactions_qs
            .filter(completed_at__gte=period_start)
            .annotate(month=TruncMonth('completed_at'))
            .values('month')
            .annotate(total=Sum('net_amount'))
            .order_by('month')
        )
        monthly_map = {row['month'].strftime('%Y-%m'): row['total'] for row in monthly if row['month']}

        revenue_by_month = []
        cursor = period_start
        for _ in range(months):
            key = cursor.strftime('%Y-%m')
            revenue_by_month.append({
                'month': key,
                'label': cursor.strftime('%b %Y'),
                'total': monthly_map.get(key, 0),
            })
            cursor = self._add_months(cursor, 1)

        # ===== TRANSACTIONS PAR TYPE =====

        by_type = (
            transactions_qs
            .values('transaction_type')
            .annotate(total=Sum('net_amount'), count=Count('id'))
            .order_by('-total')
        )
        type_labels = dict(Transaction.TYPE_CHOICES)
        transactions_by_type = [{
            'type': row['transaction_type'],
            'label': type_labels.get(row['transaction_type'], row['transaction_type']),
            'total': row['total'],
            'count': row['count'],
        } for row in by_type]

        return Response(success_response({
            'summary': summary,
            'properties_by_status': properties_by_status,
            'revenue_by_month': revenue_by_month,
            'transactions_by_type': transactions_by_type,
        }))