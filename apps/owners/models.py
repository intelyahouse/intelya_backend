import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class OwnerProfile(models.Model):

    id    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user  = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='owner_profile'
    )

    # ===== INFORMATIONS =====
    bio              = models.TextField(null=True, blank=True)
    property_count   = models.IntegerField(default=0)

    # ===== TITRE FONCIER =====
    land_title       = models.FileField(upload_to='owners/docs/', null=True, blank=True)
    land_title_number = models.CharField(max_length=100, null=True, blank=True)

    # ===== COMPTES BANCAIRES (pour recevoir les loyers) =====
    mtn_momo_number     = models.CharField(max_length=20, null=True, blank=True)
    orange_money_number = models.CharField(max_length=20, null=True, blank=True)
    bank_account_number = models.CharField(max_length=50, null=True, blank=True)
    bank_name           = models.CharField(max_length=100, null=True, blank=True)

    # ===== PARAMÈTRES =====
    # Si False = propriétaire hors plateforme (agent gère tout)
    manages_own_tenants = models.BooleanField(default=True)

    # ===== DATES =====
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil Propriétaire'

    def __str__(self):
        return f"Propriétaire: {self.user.get_full_name()}"

    def get_active_agent(self):
        """Retourne l'agent actif du propriétaire"""
        from apps.agents.models import OwnerAgentRelation
        relation = OwnerAgentRelation.objects.filter(
            owner=self.user, status='active'
        ).select_related('agent').first()
        return relation.agent if relation else None

    def has_active_agent(self):
        return self.get_active_agent() is not None
