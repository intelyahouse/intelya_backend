from django.urls import path
from .views import CreateLeaseView, SignLeaseView, MyLeasesView

urlpatterns = [
    path('leases/', MyLeasesView.as_view(), name='my-leases'),
    path('leases/create/', CreateLeaseView.as_view(), name='create-lease'),
    path('leases/<uuid:lease_id>/sign/', SignLeaseView.as_view(), name='sign-lease'),
]
