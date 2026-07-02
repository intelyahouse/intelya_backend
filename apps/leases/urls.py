from django.urls import path
from .views import (
    MyRentPaymentsView, ConfirmCashPaymentView,
    DebtManagementView, SubmitComplaintView,
    MyComplaintsView, ResolveComplaintView
)

urlpatterns = [
    path('payments/', MyRentPaymentsView.as_view(), name='rent-payments'),
    path('payments/confirm-cash/', ConfirmCashPaymentView.as_view(), name='confirm-cash'),
    path('payments/<uuid:payment_id>/debt/', DebtManagementView.as_view(), name='debt-action'),
    path('complaints/', MyComplaintsView.as_view(), name='my-complaints'),
    path('complaints/submit/', SubmitComplaintView.as_view(), name='submit-complaint'),
    path('complaints/<uuid:complaint_id>/resolve/', ResolveComplaintView.as_view(), name='resolve-complaint'),
]
