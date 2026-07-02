import uuid
import random
import string
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


def _generate_referral_code():
    chars = string.ascii_uppercase + string.digits
    from django.contrib.auth import get_user_model
    while True:
        code = ''.join(random.choices(chars, k=8))
        try:
            User = get_user_model()
            if not User.objects.filter(referral_code=code).exists():
                return code
        except Exception:
            return code


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email obligatoire")
        email = self.normalize_email(email)
        if not extra_fields.get('referral_code'):
            chars = string.ascii_uppercase + string.digits
            while True:
                code = ''.join(random.choices(chars, k=8))
                if not self.model.objects.filter(referral_code=code).exists():
                    extra_fields['referral_code'] = code
                    break
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_validated', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('admin',  'Administrateur'),
        ('agent',  'Agent Immobilier'),
        ('owner',  'Propriétaire'),
        ('client', 'Client'),
        ('tenant', 'Locataire'),
    ]
    id                 = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email              = models.EmailField(unique=True, db_index=True)
    phone              = models.CharField(max_length=20, unique=True, db_index=True)
    role               = models.CharField(max_length=10, choices=ROLE_CHOICES, default='client', db_index=True)
    first_name         = models.CharField(max_length=100)
    last_name          = models.CharField(max_length=100)
    profile_photo      = models.ImageField(upload_to='profiles/', null=True, blank=True)
    cni_number         = models.CharField(max_length=50, unique=True, null=True, blank=True, db_index=True)
    cni_front_photo    = models.FileField(upload_to='cni/', null=True, blank=True)
    cni_back_photo     = models.FileField(upload_to='cni/', null=True, blank=True)
    selfie_photo       = models.FileField(upload_to='selfies/', null=True, blank=True)
    cni_verified       = models.BooleanField(default=False)
    is_active          = models.BooleanField(default=True, db_index=True)
    is_staff           = models.BooleanField(default=False)
    is_validated       = models.BooleanField(default=False, db_index=True)
    is_blocked         = models.BooleanField(default=False, db_index=True)
    is_phone_verified  = models.BooleanField(default=False)
    terms_accepted     = models.BooleanField(default=False)
    terms_accepted_at  = models.DateTimeField(null=True, blank=True)
    referral_code      = models.CharField(max_length=10, unique=True, null=True, blank=True, db_index=True)
    referred_by        = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    login_attempts     = models.IntegerField(default=0)
    last_login_attempt = models.DateTimeField(null=True, blank=True)
    language           = models.CharField(max_length=5, default='fr')
    date_joined        = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at         = models.DateTimeField(auto_now=True)
    validation_status  = models.CharField(
        max_length=20,
        choices=[('pending','En attente'),('approved','Approuvé'),('rejected','Rejeté')],
        default='pending',
        db_index=True
    )
    validation_note    = models.TextField(null=True, blank=True)
    validated_at       = models.DateTimeField(null=True, blank=True)
    validated_by       = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='validated_users'
    )

    objects = UserManager()
    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone']

    class Meta:
        verbose_name         = 'Utilisateur'
        verbose_name_plural  = 'Utilisateurs'
        ordering             = ['-date_joined']
        indexes = [
            models.Index(fields=['role', 'is_validated']),
            models.Index(fields=['role', 'is_blocked']),
            models.Index(fields=['is_validated', 'validation_status']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class OTPVerification(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code       = models.CharField(max_length=6)
    phone      = models.CharField(max_length=20, db_index=True)
    is_used    = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['phone', 'is_used']),
            models.Index(fields=['code', 'is_used']),
        ]

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"OTP {self.phone} - {self.code}"


class Blacklist(models.Model):
    phone      = models.CharField(max_length=20, null=True, blank=True, unique=True, db_index=True)
    cni_number = models.CharField(max_length=50, null=True, blank=True, unique=True, db_index=True)
    reason     = models.TextField()
    banned_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Banni: {self.phone or self.cni_number}"


class UserDevice(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_token = models.TextField()
    device_type  = models.CharField(
        max_length=10,
        choices=[('android','Android'),('ios','iOS'),('web','Web')]
    )
    is_active  = models.BooleanField(default=True, db_index=True)
    last_used  = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'device_token']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.device_type}"
