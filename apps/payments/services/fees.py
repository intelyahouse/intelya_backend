"""
Frais fixe ajoute au loyer -- JAMAIS un pourcentage preleve sur le loyer
lui-meme (qui reste integralement du au proprietaire). Le montant depend
d'un bareme par palier (RentFeeTier, modifiable en admin sans deploiement),
puis se repartit entre la plateforme et l'agence gestionnaire du bail
selon RENT_SURCHARGE_PLATFORM_PERCENT / RENT_SURCHARGE_AGENCY_PERCENT.

Desactive tant que RENT_SURCHARGE_ENABLED est faux (lie a FREE_MODE) :
aucun frais n'est alors ajoute, le locataire ne paie que le loyer.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings


def get_rent_fee(monthly_rent):
    """Retourne le frais fixe applicable pour ce loyer mensuel, selon le
    bareme actif. Decimal('0') si aucun palier ne correspond ou si le
    dispositif est desactive (FREE_MODE)."""
    if not getattr(settings, 'RENT_SURCHARGE_ENABLED', False):
        return Decimal('0')

    from apps.payments.models import RentFeeTier
    from django.db.models import Q

    tier = RentFeeTier.objects.filter(
        is_active=True, min_rent__lte=monthly_rent
    ).filter(
        Q(max_rent__isnull=True) | Q(max_rent__gte=monthly_rent)
    ).order_by('-min_rent').first()

    return tier.fee_amount if tier else Decimal('0')


def split_rent_fee(fee_amount):
    """Repartit le frais fixe entre plateforme et agence. Le reste (apres
    arrondi de la part plateforme) revient integralement a l'agence, pour
    ne jamais perdre ou dupliquer un centime par arrondi."""
    fee_amount = Decimal(fee_amount)
    platform_percent = Decimal(str(getattr(settings, 'RENT_SURCHARGE_PLATFORM_PERCENT', 60)))

    platform_share = (fee_amount * platform_percent / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    agency_share = fee_amount - platform_share
    return platform_share, agency_share
