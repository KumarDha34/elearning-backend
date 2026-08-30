from django.contrib import admin

# Register your models here.
# apps/notes/admin.py
from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.utils import timezone
from django_ckeditor_5.widgets import CKEditor5Widget  # ✅ CKEditor 5 widget
from .models import Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    """
    Admin configuration for Note model with CKEditor 5 support
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
        'uploaded_by__first_name',
        'uploaded_by__last_name'
    )
    
    # ✅ CKEditor 5 widget for content field
    formfield_overrides = {
        models.TextField: {
            'widget': CKEditor5Widget(
                config_name='default',
                attrs={'style': 'width: 100%; height: 400px;'}
            )
        },
    }
    
    # Read-only fields
    readonly_fields = (
        'uploaded_by',
        'views',
        'created_at',
        'updated_at',
        'approved_at',
        'published_at',
        'rejected_at',
        'featured_image_preview'
    )
    
    # Detail View Layout
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'title',
                'content',
                'description',
                'featured_image',
                'featured_image_preview'
            )
        }),
        ('Academic Details', {
            'fields': (
                'subject',
                'class_level',
                'chapter'
            )
        }),
        ('Status & Review', {
            'fields': (
                'status',
                'rejection_reason',
                'rejection_feedback',
                'rejected_by',
                'rejected_at',
                'approved_at',
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
    
    # Bulk Actions
    actions = ['approve_notes', 'reject_notes', 'mark_as_published']
    
    # Custom Methods
    def subject_name(self, obj):
        """Display subject name"""
        return obj.subject.name if obj.subject else '-'
    subject_name.short_description = 'Subject'
    
    def class_level_name(self, obj):
        """Display class level name"""
        return obj.class_level.name if obj.class_level else '-'
    class_level_name.short_description = 'Class Level'
    
    def status_badge(self, obj):
        """Display status as a colored badge"""
        status_colors = {
            'draft': '#6c757d',     # gray
            'pending': '#ffc107',   # orange/yellow
            'published': '#28a745', # green
            'rejected': '#dc3545',  # red
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def featured_image_preview(self, obj):
        """Show featured image thumbnail"""
        if obj.featured_image:
            return format_html(
                '<img src="{}" style="max-height: 150px; max-width: 200px; border-radius: 4px;" />',
                obj.featured_image.url
            )
        return 'No image'
    featured_image_preview.short_description = 'Image Preview'
    
    # Bulk Actions Implementation
    def approve_notes(self, request, queryset):
        """Approve selected notes"""
        updated = queryset.filter(status='pending').update(
            status='published',
            approved_at=timezone.now(),
            published_at=timezone.now()
        )
        self.message_user(request, f'{updated} notes approved and published.')
    approve_notes.short_description = 'Approve selected notes'
    
    def reject_notes(self, request, queryset):
        """Reject selected notes"""
        updated = queryset.filter(status='pending').update(
            status='rejected',
            rejected_at=timezone.now()
        )
        self.message_user(request, f'{updated} notes rejected.')
    reject_notes.short_description = 'Reject selected notes'
    
    def mark_as_published(self, request, queryset):
        """Mark selected notes as published"""
        updated = queryset.filter(status='draft').update(
            status='published',
            published_at=timezone.now()
        )
        self.message_user(request, f'{updated} notes marked as published.')
    mark_as_published.short_description = 'Mark as published'
    
    def save_model(self, request, obj, form, change):
        """Set uploaded_by when creating a new note"""
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
    
    # Media for CKEditor 5
    class Media:
        css = {
            'all': ('admin/css/ckeditor5.css',)
        }