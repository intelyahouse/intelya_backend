from django.urls import path
from apps.users.views import (
    RegisterView, LoginView, LogoutView,
    VerifyOTPView, ResendOTPView,
    ChangePasswordView, RequestRoleView,
    ForgotPasswordView, ResetPasswordView,
    GoogleAuthView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('request-role/', RequestRoleView.as_view(), name='request-role'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('google/', GoogleAuthView.as_view(), name='google-auth'),
]
