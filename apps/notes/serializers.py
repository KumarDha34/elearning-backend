from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Note,OldQuestion
from apps.academics.models import Subject, ClassLevel, Chapter
import re


class NoteCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notes"""
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'content', 'description',
            'subject', 'class_level', 'chapter',
            'featured_image',
        ]
        extra_kwargs = {
            'content': {
                'help_text': 'Rich text content from CKEditor',
                'required': True
            },
            'featured_image': {
                'help_text': 'Featured image for the note (optional)',
                'required': False
            },
        }
    
    def validate_content(self, value):
        if not value or value.strip() in ['', '<p><br></p>', '<p>&nbsp;</p>']:
            raise serializers.ValidationError("Content cannot be empty")
        
        plain_text = re.sub(r'<[^>]+>', '', value).strip()
        if len(plain_text) < 10:
            raise serializers.ValidationError("Content must have at least 10 characters of text")
        
        return value
    
    def validate(self, data):
        user = self.context['request'].user
        
        if user.role == 'admin':
            return data
        
        if not hasattr(user, 'teacher_profile'):
            raise serializers.ValidationError({
                'error': 'Only teachers can upload notes.'
            })
        
        if not user.is_verified_teacher:
            raise serializers.ValidationError({
                'error': 'Teacher account must be verified to upload notes.'
            })
        
        teacher = user.teacher_profile
        if teacher.content_count >= teacher.content_limit:
            raise serializers.ValidationError({
                'error': f'Content limit reached ({teacher.content_count}/{teacher.content_limit})'
            })
        
        return data
    
    def create(self, validated_data):
        user = self.context['request'].user
        note = Note.objects.create(
            **validated_data,
            uploaded_by=user,
            status=Note.Status.PENDING
        )
        return note


class NoteListSerializer(serializers.ModelSerializer):
    """Serializer for listing notes"""
    
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.get_full_name', 
        read_only=True
    )
    subject_name = serializers.CharField(
        source='subject.name', 
        read_only=True
    )
    class_level_name = serializers.CharField(
        source='class_level.name', 
        read_only=True
    )
    chapter_name = serializers.CharField(
        source='chapter.name', 
        read_only=True, 
        allow_null=True
    )
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )
    content_preview = serializers.SerializerMethodField()
    featured_image_url = serializers.SerializerMethodField()
    rejection_reason_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'description', 'content_preview',
            'subject', 'subject_name',
            'class_level', 'class_level_name',
            'chapter', 'chapter_name',
            'uploaded_by', 'uploaded_by_name',
            'status', 'status_display',
            'featured_image', 'featured_image_url',
            'views',
            'rejection_reason', 'rejection_reason_preview',
            'created_at', 'updated_at', 'published_at', 'rejected_at'
        ]
        read_only_fields = [
            'uploaded_by', 'uploaded_by_name', 
            'status', 'status_display', 'views'
        ]
    
    @extend_schema_field(serializers.CharField())
    def get_content_preview(self, obj):
        if obj.content:
            plain_text = re.sub(r'<[^>]+>', '', obj.content)
            return plain_text[:200] + '...' if len(plain_text) > 200 else plain_text
        return ''
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_featured_image_url(self, obj):
        if obj.featured_image:
            return obj.featured_image.url
        return None
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_rejection_reason_preview(self, obj):
        if obj.rejection_reason:
            return obj.rejection_reason[:100] + '...' if len(obj.rejection_reason) > 100 else obj.rejection_reason
        return ''


class NoteDetailSerializer(serializers.ModelSerializer):
    """Serializer for note details (full content)"""
    
    uploaded_by_name = serializers.CharField(
        source='uploaded_by.get_full_name', 
        read_only=True
    )
    subject_name = serializers.CharField(
        source='subject.name', 
        read_only=True
    )
    class_level_name = serializers.CharField(
        source='class_level.name', 
        read_only=True
    )
    chapter_name = serializers.CharField(
        source='chapter.name', 
        read_only=True, 
        allow_null=True
    )
    status_display = serializers.CharField(
        source='get_status_display', 
        read_only=True
    )
    rejected_by_name = serializers.CharField(
        source='rejected_by.get_full_name', 
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'content', 'description',
            'subject', 'subject_name',
            'class_level', 'class_level_name',
            'chapter', 'chapter_name',
            'uploaded_by', 'uploaded_by_name',
            'status', 'status_display',
            'featured_image',
            'views',
            'rejection_reason', 'rejection_feedback',
            'rejected_by', 'rejected_by_name',
            'rejected_at',
            'created_at', 'updated_at', 'approved_at', 'published_at'
        ]
        read_only_fields = [
            'uploaded_by', 'uploaded_by_name', 
            'views', 'rejected_by', 'rejected_by_name'
        ]


class NoteUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating notes"""
    
    class Meta:
        model = Note
        fields = [
            'title', 'content', 'description',
            'subject', 'class_level', 'chapter',
            'featured_image',
        ]
    
    def validate_content(self, value):
        if not value or value.strip() in ['', '<p><br></p>', '<p>&nbsp;</p>']:
            raise serializers.ValidationError("Content cannot be empty")
        return value
    
    def update(self, instance, validated_data):
        if not instance.can_edit():
            raise serializers.ValidationError({
                'error': f'Notes in {instance.status} status cannot be updated.'
            })
        return super().update(instance, validated_data)


class NoteStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating note status"""
    
    status = serializers.ChoiceField(
        choices=['draft', 'pending', 'published'],
        help_text="Update note status"
    )
    
    def validate(self, data):
        instance = self.context.get('instance')
        if instance and instance.status == data['status']:
            raise serializers.ValidationError({
                'status': f'Note is already in {data["status"]} status.'
            })
        return data


class NoteApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting notes"""
    
    status = serializers.ChoiceField(
        choices=['approved', 'rejected'],
        help_text="Status to set for the note"
    )
    rejection_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Reason for rejection (required if status is rejected)"
    )
    rejection_feedback = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Detailed feedback for the teacher (optional)"
    )
    
    def validate(self, data):
        if data['status'] == 'rejected' and not data.get('rejection_reason'):
            raise serializers.ValidationError({
                'rejection_reason': 'Rejection reason is required when rejecting a note.'
            })
        return data


class NoteResubmitSerializer(serializers.Serializer):
    """Serializer for resubmitting a rejected note"""
    
    resubmit_note = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional note to the editor when resubmitting"
    )


class NotePreviewSerializer(serializers.Serializer):
    """Serializer for previewing note content (READ-ONLY)"""
    
    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    subject = serializers.IntegerField()
    class_level = serializers.IntegerField()
    chapter = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_content(self, value):
        """Validate CKEditor content is not empty"""
        if not value or value.strip() in ['', '<p><br></p>', '<p>&nbsp;</p>']:
            raise serializers.ValidationError("Content cannot be empty")
        
        # Optional: Check minimum text length
        import re
        plain_text = re.sub(r'<[^>]+>', '', value).strip()
        if len(plain_text) < 10:
            raise serializers.ValidationError("Content must have at least 10 characters of text")
        
        return value
    
    def validate(self, data):
        """Validate subject and class_level exist"""
        try:
            subject = Subject.objects.get(id=data['subject'])
        except Subject.DoesNotExist:
            raise serializers.ValidationError({
                'subject': f'Subject with ID {data["subject"]} does not exist'
            })
        
        try:
            class_level = ClassLevel.objects.get(id=data['class_level'])
        except ClassLevel.DoesNotExist:
            raise serializers.ValidationError({
                'class_level': f'Class Level with ID {data["class_level"]} does not exist'
            })
        
        # Optional: Validate chapter if provided
        if data.get('chapter'):
            try:
                chapter = Chapter.objects.get(id=data['chapter'])
                # Verify chapter belongs to subject
                if chapter.subject_id != data['subject']:
                    raise serializers.ValidationError({
                        'chapter': f'Chapter {data["chapter"]} does not belong to subject {data["subject"]}'
                    })
            except Chapter.DoesNotExist:
                raise serializers.ValidationError({
                    'chapter': f'Chapter with ID {data["chapter"]} does not exist'
                })
        
        return data
    
    def get_preview_data(self):
        """Generate READ-ONLY preview data"""
        subject = Subject.objects.get(id=self.validated_data['subject'])
        class_level = ClassLevel.objects.get(id=self.validated_data['class_level'])
        
        chapter = None
        if self.validated_data.get('chapter'):
            chapter = Chapter.objects.get(id=self.validated_data['chapter'])
        
        return {
            'title': self.validated_data['title'],
            'content': self.validated_data['content'],
            'subject': {
                'id': subject.id,
                'name': subject.name,
            },
            'class_level': {
                'id': class_level.id,
                'name': class_level.name,
            },
            'chapter': {
                'id': chapter.id,
                'name': chapter.name,
            } if chapter else None,
        }

class OldQuestionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OldQuestion
        fields = ['title', 'content', 'subject', 'class_level', 'exam_year']
        extra_kwargs = {
            'content': {
                'help_text': 'Rich text content from CKEditor for question paper',
                'required': True
            },
        }
    
    def validate_content(self, value):
        if not value or value.strip() in ['', '<p><br></p>', '<p>&nbsp;</p>']:
            raise serializers.ValidationError("Question content cannot be empty")
        
        plain_text = re.sub(r'<[^>]+>', '', value).strip()
        if len(plain_text) < 10:
            raise serializers.ValidationError("Question must have at least 10 characters")
        
        return value
    
    def validate(self, data):
        user = self.context['request'].user
        
        if not hasattr(user, 'teacher_profile'):
            raise serializers.ValidationError({
                'error': 'Only teachers can upload old questions.'
            })
        
        if not user.is_verified_teacher:
            raise serializers.ValidationError({
                'error': 'Teacher account must be verified to upload old questions.'
            })
        
        return data

class OldQuestionListSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name')
    class_level_name = serializers.CharField(source='class_level.name')
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name')
    content_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = OldQuestion
        fields = ['id', 'title', 'content_preview', 'subject_name', 
                  'class_level_name', 'exam_year', 'uploaded_by_name', 
                  'status', 'created_at']
    
    def get_content_preview(self, obj):
        if obj.content:
            plain_text = re.sub(r'<[^>]+>', '', obj.content)
            return plain_text[:150] + '...' if len(plain_text) > 150 else plain_text

    @extend_schema_field(serializers.CharField())
    def get_content_preview(self, obj):
        if obj.content:
            plain_text = re.sub(r'<[^>]+>', '', obj.content)
            return plain_text[:150] + '...' if len(plain_text) > 150 else plain_text
        return ''

class OldQuestionDetailSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name')
    class_level_name = serializers.CharField(source='class_level.name')
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name')
    status_display = serializers.CharField(source='get_status_display')
    
    class Meta:
        model = OldQuestion
        fields = ['id', 'title', 'content', 'subject_name', 'class_level_name', 
                  'exam_year', 'uploaded_by', 'uploaded_by_name', 
                  'status', 'status_display', 'rejection_reason', 'created_at']

class OldQuestionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OldQuestion
        fields = ['title', 'content', 'subject', 'class_level', 'exam_year']
    
    def validate_content(self, value):
        if not value or value.strip() in ['', '<p><br></p>', '<p>&nbsp;</p>']:
            raise serializers.ValidationError("Question content cannot be empty")
        return value


class OldQuestionApprovalSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['approved', 'rejected'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['status'] == 'rejected' and not data.get('rejection_reason'):
            raise serializers.ValidationError({
                'rejection_reason': 'Reason required when rejecting'
            })
        return data

class OldQuestionResubmitSerializer(serializers.Serializer):
    """Serializer for resubmitting a rejected question"""
    
    resubmit_note = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional note to the admin when resubmitting"
    )