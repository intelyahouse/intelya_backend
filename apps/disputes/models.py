import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Dispute(models.Model):

    TYPE_CHOICES = [
        ('visit',    'Litige visite'),
        ('payment',  'Litige paiement'),
        ('property', 'Litige bien'),
        ('agent',    'Litige agent'),
        ('other',    'Autre'),
    ]

    STATUS_CHOICES = [
        ('open',     'Ouvert'),
        ('reviewing','En examen'),
        ('resolved', 'Résolu'),
        ('closed',   'Fermé'),
    ]

    DECISION_CHOICES = [
        ('claimant_wins',    'Demandeur gagne'),
        ('defendant_wins',   'Défendeur gagne'),
        ('compromise',       'Compromis'),
        ('no_action',        'Aucune action'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claimant     = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='disputes_filed'
    )
    defendant    = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='disputes_received'
    )
    dispute_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    title        = models.CharField(max_length=200)
    description  = models.TextField()
    evidence     = models.FileField(upload_to='disputes/evidence/', null=True, blank=True)

    defendant_response = models.TextField(null=True, blank=True)
    defendant_responded_at = models.DateTimeField(null=True, blank=True)

    decision     = models.CharField(max_length=20, choices=DECISION_CHOICES, null=True, blank=True)
    decision_note = models.TextField(null=True, blank=True)
    decided_by   = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='disputes_decided'
    )
    decided_at   = models.DateTimeField(null=True, blank=True)

    related_visit_id    = models.UUIDField(null=True, blank=True)
    related_payment_id  = models.UUIDField(null=True, blank=True)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Litige'
        ordering     = ['-created_at']

    def __str__(self):
        return f"Litige: {self.title} ({self.status})"


class Report(models.Model):

    REASON_CHOICES = [
        ('abusive',      'Comportement abusif'),
        ('fake_info',    'Fausse information'),
        ('fraud',        'Fraude'),
        ('harassment',   'Harcèlement'),
        ('inappropriate','Contenu inapproprié'),
        ('other',        'Autre'),
    ]

    STATUS_CHOICES = [
        ('pending',  'En attente'),
        ('reviewed', 'Examiné'),
        ('action_taken', 'Action prise'),
        ('dismissed','Rejeté'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reporter    = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='reports_made'
    )
    reported    = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='reports_received'
    )

    reason      = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField()
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_note  = models.TextField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reports_reviewed'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Signalement'
        ordering     = ['-created_at']

    def __str__(self):
        return f"Signalement: {self.reporter.get_full_name()} → {self.reported.get_full_name()}"
