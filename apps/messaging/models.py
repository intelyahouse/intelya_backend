import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Conversation(models.Model):

    TYPE_CHOICES = [
        ('client_agent',    'Client ↔ Agent'),
        ('agent_owner',     'Agent ↔ Propriétaire'),
        ('owner_tenant',    'Propriétaire ↔ Locataire'),
        ('agent_forum',     'Forum Agents'),
    ]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    participants  = models.ManyToManyField(User, related_name='conversations')
    title         = models.CharField(max_length=200, null=True, blank=True)

    # Lien vers un bien ou une visite si applicable
    related_property = models.ForeignKey(
        'properties.Property',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    is_active     = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Conversation'
        ordering     = ['-last_message_at']

    def __str__(self):
        return f"Conversation {self.conversation_type} — {self.id}"


class Message(models.Model):

    TYPE_CHOICES = [
        ('text',     'Texte'),
        ('image',    'Image'),
        ('document', 'Document'),
        ('system',   'Système'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE,
        related_name='messages'
    )
    sender       = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='messages_sent'
    )

    message_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='text')
    content      = models.TextField(null=True, blank=True)
    file         = models.FileField(upload_to='messages/files/', null=True, blank=True)

    is_read      = models.BooleanField(default=False)
    read_at      = models.DateTimeField(null=True, blank=True)
    is_deleted   = models.BooleanField(default=False)

    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Message'
        ordering     = ['created_at']

    def __str__(self):
        return f"{self.sender.get_full_name()}: {self.content[:50] if self.content else '[fichier]'}"


class ForumMessage(models.Model):
    """Messagerie inter-agents — confidentielle"""

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender       = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='forum_messages_sent',
        limit_choices_to={'role': 'agent'}
    )
    receiver     = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='forum_messages_received',
        limit_choices_to={'role': 'agent'}
    )

    # Lien vers le bien en question — confidentiel
    related_property = models.ForeignKey(
        'properties.Property',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    content      = models.TextField()
    is_read      = models.BooleanField(default=False)
    read_at      = models.DateTimeField(null=True, blank=True)

    # Résultat de la négociation
    negotiation_status = models.CharField(
        max_length=20,
        choices=[
            ('pending',  'En attente'),
            ('accepted', 'Accepté'),
            ('refused',  'Refusé'),
        ],
        default='pending'
    )

    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Message Forum'
        ordering     = ['created_at']

    def __str__(self):
        return f"Forum: {self.sender.get_full_name()} → {self.receiver.get_full_name()}"
