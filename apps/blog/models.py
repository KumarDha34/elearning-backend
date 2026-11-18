from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.fields import CKEditor5Field


class BlogCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_('Name'))
    slug = models.SlugField(max_length=120, unique=True, blank=True, verbose_name=_('Slug'))
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'blog_categories'
        ordering = ['name']
        verbose_name = _('Blog Category')
        verbose_name_plural = _('Blog Categories')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class BlogPost(models.Model):
    class Status(models.TextChoices):
        PUBLISHED = 'published', _('Published')
        REJECTED = 'rejected', _('Rejected')

    title = models.CharField(max_length=255, verbose_name=_('Title'))
    slug = models.SlugField(max_length=280, unique=True, blank=True, verbose_name=_('Slug'))
    description = models.TextField(blank=True, verbose_name=_('Short Description'))
    content = CKEditor5Field(verbose_name=_('Content'), config_name='default')
    featured_image = models.ImageField(
        upload_to='blog/featured/%Y/%m/%d/',
        null=True, blank=True,
        verbose_name=_('Featured Image'),
    )

    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='posts',
        verbose_name=_('Category'),
    )
    tags = models.JSONField(default=list, blank=True, verbose_name=_('Tags'))

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blog_posts',
        verbose_name=_('Author'),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PUBLISHED,
        verbose_name=_('Status'),
    )
    rejection_reason = models.TextField(blank=True, verbose_name=_('Rejection Reason'))
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rejected_blog_posts',
        verbose_name=_('Rejected By'),
    )
    rejected_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Rejected At'))

    views = models.PositiveIntegerField(default=0, verbose_name=_('Views'))
    likes_count = models.PositiveIntegerField(default=0, verbose_name=_('Likes Count'))
    comments_count = models.PositiveIntegerField(default=0, verbose_name=_('Comments Count'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Published At'))

    class Meta:
        db_table = 'blog_posts'
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', 'published_at']),
            models.Index(fields=['uploaded_by', 'status']),
            models.Index(fields=['category']),
        ]
        verbose_name = _('Blog Post')
        verbose_name_plural = _('Blog Posts')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug = base
            n = 1
            while BlogPost.objects.filter(slug=slug).exclude(id=self.id).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug

        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

    def increment_views(self):
        self.views += 1
        self.save(update_fields=['views'])


class BlogComment(models.Model):
    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blog_comments',
    )
    content = models.TextField(verbose_name=_('Comment'))
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='replies',
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'blog_comments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', 'is_active']),
        ]
        verbose_name = _('Blog Comment')
        verbose_name_plural = _('Blog Comments')

    def __str__(self):
        return f"Comment by {self.author.full_name or self.author.phone_number}"


class BlogLike(models.Model):
    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='likes',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blog_likes',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blog_likes'
        unique_together = [['post', 'user']]
        verbose_name = _('Blog Like')
        verbose_name_plural = _('Blog Likes')

    def __str__(self):
        return f"{self.user.phone_number} → {self.post.title}"


class TeacherFollow(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='following_teachers',
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_followers',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'teacher_follows'
        unique_together = [['student', 'teacher']]
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['teacher']),
        ]
        verbose_name = _('Teacher Follow')
        verbose_name_plural = _('Teacher Follows')

    def __str__(self):
        return f"{self.student.phone_number} follows {self.teacher.phone_number}"