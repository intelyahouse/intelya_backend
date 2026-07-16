from django.urls import path
from .views import (
    InitiatePaymentView, CampayWebhookView, KPayWebhookView,
    MyTransactionsView, CheckPaymentStatusView
)

urlpatterns = [
    path('initiate/', InitiatePaymentView.as_view(), name='initiate-payment'),
    path('webhook/campay/', CampayWebhookView.as_view(), name='webhook-campay'),
    path('webhook/kpay/', KPayWebhookView.as_view(), name='webhook-kpay'),
    path('history/', MyTransactionsView.as_view(), name='my-transactions'),
    path('status/<str:reference>/', CheckPaymentStatusView.as_view(), name='payment-status'),
]
