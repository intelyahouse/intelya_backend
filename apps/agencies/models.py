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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Agence"
        verbose_name_plural = "Agences"

    def __str__(self):
        return self.name


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
