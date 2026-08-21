import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AgentOwnerContract(models.Model):
    STATUS_CHOICES = [
        ("active",     "Actif"),
        ("expired",    "Expire"),
        ("terminated", "Resilie"),
    ]

    id                 = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent              = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agent_contracts", limit_choices_to={"role": "agent"})
    owner              = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owner_contracts", limit_choices_to={"role": "owner"})
    agency             = models.ForeignKey("agencies.Agency", on_delete=models.PROTECT, related_name="agent_owner_contracts", null=True, blank=True)
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    start_date         = models.DateField(db_index=True)
    end_date           = models.DateField(null=True, blank=True, db_index=True)
    terms              = models.TextField(null=True, blank=True)
    pdf_file           = models.FileField(upload_to="contracts/agent_owner/", null=True, blank=True)
    signed_at          = models.DateTimeField(null=True, blank=True)
    signed_by_agent    = models.BooleanField(default=False)
    signed_by_owner    = models.BooleanField(default=False)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Contrat Agent-Proprietaire"
        ordering     = ["-created_at"]
        indexes = [
            models.Index(fields=["agent", "status"]),
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["status", "end_date"]),
        ]

    def __str__(self):
        return f"Contrat {self.agent.get_full_name()} - {self.owner.get_full_name()}"

    def is_fully_signed(self):
        return self.signed_by_agent and self.signed_by_owner


class LeaseContract(models.Model):
    STATUS_CHOICES = [
        ("draft",      "Brouillon"),
        ("active",     "Actif"),
        ("expired",    "Expire"),
        ("terminated", "Resilie"),
    ]

    id                     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant                 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="lease_contracts", limit_choices_to={"role__in": ["client", "tenant"]})
    owner                  = models.ForeignKey(User, on_delete=models.CASCADE, related_name="landlord_contracts", limit_choices_to={"role": "owner"})
    agent                  = models.ForeignKey(User, on_delete=models.CASCADE, related_name="managed_contracts", limit_choices_to={"role": "agent"}, null=True, blank=True)
    agency                 = models.ForeignKey("agencies.Agency", on_delete=models.PROTECT, related_name="lease_contracts", null=True, blank=True)
    rental_property        = models.ForeignKey("properties.Property", on_delete=models.CASCADE, related_name="lease_contracts")
    status                 = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    monthly_rent           = models.DecimalField(max_digits=12, decimal_places=2)
    deposit_amount         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_fee_percent   = models.DecimalField(max_digits=5, decimal_places=2, default=2)
    agent_commission       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_paid        = models.BooleanField(default=False)
    commission_before_rent = models.BooleanField(default=True)
    start_date             = models.DateField(db_index=True)
    end_date               = models.DateField(db_index=True)
    min_duration_months    = models.IntegerField(default=1)
    payment_day            = models.IntegerField(default=1)
    pdf_file               = models.FileField(upload_to="contracts/leases/", null=True, blank=True)
    signed_by_tenant       = models.BooleanField(default=False)
    signed_by_owner        = models.BooleanField(default=False)
    signed_at              = models.DateTimeField(null=True, blank=True)
    renewal_notified       = models.BooleanField(default=False)
    renewal_notified_at    = models.DateTimeField(null=True, blank=True)
    created_at             = models.DateTimeField(auto_now_add=True)
    updated_at             = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bail"
        ordering     = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["agent", "status"]),
            models.Index(fields=["agency", "status"]),
            models.Index(fields=["status", "end_date"]),
            models.Index(fields=["renewal_notified", "end_date"]),
            models.Index(fields=["rental_property", "status"]),
        ]

    def __str__(self):
        return f"Bail {self.tenant.get_full_name()} -> {self.rental_property.title}"

    def is_fully_signed(self):
        return self.signed_by_tenant and self.signed_by_owner

    def get_renewal_notification_date(self):
        from django.conf import settings
        from datetime import timedelta
        total_days   = (self.end_date - self.start_date).days
        renewal_day  = int(total_days * settings.LEASE_RENEWAL_PERCENT / 100)
        return self.start_date + timedelta(days=renewal_day)
