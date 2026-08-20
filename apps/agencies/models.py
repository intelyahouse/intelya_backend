import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Agency(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=200)
    owner_agent = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name="owned_agencies",
        limit_choices_to={"role": "agent"},
    )
    is_solo     = models.BooleanField(default=True, db_index=True)

    mtn_momo_number     = models.CharField(max_length=20, null=True, blank=True)
    orange_money_number = models.CharField(max_length=20, null=True, blank=True)
    bank_account_number = models.CharField(max_length=50, null=True, blank=True)
    bank_name           = models.CharField(max_length=100, null=True, blank=True)

    # ===== REPUTATION =====
    # reliability_score/total_reviews : moyenne objective de tous les avis
    # recus par tous les agents de l'agence (recalculee a chaque nouvel avis
    # et a chaque changement de composition de l'agence).
    # disputes_confirmed_against : simple compteur des litiges ou l'admin a
    # tranche en faveur du plaignant contre un agent de cette agence -- un
    # fait objectif, delibrement PAS transforme en penalite automatique sur
    # le score : la regle de ponderation exacte reste une decision metier a
    # definir, pas quelque chose a inventer ici.
    reliability_score          = models.FloatField(default=0.0, db_index=True)
    total_reviews              = models.IntegerField(default=0)
    disputes_confirmed_against = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Agence"
        verbose_name_plural = "Agences"

    def __str__(self):
        return self.name

    def update_reliability_score(self):
        from django.db.models import Avg
        from apps.reviews.models import Review

        member_user_ids = self.agents.values_list('user_id', flat=True)
        reviews = Review.objects.filter(agent_id__in=member_user_ids, agent_rating__isnull=False)
        if reviews.exists():
            avg = reviews.aggregate(Avg('agent_rating'))['agent_rating__avg']
            self.reliability_score = round(avg, 2)
            self.total_reviews = reviews.count()
        else:
            self.reliability_score = 0.0
            self.total_reviews = 0
        self.save(update_fields=['reliability_score', 'total_reviews'])


class AgencyInvitation(models.Model):
    STATUS_CHOICES = [
        ("pending",   "En attente"),
        ("accepted",  "Acceptee"),
        ("declined",  "Refusee"),
        ("cancelled", "Annulee"),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency       = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name="invitations")
    invited_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="agency_invitations",
        limit_choices_to={"role": "agent"},
    )
    invited_by   = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_agency_invitations",
        limit_choices_to={"role": "agent"},
    )
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    responded_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = "Invitation Agence"
        verbose_name_plural = "Invitations Agence"
        indexes = [
            models.Index(fields=["invited_user", "status"]),
            models.Index(fields=["agency", "status"]),
        ]

    def __str__(self):
        return f"{self.agency.name} -> {self.invited_user.get_full_name()} ({self.status})"
