import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Notification(models.Model):
    TYPE_CHOICES = [
        ("visit_request",     "Demande de visite"),
        ("visit_scheduled",   "Visite planifiee"),
        ("visit_confirmed",   "Visite confirmee"),
        ("visit_cancelled",   "Visite annulee"),
        ("rent_reminder",     "Rappel loyer"),
        ("rent_late",         "Loyer en retard"),
        ("rent_received",     "Loyer recu"),
        ("lease_renewal",     "Renouvellement bail"),
        ("complaint_new",     "Nouvelle plainte"),
        ("complaint_resolved","Plainte resolue"),
        ("boost_active",      "Boost active"),
        ("boost_expired",     "Boost expire"),
        ("referral_reward",   "Bonus parrainage"),
        ("account_validated", "Compte valide"),
        ("payment_success",   "Paiement reussi"),
        ("payment_failed",    "Paiement echoue"),
        ("agency_invitation",          "Invitation agence"),
        ("agency_invitation_accepted", "Invitation acceptee"),
        ("agency_invitation_declined", "Invitation refusee"),
        ("agency_member_removed",      "Retire de l'agence"),
        ("system",            "Systeme"),
    ]

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient         = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, db_index=True)
    title             = models.CharField(max_length=200)
    body              = models.TextField()
    data              = models.JSONField(null=True, blank=True)
    is_read           = models.BooleanField(default=False, db_index=True)
    read_at           = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Notification"
        ordering     = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["recipient", "notification_type"]),
            models.Index(fields=["recipient", "created_at"]),
            models.Index(fields=["is_read", "created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient.get_full_name()} - {self.title}"
