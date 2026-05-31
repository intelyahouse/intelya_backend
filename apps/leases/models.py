import uuid
from django.db import models
from django.contrib.auth import get_user_model
from apps.contracts.models import LeaseContract

User = get_user_model()


class RentPayment(models.Model):
    """Paiement de loyer mensuel"""

    STATUS_CHOICES = [
        ('pending',  'En attente'),
        ('paid',     'Payé'),
        ('late',     'En retard'),
        ('disputed', 'Contesté'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('mtn',    'MTN Mobile Money'),
        ('orange', 'Orange Money'),
        ('bank',   'Virement bancaire'),
        ('cash',   'Espèces'),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease         = models.ForeignKey(
        LeaseContract, on_delete=models.CASCADE,
        related_name='rent_payments'
    )
    tenant        = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='rent_payments_made'
    )

    amount        = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    owner_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True)
    payment_reference = models.CharField(max_length=100, null=True, blank=True)

    due_date      = models.DateField()
    paid_at       = models.DateTimeField(null=True, blank=True)

    # Confirmation agent (pour paiement cash)
    confirmed_by_agent = models.BooleanField(default=False)
    confirmed_at       = models.DateTimeField(null=True, blank=True)

    # Alertes envoyées
    alert_sent_minus5  = models.BooleanField(default=False)
    alert_sent_plus3   = models.BooleanField(default=False)
    alert_sent_plus7   = models.BooleanField(default=False)
    alert_sent_plus15  = models.BooleanField(default=False)
    alert_sent_plus30  = models.BooleanField(default=False)

    receipt_pdf   = models.FileField(upload_to='receipts/', null=True, blank=True)
    period_month  = models.IntegerField()
    period_year   = models.IntegerField()
    notes         = models.TextField(null=True, blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Paiement de loyer'
        unique_together = ['lease', 'period_month', 'period_year']
        ordering = ['-due_date']

    def __str__(self):
        return f"Loyer {self.period_month}/{self.period_year} - {self.tenant.get_full_name()}"


class DebtRecord(models.Model):
    """Gestion des dettes locataires"""

    ACTION_CHOICES = [
        ('extend',  'Prolonger'),
        ('claim',   'Réclamer'),
        ('blocked', 'Bloqué'),
        ('resolved','Résolu'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease       = models.ForeignKey(
        LeaseContract, on_delete=models.CASCADE,
        related_name='debts'
    )
    rent_payment = models.ForeignKey(
        RentPayment, on_delete=models.CASCADE,
        related_name='debt_records'
    )
    tenant      = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='debts'
    )
    agent       = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='managed_debts',
        null=True, blank=True
    )

    amount_owed  = models.DecimalField(max_digits=12, decimal_places=2)
    action_taken = models.CharField(max_length=20, choices=ACTION_CHOICES, null=True, blank=True)
    new_due_date = models.DateField(null=True, blank=True)
    notes        = models.TextField(null=True, blank=True)
    resolved_at  = models.DateTimeField(null=True, blank=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dette locataire'
        ordering = ['-created_at']

    def __str__(self):
        return f"Dette {self.tenant.get_full_name()} - {self.amount_owed} FCFA"


class Complaint(models.Model):
    """Plainte d'un locataire sur un bien"""

    STATUS_CHOICES = [
        ('open',     'Ouverte'),
        ('in_progress', 'En cours'),
        ('resolved', 'Résolue'),
        ('escalated','Escaladée admin'),
    ]

    CATEGORY_CHOICES = [
        ('maintenance', 'Maintenance / Réparation'),
        ('payment',     'Problème de paiement'),
        ('neighbor',    'Problème de voisinage'),
        ('security',    'Problème de sécurité'),
        ('water',       'Eau / Électricité'),
        ('other',       'Autre'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease       = models.ForeignKey(
        LeaseContract, on_delete=models.CASCADE,
        related_name='complaints'
    )
    tenant      = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='complaints_filed'
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='complaints_assigned'
    )

    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title       = models.CharField(max_length=200)
    description = models.TextField()
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution_note = models.TextField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plainte'
        ordering = ['-created_at']

    def __str__(self):
        return f"Plainte: {self.title} ({self.status})"
