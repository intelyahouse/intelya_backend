from .models import AgentProfile


def ensure_agent_profile_and_agency(user, working_city_default="Non définie"):
    """
    Filet de securite idempotent : garantit qu'un agent valide a toujours
    un AgentProfile ET une Agency (creee automatiquement en "agence solo"
    si l'agent n'en a pas encore). AgentProfile.agency est NOT NULL, donc
    l'Agency doit exister avant la creation du profil.
    """
    from apps.agencies.services import create_solo_agency

    try:
        profile = AgentProfile.objects.get(user=user)
    except AgentProfile.DoesNotExist:
        agency = create_solo_agency(user)
        return AgentProfile.objects.create(
            user=user, working_city=working_city_default, agency=agency,
        )

    if profile.agency_id is None:
        agency = create_solo_agency(user, name=profile.agency_name)
        profile.agency = agency
        profile.save(update_fields=["agency"])
    return profile
