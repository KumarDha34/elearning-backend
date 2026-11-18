from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from django.utils.html import strip_tags
from django.utils import timezone
from .models import Note, OldQuestion, NoteRating
from .utils import sanitize_ckeditor_html
import re

# NOTE SERIALIZERS

class NoteTeacherUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ['id', 'title', 'description', 'pdf_file', 'subject', 'class_level', 'chapter']
        
    def validate_pdf_file(self, value):
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError("Only PDF files are allowed.")
        
        max_size = 5 * 1024 * 1024  # 5 MB in bytes
        if value.size > max_size:
            raise serializers.ValidationError("File size cannot exceed 5MB.")
        return value

    def validate(self, data):
        user = self.context['request'].user
        # if user.role == 'admin': return data  #admin access in uploading notes not allowed
        if not hasattr(user, 'teacher_profile'):
            raise serializers.ValidationError({'error': 'Only teachers can upload notes.'})
        if not user.is_verified_teacher:
            raise serializers.ValidationError({'error': 'Teacher account must be verified to upload notes.'})

        return data
    
    def create(self, validated_data):
        user = self.context['request'].user
        return Note.objects.create(**validated_data, uploaded_by=user, status=Note.Status.PENDING)


class NoteEditorReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ['title', 'description', 'content', 'featured_image', 'status', 'editor_feedback']
        
    def validate_content(self, value):
        if not value:
            return value
            
        value = sanitize_ckeditor_html(value)

        if self.instance.status == Note.Status.PUBLISHED and not value:
            raise serializers.ValidationError("Published notes must have content.")
        if value.strip() in ['', '<p><br></p>', '<p>&nbsp;</p>']:
            raise serializers.ValidationError("Content cannot be empty if provided.")
            
        plain_text = re.sub(r'<[^>]+>', '', value).strip()
        if len(plain_text) < 10:
            raise serializers.ValidationError("Content must have at least 10 characters of text")
        return value

    def validate(self, attrs):
        status = attrs.get('status', self.instance.status)
        feedback = attrs.get('editor_feedback')
        if status == Note.Status.REJECTED and not feedback:
            raise serializers.ValidationError({"editor_feedback": "Feedback is required when rejecting a note."})
        return attrs

    def update(self, instance, validated_data):
        user = self.context['request'].user
        status = validated_data.get('status', instance.status)
        
        instance.reviewed_by = user
        instance.reviewed_at = timezone.now()
        
        if status == Note.Status.PUBLISHED and instance.status != Note.Status.PUBLISHED:
            instance.published_at = timezone.now()
            
            
    #----------------implemented throttling as it will checck the db - Sujal----------------------
            # teacher = instance.uploaded_by.teacher_profile
            # teacher.content_count += 1
            # teacher.save(update_fields=['content_count'])
            
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        instance.save()
        return instance


class NoteRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = NoteRating
        fields = ['rating']


class NoteTeacherViewSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_level_name = serializers.CharField(source='class_level.name', read_only=True)
    editor_name = serializers.CharField(source='reviewed_by.full_name', read_only=True)
    pdf_url = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    editor_feedback = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'title', 'description', 'pdf_url', 
            'subject_name', 'class_level_name', 'status', 'status_display',
            'content', 'editor_feedback', 'editor_name','average_rating', 'total_reviews', 'reviewed_at', 'created_at'
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_pdf_url(self, obj):
        request = self.context.get('request')
        if obj.pdf_file and request: return request.build_absolute_uri(obj.pdf_file.url)
        return None
    
    @extend_schema_field(serializers.CharField())
    def get_editor_feedback(self, obj):
        if not obj.editor_feedback: return ""
        return strip_tags(obj.editor_feedback).strip()

    @extend_schema_field(serializers.CharField())
    def get_description(self, obj):
        if not obj.description: return ""
        return strip_tags(obj.description).strip()
    
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_content(self, obj):
        if obj.status in ['teacher_review', 'published']:
            return obj.content
        return None


class NotePublicViewSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_level_name = serializers.CharField(source='class_level.name', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    featured_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'title', 'description', 'content', 'featured_image_url', 
            'subject_name', 'class_level_name', 'status' 'uploaded_by_name', 'views', 'published_at','average_rating', 'total_reviews'
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_featured_image_url(self, obj):
        request = self.context.get('request')
        if obj.featured_image and request: return request.build_absolute_uri(obj.featured_image.url)
        return None


class NoteTeacherUpdateSerializer(serializers.ModelSerializer):
    """
    Allows Teachers to update their note (title, description, PDF) 
    ONLY if it is PENDING or REJECTED.
    """
    class Meta:
        model = Note
        fields = ['title', 'description', 'pdf_file', 'subject', 'class_level', 'chapter']
        
    def validate_pdf_file(self, value):
        if value and not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError("Only PDF files are allowed.")
        
        max_size = 5 * 1024 * 1024  # 5 MB in bytes
        if value.size > max_size:
            raise serializers.ValidationError("File size cannot exceed 5MB.")
        return value

    def update(self, instance, validated_data):
        # Reset status to PENDING so the editor reviews it again
        instance.status = Note.Status.PENDING
        # Clear old editor feedback
        instance.editor_feedback = ""
        instance.reviewed_by = None
        instance.reviewed_at = None
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        instance.save()
        return instance

# OLD QUESTION SERIALIZERS
class OldQuestionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OldQuestion
        fields = ['title', 'content', 'subject', 'class_level', 'exam_year']
    
    def validate_content(self, value):
        if not value:
            return value
            
        value = sanitize_ckeditor_html(value)

        if value.strip() in ['', '<p><br></p>', '<p>&nbsp;</p>']:
            raise serializers.ValidationError("Question content cannot be empty")
        plain_text = re.sub(r'<[^>]+>', '', value).strip()
        if len(plain_text) < 10:
            raise serializers.ValidationError("Question must have at least 10 characters")
        return value
    
    def validate(self, data):
        user = self.context['request'].user
        if not hasattr(user, 'teacher_profile'):
            raise serializers.ValidationError({'error': 'Only teachers can upload old questions.'})
        if not user.is_verified_teacher:
            raise serializers.ValidationError({'error': 'Teacher account must be verified to upload old questions.'})
        return data

class OldQuestionListSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name')
    class_level_name = serializers.CharField(source='class_level.name')
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name')
    content_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = OldQuestion
        fields = ['id', 'title', 'content_preview', 'subject_name', 'class_level_name', 'exam_year', 'uploaded_by_name', 'status', 'created_at']

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
        fields = ['id', 'title', 'content', 'subject_name', 'class_level_name', 'exam_year', 'uploaded_by', 'uploaded_by_name', 'status_display', 'rejection_reason', 'created_at']

class OldQuestionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OldQuestion
        fields = ['title', 'content', 'subject', 'class_level', 'exam_year']
    
    def validate_content(self, value):
        if not value:
            return value
            
        value = sanitize_ckeditor_html(value)

        if value.strip() in ['', '<p><br></p>', '<p>&nbsp;</p>']:
            raise serializers.ValidationError("Question content cannot be empty")
        return value

class OldQuestionApprovalSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['approved', 'rejected'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['status'] == 'rejected' and not data.get('rejection_reason'):
            raise serializers.ValidationError({'rejection_reason': 'Reason required when rejecting'})
        return data

class OldQuestionResubmitSerializer(serializers.Serializer):
    resubmit_note = serializers.CharField(required=False, allow_blank=True)
    
