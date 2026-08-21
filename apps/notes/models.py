from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ckeditor.fields import RichTextField
from apps.academics.models import Subject, ClassLevel, Chapter


class Note(models.Model):
    """Teacher create notes using CKEditor"""
    
    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        PENDING = 'pending', _('Pending Review')
        PUBLISHED = 'published', _('Published')
        REJECTED = 'rejected', _('Rejected')
    
    # Basic Info
    title = models.CharField(max_length=255, verbose_name=_("Title"))
    content = RichTextField(verbose_name=_("Content"), help_text=_("Write your notes using the rich text editor"))
    description = models.TextField(blank=True, verbose_name=_("Short Description"))
    featured_image = models.ImageField(
        upload_to='notes/featured/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Featured Image")
    )
    
    # Academic Links
    subject = models.ForeignKey(
        Subject, 
        on_delete=models.CASCADE, 
        related_name='notes',
        verbose_name=_("Subject")
    )
    class_level = models.ForeignKey(
        ClassLevel, 
        on_delete=models.CASCADE, 
        related_name='notes',
        verbose_name=_("Class Level")
    )
    chapter = models.ForeignKey(
        Chapter, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='notes',
        verbose_name=_("Chapter")
    )
    
    # Author
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='uploaded_notes',
        verbose_name=_("Uploaded By")
    )
    
    # Status
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.DRAFT,
        verbose_name=_("Status")
    )
    
    # Rejection Response Fields
    rejection_reason = models.TextField(
        blank=True, 
        verbose_name=_("Rejection Reason"),
        help_text=_("Reason why the note was rejected")
    )
    rejection_feedback = models.TextField(
        blank=True, 
        verbose_name=_("Rejection Feedback"),
        help_text=_("Detailed feedback for the teacher")
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rejected_notes',
        verbose_name=_("Rejected By")
    )
    rejected_at = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name=_("Rejected At")
    )
    
    # Statistics
    views = models.PositiveIntegerField(default=0, verbose_name=_("Views"))
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Approved At"))
    published_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Published At"))
    
    class Meta:
        db_table = 'notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'subject']),
            models.Index(fields=['uploaded_by', 'status']),
            models.Index(fields=['class_level']),
            models.Index(fields=['rejected_at']),
        ]
        verbose_name = _("Note")
        verbose_name_plural = _("Notes")
    
    def __str__(self):
        return f"{self.title} - {self.uploaded_by.phone_number}"
    
    def is_draft(self):
        return self.status == self.Status.DRAFT
    
    def is_pending(self):
        return self.status == self.Status.PENDING
    
    def is_published(self):
        return self.status == self.Status.PUBLISHED
    
    def is_rejected(self):
        return self.status == self.Status.REJECTED
    
    def can_edit(self):
        return self.status in [self.Status.DRAFT, self.Status.PENDING]
    
    def can_resubmit(self):
        return self.status == self.Status.REJECTED
    
    def increment_views(self):
        self.views += 1
        self.save(update_fields=['views'])
    
    def reject(self, user, reason, feedback=""):
        self.status = self.Status.REJECTED
        self.rejection_reason = reason
        self.rejection_feedback = feedback
        self.rejected_by = user
        self.rejected_at = timezone.now()
        self.save()
    
    def resubmit(self):
        if self.is_rejected():
            self.status = self.Status.PENDING
            self.rejection_reason = ""
            self.rejection_feedback = ""
            self.rejected_by = None
            self.rejected_at = None
            self.save()
            return True
        return False