import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AgentOwnerContract(models.Model):
    """Contrat entre agent et propriétaire"""

    STATUS_CHOICES = [
        ('active',     'Actif'),
        ('expired',    'Expiré'),
        ('terminated', 'Résilié'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent        = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='agent_contracts',
        limit_choices_to={'role': 'agent'}
    )
    owner        = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='owner_contracts',
        limit_choices_to={'role': 'owner'}
    )

    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    start_date    = models.DateField()
    end_date      = models.DateField(null=True, blank=True)
    terms         = models.TextField(null=True, blank=True)

    # PDF généré
    pdf_file      = models.FileField(upload_to='contracts/agent_owner/', null=True, blank=True)
    signed_at     = models.DateTimeField(null=True, blank=True)
    signed_by_agent = models.BooleanField(default=False)
    signed_by_owner = models.BooleanField(default=False)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contrat Agent-Propriétaire'
        ordering     = ['-created_at']

    def __str__(self):
        return f"Contrat {self.agent.get_full_name()} ↔ {self.owner.get_full_name()}"

    def is_fully_signed(self):
        return self.signed_by_agent and self.signed_by_owner


class LeaseContract(models.Model):
    """Bail entre locataire et propriétaire"""

    STATUS_CHOICES = [
        ('draft',      'Brouillon'),
        ('active',     'Actif'),
        ('expired',    'Expiré'),
        ('terminated', 'Résilié'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant       = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='lease_contracts',
        limit_choices_to={'role__in': ['client', 'tenant']}
    )
    owner        = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='landlord_contracts',
        limit_choices_to={'role': 'owner'}
    )
    agent        = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='managed_contracts',
        limit_choices_to={'role': 'agent'},
        null=True, blank=True
    )
    rental_property = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='lease_contracts'
    )

    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # ===== CONDITIONS FINANCIÈRES =====
    monthly_rent       = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_amount     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=2)
    agent_commission   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_paid    = models.BooleanField(default=False)
    commission_before_rent = models.BooleanField(default=True)

    # ===== DURÉE =====
    start_date    = models.DateField()
    end_date      = models.DateField()
    min_duration_months = models.IntegerField(default=1)

    # ===== PAIEMENT =====
    payment_day   = models.IntegerField(default=1)  # Jour du mois

    # ===== DOCUMENTS =====
    pdf_file      = models.FileField(upload_to='contracts/leases/', null=True, blank=True)
    signed_by_tenant = models.BooleanField(default=False)
    signed_by_owner  = models.BooleanField(default=False)
    signed_at     = models.DateTimeField(null=True, blank=True)

    # ===== RENOUVELLEMENT =====
    renewal_notified    = models.BooleanField(default=False)
    renewal_notified_at = models.DateTimeField(null=True, blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bail'
        ordering     = ['-created_at']

    def __str__(self):
        return f"Bail {self.tenant.get_full_name()} → {self.rental_property.title}"

    def is_fully_signed(self):
        return self.signed_by_tenant and self.signed_by_owner

    def get_renewal_notification_date(self):
        """Date à laquelle envoyer le rappel de renouvellement (83% de la durée)"""
        from django.conf import settings
        total_days = (self.end_date - self.start_date).days
        renewal_day = int(total_days * settings.LEASE_RENEWAL_PERCENT / 100)
        from datetime import timedelta
        return self.start_date + timedelta(days=renewal_day)
