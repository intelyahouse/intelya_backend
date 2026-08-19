import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Collaboration(models.Model):
    """Accord de collaboration entre deux agences sur un bien : l'agence du
    client (qui a apporte le client) et l'agence du bien (qui le gere),
    avec une repartition de commission negociee entre elles."""

    STATUS_CHOICES = [
        ("proposed",  "Proposee"),
        ("accepted",  "Acceptee"),
        ("rejected",  "Refusee"),
        ("cancelled", "Annulee"),
    ]

    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(
        "properties.Property", on_delete=models.CASCADE, related_name="collaborations"
    )
    client   = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="collaborations", limit_choices_to={"role__in": ["client", "tenant"]},
    )

    client_agency   = models.ForeignKey(
        "agencies.Agency", on_delete=models.PROTECT, related_name="collaborations_as_client_agency",
    )
    property_agency = models.ForeignKey(
        "agencies.Agency", on_delete=models.PROTECT, related_name="collaborations_as_property_agency",
    )

    initiated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="collaborations_initiated",
    )

    client_agency_amount   = models.DecimalField(max_digits=10, decimal_places=2)
    property_agency_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount            = models.DecimalField(max_digits=10, decimal_places=2)

    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default="proposed", db_index=True)
    last_proposed_by_agency = models.ForeignKey(
        "agencies.Agency", on_delete=models.SET_NULL, null=True, related_name="+",
    )
    responded_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="collaborations_responded",
    )
    responded_at  = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Collaboration"
        verbose_name_plural = "Collaborations"
        indexes = [
            models.Index(fields=["client_agency", "status"]),
            models.Index(fields=["property_agency", "status"]),
            models.Index(fields=["property", "status"]),
        ]

    def __str__(self):
        return f"{self.client_agency.name} <-> {self.property_agency.name} sur {self.property_id} ({self.status})"


class CollaborationProposal(models.Model):
    """Historique immuable de chaque proposition de repartition faite sur
    une Collaboration -- jamais modifie ni supprime, sert de piste d'audit."""

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collaboration  = models.ForeignKey(Collaboration, on_delete=models.CASCADE, related_name="proposals")
    proposed_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    proposed_by_agency = models.ForeignKey("agencies.Agency", on_delete=models.SET_NULL, null=True)

    client_agency_amount   = models.DecimalField(max_digits=10, decimal_places=2)
    property_agency_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount            = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Proposition de Collaboration"
        verbose_name_plural = "Propositions de Collaboration"
        ordering = ["created_at"]

    def __str__(self):
        return f"Proposition {self.total_amount} sur {self.collaboration_id} ({self.created_at:%Y-%m-%d})"
