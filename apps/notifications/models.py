import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Notification(models.Model):

    TYPE_CHOICES = [
        ('visit_request',    'Demande de visite'),
        ('visit_scheduled',  'Visite planifiée'),
        ('visit_confirmed',  'Visite confirmée'),
        ('visit_cancelled',  'Visite annulée'),
        ('rent_reminder',    'Rappel loyer'),
        ('rent_late',        'Loyer en retard'),
        ('rent_received',    'Loyer reçu'),
        ('lease_renewal',    'Renouvellement bail'),
        ('complaint_new',    'Nouvelle plainte'),
        ('complaint_resolved','Plainte résolue'),
        ('boost_active',     'Boost activé'),
        ('boost_expired',    'Boost expiré'),
        ('referral_reward',  'Bonus parrainage'),
        ('account_validated','Compte validé'),
        ('payment_success',  'Paiement réussi'),
        ('payment_failed',   'Paiement échoué'),
        ('system',           'Système'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    title        = models.CharField(max_length=200)
    body         = models.TextField()
    data         = models.JSONField(null=True, blank=True)
    is_read      = models.BooleanField(default=False)
    read_at      = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        ordering     = ['-created_at']

    def __str__(self):
        return f"{self.recipient.get_full_name()} — {self.title}"
