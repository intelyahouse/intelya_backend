import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.gis.db import models as gis_models

User = get_user_model()


class Property(models.Model):

    TYPE_CHOICES = [
        ('studio',     'Studio'),
        ('room',       'Chambre'),
        ('apartment',  'Appartement'),
        ('villa',      'Villa'),
        ('duplex',     'Duplex'),
        ('office',     'Bureau/Local commercial'),
    ]

    STATUS_CHOICES = [
        ('available',  'Disponible'),
        ('rented',     'Loué'),
        ('suspended',  'Suspendu'),
        ('expired',    'Expiré'),
    ]

    PAYMENT_CHOICES = [
        ('monthly',   'Mensuel'),
        ('quarterly', 'Trimestriel'),
        ('yearly',    'Annuel'),
    ]

    # ===== IDENTITÉ =====
    id    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='properties',
        limit_choices_to={'role': 'owner'}
    )
    agent = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='managed_properties',
        limit_choices_to={'role': 'agent'},
        null=True, blank=True
    )

    # ===== INFORMATIONS DE BASE =====
    title         = models.CharField(max_length=200, db_index=True)
    description   = models.TextField()
    property_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)

    # ===== PRIX =====
    price            = models.DecimalField(max_digits=12, decimal_places=2, db_index=True)
    payment_period   = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='monthly')
    min_lease_months = models.IntegerField(default=1)

    # ===== CARACTÉRISTIQUES =====
    bedrooms     = models.IntegerField(default=1, db_index=True)
    bathrooms    = models.IntegerField(default=1)
    living_rooms = models.IntegerField(default=0)
    kitchens     = models.IntegerField(default=0)
    area_sqm     = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    floor        = models.IntegerField(default=0)
    total_floors = models.IntegerField(default=1)
    is_furnished = models.BooleanField(default=False, db_index=True)

    # ===== ÉQUIPEMENTS AFRICAINS =====
    has_generator       = models.BooleanField(default=False, db_index=True)
    has_borehole        = models.BooleanField(default=False, db_index=True)
    has_water_tank      = models.BooleanField(default=False)
    has_fence           = models.BooleanField(default=False)
    has_security_guard  = models.BooleanField(default=False)
    has_parking         = models.BooleanField(default=False, db_index=True)
    has_air_conditioning = models.BooleanField(default=False)
    parking_spots       = models.IntegerField(default=0)

    # ===== LOCALISATION =====
    full_address  = models.TextField()
    city          = models.CharField(max_length=100, db_index=True)
    neighborhood  = models.CharField(max_length=100, db_index=True)
    location      = gis_models.PointField(null=True, blank=True, srid=4326)

    # ===== DISPONIBILITÉ =====
    available_from = models.DateField(null=True, blank=True, db_index=True)

    # ===== STATISTIQUES =====
    views_count      = models.IntegerField(default=0)
    likes_count      = models.IntegerField(default=0)
    interested_count = models.IntegerField(default=0)

    # ===== VERIFICATION =====
    is_verified = models.BooleanField(default=False, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    # ===== DATES =====
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name         = 'Bien Immobilier'
        verbose_name_plural  = 'Biens Immobiliers'
        ordering             = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'city']),
            models.Index(fields=['status', 'neighborhood']),
            models.Index(fields=['status', 'price']),
            models.Index(fields=['status', 'property_type']),
            models.Index(fields=['status', 'bedrooms']),
            models.Index(fields=['agent', 'status']),
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['city', 'neighborhood', 'status']),
            models.Index(fields=['price', 'status', 'bedrooms']),
            models.Index(fields=['has_generator', 'status']),
            models.Index(fields=['has_parking', 'status']),
            models.Index(fields=['is_furnished', 'status']),
        ]

    def __str__(self):
        return f"{self.title} - {self.neighborhood}, {self.city}"

    def get_public_data(self):
        """Retourne les données sans adresse complète"""
        return {
            'city': self.city,
            'neighborhood': self.neighborhood,
        }


class PropertyPhoto(models.Model):
    """Photos du bien immobilier"""

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property   = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='photos')
    photo      = models.ImageField(upload_to='properties/photos/')
    caption    = models.CharField(max_length=200, null=True, blank=True)
    is_cover   = models.BooleanField(default=False)
    order      = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Photo'
        ordering     = ['order', '-is_cover']

    def __str__(self):
        return f"Photo {self.property.title}"


class PropertyVideo(models.Model):
    """Vidéo de présentation du bien"""

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property         = models.OneToOneField(Property, on_delete=models.CASCADE, related_name='video')
    video_file       = models.FileField(upload_to='properties/videos/', null=True, blank=True)
    video_url        = models.URLField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    created_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Vidéo {self.property.title}"


class FloorPlan(models.Model):
    """Plan du bien"""

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property   = models.OneToOneField(Property, on_delete=models.CASCADE, related_name='floor_plan')
    plan_file  = models.FileField(upload_to='properties/plans/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Plan {self.property.title}"


class PropertyLike(models.Model):
    """Likes sur les biens"""

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property   = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='likes')
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='liked_properties')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['property', 'user']
        verbose_name    = 'Like'

    def __str__(self):
        return f"{self.user.get_full_name()} ❤️ {self.property.title}"
