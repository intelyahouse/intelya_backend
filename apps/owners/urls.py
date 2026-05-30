from django.urls import path
from .views import OwnerProfileView, OwnerBankAccountView, OwnerAgentRelationView

urlpatterns = [
    path('me/', OwnerProfileView.as_view(), name='owner-profile'),
    path('me/bank-accounts/', OwnerBankAccountView.as_view(), name='owner-bank'),
    path('me/agent/', OwnerAgentRelationView.as_view(), name='owner-agent'),
]
