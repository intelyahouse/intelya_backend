from django.urls import path
from .views import MyReferralsView

urlpatterns = [
    path('mine/', MyReferralsView.as_view(), name='my-referrals'),
]
