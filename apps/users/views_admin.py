from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Count, Sum
from drf_spectacular.utils import extend_schema
from core.permissions import IsAdmin
from core.utils import success_response, error_response

User = get_user_model()


class AdminStatsView(APIView):
    """Statistiques globales de la plateforme — admin uniquement"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Statistiques globales de la plateforme")
    def get(self, request):
        from apps.properties.models import Property
        from apps.visits.models import VisitRequest
        from apps.contracts.models import LeaseContract
        from apps.payments.models import Transaction
        from apps.boost.models import Boost

        # Utilisateurs — une seule requête avec annotation
        from django.db.models import Count, Q
        user_stats = User.objects.aggregate(
            total=Count('id'),
            agents=Count('id', filter=Q(role='agent', is_validated=True)),
            owners=Count('id', filter=Q(role='owner', is_validated=True)),
            clients=Count('id', filter=Q(role__in=['client', 'tenant'])),
            pending=Count('id', filter=Q(validation_status='pending', role__in=['agent', 'owner'])),
        )
        total_users        = user_stats['total']
        total_agents       = user_stats['agents']
        total_owners       = user_stats['owners']
        total_clients      = user_stats['clients']
        pending_validation = user_stats['pending']

        # Biens
        total_properties   = Property.objects.count()
        available_properties = Property.objects.filter(status='available').count()
        rented_properties  = Property.objects.filter(status='rented').count()

        # Visites
        total_visits    = VisitRequest.objects.count()
        completed_visits = VisitRequest.objects.filter(status='completed').count()

        # Baux actifs
        active_leases   = LeaseContract.objects.filter(status='active').count()

        # Revenus plateforme (2%)
        platform_revenue = Transaction.objects.filter(
            status='completed'
        ).aggregate(total=Sum('platform_fee'))['total'] or 0

        # Boosts actifs
        active_boosts   = Boost.objects.filter(is_active=True).count()

        return Response(success_response({
            'users': {
                'total': total_users,
                'agents': total_agents,
                'owners': total_owners,
                'clients': total_clients,
                'pending_validation': pending_validation,
            },
            'properties': {
                'total': total_properties,
                'available': available_properties,
                'rented': rented_properties,
            },
            'visits': {
                'total': total_visits,
                'completed': completed_visits,
            },
            'leases': {
                'active': active_leases,
            },
            'revenue': {
                'platform_total_fcfa': float(platform_revenue),
                'active_boosts': active_boosts,
            }
        }))


class AdminValidateUserView(APIView):
    """Valider ou rejeter un agent ou propriétaire"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Valider ou rejeter un compte")
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id, role__in=['agent', 'owner'])
        except User.DoesNotExist:
            return Response(error_response("Utilisateur introuvable"), status=404)

        action = request.data.get('action')
        note   = request.data.get('note', '')

        if action == 'approve':
            user.is_validated     = True
            user.validation_status = 'approved'
            user.validated_at     = timezone.now()
            user.validated_by     = request.user
            user.validation_note  = note
            user.save()

            # Créer le profil selon le rôle
            if user.role == 'agent':
                from apps.agents.services import ensure_agent_profile_and_agency
                ensure_agent_profile_and_agency(user)
            elif user.role == 'owner':
                from apps.owners.models import OwnerProfile
                OwnerProfile.objects.get_or_create(user=user)

            # Notifier l'utilisateur — push + email (notify_account_validated) + SMS
            from apps.notifications.utils import notify_account_validated
            from apps.notifications.services.sms import sms_service
            notify_account_validated(user)
            sms_service.send_account_validated(user.phone, user.role)

            return Response(success_response(message=f"Compte {user.get_full_name()} validé ✅"))

        elif action == 'reject':
            requested_role = user.role
            user.validation_status = 'rejected'
            user.validation_note  = note
            # Retour au role client -- sans ca l'utilisateur reste bloque :
            # pas valide comme agent/proprietaire, mais plus reconnu comme
            # client non plus (IsClient exige role in ['client','tenant']).
            user.role = 'client'
            user.save()

            from apps.notifications.utils import notify
            notify(
                user, 'system', "Votre demande n'a pas été retenue",
                f"Votre demande pour devenir {requested_role} a été rejetée."
                + (f" Motif : {note}" if note else ""),
                send_email=True
            )

            return Response(success_response(message=f"Compte {user.get_full_name()} rejeté"))

        return Response(error_response("Action invalide. Utilisez 'approve' ou 'reject'"), status=400)


class AdminPendingUsersView(APIView):
    """Liste des comptes en attente de validation"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Comptes en attente de validation")
    def get(self, request):
        from apps.users.serializers import UserProfileSerializer
        pending = User.objects.filter(
            validation_status='pending',
            role__in=['agent', 'owner']
        ).order_by('-date_joined')
        return Response(success_response(UserProfileSerializer(pending, many=True).data))


class AdminBlockUserView(APIView):
    """Bloquer ou débloquer un utilisateur"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Bloquer ou débloquer un utilisateur")
    def post(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(error_response("Utilisateur introuvable"), status=404)

        action = request.data.get('action')
        if action == 'block':
            user.is_blocked = True
            user.save(update_fields=['is_blocked'])
            return Response(success_response(message=f"{user.get_full_name()} bloqué"))
        elif action == 'unblock':
            user.is_blocked = False
            user.save(update_fields=['is_blocked'])
            return Response(success_response(message=f"{user.get_full_name()} débloqué"))

        return Response(error_response("Action invalide"), status=400)


class AdminAllUsersView(APIView):
    """Tous les utilisateurs de la plateforme"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Tous les utilisateurs")
    def get(self, request):
        from apps.users.serializers import UserProfileSerializer
        from core.pagination import StandardResultsSetPagination
        role = request.query_params.get('role', '')
        search = request.query_params.get('search', '')
        users = User.objects.all().order_by('-date_joined')
        if role:
            users = users.filter(role=role)
        if search:
            users = users.filter(
                email__icontains=search
            ) | users.filter(
                phone__icontains=search
            ) | users.filter(
                first_name__icontains=search
            )
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(users, request)
        return paginator.get_paginated_response(
            UserProfileSerializer(page, many=True).data
        )


class AdminDisputesView(APIView):
    """Tous les litiges — arbitrage admin"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Tous les litiges")
    def get(self, request):
        from apps.disputes.models import Dispute
        from apps.disputes.serializers import DisputeSerializer
        from core.pagination import StandardResultsSetPagination
        disputes = Dispute.objects.all().select_related(
            'claimant', 'defendant', 'agency'
        ).order_by('-created_at')
        status_ = request.query_params.get('status')
        if status_:
            disputes = disputes.filter(status=status_)
        agency_id = request.query_params.get('agency_id')
        if agency_id:
            disputes = disputes.filter(agency_id=agency_id)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(disputes, request)
        return paginator.get_paginated_response(
            DisputeSerializer(page, many=True).data
        )

    @extend_schema(tags=['Admin'], summary="Décision sur un litige")
    def post(self, request, dispute_id):
        from apps.disputes.models import Dispute
        from apps.disputes.serializers import DisputeSerializer
        try:
            dispute = Dispute.objects.get(id=dispute_id)
        except Dispute.DoesNotExist:
            return Response(error_response("Litige introuvable"), status=404)

        decision = request.data.get('decision')
        note     = request.data.get('decision_note', '')

        if decision not in ['claimant_wins', 'defendant_wins', 'compromise', 'no_action']:
            return Response(error_response("Décision invalide"), status=400)

        dispute.decision      = decision
        dispute.decision_note = note
        dispute.decided_by    = request.user
        dispute.decided_at    = timezone.now()
        dispute.status        = 'resolved'
        dispute.save()

        # Plainte confirmee contre un agent d'agence — fait objectif conserve,
        # sans ponderation automatique sur le score (regle metier a definir)
        if decision == 'claimant_wins' and dispute.agency_id:
            from django.db.models import F
            from apps.agencies.models import Agency
            Agency.objects.filter(pk=dispute.agency_id).update(
                disputes_confirmed_against=F('disputes_confirmed_against') + 1
            )

        # Libérer l'escrow selon la décision
        if dispute.related_transaction_id:
            try:
                from apps.payments.models import Escrow
                from apps.payments.services.kpay import kpay_service
                escrow = Escrow.objects.filter(
                    transaction_id=dispute.related_transaction_id,
                    status='held'
                ).first()
                if escrow:
                    if decision == 'claimant_wins':
                        # Rembourser le plaignant
                        kpay_service.disburse(
                            phone=dispute.claimant.phone,
                            amount=int(escrow.amount),
                            reference=f"DISPUTE-WIN-{dispute.id}"
                        )
                    elif decision == 'defendant_wins':
                        # Libérer au défendeur
                        kpay_service.disburse(
                            phone=dispute.defendant.phone,
                            amount=int(escrow.amount),
                            reference=f"DISPUTE-DEF-{dispute.id}"
                        )
                    escrow.status = 'released'
                    escrow.released_at = timezone.now()
                    escrow.released_by = request.user
                    escrow.save()
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"[ESCROW LITIGE] {e}")

        from core.audit import log_dispute_decided
        log_dispute_decided(request.user, dispute, decision, request)

        from apps.notifications.utils import notify
        for party in [dispute.claimant, dispute.defendant]:
            notify(
                party, 'dispute_decided', "Litige tranché",
                f"Décision : {dispute.get_decision_display()}." + (f" {note}" if note else ""),
                {'dispute_id': str(dispute.id)}, send_email=True
            )

        return Response(success_response(
            DisputeSerializer(dispute).data,
            f"Décision enregistrée : {decision}"
        ))


class AdminRevenueView(APIView):
    """Revenus détaillés de la plateforme"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Revenus de la plateforme")
    def get(self, request):
        from apps.payments.models import Transaction
        from django.db.models import Sum, Count

        transactions = Transaction.objects.filter(status='completed')

        by_type = transactions.values('transaction_type').annotate(
            total=Sum('platform_fee'),
            count=Count('id')
        )

        by_method = transactions.values('payment_method').annotate(
            total=Sum('amount'),
            count=Count('id')
        )

        total_revenue = transactions.aggregate(total=Sum('platform_fee'))['total'] or 0

        return Response(success_response({
            'total_platform_revenue_fcfa': float(total_revenue),
            'by_transaction_type': list(by_type),
            'by_payment_method': list(by_method),
        }))


class AdminAllPropertiesView(APIView):
    """Tous les biens — admin voit les adresses complètes"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Tous les biens avec adresses complètes")
    def get(self, request):
        from apps.properties.models import Property
        from apps.properties.serializers import PropertyAdminSerializer
        properties = Property.objects.all().select_related(
            'owner', 'agent'
        ).prefetch_related('photos').order_by('-created_at')
        city = request.query_params.get('city')
        status_ = request.query_params.get('status')
        if city:
            properties = properties.filter(city__icontains=city)
        if status_:
            properties = properties.filter(status=status_)
        from core.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(properties, request)
        return paginator.get_paginated_response(
            PropertyAdminSerializer(page, many=True, context={'request': request}).data
        )

    @extend_schema(tags=['Admin'], summary="Suspendre ou activer un bien")
    def patch(self, request, property_id):
        from apps.properties.models import Property
        try:
            prop = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Response(error_response("Bien introuvable"), status=404)
        new_status = request.data.get('status', 'suspended')
        prop.status = new_status
        prop.save(update_fields=['status'])
        return Response(success_response(message=f"Bien mis à jour : {new_status}"))


class AdminAllTransactionsView(APIView):
    """Toutes les transactions financières"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Toutes les transactions")
    def get(self, request):
        from apps.payments.models import Transaction
        from apps.payments.serializers import TransactionSerializer
        from core.pagination import StandardResultsSetPagination
        transactions = Transaction.objects.all().select_related(
            'payer', 'receiver'
        ).order_by('-created_at')
        status_ = request.query_params.get('status')
        t_type  = request.query_params.get('type')
        if status_:
            transactions = transactions.filter(status=status_)
        if t_type:
            transactions = transactions.filter(transaction_type=t_type)
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(transactions, request)
        return paginator.get_paginated_response(
            TransactionSerializer(page, many=True).data
        )


class AdminAllReportsView(APIView):
    """Tous les signalements"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Tous les signalements")
    def get(self, request):
        from apps.disputes.models import Report
        from apps.disputes.serializers import ReportSerializer
        from core.pagination import StandardResultsSetPagination
        reports = Report.objects.all().select_related(
            'reporter', 'reported'
        ).order_by('-created_at')
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(reports, request)
        return paginator.get_paginated_response(
            ReportSerializer(page, many=True).data
        )

    @extend_schema(tags=['Admin'], summary="Traiter un signalement")
    def post(self, request, report_id):
        from apps.disputes.models import Report
        from apps.disputes.serializers import ReportSerializer
        try:
            report = Report.objects.get(id=report_id)
        except Report.DoesNotExist:
            return Response(error_response("Signalement introuvable"), status=404)

        action     = request.data.get('action')
        admin_note = request.data.get('admin_note', '')

        if action == 'suspend':
            report.reported.is_active = False
            report.reported.save(update_fields=['is_active'])
            report.status = 'action_taken'
        elif action == 'ban':
            # Blacklist définitive
            from apps.users.models import Blacklist
            Blacklist.objects.get_or_create(
                phone=report.reported.phone,
                defaults={
                    'reason': admin_note or 'Banni par admin',
                    'banned_by': request.user
                }
            )
            if report.reported.cni_number:
                Blacklist.objects.get_or_create(
                    cni_number=report.reported.cni_number,
                    defaults={
                        'reason': admin_note or 'Banni par admin',
                        'banned_by': request.user
                    }
                )
            report.reported.is_active = False
            report.reported.save(update_fields=['is_active'])
            report.status = 'action_taken'
        elif action == 'dismiss':
            report.status = 'dismissed'
        else:
            return Response(error_response("Action invalide. Utilisez suspend, ban ou dismiss"), status=400)

        report.admin_note   = admin_note
        report.reviewed_by  = request.user
        report.reviewed_at  = timezone.now()
        report.save()

        return Response(success_response(
            ReportSerializer(report).data,
            f"Signalement traité : {action}"
        ))


class AdminPlatformConfigView(APIView):
    """Configuration de la plateforme"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Voir la configuration actuelle")
    def get(self, request):
        from django.conf import settings
        return Response(success_response({
            'platform_commission_percent': settings.PLATFORM_COMMISSION_PERCENT,
            'platform_name': settings.PLATFORM_NAME,
            'platform_currency': settings.PLATFORM_CURRENCY,
            'visit_gps_radius_meters': settings.VISIT_GPS_RADIUS_METERS,
            'visit_confirmation_hours': settings.VISIT_CONFIRMATION_HOURS,
            'debt_grace_days': {
                'alert': settings.DEBT_GRACE_DAYS_ALERT,
                'claim': settings.DEBT_GRACE_DAYS_CLAIM,
                'admin': settings.DEBT_GRACE_DAYS_ADMIN,
                'block': settings.DEBT_GRACE_DAYS_BLOCK,
            },
            'lease_renewal_percent': settings.LEASE_RENEWAL_PERCENT,
            'boost_prices': {
                'bronze': {'7': 5000, '15': 10000, '30': 18000},
                'silver': {'7': 10000, '15': 20000, '30': 35000},
                'gold':   {'7': 20000, '15': 38000, '30': 65000},
            }
        }))


class AdminAllBoostsView(APIView):
    """Tous les boosts actifs"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Tous les boosts")
    def get(self, request):
        from apps.boost.models import Boost
        from apps.boost.serializers import BoostSerializer
        boosts = Boost.objects.filter(is_active=True).order_by('-created_at')
        return Response(success_response(BoostSerializer(boosts, many=True).data))


class AdminAllLeasesView(APIView):
    """Tous les baux actifs"""
    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(tags=['Admin'], summary="Tous les baux")
    def get(self, request):
        from apps.contracts.models import LeaseContract
        from apps.contracts.serializers import LeaseContractSerializer
        leases = LeaseContract.objects.all().order_by('-created_at')
        status_ = request.query_params.get('status')
        if status_:
            leases = leases.filter(status=status_)
        from core.pagination import StandardResultsSetPagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(leases, request)
        return paginator.get_paginated_response(
            LeaseContractSerializer(page, many=True).data
        )
