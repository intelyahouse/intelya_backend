from django.urls import path
from .views import BoostPricesView, ActivateBoostView, MyBoostsView

urlpatterns = [
    path('prices/', BoostPricesView.as_view(), name='boost-prices'),
    path('activate/', ActivateBoostView.as_view(), name='activate-boost'),
    path('mine/', MyBoostsView.as_view(), name='my-boosts'),
]
