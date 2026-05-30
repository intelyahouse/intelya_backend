from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema
from .models import VisitRequest, VisitReview
from .serializers import (
    VisitRequestSerializer, CreateVisitSerializer,
    ScheduleVisitSerializer, GPSConfirmSerializer,
    CancelVisitSerializer, VisitReviewSerializer
)
from apps.properties.models import Property
from apps.agents.models import ClientAgentRelation
from core.utils import success_response, error_response, is_within_radius
from core.permissions import IsAgent
from django.conf import settings

User = get_user_model()


class RequestVisitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Visits'],
        summary="Demander une visite",
        request=CreateVisitSerializer
    )
    def post(self, request):
        if request.user.role not in ['client', 'tenant']:
            return Response(
                error_response("Seuls les clients peuvent demander des visites"),
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CreateVisitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        property_id = serializer.validated_data['property_id']
        try:
            prop = Property.objects.get(id=property_id, status='available')
        except Property.DoesNotExist:
            return Response(
                error_response("Bien introuvable ou non disponible"),
                status=status.HTTP_404_NOT_FOUND
            )

        relation = ClientAgentRelation.objects.filter(
            client=request.user, is_active=True
        ).first()

        if not relation:
            return Response(
                error_response("Choisissez un agent d'abord"),
                status=status.HTTP_400_BAD_REQUEST
            )

        agent = relation.agent

        existing = VisitRequest.objects.filter(
            client=request.user,
            rental_property=prop,
            status__in=['pending', 'scheduled']
        ).exists()

        if existing:
            return Response(
                error_response("Vous avez déjà une demande en cours pour ce bien"),
                status=status.HTTP_400_BAD_REQUEST
            )

        visit_fee = 0
        is_free = True
        if hasattr(agent, 'agent_profile'):
            visit_fee = agent.agent_profile.visit_fee
            is_free   = agent.agent_profile.visit_fee_is_free

        visit = VisitRequest.objects.create(
            client=request.user,
            agent=agent,
            rental_property=prop,
            visit_fee=visit_fee,
            is_free=is_free,
            client_message=serializer.validated_data.get('client_message', ''),
            payment_status='not_required' if is_free else 'pending'
        )

        prop.interested_count += 1
        prop.save(update_fields=['interested_count'])

        return Response(
            success_response(
                VisitRequestSerializer(visit).data,
                f"Demande envoyée à {agent.get_full_name()}"
            ),
            status=status.HTTP_201_CREATED
        )


class ScheduleVisitView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Visits'], summary="Planifier une visite (agent)", request=ScheduleVisitSerializer)
    def post(self, request, visit_id):
        try:
            visit = VisitRequest.objects.get(id=visit_id, agent=request.user, status='pending')
        except VisitRequest.DoesNotExist:
            return Response(error_response("Visite introuvable"), status=status.HTTP_404_NOT_FOUND)

        serializer = ScheduleVisitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        visit.scheduled_date = serializer.validated_data['scheduled_date']
        visit.scheduled_time = serializer.validated_data['scheduled_time']
        visit.status = 'scheduled'
        visit.save()

        return Response(success_response(VisitRequestSerializer(visit).data, "Visite planifiée ✅"))


class ConfirmGPSView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Visits'],
        summary="Confirmer présence GPS client",
        request=GPSConfirmSerializer
    )
    def post(self, request, visit_id):
        try:
            visit = VisitRequest.objects.get(id=visit_id, client=request.user, status='scheduled')
        except VisitRequest.DoesNotExist:
            return Response(error_response("Visite introuvable"), status=status.HTTP_404_NOT_FOUND)

        serializer = GPSConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        client_lat = serializer.validated_data['latitude']
        client_lng = serializer.validated_data['longitude']

        prop = visit.rental_property
        if prop.location:
            within_radius, distance = is_within_radius(
                client_lat, client_lng,
                prop.location.y, prop.location.x
            )
            if not within_radius:
                return Response(
                    error_response(f"Vous êtes à {int(distance)}m du bien. Maximum autorisé : {settings.VISIT_GPS_RADIUS_METERS}m"),
                    status=status.HTTP_400_BAD_REQUEST
                )

        visit.client_gps_confirmed = True
        visit.client_gps_lat       = client_lat
        visit.client_gps_lng       = client_lng
        visit.client_confirmed_at  = timezone.now()
        visit.auto_release_at      = timezone.now() + timedelta(hours=settings.VISIT_CONFIRMATION_HOURS)

        if visit.is_both_confirmed():
            visit.status = 'completed'

        visit.save()
        return Response(success_response(message="Présence GPS confirmée ✅"))


class AgentConfirmVisitView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Visits'], summary="Confirmer visite effectuée (agent)")
    def post(self, request, visit_id):
        try:
            visit = VisitRequest.objects.get(id=visit_id, agent=request.user, status='scheduled')
        except VisitRequest.DoesNotExist:
            return Response(error_response("Visite introuvable"), status=status.HTTP_404_NOT_FOUND)

        visit.agent_confirmed    = True
        visit.agent_confirmed_at = timezone.now()

        if visit.is_both_confirmed():
            visit.status = 'completed'

        visit.save()
        return Response(success_response(
            message="Visite complétée ✅" if visit.status == 'completed' else "Confirmation enregistrée"
        ))


class CancelVisitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Visits'], summary="Annuler une visite", request=CancelVisitSerializer)
    def post(self, request, visit_id):
        try:
            visit = VisitRequest.objects.get(id=visit_id, status__in=['pending', 'scheduled'])
        except VisitRequest.DoesNotExist:
            return Response(error_response("Visite introuvable"), status=status.HTTP_404_NOT_FOUND)

        if request.user not in [visit.client, visit.agent] and request.user.role != 'admin':
            return Response(error_response("Non autorisé"), status=status.HTTP_403_FORBIDDEN)

        serializer = CancelVisitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Un motif est requis"), status=status.HTTP_400_BAD_REQUEST)

        cancelled_by = 'client' if request.user == visit.client else 'agent'
        visit.status             = 'cancelled'
        visit.cancelled_by       = cancelled_by
        visit.cancellation_reason = serializer.validated_data['reason']
        visit.cancelled_at       = timezone.now()

        if not visit.is_free and visit.payment_status == 'paid':
            visit.payment_status = 'refunded'

        visit.save()
        return Response(success_response(message="Visite annulée"))


class MyVisitsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Visits'], summary="Mes visites")
    def get(self, request):
        if request.user.role in ['client', 'tenant']:
            visits = VisitRequest.objects.filter(client=request.user).select_related('agent', 'rental_property')
        elif request.user.role == 'agent':
            visits = VisitRequest.objects.filter(agent=request.user).select_related('client', 'rental_property')
        else:
            visits = VisitRequest.objects.none()

        return Response(success_response(VisitRequestSerializer(visits, many=True).data))


class LeaveReviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Visits'],
        summary="Laisser un avis après visite GPS confirmée",
        request=VisitReviewSerializer
    )
    def post(self, request, visit_id):
        try:
            visit = VisitRequest.objects.get(
                id=visit_id, client=request.user,
                status='completed', client_gps_confirmed=True
            )
        except VisitRequest.DoesNotExist:
            return Response(
                error_response("Visite introuvable ou non éligible"),
                status=status.HTTP_404_NOT_FOUND
            )

        if hasattr(visit, 'review'):
            return Response(
                error_response("Vous avez déjà laissé un avis"),
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = VisitReviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        review = serializer.save(visit=visit, client=request.user)

        if review.agent_rating and hasattr(visit.agent, 'agent_profile'):
            visit.agent.agent_profile.update_reliability_score()

        return Response(
            success_response(serializer.data, "Avis enregistré ✅"),
            status=status.HTTP_201_CREATED
        )
