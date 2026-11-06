# apps/ads/views.py

from django.db.models import Count, Q, F, FloatField, ExpressionWrapper
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.generics import get_object_or_404
from drf_spectacular.utils import extend_schema

from .models import AdCampaign, AdInteraction
from .serializers import (
    AdCampaignAdminSerializer,
    AdCampaignListSerializer,
    AdFeedSerializer,
    AdClickResponseSerializer,
)
from .services.delivery import AdDeliveryService


class AdCampaignViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        # Annotate counts here to avoid N+1 queries in the list serializer
        return AdCampaign.objects.annotate(
            impressions=Count(
                'interactions',
                filter=Q(interactions__interaction_type=AdInteraction.InteractionType.IMPRESSION),
            ),
            clicks=Count(
                'interactions',
                filter=Q(interactions__interaction_type=AdInteraction.InteractionType.CLICK),
            ),
        ).annotate(
            ctr=ExpressionWrapper(
                F('clicks') * 100.0 / F('impressions'),
                output_field=FloatField(),
            )
        ).prefetch_related('targeting__schools', 'targeting__faculties', 'targeting__classes')

    def get_serializer_class(self):
        if self.action == 'list':
            return AdCampaignListSerializer
        return AdCampaignAdminSerializer


class AdFeedView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AdFeedSerializer(many=True))
    def get(self, request):
        ads = AdDeliveryService.get_feed_for_user(request.user)
        serializer = AdFeedSerializer(
            ads, 
            many=True, 
            context={'request': request}
        )
        return Response(serializer.data)


class AdInteractionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None, 
        responses={200: AdClickResponseSerializer},
        description="Log an impression or click. Returns the redirect URL for clicks."
    )
    def post(self, request, pk, action_type):
        ad = get_object_or_404(AdCampaign, pk=pk)
        
        if not ad.is_active_and_scheduled():
            return Response(
                {"error": "This ad campaign is not currently active."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        interaction_map = {
            'impression': AdInteraction.InteractionType.IMPRESSION,
            'click': AdInteraction.InteractionType.CLICK,
        }
        
        if action_type not in interaction_map:
            return Response(
                {"error": "Invalid action type."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        interaction_type = interaction_map[action_type]

        # Deduplication: ignore interactions within 10 seconds to prevent double-clicks/refresh spam
        time_threshold = timezone.now() - timezone.timedelta(seconds=10)
        recent_interaction = AdInteraction.objects.filter(
            campaign=ad,
            user=request.user,
            interaction_type=interaction_type,
            created_at__gte=time_threshold
        ).exists()

        if not recent_interaction:
            metadata = {
                'ip': request.META.get('REMOTE_ADDR'),
                'ua': request.META.get('HTTP_USER_AGENT', '')[:255]
            }
            
            AdInteraction.objects.create(
                campaign=ad,
                user=request.user,
                interaction_type=interaction_type,
                metadata=metadata
            )

        if action_type == 'click':
            return Response({
                "success": True,
                "message": "Click recorded.",
                "redirect_url": ad.destination_url,
                "destination_type": ad.destination_type
            }, status=status.HTTP_200_OK)

        return Response({"success": True}, status=status.HTTP_200_OK)