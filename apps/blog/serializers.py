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
    replies = serializers.SerializerMethodField() 

    class Meta:
        model = BlogComment
        fields = [
            'id', 'post', 'author', 'content', 'parent',
            'replies_count','replies', 'created_at',
        ]
        read_only_fields = ['author', 'created_at']

    @extend_schema_field(serializers.IntegerField())
    def get_replies_count(self, obj):
        # Uses prefetch to avoid N+1
        return getattr(obj, '_replies_count', obj.replies.filter(is_active=True).count())
    @extend_schema_field(serializers.ListField(child=serializers.DictField())) 
    def get_replies(self, obj):                           
        replies = getattr(obj, '_prefetched_replies', None)
        if replies is None:
            replies = obj.replies.filter(is_active=True).select_related('author')
        return [
            {
                'id': r.id,
                'author': UserSerializer(r.author).data,
                'content': r.content,
                'parent': r.parent_id,
                'created_at': r.created_at,
            }
            for r in replies
        ]


class BlogCommentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogComment
        fields = ['post', 'content', 'parent']

    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        return value.strip()

    def validate(self, attrs):
        parent = attrs.get('parent')
        post = attrs.get('post')

        if parent:
            if parent.post_id != post.id:
                raise serializers.ValidationError(
                    {'parent': 'Parent comment belongs to a different post.'}
                )
            if parent.parent is not None:
                raise serializers.ValidationError(
                    {'parent': 'Cannot reply to a reply. Reply to the top-level comment.'}
                )
        return attrs


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
            'status','rejection_reason', 'views', 'likes_count', 'comments_count',
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

class BlogPostRejectSerializer(serializers.Serializer):
    """Used by editors/admins to reject a published post."""
    rejection_reason = serializers.CharField(required=True, allow_blank=False)

    def validate_rejection_reason(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError("Rejection reason is required.")
        return value