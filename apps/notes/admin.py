from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.utils import timezone
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import Note

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    """
    Admin configuration for Note model with CKEditor 5 support.
    """
    
    # List View Configuration
    list_display = (
        'id',
        'title',
        'subject_name',
        'class_level_name',
        'uploaded_by',
        'status',
        'status_badge',
        'views',
        'created_at'
    )
    
    list_filter = (
        'status',
        'subject',
        'class_level',
        'created_at',
        'uploaded_by'
    )
    
    search_fields = (
        'title',
        'description',
        'content',
        'uploaded_by__phone_number',
        'uploaded_by__full_name',
    )
    
    # CKEditor 5 widget for content field
    formfield_overrides = {
        models.TextField: {
            'widget': CKEditor5Widget(
                config_name='default',
                attrs={'style': 'width: 100%; height: 400px;'}
            )
        },
    }
    
    # Read-only fields (Updated to match new field names)
    readonly_fields = (
        'uploaded_by',
        'views',
        'created_at',
        'updated_at',
        'published_at',
        'reviewed_at',           # Renamed from rejected_at
        'featured_image_preview'
    )
    
    # Detail View Layout
    fieldsets = (
        ('Phase 1: Teacher Upload', {
            'fields': (
                'title',
                'description',
                'pdf_file',
                'subject',
                'class_level',
                'chapter',
                'uploaded_by',
            )
        }),
        ('Phase 2: Editor Review', {
            'fields': (
                'content',
                'featured_image',
                'featured_image_preview',
                'status',
                'editor_feedback',   # Renamed from rejection_reason
                'reviewed_by',       # Renamed from rejected_by
                'reviewed_at',       # Renamed from rejected_at
                'published_at'
            )
        }),
        ('Statistics', {
            'fields': (
                'views',
                'created_at',
                'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    # Custom Methods
    def subject_name(self, obj):
        return obj.subject.name if obj.subject else '-'
    subject_name.short_description = 'Subject'
    
    def class_level_name(self, obj):
        return obj.class_level.name if obj.class_level else '-'
    class_level_name.short_description = 'Class Level'
    
    def status_badge(self, obj):
        status_colors = {
            'teacher_review': '#17a2b8', # Blue for Teacher Review
            'pending': '#ffc107',        # Yellow for Pending Editor Review
            'published': '#28a745',      # Green for Published
            'rejected': '#dc3545',       # Red for Rejected
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def featured_image_preview(self, obj):
        if obj.featured_image:
            return format_html(
                '<img src="{}" style="max-height: 150px; max-width: 200px; border-radius: 4px;" />',
                obj.featured_image.url
            )
        return 'No image'
    featured_image_preview.short_description = 'Image Preview'
    
    def save_model(self, request, obj, form, change):
        """Automatically assign uploader if creating via admin."""
        if not change and not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
    
    class Media:
        css = {
            'all': ('admin/css/ckeditor5.css',)
        }