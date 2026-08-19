from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User


@receiver(post_save, sender=User)
def ensure_role_profile_exists(sender, instance, **kwargs):
    """
    Filet de securite : quel que soit le chemin par lequel un compte agent/owner
    est valide (le vrai bouton "Valider" de la plateforme, OU l'admin Django
    directement), on s'assure que son profil (AgentProfile/OwnerProfile) existe.
    Idempotent (get_or_create) donc sans risque a chaque sauvegarde.
    """
    if not instance.is_validated:
        return

    if instance.role == 'agent':
        from apps.agents.services import ensure_agent_profile_and_agency
        ensure_agent_profile_and_agency(instance)
    elif instance.role == 'owner':
        from apps.owners.models import OwnerProfile
        OwnerProfile.objects.get_or_create(user=instance)
