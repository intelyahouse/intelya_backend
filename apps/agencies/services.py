from django.db import transaction

from .models import Agency


def _default_agency_name(user):
    return f"Agence de {user.get_full_name() or user.email}"


def create_solo_agency(user, name=None):
    """Cree une nouvelle agence solo dont `user` est le gerant."""
    return Agency.objects.create(
        name=(name or "").strip() or _default_agency_name(user),
        owner_agent=user,
        is_solo=True,
    )


def recompute_is_solo(agency):
    count = agency.agents.count()
    Agency.objects.filter(pk=agency.pk).update(is_solo=count <= 1)


@transaction.atomic
def transfer_agent_to_agency(agent_profile, new_agency):
    """Deplace un agent vers une nouvelle agence et recalcule is_solo et
    la reputation agregee sur l'ancienne et la nouvelle agence -- le
    depart/l'arrivee d'un agent change le pool d'avis qui les compose."""
    old_agency = agent_profile.agency
    agent_profile.agency = new_agency
    agent_profile.save(update_fields=["agency"])
    recompute_is_solo(new_agency)
    new_agency.update_reliability_score()
    if old_agency:
        recompute_is_solo(old_agency)
        old_agency.update_reliability_score()
    return agent_profile


@transaction.atomic
def remove_agent_from_agency(agent_profile):
    """Retire un agent de son agence actuelle et lui cree une nouvelle
    agence solo (utilise pour un depart volontaire ou une exclusion)."""
    new_agency = create_solo_agency(agent_profile.user, name=agent_profile.agency_name)
    return transfer_agent_to_agency(agent_profile, new_agency)
