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
from .models import OTPVerification
from core.utils import generate_otp, success_response, error_response

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
                UserProfileSerializer(user).data,
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
        print(f"[SMS] Code OTP pour {user.phone}: {code}")


@method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='post')
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
        user.save(update_fields=['login_attempts'])

        refresh = RefreshToken.for_user(user)
        return Response(success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserProfileSerializer(user).data
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


@method_decorator(ratelimit(key='ip', rate='5/m', block=True), name='post')
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

        return Response(success_response(message="Téléphone vérifié avec succès ✅"))


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
        print(f"[SMS] Nouveau OTP pour {phone}: {code}")

        return Response(success_response(message="Code OTP renvoyé"))


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Users'], summary="Mon profil")
    def get(self, request):
        return Response(success_response(
            UserProfileSerializer(request.user).data
        ))

    @extend_schema(tags=['Users'], summary="Modifier mon profil", request=UserProfileSerializer)
    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True
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
        if not user.check_password(serializer.validated_data['old_password']):
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
        user.cni_number = data['cni_number']
        user.cni_front_photo = data['cni_front_photo']
        user.cni_back_photo = data['cni_back_photo']
        user.selfie_photo = data['selfie_photo']
        user.validation_status = 'pending'
        user.save()

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
        print(f"[RESET PASSWORD] Code pour {user.email} / {user.phone}: {code}")

        return Response(success_response(
            message="Code de réinitialisation envoyé sur votre téléphone."
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

        if needs_phone:
            return Response(
                success_response(
                    {
                        'needs_phone': True,
                        'email': user.email,
                        'user_id': str(user.id),
                    },
                    "Veuillez vérifier votre numéro de téléphone pour continuer."
                ),
                status=status.HTTP_200_OK
            )

        if user.is_blocked:
            return Response(
                error_response("Votre compte est bloqué."),
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)
        return Response(success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserProfileSerializer(user).data,
            'needs_phone': False,
        }, "Connexion Google réussie"))
