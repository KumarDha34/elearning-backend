from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Avg
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.fields import CKEditor5Field 
from apps.academics.models import Subject, ClassLevel, Chapter

class Note(models.Model):
    """Notes uploaded by Teachers (PDF), reviewed & published by Editors."""
    
    class Status(models.TextChoices):
        TEACHER_REVIEW = 'teacher_review', _('Teacher Review')
        PENDING = 'pending', _('Pending Editor Review')
        PUBLISHED = 'published', _('Published')
        REJECTED = 'rejected', _('Rejected')
    
    # ── Phase 1: Teacher Upload ──
    title = models.CharField(max_length=255, verbose_name=_("Title"))
    pdf_file = models.FileField(
        upload_to='notes/pdfs/%Y/%m/%d/',
        verbose_name=_("PDF File"),
        help_text=_("Upload the notes as a PDF file")
    )
    description = models.TextField(blank=True, verbose_name=_("Short Description"))
    
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='notes', verbose_name=_("Subject"))
    class_level = models.ForeignKey(ClassLevel, on_delete=models.CASCADE, related_name='notes', verbose_name=_("Class Level"))
    chapter = models.ForeignKey(Chapter, on_delete=models.SET_NULL, null=True, blank=True, related_name='notes', verbose_name=_("Chapter"))
    
    
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_notes',
        verbose_name=_("Uploaded By")
    )
    
    # ── Phase 2: Editor Content & Review ──
    content = CKEditor5Field(
        verbose_name=_("Content"),
        help_text=_("Rich text content added by the Editor"),
        config_name='default',
        blank=True,
        null=True
    )
    featured_image = models.ImageField(
        upload_to='notes/featured/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name=_("Featured Image"),
        help_text=_("Uploaded by the Editor")
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Status")
    )
    
    # ── Editor Feedback & Review Details ──
    editor_feedback = models.TextField(
        blank=True,
        verbose_name=_("Editor Feedback"),
        help_text=_("Feedback from the editor (e.g., reason for rejection or requested changes)")
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_notes',
        verbose_name=_("Reviewed By")
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Reviewed At")
    )
    
    average_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00, verbose_name="Average Rating"
    )
    total_reviews = models.PositiveIntegerField(default=0, verbose_name="Total Ratings")
    
    # ── Statistics & Timestamps ──
    views = models.PositiveIntegerField(default=0, verbose_name=_("Views"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    published_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Published At"))
    
    class Meta:
        db_table = 'notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'subject']),
            models.Index(fields=['uploaded_by', 'status']),
            models.Index(fields=['class_level']),
            models.Index(fields=['reviewed_at']),
        ]
        verbose_name = _("Note")
        verbose_name_plural = _("Notes")
    
    def __str__(self):
        return f"{self.title} - {self.uploaded_by.phone_number}"
    
    def increment_views(self):
        self.views += 1
        self.save(update_fields=['views'])
    
    def save(self, *args, **kwargs):
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
        
        
    def update_rating(self):
    
        avg = self.ratings.aggregate(Avg('rating'))['rating__avg']
        
        self.average_rating = round(avg, 2) if avg else 0.00
        self.total_reviews = self.ratings.count()
        self.save(update_fields=['average_rating', 'total_reviews'])

class NoteRating(models.Model):
    """Stores ONLY the star rating (1-5) left by a student on a Note."""
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'note_ratings'
        unique_together = ('note', 'user')

class OldQuestion(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PUBLISHED = 'published', 'Published'
        REJECTED = 'rejected', 'Rejected'
        
    title = models.CharField(max_length=255)
    content = CKEditor5Field(verbose_name="Question Content", config_name='default')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_level = models.ForeignKey(ClassLevel, on_delete=models.CASCADE)
    exam_year = models.IntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'old_questions'