# apps/ads/serializers.py

from rest_framework import serializers

from .models import AdCampaign, AdTargeting, AdInteraction


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
    targeting = AdTargetingSerializer(required=False)

    impressions = serializers.IntegerField(read_only=True, required=False)
    clicks = serializers.IntegerField(read_only=True, required=False)
    ctr = serializers.FloatField(read_only=True, required=False)

    media_url = serializers.SerializerMethodField()

    class Meta:
        model = AdCampaign
        fields = [
            'id',
            'title',
            'description',
            'ad_type',
            'ad_format',
            'media_file',
            'media_url',
            'text_content',
            'destination_type',
            'destination_url',
            'status',
            'start_date',
            'end_date',
            'targeting',
            'impressions',
            'clicks',
            'ctr',
            'created_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'media_url', 'impressions', 'clicks', 'ctr',
            'created_by', 'created_at', 'updated_at',
        ]

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
            targeting = attrs.get('targeting')
            if targeting is None and self.instance:
                targeting_exists = hasattr(self.instance, 'targeting')
            else:
                targeting_exists = bool(targeting)

            if not targeting_exists:
                raise serializers.ValidationError({
                    'targeting': 'TARGETED campaigns require at least one targeting dimension.'
                })

        return attrs

    def create(self, validated_data):
        targeting_data = validated_data.pop('targeting', None)
        request = self.context.get('request')
        if request and not validated_data.get('created_by'):
            validated_data['created_by'] = request.user

        campaign = AdCampaign.objects.create(**validated_data)

        if targeting_data:
            self._write_targeting(campaign, targeting_data)
        elif campaign.ad_type == AdCampaign.AdType.TARGETED:
            AdTargeting.objects.create(campaign=campaign)

        return campaign

    def update(self, instance, validated_data):
        targeting_data = validated_data.pop('targeting', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if targeting_data is not None:
            self._write_targeting(instance, targeting_data)
        elif instance.ad_type == AdCampaign.AdType.TARGETED and not hasattr(instance, 'targeting'):
            AdTargeting.objects.create(campaign=instance)

        return instance

    def _write_targeting(self, campaign, targeting_data):
        school_ids = targeting_data.pop('schools', [])
        faculty_ids = targeting_data.pop('faculties', [])
        class_ids = targeting_data.pop('classes', [])
        address_keywords = targeting_data.pop('address_keywords', [])

        targeting, _ = AdTargeting.objects.get_or_create(campaign=campaign)

        targeting.address_keywords = address_keywords
        targeting.save()

        targeting.schools.set(school_ids)
        targeting.faculties.set(faculty_ids)
        targeting.classes.set(class_ids)


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