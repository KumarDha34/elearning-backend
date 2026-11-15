import re
import bleach
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import BlogCategory, BlogPost, BlogComment, BlogLike, TeacherFollow
from apps.accounts.serializers import UserSerializer


# ============================================================================
# XSS SANITIZATION
# ============================================================================

ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 's', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'a', 'img', 'figure', 'figcaption',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'pre', 'code',
]
ALLOWED_ATTRS = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'width', 'height'],
    '*': ['class'],
}


def sanitize_content(html: str) -> str:
    """Strip dangerous HTML including <script>/<style> content."""
    if not html:
        return html

    # Remove entire <script> and <style> blocks (tag + content)
    html = re.sub(
        r'<(script|style)[^>]*>.*?</\1>',
        '',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=['http', 'https', 'mailto'],
        strip=True,
    )


# ============================================================================
# CATEGORY SERIALIZERS
# ============================================================================

class BlogCategorySerializer(serializers.ModelSerializer):
    posts_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = BlogCategory
        fields = ['id', 'name', 'slug', 'is_active', 'posts_count', 'created_at', 'updated_at']
        read_only_fields = ['slug', 'posts_count', 'created_at', 'updated_at']


class BlogCategoryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = ['name', 'is_active']


# ============================================================================
# COMMENT SERIALIZERS
# ============================================================================

class BlogCommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = BlogComment
        fields = [
            'id', 'post', 'author', 'content', 'parent',
            'replies_count', 'created_at',
        ]
        read_only_fields = ['author', 'created_at']

    @extend_schema_field(serializers.IntegerField())
    def get_replies_count(self, obj):
        # Uses prefetch to avoid N+1
        return getattr(obj, '_replies_count', obj.replies.filter(is_active=True).count())


class BlogCommentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogComment
        fields = ['post', 'content', 'parent']

    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        return value.strip()


# ============================================================================
# POST SERIALIZERS
# ============================================================================

class BlogPostListSerializer(serializers.ModelSerializer):
    """Lightweight — for lists."""
    author_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)

    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'description', 'featured_image',
            'author_name', 'category', 'category_name', 'tags',
            'status', 'views', 'likes_count', 'comments_count',
            'created_at', 'published_at',
        ]


class BlogPostDetailSerializer(serializers.ModelSerializer):
    """Full detail — includes author, likes, comments inline."""
    author = UserSerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    is_liked = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'description', 'content', 'featured_image',
            'author', 'category', 'category_name', 'tags',
            'status', 'rejection_reason',
            'views', 'likes_count', 'comments_count', 'is_liked', 'comments',
            'created_at', 'updated_at', 'published_at',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_is_liked(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        # Prefetched via view
        return getattr(obj, '_is_liked', obj.likes.filter(user=request.user).exists())

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_comments(self, obj):
        # Prefetched via view — no N+1
        comments = getattr(obj, '_prefetched_comments', None)
        if comments is None:
            comments = obj.comments.filter(is_active=True, parent__isnull=True).select_related('author')
        return BlogCommentSerializer(comments, many=True, context=self.context).data


class BlogPostWriteSerializer(serializers.ModelSerializer):
    """Create / update — sanitizes content."""
    tags = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = BlogPost
        fields = ['title', 'description', 'content', 'featured_image', 'category', 'tags']

    def validate_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Title cannot be blank.")
        return value.strip()

    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Content cannot be empty.")
        return sanitize_content(value)

    def validate_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list of strings.")
        return [str(t).strip() for t in value if str(t).strip()]

    def validate_category(self, value):
        if value and not value.is_active:
            raise serializers.ValidationError("Category is inactive.")
        return value


class BlogPostStatusSerializer(serializers.Serializer):
    """Used for status transitions (submit / approve / reject)."""
    status = serializers.ChoiceField(choices=['pending', 'published', 'rejected'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['status'] == 'rejected' and not attrs.get('rejection_reason', '').strip():
            raise serializers.ValidationError({
                'rejection_reason': 'Rejection reason is required when rejecting a post.'
            })
        return attrs