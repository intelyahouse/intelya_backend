from django.urls import path
from .views import (
    OwnerProfileView, OwnerBankAccountView, OwnerAgentRelationView,
    OwnerDashboardView, MandatePDFView
)

urlpatterns = [
    path('me/dashboard/', OwnerDashboardView.as_view(), name='owner-dashboard'),
    path('me/', OwnerProfileView.as_view(), name='owner-profile'),
    path('me/bank-accounts/', OwnerBankAccountView.as_view(), name='owner-bank'),
    path('me/agent/', OwnerAgentRelationView.as_view(), name='owner-agent'),
    path('mandates/<uuid:relation_id>/pdf/', MandatePDFView.as_view(), name='mandate-pdf'),
]
