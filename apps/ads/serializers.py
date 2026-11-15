# apps/ads/serializers.py

from rest_framework import serializers
from apps.academics.models import School, Faculty, ClassLevel
from .models import AdCampaign, AdTargeting, AdInteraction


class OptionalPKRelatedField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        # 1. Catch completely empty or zero values from Swagger
        if data in [0, '0', '', None, [0], ['0'], [], [None]]:
            return []
            
        # 2. If Swagger sends a single string/int, wrap it in a list so many=True works
        if not isinstance(data, list):
            data = [data]
            
        # 3. Clean the list (remove empty strings or zeros, convert strings to ints)
        clean_data = []
        for item in data:
            if item in [0, '0', '', None]:
                continue
            try:
                clean_data.append(int(item))
            except (ValueError, TypeError):
                pass
                
        if not clean_data:
            return []
            
        return super().to_internal_value(clean_data)

class AdTargetingSerializer(serializers.ModelSerializer):
    school_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=AdTargeting._meta.get_field('schools').related_model.objects.all(),
        source='schools',
        required=False,
    )
    faculty_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=AdTargeting._meta.get_field('faculties').related_model.objects.all(),
        source='faculties',
        required=False,
    )
    class_level_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=AdTargeting._meta.get_field('classes').related_model.objects.all(),
        source='classes',
        required=False,
    )

    class Meta:
        model = AdTargeting
        fields = [
            'id',
            'school_ids',
            'faculty_ids',
            'class_level_ids',
            'address_keywords',
        ]

    def validate_address_keywords(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Must be a list of strings.')
        for kw in value:
            if not isinstance(kw, str):
                raise serializers.ValidationError(
                    f'Each keyword must be a string. Got: {type(kw).__name__}'
                )
            if not kw.strip():
                raise serializers.ValidationError('Keywords cannot be empty.')
        return [kw.strip() for kw in value]


class AdCampaignAdminSerializer(serializers.ModelSerializer):
    school_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=School.objects.all(), 
        required=False,
        allow_empty=True,
        help_text="Select schools to target."
    )
    faculty_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=Faculty.objects.all(), 
        required=False,
        allow_empty=True,
        help_text="Select faculties to target."
    )
    class_level_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=ClassLevel.objects.all(), 
        required=False,
        allow_empty=True,
        help_text="Select classes to target."
    )
    address_keywords = serializers.ListField(
        child=serializers.CharField(), 
        required=False,
        allow_empty=True,
        help_text="List of address keywords (e.g., ['Kathmandu', 'Lalitpur'])."
    )

    impressions = serializers.IntegerField(read_only=True, required=False)
    clicks = serializers.IntegerField(read_only=True, required=False)
    ctr = serializers.FloatField(read_only=True, required=False)
    media_url = serializers.SerializerMethodField()

    class Meta:
        model = AdCampaign
        fields = [
            'id', 'title', 'description',
            'ad_type', 'ad_format',
            'media_file', 'media_url', 'text_content',
            'destination_type', 'destination_url',
            'status', 'start_date', 'end_date',
            
            'school_ids', 'faculty_ids', 'class_level_ids', 'address_keywords',
            
            'impressions', 'clicks', 'ctr',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'media_url', 'impressions', 'clicks', 'ctr',
            'created_by', 'created_at', 'updated_at',
        ]

    def to_internal_value(self, data):
        # Handle Swagger's empty array fields in multipart form data
        if hasattr(data, 'lists'):
            data = data.copy()
            for field in ['school_ids', 'faculty_ids', 'class_level_ids', 'address_keywords']:
                if field in data:
                    values = data.getlist(field)
                    clean_values = [v for v in values if v and str(v).strip() not in ['', '0']]
                    data.setlist(field, clean_values)
        return super().to_internal_value(data)

    def get_media_url(self, obj):
        if not obj.media_file:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.media_file.url)
        return obj.media_file.url

    def validate(self, attrs):
        ad_type = attrs.get('ad_type', getattr(self.instance, 'ad_type', None))
        ad_format = attrs.get('ad_format', getattr(self.instance, 'ad_format', None))
        destination_type = attrs.get(
            'destination_type',
            getattr(self.instance, 'destination_type', AdCampaign.DestinationType.EXTERNAL),
        )
        destination_url = attrs.get(
            'destination_url',
            getattr(self.instance, 'destination_url', ''),
        )
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))

        if destination_type == AdCampaign.DestinationType.EXTERNAL and not destination_url:
            raise serializers.ValidationError({
                'destination_url': 'Required when destination_type is EXTERNAL.'
            })

        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError({
                'end_date': 'Must be after start_date.'
            })

        media_file = attrs.get('media_file', getattr(self.instance, 'media_file', None))
        text_content = attrs.get('text_content', getattr(self.instance, 'text_content', ''))

        if ad_format == AdCampaign.AdFormat.TEXT:
            if not text_content.strip():
                raise serializers.ValidationError({
                    'text_content': 'Required for TEXT format ads.'
                })
        elif ad_format in (
            AdCampaign.AdFormat.IMAGE,
            AdCampaign.AdFormat.VIDEO,
            AdCampaign.AdFormat.BANNER,
        ):
            if not media_file:
                raise serializers.ValidationError({
                    'media_file': f'Required for {ad_format} format ads.'
                })

        if ad_type == AdCampaign.AdType.TARGETED:
            school_ids = attrs.get('school_ids', [])
            faculty_ids = attrs.get('faculty_ids', [])
            class_level_ids = attrs.get('class_level_ids', [])
            address_keywords = attrs.get('address_keywords', [])
            
            has_rules = any([school_ids, faculty_ids, class_level_ids, address_keywords])
            
            if not has_rules and self.instance and hasattr(self.instance, 'targeting'):
                t = self.instance.targeting
                has_rules = t.schools.exists() or t.faculties.exists() or t.classes.exists() or bool(t.address_keywords)

            if not has_rules:
                raise serializers.ValidationError({
                    'targeting': 'TARGETED campaigns require at least one targeting dimension (schools, faculties, classes, or address keywords).'
                })

        return attrs

    def create(self, validated_data):
        school_ids = validated_data.pop('school_ids', [])
        faculty_ids = validated_data.pop('faculty_ids', [])
        class_level_ids = validated_data.pop('class_level_ids', [])
        address_keywords = validated_data.pop('address_keywords', [])

        request = self.context.get('request')
        if request and not validated_data.get('created_by'):
            validated_data['created_by'] = request.user

        campaign = AdCampaign.objects.create(**validated_data)

        if campaign.ad_type == AdCampaign.AdType.TARGETED:
            targeting, _ = AdTargeting.objects.get_or_create(campaign=campaign)
            targeting.schools.set(school_ids)
            targeting.faculties.set(faculty_ids)
            targeting.classes.set(class_level_ids)
            targeting.address_keywords = address_keywords
            targeting.save()

        return campaign

    def update(self, instance, validated_data):
        school_ids = validated_data.pop('school_ids', None)
        faculty_ids = validated_data.pop('faculty_ids', None)
        class_level_ids = validated_data.pop('class_level_ids', None)
        address_keywords = validated_data.pop('address_keywords', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if instance.ad_type == AdCampaign.AdType.TARGETED:
            targeting, _ = AdTargeting.objects.get_or_create(campaign=instance)
            
            if school_ids is not None:
                targeting.schools.set(school_ids)
            if faculty_ids is not None:
                targeting.faculties.set(faculty_ids)
            if class_level_ids is not None:
                targeting.classes.set(class_level_ids)
            if address_keywords is not None:
                targeting.address_keywords = address_keywords
                
            targeting.save()

        return instance


class AdCampaignListSerializer(serializers.ModelSerializer):
    media_url = serializers.SerializerMethodField()
    targeting_summary = serializers.SerializerMethodField()
    impressions = serializers.IntegerField(read_only=True)
    clicks = serializers.IntegerField(read_only=True)
    ctr = serializers.FloatField(read_only=True)

    class Meta:
        model = AdCampaign
        fields = [
            'id', 'title', 'ad_type', 'ad_format', 'status',
            'media_url', 'start_date', 'end_date',
            'targeting_summary', 'impressions', 'clicks', 'ctr',
            'created_at',
        ]

    def get_media_url(self, obj):
        if not obj.media_file:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.media_file.url) if request else obj.media_file.url

    def get_targeting_summary(self, obj):
        if obj.ad_type != AdCampaign.AdType.TARGETED:
            return 'Public — visible to everyone'
        if not hasattr(obj, 'targeting'):
            return 'Targeted — no rules configured'
        t = obj.targeting
        parts = []
        if t.schools.exists():
            parts.append(f"{t.schools.count()} school(s)")
        if t.faculties.exists():
            parts.append(f"{t.faculties.count()} faculty(ies)")
        if t.classes.exists():
            parts.append(f"{t.classes.count()} class(es)")
        if t.address_keywords:
            parts.append(f"addresses: {', '.join(t.address_keywords[:3])}")
        return ' + '.join(parts) if parts else 'Targeted — no rules configured'


class AdFeedSerializer(serializers.ModelSerializer):
    media_url = serializers.SerializerMethodField()
    impression_endpoint = serializers.SerializerMethodField()
    click_endpoint = serializers.SerializerMethodField()

    class Meta:
        model = AdCampaign
        fields = [
            'id',
            'title',
            'description',
            'ad_type',
            'ad_format',
            'media_url',
            'text_content',
            'destination_type',
            'destination_url',
            'impression_endpoint',
            'click_endpoint',
        ]

    def get_media_url(self, obj):
        if not obj.media_file:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.media_file.url) if request else obj.media_file.url

    def get_impression_endpoint(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        return request.build_absolute_uri(f'/api/v1/ads/{obj.id}/impression/')

    def get_click_endpoint(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        return request.build_absolute_uri(f'/api/v1/ads/{obj.id}/click/')


class AdInteractionSerializer(serializers.ModelSerializer):
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    campaign_title = serializers.CharField(source='campaign.title', read_only=True)

    class Meta:
        model = AdInteraction
        fields = [
            'id',
            'campaign',
            'campaign_title',
            'user',
            'user_phone',
            'interaction_type',
            'metadata',
            'created_at',
        ]
        read_only_fields = fields


class AdClickResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    redirect_url = serializers.URLField(allow_blank=True)
    destination_type = serializers.CharField()