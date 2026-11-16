# apps/ads/services/targeting.py

from django.db.models import Q
from django.utils import timezone
from apps.ads.models import AdCampaign


class AdTargetingEngine:
    """
    Evaluates whether a user's profile matches the targeting rules of a campaign.
    """

    @classmethod
    def get_targeting_queryset(cls, user, queryset):
        """
        Takes an AdCampaign queryset, filters for active public ads, 
        and evaluates targeted ads against the user's profile at the database level.
        """
        now = timezone.now()

        # 1. Base active campaign filter
        queryset = queryset.filter(
            status=AdCampaign.Status.ACTIVE,
            start_date__lte=now
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )

        # 2. Public Ads Query
        public_ads_q = Q(ad_type=AdCampaign.AdType.PUBLIC)

        # 3. Targeted Ads Query
        # If user is not a student or has no profile, they can only see public ads
        if not (user.is_student and hasattr(user, 'student_profile')):
            return queryset.filter(public_ads_q)

        profile = user.student_profile

        # Build the Q object for targeted ads
        targeted_ads_q = Q(ad_type=AdCampaign.AdType.TARGETED)
        rule_q = Q()

        # --- Dimension 1: Schools ---
        # If the ad specifies schools, the user's school MUST be in that list.
        # If the ad specifies NO schools, this dimension doesn't restrict the user.
        school_restriction = Q(targeting__schools__isnull=True)
        if profile.school_id:
            school_restriction |= Q(targeting__schools__id=profile.school_id)
        rule_q &= school_restriction

        # --- Dimension 2: Faculties ---
        faculty_restriction = Q(targeting__faculties__isnull=True)
        if profile.faculty_id:
            faculty_restriction |= Q(targeting__faculties__id=profile.faculty_id)
        rule_q &= faculty_restriction

        # --- Dimension 3: Classes ---
        class_restriction = Q(targeting__classes__isnull=True)
        if profile.class_level_id:
            class_restriction |= Q(targeting__classes__id=profile.class_level_id)
        rule_q &= class_restriction

        # --- Dimension 4: Address Keywords ---
        # Since address_keywords is a JSONField, we filter it in Python during delivery 
        # to avoid complex database-specific JSON queries.
        # Here, we only require that the ad doesn't have address keywords, 
        # OR the user has a school address that we can check later.
        # (If the ad has address keywords, we'll filter it in Python later).
        
        # Combine: (Public) OR (Targeted AND Rules)
        final_q = public_ads_q | (targeted_ads_q & rule_q)

        # Use distinct() because M2M joins can create duplicate rows
        return queryset.filter(final_q).distinct()


    @classmethod
    def matches(cls, user, campaign):
        """
        Evaluates a single campaign against a user.
        Useful for single-item checks (e.g., clicking an ad).
        """
        if campaign.ad_type == AdCampaign.AdType.PUBLIC:
            return True
            
        if not (user.is_student and hasattr(user, 'student_profile')):
            return False

        if not hasattr(campaign, 'targeting'):
            return False 

        profile = user.student_profile
        targeting = campaign.targeting

        # 1. Check Schools
        targeted_schools = targeting.schools.all()
        if targeted_schools.exists():
            if not profile.school or not targeted_schools.filter(id=profile.school.id).exists():
                return False

        # 2. Check Faculties
        targeted_faculties = targeting.faculties.all()
        if targeted_faculties.exists():
            if not profile.faculty or not targeted_faculties.filter(id=profile.faculty.id).exists():
                return False

        # 3. Check Classes
        targeted_classes = targeting.classes.all()
        if targeted_classes.exists():
            if not profile.class_level or not targeted_classes.filter(id=profile.class_level.id).exists():
                return False

        # 4. Check Address Keywords
        if targeting.address_keywords:
            if not profile.school or not profile.school.address:
                return False
            
            user_address = profile.school.address.lower()
            # If none of the keywords are found in the user's address, they don't match
            if not any(keyword.lower() in user_address for keyword in targeting.address_keywords):
                return False

        return True