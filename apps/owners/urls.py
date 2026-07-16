from django.urls import path
from .views import (
    OwnerProfileView, OwnerBankAccountView, OwnerAgentRelationView,
    BankAccountListCreateView, BankAccountDetailView, BankAccountSetDefaultView,
    PaymentPreferencesView
)

urlpatterns = [
    # Profil propriétaire
    path('me/', OwnerProfileView.as_view(), name='owner-profile'),
    
    # LEGACY : Anciens endpoints de comptes bancaires (OwnerProfile)
    path('me/bank-accounts/', OwnerBankAccountView.as_view(), name='owner-bank'),
    
    # NOUVEAUX : Comptes bancaires (modèle BankAccount - CRUD complet)
    path('me/bank/', BankAccountListCreateView.as_view(), name='bank-list-create'),
    path('me/bank/<str:account_id>/', BankAccountDetailView.as_view(), name='bank-detail'),
    path('me/bank/<str:account_id>/set-default/', BankAccountSetDefaultView.as_view(), name='bank-set-default'),
    
    # Préférences de payout
    path('me/payment-preferences/', PaymentPreferencesView.as_view(), name='payment-preferences'),
    
    # Agent
    path('me/agent/', OwnerAgentRelationView.as_view(), name='owner-agent'),
]
