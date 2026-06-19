import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Transaction(models.Model):

    TYPE_CHOICES = [
        ("visit_fee",  "Frais de visite"),
        ("rent",       "Loyer"),
        ("commission", "Commission agent"),
        ("deposit",    "Caution"),
        ("boost",      "Boost agent"),
        ("refund",     "Remboursement"),
    ]
    STATUS_CHOICES = [
        ("pending",    "En attente"),
        ("processing", "En cours"),
        ("completed",  "Complete"),
        ("failed",     "Echoue"),
        ("refunded",   "Rembourse"),
        ("cancelled",  "Annule"),
    ]
    METHOD_CHOICES = [
        ("mtn",    "MTN Mobile Money"),
        ("orange", "Orange Money"),
        ("bank",   "Compte bancaire"),
        ("cash",   "Especes"),
    ]

    id                 = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference          = models.CharField(max_length=100, unique=True, db_index=True)
    payer              = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="transactions_sent")
    receiver           = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="transactions_received")
    transaction_type   = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    amount             = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency           = models.CharField(max_length=10, default="FCFA")
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    payment_method     = models.CharField(max_length=20, choices=METHOD_CHOICES, null=True, blank=True, db_index=True)
    external_reference = models.CharField(max_length=200, null=True, blank=True, db_index=True)
    idempotency_key    = models.CharField(max_length=200, null=True, blank=True, db_index=True)
    operator_reference = models.CharField(max_length=200, null=True, blank=True)
    webhook_data       = models.JSONField(null=True, blank=True)
    related_lease_id   = models.UUIDField(null=True, blank=True, db_index=True)
    related_visit_id   = models.UUIDField(null=True, blank=True, db_index=True)
    description        = models.TextField(null=True, blank=True)
    receipt_pdf        = models.FileField(upload_to="receipts/", null=True, blank=True)
    completed_at       = models.DateTimeField(null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Transaction"
        ordering     = ["-created_at"]
        indexes = [
            models.Index(fields=["payer", "status"]),
            models.Index(fields=["receiver", "status"]),
            models.Index(fields=["status", "transaction_type"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["payment_method", "status"]),
        ]

    def __str__(self):
        return f"{self.reference} - {self.amount} {self.currency} ({self.status})"


class Escrow(models.Model):
    STATUS_CHOICES = [
        ("held",     "Bloque"),
        ("released", "Libere"),
        ("refunded", "Rembourse"),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction   = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name="escrow")
    amount        = models.DecimalField(max_digits=12, decimal_places=2)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default="held", db_index=True)
    held_for      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="escrows_pending")
    release_after = models.DateTimeField(null=True, blank=True, db_index=True)
    released_at   = models.DateTimeField(null=True, blank=True)
    released_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="escrows_released")
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Escrow"
        indexes = [
            models.Index(fields=["status", "release_after"]),
        ]

    def __str__(self):
        return f"Escrow {self.amount} FCFA - {self.status}"
