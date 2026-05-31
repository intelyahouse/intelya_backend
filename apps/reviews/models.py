import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Review(models.Model):

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reviewer         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given')
    agent            = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_reviews', limit_choices_to={'role': 'agent'})
    rental_property  = models.ForeignKey('properties.Property', on_delete=models.SET_NULL, null=True, blank=True, related_name='property_reviews')

    # Notes séparées
    agent_rating     = models.IntegerField(null=True, blank=True)
    agent_comment    = models.TextField(null=True, blank=True)
    property_rating  = models.IntegerField(null=True, blank=True)
    property_comment = models.TextField(null=True, blank=True)

    # Vérification GPS obligatoire
    gps_verified     = models.BooleanField(default=False)
    visit_id         = models.UUIDField(null=True, blank=True)

    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Avis'
        ordering     = ['-created_at']

    def __str__(self):
        return f"Avis de {self.reviewer.get_full_name()}"
