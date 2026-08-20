"""
Decaissement des loyers -- verse le propriétaire ET les commissions d'agence
(mandat simple ou split negocie via Network) pour une Transaction de type
'rent' completee. Best-effort, sans reessai automatique : meme logique de
tolerance que le virement proprietaire historique (une erreur est loggee et
n'empeche pas le reste du traitement).
"""
import logging

logger = logging.getLogger(__name__)


def _agency_payout_phone(agency):
    return agency.mtn_momo_number or agency.orange_money_number


def _transfer_to_owner(txn, lease):
    from .kpay import kpay_service

    try:
        owner_profile = lease.owner.owner_profile
        phone = owner_profile.mtn_momo_number or owner_profile.orange_money_number
        if phone and float(txn.net_amount) > 0:
            kpay_service.disburse(phone=phone, amount=int(txn.net_amount), reference=f"OWNER-{txn.reference}")
    except Exception as e:
        logger.error(f"[VIREMENT PROPRIO] Erreur: {e}")


def _agency_commission_plan(lease):
    """Retourne la repartition a verser aux agences pour ce bail, sans rien
    modifier. Priorite a la Collaboration acceptee sur le bien (split
    negocie entre deux agences) ; a defaut, la commission simple du bail
    revient a l'agence titulaire du mandat."""
    from apps.network.models import Collaboration

    collaboration = Collaboration.objects.filter(
        property_id=lease.rental_property_id, status='accepted'
    ).select_related('client_agency', 'property_agency').order_by('-updated_at').first()

    if collaboration:
        return collaboration, [
            (collaboration.client_agency, collaboration.client_agency_amount),
            (collaboration.property_agency, collaboration.property_agency_amount),
        ]

    if lease.agency_id and lease.agent_commission and float(lease.agent_commission) > 0:
        return None, [(lease.agency, lease.agent_commission)]

    return None, []


def _transfer_agency_commissions(txn, lease):
    from django.utils import timezone
    from .kpay import kpay_service
    from apps.contracts.models import LeaseContract
    from apps.payments.models import PaymentSplitEntry

    if lease.commission_paid:
        return

    collaboration, plan = _agency_commission_plan(lease)
    if collaboration and collaboration.commission_disbursed:
        return
    if not plan:
        return

    for agency, amount in plan:
        entry = PaymentSplitEntry.objects.create(
            transaction=txn, agency=agency, amount=amount, status='pending',
        )
        try:
            phone = _agency_payout_phone(agency)
            if not phone:
                entry.status = 'failed'
                entry.error_message = "Aucun numero mobile money configure pour cette agence"
                entry.save(update_fields=['status', 'error_message'])
                continue

            result = kpay_service.disburse(
                phone=phone, amount=int(amount), reference=f"AGENCY-{agency.id}-{txn.reference}"
            )
            if result and result.get('success'):
                entry.status = 'completed'
                entry.disbursed_reference = result.get('reference', '')
            else:
                entry.status = 'failed'
                entry.error_message = str(result.get('error', '')) if result else "Echec disburse"
            entry.save(update_fields=['status', 'disbursed_reference', 'error_message'])
        except Exception as e:
            logger.error(f"[VIREMENT AGENCE] Erreur pour {agency.id}: {e}")
            entry.status = 'failed'
            entry.error_message = str(e)
            entry.save(update_fields=['status', 'error_message'])

    if collaboration:
        collaboration.commission_disbursed = True
        collaboration.commission_disbursed_at = timezone.now()
        collaboration.save(update_fields=['commission_disbursed', 'commission_disbursed_at'])
    else:
        LeaseContract.objects.filter(id=lease.id).update(commission_paid=True)


def process_rent_transfer(txn):
    """Point d'entree appele par les webhooks de paiement quand une
    Transaction de type 'rent' passe a 'completed'."""
    if txn.transaction_type != 'rent' or not txn.related_lease_id:
        return
    from apps.contracts.models import LeaseContract

    try:
        lease = LeaseContract.objects.select_related(
            'owner__owner_profile', 'agency'
        ).get(id=txn.related_lease_id)
    except LeaseContract.DoesNotExist:
        return

    _transfer_to_owner(txn, lease)
    _transfer_agency_commissions(txn, lease)
