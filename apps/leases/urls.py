from django.urls import path
from .views import (
    MyRentPaymentsView, ConfirmCashPaymentView,
    DebtManagementView, SubmitComplaintView,
    MyComplaintsView, ResolveComplaintView,
    TenantDashboardView, RentPaymentReceiptView
)

urlpatterns = [
    # IMPORTANT : routes spécifiques AVANT les routes génériques
    path('dashboard/', TenantDashboardView.as_view(), name='tenant-dashboard'),
    path('payments/confirm-cash/', ConfirmCashPaymentView.as_view(), name='confirm-cash'),
    path('payments/<uuid:payment_id>/receipt/', RentPaymentReceiptView.as_view(), name='rent-payment-receipt'),
    path('payments/<uuid:payment_id>/debt/', DebtManagementView.as_view(), name='debt-action'),
    path('payments/', MyRentPaymentsView.as_view(), name='rent-payments'),
    path('complaints/submit/', SubmitComplaintView.as_view(), name='submit-complaint'),
    path('complaints/<uuid:complaint_id>/resolve/', ResolveComplaintView.as_view(), name='resolve-complaint'),
    path('complaints/', MyComplaintsView.as_view(), name='my-complaints'),
]
