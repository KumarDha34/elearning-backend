# apps/ads/services/delivery.py

from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from apps.ads.models import AdCampaign, AdInteraction
from .targeting import AdTargetingEngine


class AdDeliveryService:
    """
    Orchestrates the ad feed by applying targeting rules, 
    frequency capping, and ordering.
    """

    @classmethod
    def get_feed_for_user(cls, user, limit=10):
        """
        Returns a list of AdCampaign objects tailored for the given user.
        """
        # 1. Get all active, currently scheduled campaigns
        now = timezone.now()
        active_campaigns = AdCampaign.objects.filter(
            status=AdCampaign.Status.ACTIVE,
            start_date__lte=now
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )

        # 2. Apply the targeting engine to filter eligible campaigns
        eligible_campaigns = AdTargetingEngine.get_targeting_queryset(
            user, active_campaigns
        )

        # 3. Frequency Capping
        # Prevent showing the same ad too many times in a short window.
        # Example rule: Don't show an ad if the user has seen it in the last 24 hours.
        recent_cutoff = now - timedelta(hours=24)
        recently_seen_ad_ids = AdInteraction.objects.filter(
            user=user,
            interaction_type=AdInteraction.InteractionType.IMPRESSION,
            created_at__gte=recent_cutoff
        ).values_list('campaign_id', flat=True)

        filtered_campaigns = eligible_campaigns.exclude(id__in=recently_seen_ad_ids)

        # 4. Prioritization / Sorting
        # Prioritize targeted ads over public ads. 
        # (Targeted ads are more relevant, so they should appear first).
        ordered_campaigns = filtered_campaigns.order_by(
            # This puts 'TARGETED' before 'PUBLIC' alphabetically
            'ad_type', 
            '-created_at'
        )

        # 5. Apply limit
        final_feed = ordered_campaigns[:limit]

        # If the feed is empty because of the 24h cap, you could optionally 
        # fall back to showing the most recent public ads, but returning empty 
        # is usually the correct behavior for a frequency-capped system.
        
        return final_feed