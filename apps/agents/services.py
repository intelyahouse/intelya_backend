from .models import AgentProfile


def ensure_agent_profile_and_agency(user, working_city_default="Non définie"):
    """
    Filet de securite idempotent : garantit qu'un agent valide a toujours
    un AgentProfile ET une Agency (creee automatiquement en "agence solo"
    si l'agent n'en a pas encore). AgentProfile.agency est NOT NULL, donc
    l'Agency doit exister avant la creation du profil.
    """
    from apps.agencies.models import Agency

    try:
        profile = AgentProfile.objects.get(user=user)
    except AgentProfile.DoesNotExist:
        agency = Agency.objects.create(
            name=f"Agence de {user.get_full_name() or user.email}",
            owner_agent=user,
        )
        return AgentProfile.objects.create(
            user=user, working_city=working_city_default, agency=agency,
        )

    if profile.agency_id is None:
        name = (profile.agency_name or "").strip() or f"Agence de {user.get_full_name() or user.email}"
        agency = Agency.objects.create(name=name, owner_agent=user)
        profile.agency = agency
        profile.save(update_fields=["agency"])
    return profile
