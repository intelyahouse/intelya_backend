from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from .models import Referral
from .serializers import ReferralSerializer
from core.utils import success_response


class MyReferralsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Referrals'], summary="Mon code parrainage et mes filleuls")
    def get(self, request):
        referrals = Referral.objects.filter(referrer=request.user)
        total_bonus = sum(r.bonus_amount for r in referrals if r.status)
        return Response(success_response({
            'referral_code': request.user.referral_code,
            'total_referrals': referrals.count(),
            'rewarded': referrals.filter(status=True).count(),
            'total_bonus_fcfa': float(total_bonus),
            'referrals': ReferralSerializer(referrals, many=True).data
        }))
