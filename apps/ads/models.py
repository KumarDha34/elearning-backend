from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AdCampaign(models.Model):
    """
    Central advertisement campaign.
    Separates Audience Type (who sees it) from Format (what it looks like).
    """

    class AdType(models.TextChoices):
        PUBLIC = 'PUBLIC', 'Public'
        TARGETED = 'TARGETED', 'Targeted'

    class AdFormat(models.TextChoices):
        IMAGE = 'IMAGE', 'Image'
        VIDEO = 'VIDEO', 'Video'
        BANNER = 'BANNER', 'Banner'
        TEXT = 'TEXT', 'Text'

    class DestinationType(models.TextChoices):
        EXTERNAL = 'EXTERNAL', 'External Website'
        INTERNAL = 'INTERNAL', 'Internal Page'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ACTIVE = 'ACTIVE', 'Active'
        PAUSED = 'PAUSED', 'Paused'
        EXPIRED = 'EXPIRED', 'Expired'

    # ── Core Content ──
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # ── Audience & Format ──
    ad_type = models.CharField(
        max_length=20,
        choices=AdType.choices,
        default=AdType.PUBLIC,
        help_text='PUBLIC = visible to everyone. TARGETED = only matching users see it.',
    )
    ad_format = models.CharField(
        max_length=20,
        choices=AdFormat.choices,
        default=AdFormat.IMAGE,
    )

    # ── Media ──
    media_file = models.FileField(
        upload_to='ads/media/',
        blank=True,
        null=True,
        help_text='Image, video, or banner asset.',
    )
    text_content = models.TextField(
        blank=True,
        help_text='For TEXT format ads, the ad copy itself.',
    )

    # ── Destination ──
    destination_type = models.CharField(
        max_length=20,
        choices=DestinationType.choices,
        default=DestinationType.EXTERNAL,
    )
    destination_url = models.URLField(
        blank=True,
        help_text='Where the user is sent on click.',
    )

    # ── Lifecycle ──
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(
        null=True, 
        blank=True,
        help_text='Leave blank for a campaign with no expiry.'
    )

    # ── Audit ──
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ad_campaigns',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ad_campaigns'
        ordering = ['-created_at']
        indexes = [
            # Optimized for the delivery/feed engine
            models.Index(fields=['status', 'ad_type', 'start_date']),
            models.Index(fields=['end_date']),
        ]

    def __str__(self):
        return f"[{self.ad_type}] {self.title}"

    def is_active_and_scheduled(self):
        """Helper to check if the campaign is currently live."""
        if self.status != self.Status.ACTIVE:
            return False
        now = timezone.now()
        if self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True


class AdTargeting(models.Model):
    """
    Targeting rules for a TARGETED campaign.
    One-to-one with AdCampaign.
    
    LOGIC: 
    - Different dimensions (school, faculty, class) combine with AND.
    - Multiple values within a dimension combine with OR.
    - Empty dimensions impose no restriction.
    """
    campaign = models.OneToOneField(
        AdCampaign,
        on_delete=models.CASCADE,
        related_name='targeting',
    )

    schools = models.ManyToManyField(
        'academics.School',
        blank=True,
        related_name='ad_targetings',
        help_text='Target users in these specific schools.',
    )
    faculties = models.ManyToManyField(
        'academics.Faculty',
        blank=True,
        related_name='ad_targetings',
        help_text='Target users in these specific faculties (e.g., BCA, BBS).',
    )
    classes = models.ManyToManyField(
        'academics.ClassLevel',
        blank=True,
        related_name='ad_targetings',
        help_text='Target users in these specific class levels (e.g., 1st Year).',
    )

    # Address string matching against School.address (since Lat/Lng is not in the DB yet)
    address_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text='List of address keywords, e.g. ["Kathmandu", "Lalitpur"].',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ad_targetings'
        verbose_name = 'Ad Targeting Rule'
        verbose_name_plural = 'Ad Targeting Rules'

    def __str__(self):
        return f"Targeting for {self.campaign.title}"


class AdInteraction(models.Model):
    """
    Unified analytics tracking for both Impressions and Clicks.
    Avoids duplicate tables and makes CTR calculation trivial.
    """

    class InteractionType(models.TextChoices):
        IMPRESSION = 'IMPRESSION', 'Impression'
        CLICK = 'CLICK', 'Click'

    campaign = models.ForeignKey(
        AdCampaign,
        on_delete=models.CASCADE,
        related_name='interactions',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ad_interactions',
    )
    interaction_type = models.CharField(
        max_length=20,
        choices=InteractionType.choices,
    )

    # Structured metadata for future-proofing (IP, device, browser, etc.)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional context (IP, user agent, device type).'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ad_interactions'
        ordering = ['-created_at']
        indexes = [
            # Fast lookups for analytics and frequency capping
            models.Index(fields=['campaign', 'interaction_type', 'created_at']),
            models.Index(fields=['user', 'interaction_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.interaction_type} — {self.campaign.title} (User: {self.user_id})"