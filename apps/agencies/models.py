import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Agency(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=200)
    owner_agent = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name="owned_agencies",
        limit_choices_to={"role": "agent"},
    )
    is_solo     = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Agence"
        verbose_name_plural = "Agences"

    def __str__(self):
        return self.name
