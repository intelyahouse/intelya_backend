from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from datetime import timedelta
from drf_spectacular.utils import extend_schema
from .models import Transaction, Escrow
from apps.visits.models import VisitRequest
from .serializers import TransactionSerializer, InitiatePaymentSerializer
from .services.kpay import kpay_service
from .services.bank import bank_service
from .services.disbursement import process_rent_transfer, notify_payment_completed
from .services.fees import get_rent_fee, split_rent_fee
from core.utils import success_response, error_response, generate_transaction_reference, calculate_platform_commission
from core.throttles import PaymentThrottle
from core.permissions import IsAdmin
import logging

logger = logging.getLogger(__name__)


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes   = [PaymentThrottle]

    @extend_schema(tags=['Payments'], summary="Initier un paiement", request=InitiatePaymentSerializer)
    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(error_response("Données invalides", serializer.errors), status=status.HTTP_400_BAD_REQUEST)

        data         = serializer.validated_data
        amount       = float(data['amount'])
        method       = data['payment_method']
        phone        = data.get('phone_number', request.user.phone)
        related_type = data['related_type']
        related_id   = data['related_id']

        # Vérifier montant minimum (montant soumis par le client — sera
        # recalcule par le serveur pour visite/loyer, mais reste un
        # garde-fou contre une soumission absurde des le depart)
        if amount < 100:
            return Response(error_response("Montant minimum: 100 FCFA"), status=status.HTTP_400_BAD_REQUEST)

        # Clé d'idempotence — stockée dans idempotency_key, jamais écrasée
        idempotency_key = f"{request.user.id}_{related_type}_{related_id}"
        existing = Transaction.objects.filter(
            idempotency_key=idempotency_key,
            status__in=['pending', 'processing', 'completed']
        ).first()
        if existing:
            return Response(success_response(
                TransactionSerializer(existing).data,
                "Transaction déjà en cours"
            ), status=status.HTTP_200_OK)

        receiver = None
        txn_type = related_type
        agency_fee_amount = 0
        rent_breakdown = None

        if related_type == 'visit':
            txn_type = 'visit_fee'
            try:
                visit = VisitRequest.objects.select_related('agent').get(
                    id=related_id, client=request.user
                )
            except VisitRequest.DoesNotExist:
                return Response(error_response("Visite introuvable"), status=status.HTTP_404_NOT_FOUND)
            receiver = visit.agent
            amount = float(visit.visit_fee)
            commission_data = calculate_platform_commission(amount)
            platform_fee, net_amount = commission_data['platform_commission'], commission_data['owner_amount']

        elif related_type == 'rent':
            txn_type = 'rent'
            from apps.contracts.models import LeaseContract
            try:
                lease = LeaseContract.objects.select_related('owner').get(
                    id=related_id, tenant=request.user
                )
            except LeaseContract.DoesNotExist:
                return Response(error_response("Bail introuvable"), status=status.HTTP_404_NOT_FOUND)

            months = max(1, int(data.get('months', 1)))
            monthly_rent = float(lease.monthly_rent)
            fee = float(get_rent_fee(lease.monthly_rent)) * months
            platform_fee, agency_fee_amount = split_rent_fee(fee)
            net_amount = monthly_rent * months
            amount = net_amount + fee
            receiver = lease.owner
            rent_breakdown = {
                'monthly_rent': monthly_rent, 'months': months,
                'rent_total': net_amount, 'fee': fee,
                'platform_share': float(platform_fee), 'agency_share': float(agency_fee_amount),
                'total': amount,
            }

        else:
            commission_data = calculate_platform_commission(amount)
            platform_fee, net_amount = commission_data['platform_commission'], commission_data['owner_amount']

        reference = generate_transaction_reference()

        # TRANSACTION ATOMIQUE — tout ou rien
        try:
            with transaction.atomic():
                txn = Transaction.objects.create(
                    reference=reference,
                    payer=request.user,
                    receiver=receiver,
                    transaction_type=txn_type,
                    amount=amount,
                    platform_fee=platform_fee,
                    net_amount=net_amount,
                    agency_fee_amount=agency_fee_amount,
                    currency='FCFA',
                    status='pending',
                    payment_method=method,
                    idempotency_key=idempotency_key,
                    description=f"Paiement {related_type} INTELYA HAVEN",
                )

                if related_type == 'visit':
                    txn.related_visit_id = related_id
                else:
                    txn.related_lease_id = related_id
                txn.save(update_fields=['related_visit_id', 'related_lease_id'])

        except Exception as e:
            logger.error(f"[PAYMENT] Erreur création transaction: {e}")
            return Response(error_response("Erreur lors de l'initiation du paiement"), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Appeler l'API paiement (hors transaction atomique)
        payment_result = None
        if method in ['mtn', 'orange']:
            payment_result = kpay_service.collect(phone=phone, amount=int(amount), reference=reference)
        elif method == 'bank':
            payment_result = bank_service.initiate_payment(account_number=phone, amount=int(amount), reference=reference)

        if payment_result and payment_result.get('success'):
            txn.status = 'processing'
            txn.external_reference = payment_result.get('reference', '')
            txn.save(update_fields=['status', 'external_reference'])

            if related_type == 'visit':
                Escrow.objects.create(
                    transaction=txn,
                    amount=amount,
                    held_for=request.user,
                    release_after=timezone.now() + timedelta(hours=24)
                )

        # Log audit
        from core.audit import log_payment_initiated
        log_payment_initiated(request.user, reference, amount, method, request)

        response_data = {
            'transaction_id': str(txn.id), 'reference': reference, 'status': txn.status,
            'ussd_code': payment_result.get('ussd_code', '') if payment_result else ''
        }
        if rent_breakdown:
            response_data['breakdown'] = rent_breakdown

        return Response(success_response(response_data, "Paiement initié ✅"), status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class CampayWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        import hmac, hashlib
        signature = request.headers.get('X-Campay-Signature', '')
        secret = getattr(__import__('django.conf', fromlist=['settings']).settings, 'CAMPAY_WEBHOOK_SECRET', '')

        if secret:
            expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                logger.warning("[WEBHOOK] Signature invalide")
                return Response({'status': 'invalid_signature'}, status=401)

        data = request.data
        reference = data.get('reference') or data.get('external_reference')
        status_ = data.get('status', '').upper()

        if not reference:
            return Response({'status': 'ignored'})

        try:
            txn = Transaction.objects.get(external_reference=reference)
        except Transaction.DoesNotExist:
            try:
                txn = Transaction.objects.get(reference=reference)
            except Transaction.DoesNotExist:
                return Response({'status': 'not_found'})

        with transaction.atomic():
            txn.webhook_data = data
            if status_ in ['SUCCESSFUL', 'SUCCESS', 'COMPLETED']:
                txn.status = 'completed'
                txn.completed_at = timezone.now()
                txn.save()

                if hasattr(txn, 'escrow'):
                    txn.escrow.status = 'released'
                    txn.escrow.released_at = timezone.now()
                    txn.escrow.save()

                process_rent_transfer(txn)
                self._process_visit_payment(txn)
                notify_payment_completed(txn)

            elif status_ in ['FAILED', 'CANCELLED', 'EXPIRED']:
                txn.status = 'failed'
                txn.save()
                if hasattr(txn, 'escrow'):
                    txn.escrow.status = 'refunded'
                    txn.escrow.released_at = timezone.now()
                    txn.escrow.save()
            else:
                txn.save(update_fields=['webhook_data'])

        return Response({'status': 'ok'})

    def _process_visit_payment(self, txn):
        if txn.transaction_type != 'visit_fee' or not txn.related_visit_id:
            return
        VisitRequest.objects.filter(id=txn.related_visit_id).update(
            payment_status='paid', payment_reference=txn.reference
        )


class MyTransactionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        from core.pagination import StandardResultsSetPagination
        txns = Transaction.objects.filter(
            Q(payer=request.user) | Q(receiver=request.user)
        ).order_by('-created_at').select_related('payer', 'receiver')
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(txns, request)
        return paginator.get_paginated_response(
            TransactionSerializer(page, many=True).data
        )


class CheckPaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, reference):
        try:
            txn = Transaction.objects.get(reference=reference, payer=request.user)
        except Transaction.DoesNotExist:
            return Response(error_response("Transaction introuvable"), status=status.HTTP_404_NOT_FOUND)

        if txn.status == 'processing' and txn.external_reference:
            result = kpay_service.check_status(txn.external_reference)
            if result.get('success') and result.get('status', '').upper() in ['SUCCESSFUL', 'COMPLETED']:
                with transaction.atomic():
                    txn.status = 'completed'
                    txn.completed_at = timezone.now()
                    txn.save()

        return Response(success_response(TransactionSerializer(txn).data))


class KPayWebhookView(APIView):
    """
    Webhook K-Pay — appelé automatiquement quand un paiement est complété
    K-Pay envoie : tid, refid, momtransactionid, payaccount, statusid, statusdesc
    statusid: 01 = succès, 02 = échec
    """
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        refid    = data.get('refid')
        statusid = data.get('statusid', '02')
        tid      = data.get('tid', '')

        logger.info(f"[KPAY WEBHOOK] refid={refid} statusid={statusid} tid={tid}")

        if not refid:
            return Response({'reply': 'IGNORED'})

        try:
            txn = Transaction.objects.get(reference=refid)
        except Transaction.DoesNotExist:
            logger.warning(f"[KPAY WEBHOOK] Transaction introuvable: {refid}")
            return Response({'tid': tid, 'refid': refid, 'reply': 'OK'})

        with transaction.atomic():
            txn.webhook_data = data
            txn.external_reference = tid

            if statusid == '01':
                txn.status = 'completed'
                txn.completed_at = timezone.now()
                txn.save()

                if hasattr(txn, 'escrow'):
                    txn.escrow.status = 'released'
                    txn.escrow.released_at = timezone.now()
                    txn.escrow.save()

                process_rent_transfer(txn)
                self._process_visit_payment(txn)
                notify_payment_completed(txn)

            elif statusid == '02':
                txn.status = 'failed'
                txn.save()
                if hasattr(txn, 'escrow'):
                    txn.escrow.status = 'refunded'
                    txn.escrow.released_at = timezone.now()
                    txn.escrow.save()
            else:
                txn.save(update_fields=['webhook_data'])

        # K-Pay attend cette réponse exacte
        return Response({'tid': tid, 'refid': refid, 'reply': 'OK'})

    def _process_visit_payment(self, txn):
        if txn.transaction_type != 'visit_fee' or not txn.related_visit_id:
            return
        VisitRequest.objects.filter(id=txn.related_visit_id).update(
            payment_status='paid', payment_reference=txn.reference
        )
