from django.urls import path
from apps.users.views import UserProfileView, RegisterDeviceView

urlpatterns = [
    path('me/', UserProfileView.as_view(), name='profile'),
    path('me/device/', RegisterDeviceView.as_view(), name='register-device'),
]
