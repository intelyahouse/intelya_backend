import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Referral(models.Model):
    STATUS_CHOICES = [
        ("pending",  "En attente"),
        ("rewarded", "Recompense"),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer     = models.ForeignKey(User, on_delete=models.CASCADE, related_name="referrals_made")
    referred     = models.ForeignKey(User, on_delete=models.CASCADE, related_name="referral_received")
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rewarded_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name    = "Parrainage"
        unique_together = ["referrer", "referred"]
        indexes = [
            models.Index(fields=["referrer", "status"]),
            models.Index(fields=["referred", "status"]),
        ]

    def __str__(self):
        return f"{self.referrer.get_full_name()} -> {self.referred.get_full_name()}"
