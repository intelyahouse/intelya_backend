import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Transaction(models.Model):

    TYPE_CHOICES = [
        ('visit_fee',    'Frais de visite'),
        ('rent',         'Loyer'),
        ('commission',   'Commission agent'),
        ('deposit',      'Caution'),
        ('boost',        'Boost agent'),
        ('refund',       'Remboursement'),
    ]

    STATUS_CHOICES = [
        ('pending',   'En attente'),
        ('processing','En cours'),
        ('completed', 'Complété'),
        ('failed',    'Échoué'),
        ('refunded',  'Remboursé'),
        ('cancelled', 'Annulé'),
    ]

    METHOD_CHOICES = [
        ('mtn',    'MTN Mobile Money'),
        ('orange', 'Orange Money'),
        ('bank',   'Compte bancaire'),
        ('cash',   'Espèces'),
    ]

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference         = models.CharField(max_length=100, unique=True)
    payer             = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='transactions_sent'
    )
    receiver          = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='transactions_received'
    )

    transaction_type  = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount            = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount        = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency          = models.CharField(max_length=10, default='FCFA')

    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method    = models.CharField(max_length=20, choices=METHOD_CHOICES, null=True, blank=True)

    # Références externes (API opérateurs)
    external_reference = models.CharField(max_length=200, null=True, blank=True)
    operator_reference = models.CharField(max_length=200, null=True, blank=True)
    webhook_data       = models.JSONField(null=True, blank=True)

    # Liens vers les objets concernés
    related_lease_id   = models.UUIDField(null=True, blank=True)
    related_visit_id   = models.UUIDField(null=True, blank=True)

    description        = models.TextField(null=True, blank=True)
    receipt_pdf        = models.FileField(upload_to='receipts/', null=True, blank=True)

    completed_at       = models.DateTimeField(null=True, blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transaction'
        ordering     = ['-created_at']

    def __str__(self):
        return f"{self.reference} — {self.amount} {self.currency} ({self.status})"


class Escrow(models.Model):
    """Argent bloqué en attente de confirmation"""

    STATUS_CHOICES = [
        ('held',     'Bloqué'),
        ('released', 'Libéré'),
        ('refunded', 'Remboursé'),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction   = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='escrow')
    amount        = models.DecimalField(max_digits=12, decimal_places=2)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='held')

    held_for      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='escrows_pending'
    )
    release_after = models.DateTimeField(null=True, blank=True)
    released_at   = models.DateTimeField(null=True, blank=True)
    released_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='escrows_released', blank=True
    )

    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Escrow'

    def __str__(self):
        return f"Escrow {self.amount} FCFA — {self.status}"
