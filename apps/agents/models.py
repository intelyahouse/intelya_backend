import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class AgentProfile(models.Model):

    CERTIFICATION_CHOICES = [
        ("basic",     "Agent Basique"),
        ("certified", "Agent Certifie"),
        ("premium",   "Agent Premium"),
    ]

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user                = models.OneToOneField(User, on_delete=models.CASCADE, related_name="agent_profile")
    agency_name         = models.CharField(max_length=200, null=True, blank=True)
    agency              = models.ForeignKey(
        "agencies.Agency", on_delete=models.PROTECT,
        related_name="agents",
    )
    bio                 = models.TextField(null=True, blank=True)
    certification_level = models.CharField(max_length=20, choices=CERTIFICATION_CHOICES, default="basic", db_index=True)

    working_city  = models.CharField(max_length=100, db_index=True)
    working_zones = models.JSONField(default=list)

    commission_type       = models.CharField(max_length=10, choices=[("percent","Pourcentage"),("fixed","Fixe")], default="percent")
    commission_value      = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    visit_fee             = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    visit_fee_is_free     = models.BooleanField(default=True)
    commission_before_rent = models.BooleanField(default=True)

    reliability_score  = models.FloatField(default=0.0, db_index=True)
    total_reviews      = models.IntegerField(default=0)
    response_rate      = models.FloatField(default=0.0)
    total_transactions = models.IntegerField(default=0)
    total_clients      = models.IntegerField(default=0)
    total_properties   = models.IntegerField(default=0)

    tax_certificate      = models.FileField(upload_to="agents/docs/", null=True, blank=True)
    professional_license = models.FileField(upload_to="agents/docs/", null=True, blank=True)
    office_photo         = models.ImageField(upload_to="agents/office/", null=True, blank=True)
    rcc_number           = models.CharField(max_length=100, null=True, blank=True)

    max_properties        = models.IntegerField(default=20)
    debt_grace_days       = models.IntegerField(default=7)
    notifications_enabled = models.BooleanField(default=True)

    mtn_momo_number     = models.CharField(max_length=20, null=True, blank=True)
    orange_money_number = models.CharField(max_length=20, null=True, blank=True)
    bank_account_number = models.CharField(max_length=50, null=True, blank=True)
    bank_name           = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Profil Agent"
        verbose_name_plural = "Profils Agents"
        indexes = [
            models.Index(fields=["certification_level", "reliability_score"]),
            models.Index(fields=["working_city", "certification_level"]),
            models.Index(fields=["reliability_score", "working_city"]),
        ]

    def __str__(self):
        return f"Agent: {self.user.get_full_name()} ({self.certification_level})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Seul le gerant (owner_agent) peut renommer l'agence via son propre
        # agency_name. Sans cette garde, sauvegarder le profil d'un agent
        # non-gerant (ex: rejoindre l'agence, ou simplement modifier son bio)
        # pourrait silencieusement ecraser le nom de l'agence partagee avec
        # la valeur laissee dans son propre champ agency_name.
        if (
            self.agency_id
            and self.user_id == self.agency.owner_agent_id
            and self.agency_name
            and self.agency.name != self.agency_name
        ):
            from apps.agencies.models import Agency
            Agency.objects.filter(pk=self.agency_id).update(name=self.agency_name)

    def update_reliability_score(self):
        from apps.reviews.models import Review
        reviews = Review.objects.filter(agent=self.user, agent_rating__isnull=False)
        if reviews.exists():
            avg = reviews.aggregate(models.Avg("agent_rating"))["agent_rating__avg"]
            self.reliability_score = round(avg, 2)
            self.total_reviews = reviews.count()
            self.save(update_fields=["reliability_score", "total_reviews"])

    @property
    def is_available(self):
        return self.total_properties < self.max_properties


class ClientAgentRelation(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="client_agent_relations", limit_choices_to={"role__in": ["client", "tenant"]})
    agent     = models.ForeignKey(User, on_delete=models.CASCADE, related_name="client_relations", limit_choices_to={"role": "agent"})
    agency    = models.ForeignKey("agencies.Agency", on_delete=models.PROTECT, related_name="client_relations")
    is_active = models.BooleanField(default=True, db_index=True)
    termination_reason = models.TextField(null=True, blank=True)
    terminated_at       = models.DateTimeField(null=True, blank=True)
    terminated_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="terminated_client_relations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name    = "Relation Client-Agent"
        unique_together = ["client", "agent"]
        indexes = [
            models.Index(fields=["client", "is_active"]),
            models.Index(fields=["agency", "is_active"]),
        ]

    def __str__(self):
        return f"{self.client.get_full_name()} -> Agent {self.agent.get_full_name()}"


class OwnerAgentRelation(models.Model):
    STATUS_CHOICES = [
        ("active",     "Actif"),
        ("terminated", "Resilie"),
        ("expired",    "Expire"),
    ]

    id                 = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner              = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agent_relations", limit_choices_to={"role": "owner"})
    agent              = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owner_relations", limit_choices_to={"role": "agent"})
    agency             = models.ForeignKey(
        "agencies.Agency", on_delete=models.PROTECT, related_name="mandates",
    )
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    contract_start     = models.DateField()
    contract_end       = models.DateField(null=True, blank=True)
    termination_reason = models.TextField(null=True, blank=True)
    terminated_at      = models.DateTimeField(null=True, blank=True)
    terminated_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="terminated_relations")
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Relation Proprietaire-Agent"
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["agent", "status"]),
        ]

    def __str__(self):
        return f"{self.owner.get_full_name()} -> Agent {self.agent.get_full_name()} ({self.status})"


class AgentAvailabilitySlot(models.Model):
    DAY_CHOICES = [
        (0,"Lundi"),(1,"Mardi"),(2,"Mercredi"),
        (3,"Jeudi"),(4,"Vendredi"),(5,"Samedi"),(6,"Dimanche"),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="availability_slots", limit_choices_to={"role": "agent"})
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time  = models.TimeField()
    end_time    = models.TimeField()
    is_active   = models.BooleanField(default=True)

    class Meta:
        verbose_name    = "Creneau Disponibilite"
        unique_together = ["agent", "day_of_week", "start_time"]
        ordering        = ["day_of_week", "start_time"]

    def __str__(self):
        return f"Agent {self.agent.get_full_name()} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"
