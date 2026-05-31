from django.urls import path
from .views import (
    InitiatePaymentView, CampayWebhookView,
    MyTransactionsView, CheckPaymentStatusView
)

urlpatterns = [
    path('initiate/', InitiatePaymentView.as_view(), name='initiate-payment'),
    path('webhook/campay/', CampayWebhookView.as_view(), name='webhook-campay'),
    path('history/', MyTransactionsView.as_view(), name='my-transactions'),
    path('status/<str:reference>/', CheckPaymentStatusView.as_view(), name='payment-status'),
]
