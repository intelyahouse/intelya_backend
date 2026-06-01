from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from datetime import timedelta
from drf_spectacular.utils import extend_schema
from .models import Transaction, Escrow
from .serializers import (
    TransactionSerializer, InitiatePaymentSerializer,
    WebhookPayloadSerializer
)
from .services.campay import campay_service
from .services.bank import bank_service
from core.utils import success_response, error_response, generate_transaction_reference, calculate_platform_commission
from core.permissions import IsAdmin
import logging

logger = logging.getLogger(__name__)


class InitiatePaymentView(APIView):
    """Initier un paiement MTN, Orange ou Bancaire"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Payments'],
        summary="Initier un paiement",
        description="Initie un paiement via MTN Mobile Money, Orange Money ou compte bancaire.",
        request=InitiatePaymentSerializer
    )
    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        data           = serializer.validated_data
        amount         = float(data['amount'])
        method         = data['payment_method']
        phone          = data.get('phone_number', request.user.phone)
        related_type   = data['related_type']
        related_id     = data['related_id']

        # Calcul commission plateforme
        commission_data = calculate_platform_commission(amount)
        reference       = generate_transaction_reference()

        # Créer la transaction en base
        transaction = Transaction.objects.create(
            reference         = reference,
            payer             = request.user,
            transaction_type  = related_type,
            amount            = amount,
            platform_fee      = commission_data['platform_commission'],
            net_amount        = commission_data['owner_amount'],
            currency          = 'FCFA',
            status            = 'pending',
            payment_method    = method,
            description       = f"Paiement {related_type} INTELYA HAVEN",
        )

        if related_type == 'visit':
            transaction.related_visit_id = related_id
        else:
            transaction.related_lease_id = related_id
        transaction.save(update_fields=['related_visit_id', 'related_lease_id'])

        # Appeler le bon service selon la méthode
        payment_result = None

        if method in ['mtn', 'orange']:
            payment_result = campay_service.collect(
                phone=phone,
                amount=int(amount),
                reference=reference,
                description=f"INTELYA HAVEN - {related_type}"
            )
        elif method == 'bank':
            payment_result = bank_service.initiate_payment(
                account_number=phone,
                amount=int(amount),
                reference=reference
            )

        if payment_result and payment_result.get('success'):
            transaction.external_reference = payment_result.get('reference', reference)
            transaction.status = 'processing'
            transaction.save(update_fields=['external_reference', 'status'])

            # Créer l'escrow si c'est une visite
            if related_type == 'visit':
                Escrow.objects.create(
                    transaction   = transaction,
                    amount        = amount,
                    held_for      = request.user,
                    release_after = timezone.now() + timedelta(hours=24)
                )

            return Response(success_response(
                {
                    'transaction_id': str(transaction.id),
                    'reference': reference,
                    'status': 'processing',
                    'message': payment_result.get('message', 'Paiement initié. Validez sur votre téléphone.'),
                    'ussd_code': payment_result.get('ussd_code', ''),
                },
                "Paiement initié ✅"
            ), status=status.HTTP_201_CREATED)

        # En cas d'échec API — mode simulation pour les tests
        logger.warning(f"[PAYMENT] API non disponible — simulation pour {reference}")
        transaction.status = 'processing'
        transaction.save(update_fields=['status'])

        return Response(success_response(
            {
                'transaction_id': str(transaction.id),
                'reference': reference,
                'status': 'processing',
                'message': '(Mode test) Paiement simulé. En production, validez sur votre téléphone.',
            },
            "Paiement initié (mode test)"
        ), status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class CampayWebhookView(APIView):
    """Webhook Campay — reçoit les confirmations de paiement MTN et Orange"""
    permission_classes = [AllowAny]

    @extend_schema(tags=['Payments'], summary="Webhook Campay (MTN + Orange)")
    def post(self, request):
        # Vérification signature Campay
        import hmac
        import hashlib
        from django.conf import settings

        signature = request.headers.get('X-Campay-Signature', '')
        secret    = getattr(settings, 'CAMPAY_WEBHOOK_SECRET', '')

        if secret:
            body = request.body
            expected = hmac.new(
                secret.encode(), body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                logger.warning("[WEBHOOK CAMPAY] Signature invalide !")
                return Response({'status': 'invalid_signature'}, status=401)

        data      = request.data
        reference = data.get('reference') or data.get('external_reference')
        status_   = data.get('status', '').upper()

        logger.info(f"[WEBHOOK CAMPAY] Reçu: {data}")

        if not reference:
            return Response({'status': 'ignored'})

        try:
            transaction = Transaction.objects.get(
                external_reference=reference
            )
        except Transaction.DoesNotExist:
            try:
                transaction = Transaction.objects.get(reference=reference)
            except Transaction.DoesNotExist:
                return Response({'status': 'not_found'})

        transaction.webhook_data = data

        if status_ in ['SUCCESSFUL', 'SUCCESS', 'COMPLETED']:
            transaction.status       = 'completed'
            transaction.completed_at = timezone.now()
            transaction.save()

            # Libérer l'escrow si visite
            if hasattr(transaction, 'escrow'):
                transaction.escrow.status     = 'released'
                transaction.escrow.released_at = timezone.now()
                transaction.escrow.save()

            # Déclencher le virement automatique au propriétaire
            self._process_owner_transfer(transaction)

        elif status_ in ['FAILED', 'CANCELLED', 'EXPIRED']:
            transaction.status = 'failed'
            transaction.save()

            if hasattr(transaction, 'escrow'):
                transaction.escrow.status     = 'refunded'
                transaction.escrow.released_at = timezone.now()
                transaction.escrow.save()
        else:
            transaction.save(update_fields=['webhook_data'])

        return Response({'status': 'ok'})

    def _process_owner_transfer(self, transaction):
        """Virer automatiquement au propriétaire après paiement loyer"""
        if transaction.transaction_type != 'rent':
            return
        try:
            from apps.contracts.models import LeaseContract
            lease = LeaseContract.objects.get(id=transaction.related_lease_id)
            owner_profile = lease.owner.owner_profile

            phone = (
                owner_profile.mtn_momo_number or
                owner_profile.orange_money_number
            )

            if phone and float(transaction.net_amount) > 0:
                result = campay_service.disburse(
                    phone=phone,
                    amount=int(transaction.net_amount),
                    reference=f"OWNER-{transaction.reference}",
                    description=f"Loyer {lease.rental_property.title}"
                )
                logger.info(f"[VIREMENT PROPRIO] {result}")
        except Exception as e:
            logger.error(f"[VIREMENT PROPRIO] Erreur: {e}")


class MyTransactionsView(APIView):
    """Historique de mes transactions"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Payments'], summary="Mes transactions")
    def get(self, request):
        from core.pagination import StandardResultsSetPagination
        transactions = Transaction.objects.filter(
            payer=request.user
        ) | Transaction.objects.filter(
            receiver=request.user
        )
        transactions = transactions.order_by('-created_at')
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(transactions, request)
        return paginator.get_paginated_response(
            TransactionSerializer(page, many=True).data
        )


class CheckPaymentStatusView(APIView):
    """Vérifier le statut d'un paiement"""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Payments'], summary="Vérifier statut paiement")
    def get(self, request, reference):
        try:
            transaction = Transaction.objects.get(
                reference=reference,
                payer=request.user
            )
        except Transaction.DoesNotExist:
            return Response(error_response("Transaction introuvable"), status=status.HTTP_404_NOT_FOUND)

        # Vérifier aussi chez Campay si en cours
        if transaction.status == 'processing' and transaction.external_reference:
            result = campay_service.check_status(transaction.external_reference)
            if result.get('success') and result.get('status', '').upper() in ['SUCCESSFUL', 'COMPLETED']:
                transaction.status       = 'completed'
                transaction.completed_at = timezone.now()
                transaction.save()

        return Response(success_response(TransactionSerializer(transaction).data))
