import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class Boost(models.Model):

    LEVEL_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Argent'),
        ('gold',   'Or'),
    ]

    DURATION_CHOICES = [
        (7,  '7 jours'),
        (15, '15 jours'),
        (30, '30 jours'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent        = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='boosts',
        limit_choices_to={'role': 'agent'}
    )

    level        = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='bronze')
    duration_days = models.IntegerField(choices=DURATION_CHOICES, default=7)
    target_city  = models.CharField(max_length=100)
    target_neighborhood = models.CharField(max_length=100, null=True, blank=True)

    price_paid   = models.DecimalField(max_digits=10, decimal_places=2)
    is_active    = models.BooleanField(default=True)

    start_date   = models.DateTimeField(default=timezone.now)
    end_date     = models.DateTimeField()

    transaction        = models.ForeignKey(
        "payments.Transaction",
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    payment_reference  = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    payment_verified   = models.BooleanField(default=False, db_index=True)

    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Boost Agent'
        ordering     = ['-created_at']

    def __str__(self):
        return f"Boost {self.level} — {self.agent.get_full_name()} ({self.target_city})"

    def is_expired(self):
        return timezone.now() > self.end_date

    PRICES = {
        'bronze': {7: 5000,  15: 10000, 30: 18000},
        'silver': {7: 10000, 15: 20000, 30: 35000},
        'gold':   {7: 20000, 15: 38000, 30: 65000},
    }

    LEVEL_ORDER = {'bronze': 1, 'silver': 2, 'gold': 3}

    @classmethod
    def get_price(cls, level, duration):
        return cls.PRICES.get(level, {}).get(duration, 0)
