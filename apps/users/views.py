from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from django.utils.decorators import method_decorator
from datetime import timedelta
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiExample
from django_ratelimit.decorators import ratelimit
from .serializers import (
    RegisterSerializer, LoginSerializer, OTPVerifySerializer,
    OTPResendSerializer, UserProfileSerializer,
    ChangePasswordSerializer, ForgotPasswordSerializer,
    ResetPasswordSerializer, RoleRequestSerializer
)
from .models import OTPVerification, UserDevice
from core.utils import generate_otp, success_response, error_response
from apps.notifications.services.sms import sms_service
from apps.notifications.services.email import email_service

User = get_user_model()


@method_decorator(ratelimit(key='ip', rate='3/m', block=True), name='post')
class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary="Inscription client",
        description="Crée un nouveau compte client. Envoie un OTP SMS pour vérifier le téléphone.",
        request=RegisterSerializer,
        responses={201: UserProfileSerializer},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        user = serializer.save()
        self._send_otp(user)
        return Response(
            success_response(
                UserProfileSerializer(user, context={'request': request}).data,
                "Compte créé. Vérifiez votre téléphone pour le code OTP."
            ),
            status=status.HTTP_201_CREATED
        )

    def _send_otp(self, user):
        code = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        OTPVerification.objects.filter(user=user, is_used=False).update(is_used=True)
        OTPVerification.objects.create(
            user=user, code=code,
            phone=user.phone, expires_at=expires_at
        )
        sms_service.send_otp(user.phone, code)


@method_decorator(ratelimit(key='ip', rate='3/m', block=True), name='post')
class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary="Connexion",
        description="Connexion avec email et mot de passe. Retourne access et refresh tokens JWT.",
        request=LoginSerializer,
        examples=[
            OpenApiExample(
                'Exemple connexion',
                value={'email': 'user@example.com', 'password': 'motdepasse123'}
            )
        ]
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                error_response("Email ou mot de passe incorrect"),
                status=status.HTTP_401_UNAUTHORIZED
            )

        if user_obj.login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            return Response(
                error_response("Compte bloqué après trop de tentatives. Contactez le support."),
                status=status.HTTP_403_FORBIDDEN
            )

        user = authenticate(request, email=email, password=password)
        if not user:
            user_obj.login_attempts += 1
            user_obj.last_login_attempt = timezone.now()
            user_obj.save(update_fields=['login_attempts', 'last_login_attempt'])
            return Response(
                error_response("Email ou mot de passe incorrect"),
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_phone_verified:
            return Response(
                error_response("Téléphone non vérifié. Entrez votre code OTP."),
                status=status.HTTP_403_FORBIDDEN
            )

        if user.is_blocked:
            return Response(
                error_response("Votre compte est bloqué. Réglez vos impayés."),
                status=status.HTTP_403_FORBIDDEN
            )

        user.login_attempts = 0
        user.last_login_attempt = None
        user.save(update_fields=['login_attempts', 'last_login_attempt'])

        refresh = RefreshToken.for_user(user)
        return Response(success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserProfileSerializer(user, context={'request': request}).data
        }, "Connexion réussie"))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Auth'], summary="Déconnexion")
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response(success_response(message="Déconnecté avec succès"))
        except TokenError:
            return Response(
                error_response("Token invalide"),
                status=status.HTTP_400_BAD_REQUEST
            )


@method_decorator(ratelimit(key='ip', rate='3/m', block=True), name='post')
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary="Vérifier OTP téléphone",
        description="Vérifie le code OTP reçu par SMS. Active la vérification téléphone.",
        request=OTPVerifySerializer
    )
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        phone = serializer.validated_data['phone']
        code = serializer.validated_data['code']

        otp = OTPVerification.objects.filter(
            phone=phone, code=code, is_used=False
        ).last()

        if not otp or not otp.is_valid():
            return Response(
                error_response("Code OTP invalide ou expiré"),
                status=status.HTTP_400_BAD_REQUEST
            )

        otp.is_used = True
        otp.save()

        user = otp.user
        user.is_phone_verified = True
        user.save(update_fields=['is_phone_verified'])

        if not user.has_usable_password():
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(user)
            return Response(success_response(
                {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': UserProfileSerializer(user, context={'request': request}).data,
                },
                "Téléphone vérifié avec succès !"
            ))

        return Response(success_response(message="Téléphone vérifié avec succès !"))


@method_decorator(ratelimit(key='ip', rate='3/m', block=True), name='post')
class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=['Auth'], summary="Renvoyer OTP", request=OTPResendSerializer)
    def post(self, request):
        serializer = OTPResendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        phone = serializer.validated_data['phone']
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response(
                error_response("Aucun compte avec ce numéro"),
                status=status.HTTP_404_NOT_FOUND
            )

        code = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        OTPVerification.objects.filter(user=user, is_used=False).update(is_used=True)
        OTPVerification.objects.create(
            user=user, code=code,
            phone=phone, expires_at=expires_at
        )
        sms_service.send_otp(phone, code)

        return Response(success_response(message="Code OTP renvoyé"))


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Users'], summary="Mon profil")
    def get(self, request):
        return Response(success_response(
            UserProfileSerializer(request.user, context={'request': request}).data
        ))

    @extend_schema(tags=['Users'], summary="Modifier mon profil", request=UserProfileSerializer)
    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True,
            context={'request': request}
        )
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer.save()
        return Response(success_response(serializer.data, "Profil mis à jour"))

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Auth'], summary="Changer mot de passe", request=ChangePasswordSerializer)
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        user = request.user

        # Compte cree via Google sans mot de passe reel -> pas besoin de l'ancien,
        # c'est la toute premiere definition. Sinon, on l'exige pour securiser.
        if user.has_usable_password():
            old_password = serializer.validated_data.get('old_password')
            if not old_password or not user.check_password(old_password):
                return Response(
                    error_response("Ancien mot de passe incorrect"),
                    status=status.HTTP_400_BAD_REQUEST
                )

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response(success_response(message="Mot de passe modifié avec succès"))


class RequestRoleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Users'],
        summary="Demander un rôle (agent ou propriétaire)",
        description="Upload CNI et selfie pour demander à devenir agent ou propriétaire.",
        request=RoleRequestSerializer
    )
    def post(self, request):
        if request.user.role != 'client':
            return Response(
                error_response("Vous avez déjà un rôle défini."),
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = RoleRequestSerializer(
            data=request.data, context={'request': request}
        )
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data
        user = request.user
        user.role = data['requested_role']
        user.cni_number = data['cni_number']
        user.cni_front_photo = data['cni_front_photo']
        user.cni_back_photo = data['cni_back_photo']
        user.selfie_photo = data['selfie_photo']
        user.validation_status = 'pending'
        user.role_requested_at = timezone.now()
        user.validation_reminder_sent = False
        user.save()

        from apps.notifications.utils import notify_bulk
        admins = User.objects.filter(role='admin', is_active=True)
        notify_bulk(
            admins, 'system', "Nouvelle demande de validation",
            f"{user.get_full_name()} demande à devenir {data['requested_role']}.",
            {'user_id': str(user.id)}
        )

        return Response(success_response(
            message=f"Demande envoyée pour devenir {data['requested_role']}. L'admin va valider votre compte."
        ))


@method_decorator(ratelimit(key='ip', rate='3/m', block=True), name='post')
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary="Mot de passe oublié",
        description="Envoie un code OTP par SMS pour réinitialiser le mot de passe.",
        request=ForgotPasswordSerializer
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                success_response(
                    message="Si cet email existe, un code a été envoyé."
                )
            )

        code = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=15)
        OTPVerification.objects.filter(user=user, is_used=False).update(is_used=True)
        OTPVerification.objects.create(
            user=user, code=code,
            phone=user.phone, expires_at=expires_at
        )
        sms_service.send_otp(user.phone, code)
        email_service.send_otp(user.email, code)

        return Response(success_response(
            message="Code de réinitialisation envoyé sur votre téléphone et par email."
        ))


@method_decorator(ratelimit(key='ip', rate='3/m', block=True), name='post')
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary="Réinitialiser le mot de passe",
        description="Utilise le code OTP reçu pour définir un nouveau mot de passe.",
        request=ResetPasswordSerializer
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                error_response("Données invalides", serializer.errors),
                status=status.HTTP_400_BAD_REQUEST
            )

        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        otp = OTPVerification.objects.filter(
            code=token, is_used=False
        ).last()

        if not otp or not otp.is_valid():
            return Response(
                error_response("Code invalide ou expiré."),
                status=status.HTTP_400_BAD_REQUEST
            )

        user = otp.user
        user.set_password(new_password)
        user.save()

        otp.is_used = True
        otp.save()

        return Response(success_response(
            message="Mot de passe réinitialisé avec succès."
        ))


class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary="Connexion avec Google",
        description="Connexion avec un token Google. Si premiere connexion, demande le telephone."
    )
    def post(self, request):
        from .google_auth import verify_google_token, get_or_create_google_user
        from rest_framework_simplejwt.tokens import RefreshToken

        token = request.data.get('token')
        if not token:
            return Response(
                error_response("Token Google manquant"),
                status=status.HTTP_400_BAD_REQUEST
            )

        google_data = verify_google_token(token)
        if not google_data.get('success'):
            return Response(
                error_response("Token Google invalide"),
                status=status.HTTP_401_UNAUTHORIZED
            )

        user, created, needs_phone = get_or_create_google_user(google_data)
        if not user:
            return Response(
                error_response("Impossible de créer le compte"),
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.is_blocked:
            return Response(
                error_response("Votre compte est bloqué."),
                status=status.HTTP_403_FORBIDDEN
            )

        # On n'attend plus la verification du telephone pour donner l'acces :
        # l'utilisateur entre directement sur la plateforme (role client par defaut).
        # needs_phone reste dans la reponse a titre informatif pour afficher
        # une invitation (pas un mur) a verifier son telephone plus tard.
        refresh = RefreshToken.for_user(user)
        return Response(success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserProfileSerializer(user, context={'request': request}).data,
            'needs_phone': needs_phone,
        }, "Connexion Google réussie"))
    

class GoogleCompletePhoneView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary="Finaliser l'inscription Google (téléphone)",
        description="Enregistre le téléphone pour un compte créé via Google et envoie un OTP SMS."
    )
    def post(self, request):
        user_id = request.data.get('user_id')
        phone = request.data.get('phone')

        if not user_id or not phone:
            return Response(
                error_response("user_id et phone sont requis"),
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(id=user_id, is_phone_verified=False)
        except User.DoesNotExist:
            return Response(
                error_response("Compte introuvable ou déjà vérifié"),
                status=status.HTTP_404_NOT_FOUND
            )

        if User.objects.filter(phone=phone).exclude(id=user.id).exists():
            return Response(
                error_response("Ce numéro est déjà utilisé par un autre compte"),
                status=status.HTTP_400_BAD_REQUEST
            )

        user.phone = phone
        user.save()

        code = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        OTPVerification.objects.filter(user=user, is_used=False).update(is_used=True)
        OTPVerification.objects.create(
            user=user, code=code,
            phone=user.phone, expires_at=expires_at
        )
        sms_service.send_otp(user.phone, code)

        return Response(success_response(
            {'user_id': str(user.id), 'phone': user.phone},
            "Code envoyé par SMS. Vérifiez votre téléphone."
        ))


class RegisterDeviceView(APIView):
    """Enregistrer/desenregistrer le token FCM d'un appareil pour recevoir
    les notifications push. Sans cet appel, push_service.send_to_user()
    ne trouve jamais de destinataire, meme si Firebase est correctement
    configure cote serveur."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Users'], summary="Enregistrer mon token FCM")
    def post(self, request):
        device_token = request.data.get('device_token')
        device_type  = request.data.get('device_type')

        if not device_token or device_type not in ['android', 'ios', 'web']:
            return Response(
                error_response("device_token et device_type ('android'|'ios'|'web') sont requis"),
                status=status.HTTP_400_BAD_REQUEST
            )

        UserDevice.objects.update_or_create(
            user=request.user, device_token=device_token,
            defaults={'device_type': device_type, 'is_active': True}
        )
        return Response(success_response(message="Appareil enregistré"), status=status.HTTP_201_CREATED)

    @extend_schema(tags=['Users'], summary="Desenregistrer un token FCM (deconnexion)")
    def delete(self, request):
        device_token = request.data.get('device_token')
        if not device_token:
            return Response(error_response("device_token est requis"), status=status.HTTP_400_BAD_REQUEST)

        UserDevice.objects.filter(user=request.user, device_token=device_token).update(is_active=False)
        return Response(success_response(message="Appareil désenregistré"))

