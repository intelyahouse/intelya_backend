import django_filters
from .models import Property


class PropertyFilter(django_filters.FilterSet):
    min_price    = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price    = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    min_bedrooms = django_filters.NumberFilter(field_name='bedrooms', lookup_expr='gte')
    city         = django_filters.CharFilter(field_name='city', lookup_expr='icontains')
    neighborhood = django_filters.CharFilter(field_name='neighborhood', lookup_expr='icontains')

    class Meta:
        model  = Property
        fields = [
            'property_type', 'status', 'is_furnished',
            'has_generator', 'has_parking', 'has_borehole',
            'has_water_tank', 'has_fence', 'has_security_guard',
        ]
