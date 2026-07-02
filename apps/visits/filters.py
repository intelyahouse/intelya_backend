import django_filters
from .models import VisitRequest


class VisitFilter(django_filters.FilterSet):
    class Meta:
        model  = VisitRequest
        fields = ['status', 'payment_status', 'is_free']
