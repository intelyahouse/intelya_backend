from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from .models import Dispute, Report
from .serializers import (
    DisputeSerializer, CreateDisputeSerializer,
    DisputeResponseSerializer, ReportSerializer, CreateReportSerializer
)
from core.permissions import IsAdmin
from core.utils import success_response, error_response


class CreateDisputeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Disputes'], summary="Ouvrir un litige", request=CreateDisputeSerializer)
    def post(self, request):
        serializer = CreateDisputeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        dispute = serializer.save(claimant=request.user, status='open')
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

        return Response(success_response(message="Réponse enregistrée. L'admin va arbitrer."))


class MyDisputesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Disputes'], summary="Mes litiges")
    def get(self, request):
        from core.pagination import StandardResultsSetPagination
        disputes = Dispute.objects.filter(claimant=request.user) | Dispute.objects.filter(defendant=request.user)
        disputes = disputes.order_by('-created_at')
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
            reported_user.is_active = False
            reported_user.save(update_fields=['is_active'])

        return Response(
            success_response(ReportSerializer(report).data, "Signalement enregistré"),
            status=status.HTTP_201_CREATED
        )
