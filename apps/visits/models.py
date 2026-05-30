import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class VisitRequest(models.Model):

    STATUS_CHOICES = [
        ('pending',   'En attente'),
        ('scheduled', 'Programmée'),
        ('completed', 'Effectuée'),
        ('cancelled', 'Annulée'),
    ]

    CANCEL_BY_CHOICES = [
        ('client', 'Client'),
        ('agent',  'Agent'),
        ('system', 'Système'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client          = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='visit_requests',
        limit_choices_to={'role__in': ['client', 'tenant']}
    )
    agent           = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='agent_visits',
        limit_choices_to={'role': 'agent'}
    )
    # RENOMMÉ — property est un mot réservé Python
    rental_property = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='visits'
    )

    # ===== STATUT =====
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # ===== PLANIFICATION =====
    scheduled_date  = models.DateField(null=True, blank=True)
    scheduled_time  = models.TimeField(null=True, blank=True)

    # ===== PAIEMENT =====
    visit_fee       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_free         = models.BooleanField(default=True)
    payment_status  = models.CharField(
        max_length=20,
        choices=[
            ('not_required', 'Non requis'),
            ('pending',      'En attente'),
            ('paid',         'Payé'),
            ('released',     'Libéré'),
            ('refunded',     'Remboursé'),
        ],
        default='not_required'
    )
    payment_reference = models.CharField(max_length=100, null=True, blank=True)

    # ===== CONFIRMATION GPS =====
    client_gps_confirmed = models.BooleanField(default=False)
    client_gps_lat       = models.FloatField(null=True, blank=True)
    client_gps_lng       = models.FloatField(null=True, blank=True)
    client_confirmed_at  = models.DateTimeField(null=True, blank=True)
    agent_confirmed      = models.BooleanField(default=False)
    agent_confirmed_at   = models.DateTimeField(null=True, blank=True)

    # ===== ANNULATION =====
    cancelled_by        = models.CharField(max_length=10, choices=CANCEL_BY_CHOICES, null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    cancelled_at        = models.DateTimeField(null=True, blank=True)

    # ===== LIBÉRATION AUTO =====
    auto_release_at     = models.DateTimeField(null=True, blank=True)

    # ===== MESSAGE =====
    client_message      = models.TextField(null=True, blank=True)

    # ===== DATES =====
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Demande de visite'
        ordering     = ['-created_at']

    def __str__(self):
        return f"Visite {self.client.get_full_name()} → {self.rental_property.title} ({self.status})"

    def is_both_confirmed(self):
        return self.client_gps_confirmed and self.agent_confirmed

    def can_be_released(self):
        from django.utils import timezone
        return (
            self.is_both_confirmed() or
            (self.auto_release_at and timezone.now() >= self.auto_release_at)
        )


class VisitReview(models.Model):
    """Avis laissé après visite confirmée GPS"""

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    visit            = models.OneToOneField(VisitRequest, on_delete=models.CASCADE, related_name='review')
    client           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='visit_reviews')

    property_rating  = models.IntegerField(null=True, blank=True)
    property_comment = models.TextField(null=True, blank=True)
    agent_rating     = models.IntegerField(null=True, blank=True)
    agent_comment    = models.TextField(null=True, blank=True)

    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Avis de visite'

    def __str__(self):
        return f"Avis {self.visit.rental_property.title}"
