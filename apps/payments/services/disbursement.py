"""
Decaissement des loyers -- verse le propriétaire (integralement, jamais
ampute) ET la part d'agence du frais fixe (Transaction.agency_fee_amount,
calcule et fige a l'initiation par apps.payments.services.fees) pour une
Transaction de type 'rent' completee. Recurrent : chaque paiement de loyer
declenche son propre versement, l'idempotence se fait au niveau de la
Transaction elle-meme (une seule tentative par transaction), pas au niveau
du bail. Best-effort, sans reessai automatique -- meme logique de
tolerance que le virement proprietaire historique.
"""
import logging

logger = logging.getLogger(__name__)


def _transfer_to_owner(txn, lease):
    from .kpay import kpay_service

    try:
        owner_profile = lease.owner.owner_profile
        phone = owner_profile.mtn_momo_number or owner_profile.orange_money_number
        if phone and float(txn.net_amount) > 0:
            kpay_service.disburse(phone=phone, amount=int(txn.net_amount), reference=f"OWNER-{txn.reference}")
    except Exception as e:
        logger.error(f"[VIREMENT PROPRIO] Erreur: {e}")


def _transfer_agency_fee_share(txn, lease):
    from .kpay import kpay_service
    from apps.payments.models import PaymentSplitEntry

    if not lease.agency_id or float(txn.agency_fee_amount) <= 0:
        return
    if PaymentSplitEntry.objects.filter(transaction=txn).exists():
        return  # deja tente pour cette transaction precise

    agency = lease.agency
    entry = PaymentSplitEntry.objects.create(
        transaction=txn, agency=agency, amount=txn.agency_fee_amount, status='pending',
    )
    try:
        phone = agency.mtn_momo_number or agency.orange_money_number
        if not phone:
            entry.status = 'failed'
            entry.error_message = "Aucun numero mobile money configure pour cette agence"
            entry.save(update_fields=['status', 'error_message'])
            return

        result = kpay_service.disburse(
            phone=phone, amount=int(txn.agency_fee_amount), reference=f"AGENCY-{agency.id}-{txn.reference}"
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
    _transfer_agency_fee_share(txn, lease)
