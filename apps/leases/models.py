import uuid
from django.db import models
from django.contrib.auth import get_user_model
from apps.contracts.models import LeaseContract

User = get_user_model()


class RentPayment(models.Model):
    STATUS_CHOICES = [
        ("pending",  "En attente"),
        ("paid",     "Paye"),
        ("late",     "En retard"),
        ("disputed", "Conteste"),
    ]
    PAYMENT_METHOD_CHOICES = [
        ("mtn",    "MTN Mobile Money"),
        ("orange", "Orange Money"),
        ("bank",   "Virement bancaire"),
        ("cash",   "Especes"),
    ]

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease             = models.ForeignKey(LeaseContract, on_delete=models.CASCADE, related_name="rent_payments")
    tenant            = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rent_payments_made")
    amount            = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    agency_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    owner_amount      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    payment_method    = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True)
    payment_reference = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    due_date          = models.DateField(db_index=True)
    paid_at           = models.DateTimeField(null=True, blank=True)
    confirmed_by_agent = models.BooleanField(default=False)
    confirmed_at      = models.DateTimeField(null=True, blank=True)
    alert_sent_minus5 = models.BooleanField(default=False)
    alert_sent_plus3  = models.BooleanField(default=False)
    alert_sent_plus7  = models.BooleanField(default=False)
    alert_sent_plus15 = models.BooleanField(default=False)
    alert_sent_plus30 = models.BooleanField(default=False)
    receipt_pdf       = models.FileField(upload_to="receipts/", null=True, blank=True)
    period_month      = models.IntegerField()
    period_year       = models.IntegerField()
    notes             = models.TextField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name    = "Paiement de loyer"
        unique_together = ["lease", "period_month", "period_year"]
        ordering        = ["-due_date"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["lease", "status"]),
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["due_date", "alert_sent_minus5"]),
            models.Index(fields=["due_date", "alert_sent_plus3"]),
            models.Index(fields=["due_date", "alert_sent_plus7"]),
            models.Index(fields=["due_date", "alert_sent_plus30"]),
        ]

    def __str__(self):
        return f"Loyer {self.period_month}/{self.period_year} - {self.tenant.get_full_name()}"


class DebtRecord(models.Model):
    ACTION_CHOICES = [
        ("extend",   "Prolonger"),
        ("claim",    "Reclamer"),
        ("blocked",  "Bloque"),
        ("resolved", "Resolu"),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease        = models.ForeignKey(LeaseContract, on_delete=models.CASCADE, related_name="debts")
    rent_payment = models.ForeignKey(RentPayment, on_delete=models.CASCADE, related_name="debt_records")
    tenant       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="debts")
    agent        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_debts")
    amount_owed  = models.DecimalField(max_digits=12, decimal_places=2)
    action_taken = models.CharField(max_length=20, choices=ACTION_CHOICES, null=True, blank=True, db_index=True)
    new_due_date = models.DateField(null=True, blank=True)
    notes        = models.TextField(null=True, blank=True)
    resolved_at  = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dette locataire"
        ordering     = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "action_taken"]),
            models.Index(fields=["agent", "action_taken"]),
            models.Index(fields=["lease", "action_taken"]),
        ]

    def __str__(self):
        return f"Dette {self.tenant.get_full_name()} - {self.amount_owed} FCFA"


class Complaint(models.Model):
    STATUS_CHOICES = [
        ("open",        "Ouverte"),
        ("in_progress", "En cours"),
        ("resolved",    "Resolue"),
        ("escalated",   "Escaladee admin"),
    ]
    CATEGORY_CHOICES = [
        ("maintenance", "Maintenance / Reparation"),
        ("payment",     "Probleme de paiement"),
        ("neighbor",    "Probleme de voisinage"),
        ("security",    "Probleme de securite"),
        ("water",       "Eau / Electricite"),
        ("other",       "Autre"),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease           = models.ForeignKey(LeaseContract, on_delete=models.CASCADE, related_name="complaints")
    tenant          = models.ForeignKey(User, on_delete=models.CASCADE, related_name="complaints_filed")
    assigned_to     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints_assigned")
    agency          = models.ForeignKey("agencies.Agency", on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints")
    category        = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    title           = models.CharField(max_length=200)
    description     = models.TextField()
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open", db_index=True)
    resolution_note = models.TextField(null=True, blank=True)
    resolved_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plainte"
        ordering     = ["-created_at"]
        indexes = [
            models.Index(fields=["lease", "status"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["agency", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"Plainte: {self.title} ({self.status})"
