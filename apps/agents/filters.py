import django_filters
from apps.agents.models import AgentProfile


class AgentFilter(django_filters.FilterSet):
    city = django_filters.CharFilter(field_name='working_city', lookup_expr='icontains')

    class Meta:
        model  = AgentProfile
        fields = ['certification_level', 'visit_fee_is_free']
