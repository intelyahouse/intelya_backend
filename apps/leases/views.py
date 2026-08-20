from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from .models import RentPayment, DebtRecord, Complaint
from .serializers import (
    RentPaymentSerializer, ConfirmCashPaymentSerializer,
    DebtActionSerializer, ComplaintSerializer, CreateComplaintSerializer
)
from apps.contracts.models import LeaseContract
from core.permissions import IsAgent, IsClient
from core.utils import success_response, error_response
from core.pagination import StandardResultsSetPagination
import logging

logger = logging.getLogger(__name__)


class MyRentPaymentsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Mes paiements de loyer")
    def get(self, request):
        if request.user.role in ['client', 'tenant']:
            payments = RentPayment.objects.filter(tenant=request.user).select_related('lease__rental_property')
        elif request.user.role == 'agent':
            agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
            payments = RentPayment.objects.filter(lease__agency_id=agency_id).select_related('tenant', 'lease__rental_property')
        elif request.user.role == 'owner':
            payments = RentPayment.objects.filter(lease__owner=request.user).select_related('tenant', 'lease__rental_property')
        else:
            payments = RentPayment.objects.all().select_related('tenant', 'lease')

        paginator  = StandardResultsSetPagination()
        page_data  = paginator.paginate_queryset(payments.order_by('-due_date'), request)
        serializer = RentPaymentSerializer(page_data, many=True)
        return paginator.get_paginated_response(serializer.data)


class ConfirmCashPaymentView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Leases'], summary="Confirmer paiement cash (agent)", request=ConfirmCashPaymentSerializer)
    def post(self, request):
        serializer = ConfirmCashPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
        try:
            payment = RentPayment.objects.select_related(
                'tenant', 'lease__owner__owner_profile'
            ).get(
                id=serializer.validated_data['rent_payment_id'],
                lease__agency_id=agency_id,
                status='pending'
            )
        except RentPayment.DoesNotExist:
            return Response(error_response("Paiement introuvable"), status=status.HTTP_404_NOT_FOUND)

        from apps.payments.services.fees import get_rent_fee, split_rent_fee
        fee = get_rent_fee(payment.amount)
        platform_share, agency_share = split_rent_fee(fee)

        with transaction.atomic():
            payment.status             = 'paid'
            payment.confirmed_by_agent = True
            payment.confirmed_at       = timezone.now()
            payment.paid_at            = timezone.now()
            payment.platform_fee       = platform_share
            payment.agency_fee_amount  = agency_share
            payment.owner_amount       = payment.amount
            payment.notes              = serializer.validated_data.get('notes', '')
            payment.save()

        return Response(success_response(RentPaymentSerializer(payment).data, "Paiement confirmé ✅"))


class DebtManagementView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    @extend_schema(tags=['Leases'], summary="Gérer une dette (agent)", request=DebtActionSerializer)
    def post(self, request, payment_id):
        agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
        try:
            payment = RentPayment.objects.select_related(
                'tenant', 'lease'
            ).get(
                id=payment_id, lease__agency_id=agency_id,
                status__in=['pending', 'late']
            )
        except RentPayment.DoesNotExist:
            return Response(error_response("Paiement introuvable"), status=status.HTTP_404_NOT_FOUND)

        serializer = DebtActionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        action = serializer.validated_data['action']

        with transaction.atomic():
            DebtRecord.objects.create(
                lease=payment.lease, rent_payment=payment,
                tenant=payment.tenant, agent=request.user,
                amount_owed=payment.amount, action_taken=action,
                new_due_date=serializer.validated_data.get('new_due_date'),
                notes=serializer.validated_data.get('notes', '')
            )

            update_fields = []
            if action == 'extend' and serializer.validated_data.get('new_due_date'):
                payment.due_date = serializer.validated_data['new_due_date']
                update_fields.append('due_date')
                payment.status = 'pending'
                update_fields.append('status')
            elif action == 'claim':
                payment.status = 'disputed'
                update_fields.append('status')

            if update_fields:
                payment.save(update_fields=update_fields)

        return Response(success_response(
            RentPaymentSerializer(payment).data,
            f"Action '{action}' enregistrée"
        ))


class SubmitComplaintView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Soumettre une plainte", request=CreateComplaintSerializer)
    def post(self, request):
        if request.user.role not in ['client', 'tenant']:
            return Response(error_response("Seuls les locataires peuvent soumettre des plaintes"), status=status.HTTP_403_FORBIDDEN)

        lease = LeaseContract.objects.filter(
            tenant=request.user, status='active'
        ).select_related('owner', 'agent', 'agency').first()

        if not lease:
            return Response(error_response("Aucun bail actif trouvé"), status=status.HTTP_404_NOT_FOUND)

        serializer = CreateComplaintSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        assigned_to = lease.owner if (lease.owner.is_validated and lease.owner.role == 'owner') else lease.agent

        complaint = serializer.save(lease=lease, tenant=request.user, assigned_to=assigned_to, agency=lease.agency)

        from apps.notifications.utils import notify_complaint_new
        notify_complaint_new(assigned_to, request.user.get_full_name(), complaint.category)

        return Response(
            success_response(ComplaintSerializer(complaint).data, f"Plainte envoyée à {assigned_to.get_full_name()}"),
            status=status.HTTP_201_CREATED
        )


class MyComplaintsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Mes plaintes")
    def get(self, request):
        if request.user.role in ['client', 'tenant']:
            complaints = Complaint.objects.filter(tenant=request.user).select_related('assigned_to', 'lease__rental_property')
        elif request.user.role == 'agent':
            agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
            complaints = Complaint.objects.filter(
                Q(assigned_to=request.user) | Q(agency_id=agency_id)
            ).select_related('tenant', 'lease__rental_property')
        else:
            complaints = Complaint.objects.filter(assigned_to=request.user).select_related('tenant', 'lease__rental_property')

        paginator  = StandardResultsSetPagination()
        page_data  = paginator.paginate_queryset(complaints.order_by('-created_at'), request)
        serializer = ComplaintSerializer(page_data, many=True)
        return paginator.get_paginated_response(serializer.data)


class ResolveComplaintView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Résoudre une plainte")
    def post(self, request, complaint_id):
        try:
            complaint = Complaint.objects.select_related('tenant', 'assigned_to').get(id=complaint_id)
        except (Complaint.DoesNotExist, ValueError):
            return Response(error_response("Plainte introuvable"), status=status.HTTP_404_NOT_FOUND)

        # Autorise le destinataire exact, ou -- si la plainte a ete confiee a
        # un agent (pas au proprietaire) -- n'importe quel agent de la meme
        # agence, coherent avec le principe agence-large des autres phases.
        can_resolve = complaint.assigned_to_id == request.user.id
        if not can_resolve and request.user.role == 'agent' and complaint.assigned_to and complaint.assigned_to.role == 'agent':
            agency_id = getattr(getattr(request.user, 'agent_profile', None), 'agency_id', None)
            can_resolve = agency_id is not None and agency_id == complaint.agency_id

        if not can_resolve:
            return Response(error_response("Plainte introuvable"), status=status.HTTP_404_NOT_FOUND)

        resolution = request.data.get('resolution_note', '').strip()
        if not resolution:
            return Response(error_response("Note de résolution obligatoire"), status=status.HTTP_400_BAD_REQUEST)

        complaint.status          = 'resolved'
        complaint.resolution_note = resolution
        complaint.resolved_at     = timezone.now()
        complaint.save()

        return Response(success_response(ComplaintSerializer(complaint).data, "Plainte résolue ✅"))


class TenantDashboardView(APIView):
    """Tableau de bord locataire — statut et actions disponibles"""
    permission_classes = [IsAuthenticated, IsClient]

    @extend_schema(tags=['Leases'], summary="Mon tableau de bord locataire")
    def get(self, request):
        from apps.agents.models import ClientAgentRelation
        user = request.user

        relation = ClientAgentRelation.objects.filter(
            client=user, is_active=True
        ).select_related('agent', 'agency').first()

        lease = LeaseContract.objects.filter(
            tenant=user, status='active'
        ).select_related('rental_property', 'owner', 'agent').first()

        due_payment = None
        renewal_available = False
        if lease:
            due_payment = RentPayment.objects.filter(
                lease=lease, status__in=['pending', 'late']
            ).order_by('due_date').first()
            renewal_available = timezone.now().date() >= lease.get_renewal_notification_date()

        status_data = {
            'has_agency': bool(relation),
            'agency_name': relation.agency.name if relation and relation.agency else None,
            'agent_name': relation.agent.get_full_name() if relation else None,
            'has_active_lease': bool(lease),
            'property_title': lease.rental_property.title if lease else None,
            'monthly_rent': float(lease.monthly_rent) if lease else None,
            'lease_end_date': lease.end_date if lease else None,
            'is_blocked': user.is_blocked,
        }

        actions = [
            {'action': 'search_properties', 'label': 'Rechercher un logement', 'available': True, 'reason': None},
            {'action': 'choose_agency', 'label': 'Choisir une agence', 'available': not relation,
             'reason': None if not relation else "Vous êtes déjà rattaché à une agence"},
            {'action': 'contact_agency', 'label': 'Contacter mon agence', 'available': bool(relation),
             'reason': None if relation else "Choisissez d'abord une agence"},
            {'action': 'pay_rent', 'label': 'Payer mon loyer', 'available': bool(due_payment),
             'reason': None if due_payment else ("Aucun bail actif" if not lease else "Aucun paiement en attente")},
            {'action': 'view_payments', 'label': 'Voir mes paiements', 'available': bool(lease),
             'reason': None if lease else "Aucun bail actif"},
            {'action': 'submit_complaint', 'label': 'Signaler un problème', 'available': bool(lease),
             'reason': None if lease else "Aucun bail actif"},
            {'action': 'request_renewal', 'label': 'Demander le renouvellement', 'available': renewal_available,
             'reason': None if renewal_available else "Pas encore dans la période de renouvellement"},
            {'action': 'view_complaints', 'label': 'Voir mes plaintes', 'available': True, 'reason': None},
            {'action': 'view_disputes', 'label': 'Voir mes litiges', 'available': True, 'reason': None},
        ]

        return Response(success_response({'status': status_data, 'available_actions': actions}))


class RentPaymentReceiptView(APIView):
    """Recu PDF brande d'un paiement de loyer paye -- telechargeable par le
    locataire, le proprietaire, ou un agent de l'agence gestionnaire."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Leases'], summary="Télécharger le reçu PDF d'un paiement")
    def get(self, request, payment_id):
        from django.http import HttpResponse
        from core.pdf import build_pdf
        from core.utils import format_fcfa

        try:
            payment = RentPayment.objects.select_related(
                'tenant', 'lease__owner', 'lease__rental_property', 'lease__agency'
            ).get(id=payment_id, status='paid')
        except RentPayment.DoesNotExist:
            return Response(error_response("Reçu introuvable"), status=status.HTTP_404_NOT_FOUND)

        user = request.user
        agency_id = getattr(getattr(user, 'agent_profile', None), 'agency_id', None)
        allowed = (
            payment.tenant_id == user.id or
            payment.lease.owner_id == user.id or
            (agency_id and payment.lease.agency_id == agency_id)
        )
        if not allowed:
            return Response(error_response("Accès non autorisé à ce reçu"), status=status.HTTP_403_FORBIDDEN)

        lease = payment.lease
        sections = [
            (None, [
                ["Locataire", payment.tenant.get_full_name()],
                ["Bien", lease.rental_property.title],
                ["Propriétaire", lease.owner.get_full_name()],
                ["Période", f"{payment.period_month:02d}/{payment.period_year}"],
                ["Date de paiement", str(payment.paid_at.date()) if payment.paid_at else "-"],
                ["Méthode", payment.get_payment_method_display() if payment.payment_method else "-"],
                ["Référence", payment.payment_reference or str(payment.id)],
            ]),
            ("Répartition", [
                ["Loyer", format_fcfa(payment.amount)],
                ["Frais plateforme", format_fcfa(payment.platform_fee)],
                ["Commission agence", format_fcfa(payment.agency_fee_amount)],
                ["Total payé", format_fcfa(
                    float(payment.amount) + float(payment.platform_fee) + float(payment.agency_fee_amount)
                )],
            ]),
        ]
        pdf_bytes = build_pdf("Reçu de paiement de loyer", str(payment.id), sections)

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="recu-loyer-{payment.period_month}-{payment.period_year}.pdf"'
        return response
