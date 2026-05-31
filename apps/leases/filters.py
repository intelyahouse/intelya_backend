import django_filters
from apps.contracts.models import LeaseContract


class LeaseFilter(django_filters.FilterSet):
    class Meta:
        model  = LeaseContract
        fields = ['status', 'commission_paid']
