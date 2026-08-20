from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from django.contrib.auth import get_user_model
from .models import Dispute, Report
from .serializers import (
    DisputeSerializer, CreateDisputeSerializer,
    DisputeResponseSerializer,
    ReportSerializer, CreateReportSerializer
)
from core.utils import success_response, error_response
from apps.notifications.utils import notify, notify_bulk

User = get_user_model()


def _dispute_agency(defendant):
    profile = getattr(defendant, 'agent_profile', None)
    return profile.agency if profile else None


def _notify_admins(notification_type, title, body, data=None):
    admins = User.objects.filter(role='admin', is_active=True)
    notify_bulk(admins, notification_type, title, body, data)


class CreateDisputeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Disputes'], summary="Ouvrir un litige", request=CreateDisputeSerializer)
    def post(self, request):
        serializer = CreateDisputeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        dispute = serializer.save(
            claimant=request.user, status='open',
            agency=_dispute_agency(serializer.validated_data['defendant']),
        )

        notify(
            dispute.defendant, 'dispute_opened', "Un litige a été ouvert contre vous",
            f"{request.user.get_full_name()} a ouvert un litige : {dispute.title}. Vous avez 48h pour répondre.",
            {'dispute_id': str(dispute.id)}
        )
        _notify_admins(
            'dispute_opened', "Nouveau litige à surveiller",
            f"{request.user.get_full_name()} vs {dispute.defendant.get_full_name()} — {dispute.title}",
            {'dispute_id': str(dispute.id)}
        )

        return Response(
            success_response(DisputeSerializer(dispute).data, "Litige ouvert. L'autre partie a 48h pour répondre."),
            status=status.HTTP_201_CREATED
        )


class RespondDisputeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Disputes'], summary="Répondre à un litige", request=DisputeResponseSerializer)
    def post(self, request, dispute_id):
        try:
            dispute = Dispute.objects.get(id=dispute_id, defendant=request.user, status='open')
        except Dispute.DoesNotExist:
            return Response(error_response("Litige introuvable"), status=status.HTTP_404_NOT_FOUND)

        serializer = DisputeResponseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides"), status=status.HTTP_400_BAD_REQUEST)

        dispute.defendant_response     = serializer.validated_data['response']
        dispute.defendant_responded_at = timezone.now()
        dispute.status                 = 'reviewing'
        dispute.save()

        notify(
            dispute.claimant, 'dispute_responded', "Réponse reçue sur votre litige",
            f"{dispute.defendant.get_full_name()} a répondu à votre litige : {dispute.title}.",
            {'dispute_id': str(dispute.id)}
        )
        _notify_admins(
            'dispute_responded', "Litige prêt pour arbitrage",
            f"{dispute.defendant.get_full_name()} a répondu — {dispute.title}",
            {'dispute_id': str(dispute.id)}
        )

        return Response(success_response(message="Réponse enregistrée. L'admin va arbitrer."))


class MyDisputesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Disputes'], summary="Mes litiges")
    def get(self, request):
        from core.pagination import StandardResultsSetPagination
        from apps.agencies.views import _is_gerant

        disputes = Dispute.objects.filter(claimant=request.user) | Dispute.objects.filter(defendant=request.user)

        agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
        if agency_id:
            agency = request.user.agent_profile.agency
            if _is_gerant(request.user, agency):
                disputes = disputes | Dispute.objects.filter(agency_id=agency_id)

        disputes = disputes.distinct().order_by('-created_at')
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(disputes, request)
        return paginator.get_paginated_response(
            DisputeSerializer(page, many=True).data
        )


class CreateReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Disputes'], summary="Signaler un utilisateur", request=CreateReportSerializer)
    def post(self, request):
        serializer = CreateReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        if serializer.validated_data['reported'] == request.user:
            return Response(error_response("Vous ne pouvez pas vous signaler vous-même"), status=status.HTTP_400_BAD_REQUEST)

        report = serializer.save(reporter=request.user)

        # Vérifier si 3 signalements en 30 jours → suspension auto
        from datetime import timedelta
        from django.utils import timezone as tz
        reported_user = report.reported
        recent_reports = Report.objects.filter(
            reported=reported_user,
            created_at__gte=tz.now() - timedelta(days=30)
        ).count()

        if recent_reports >= 3:
            # Bloquer avec is_blocked (cohérent avec le login)
            reported_user.is_blocked = True
            reported_user.is_active  = False
            reported_user.save(update_fields=['is_blocked', 'is_active'])
            # Notifier l'admin
            from apps.notifications.utils import notify_bulk
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admins = User.objects.filter(role='admin', is_active=True)
            notify_bulk(
                admins, 'system',
                'Suspension automatique',
                f"{reported_user.get_full_name()} suspendu après 3 signalements en 30 jours."
            )

        return Response(
            success_response(ReportSerializer(report).data, "Signalement enregistré"),
            status=status.HTTP_201_CREATED
        )
