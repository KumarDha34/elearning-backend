import logging
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.db.models import Count, Prefetch, Q, F
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .models import BlogCategory, BlogPost, BlogComment, BlogLike, TeacherFollow
from .permissions import CanWriteBlog, CanReviewBlog
from .serializers import (
    BlogCategorySerializer,
    BlogCategoryWriteSerializer,
    BlogPostListSerializer,
    BlogPostDetailSerializer,
    BlogPostWriteSerializer,
    BlogCommentSerializer,
    BlogCommentWriteSerializer,
    BlogPostRejectSerializer
)
from .cache_service import (
    increment_like_count, decrement_like_count,
    get_like_count, get_view_count, increment_view_count,
)

logger = logging.getLogger(__name__)


def _mask(phone):
    return f"{phone[:2]}******{phone[-2:]}" if phone else ""


# ============================================================================
# CATEGORIES
# ============================================================================

class BlogCategoryListCreateView(APIView):
    """
    GET  /categories/  → list (anyone)
    POST /categories/  → create (editor/admin only)
    """
    serializer_class = BlogCategorySerializer

    @extend_schema(
        summary="List Blog Categories",
        operation_id="blog_categories_list",
        responses={200: BlogCategorySerializer(many=True)},
    )
    def get(self, request):
        qs = (
            BlogCategory.objects
            .filter(is_active=True)
            .annotate(posts_count=Count('posts', filter=Q(posts__status='published')))
            .order_by('name')
        )
        return Response(BlogCategorySerializer(qs, many=True).data)

    @extend_schema(
        summary="Create Blog Category (editor/admin only)",
        operation_id="blog_categories_create",
        request=BlogCategoryWriteSerializer,
        responses={201: BlogCategorySerializer},
    )
    def post(self, request):
        if not CanReviewBlog().has_permission(request, self):
            return Response(
                {'error': 'Only editors or admins can create categories.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = BlogCategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        logger.info(f"Category created by {_mask(request.user.phone_number)}: {category.name}")
        return Response(BlogCategorySerializer(category).data, status=status.HTTP_201_CREATED)


class BlogCategoryDetailView(APIView):
    """
    GET    /categories/{id}/  → detail (anyone)
    PATCH  /categories/{id}/  → update (editor/admin only)
    DELETE /categories/{id}/  → delete (editor/admin only)
    """
    serializer_class = BlogCategorySerializer

    def get_object(self, pk):
        return get_object_or_404(BlogCategory, pk=pk)

    def get(self, request, pk):
        cat = self.get_object(pk)
        return Response(BlogCategorySerializer(cat).data)

    def patch(self, request, pk):
        if not CanReviewBlog().has_permission(request, self):
            return Response({'error': 'Only editors or admins can update categories.'}, status=status.HTTP_403_FORBIDDEN)
        cat = self.get_object(pk)
        serializer = BlogCategoryWriteSerializer(cat, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BlogCategorySerializer(cat).data)

    def delete(self, request, pk):
        if not CanReviewBlog().has_permission(request, self):
            return Response({'error': 'Only editors or admins can delete categories.'}, status=status.HTTP_403_FORBIDDEN)
        cat = self.get_object(pk)
        cat.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# POSTS — PUBLIC LIST (read-only, published only)
# ============================================================================

class BlogPostPublicListView(APIView):
    """
    GET /posts/  → list published posts (public, no auth required)

    Filters:
    - ?category=<slug>
    - ?tag=<tag>
    - ?search=<text>
    - ?author=<user_id>
    """
    permission_classes = [AllowAny]
    serializer_class = BlogPostListSerializer

    @extend_schema(
        summary="List Published Blog Posts",
        operation_id="blog_posts_public_list",
        description=(
            "Public list of published posts. Filter by category, tag, author, or search.\n"
            "Only `status='published'` posts are returned."
        ),
        parameters=[
            OpenApiParameter('category', OpenApiTypes.STR, description='Category slug'),
            OpenApiParameter('tag', OpenApiTypes.STR, description='Tag name'),
            OpenApiParameter('author', OpenApiTypes.INT, description='Filter by author user ID'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Search title/description/content'),
        ],
        responses={200: BlogPostListSerializer(many=True)},
    )
    def get(self, request):
        qs = (
            BlogPost.objects
            .filter(status=BlogPost.Status.PUBLISHED)
            .select_related('uploaded_by', 'category')
        )

        if cat := request.query_params.get('category'):
            qs = qs.filter(category__slug=cat)
        if tag := request.query_params.get('tag'):
            qs = qs.filter(tags__contains=[tag])
        if author := request.query_params.get('author'):
            qs = qs.filter(uploaded_by_id=author)
        if search := request.query_params.get('search'):
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(content__icontains=search)
            )

        qs = qs.order_by('-published_at', '-created_at')
        return Response(BlogPostListSerializer(qs, many=True).data)


# ============================================================================
# POSTS — MY POSTS (author's own posts, all statuses)
# ============================================================================

class BlogPostMyListView(APIView):
    """
    GET /posts/my/  → list current user's posts (all statuses)

    Filters:
    - ?status=published|rejected
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BlogPostListSerializer

    @extend_schema(
        summary="List My Blog Posts",
        operation_id="blog_posts_my_list",
        description="List the current user's own posts",
        parameters=[
            OpenApiParameter('status', OpenApiTypes.STR, description='published|rejected'),
        ],
        responses={200: BlogPostListSerializer(many=True)},
    )
    def get(self, request):
        qs = (
            BlogPost.objects
            .filter(uploaded_by=request.user)
            .select_related('uploaded_by', 'category')
        )

        if status_param := request.query_params.get('status'):
            qs = qs.filter(status=status_param)

        qs = qs.order_by('-created_at')
        return Response(BlogPostListSerializer(qs, many=True).data)

# ============================================================================
# POSTS — CREATE
# ============================================================================

class BlogPostCreateView(APIView):
    """
    POST /posts/  → create a new post
    """
    permission_classes = [IsAuthenticated, CanWriteBlog]
    serializer_class = BlogPostWriteSerializer

    @extend_schema(
        summary="Create Blog Post",
        operation_id="blog_posts_create",
        request=BlogPostWriteSerializer,
        responses={201: BlogPostListSerializer},
    )
    def post(self, request):
        serializer = BlogPostWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = serializer.save(uploaded_by=request.user)
        logger.info(f"Post created by {_mask(request.user.phone_number)}: {post.title}")
        return Response(BlogPostListSerializer(post).data, status=status.HTTP_201_CREATED)


# ============================================================================
# POSTS — DETAIL
# ============================================================================

class BlogPostDetailView(APIView):
    """
    GET /posts/{slug}/  → published post detail with inline comments + is_liked
    """
    permission_classes = [AllowAny]
    serializer_class = BlogPostDetailSerializer

    @extend_schema(
        summary="Get Blog Post Detail",
        operation_id="blog_posts_detail",
        responses={200: BlogPostDetailSerializer, 404: OpenApiTypes.OBJECT},
    )
    def get(self, request, slug):
        qs = (
            BlogPost.objects
            .filter(status=BlogPost.Status.PUBLISHED)
            .select_related('uploaded_by', 'category')
            .prefetch_related(
                Prefetch(
                        'comments',
                        queryset=BlogComment.objects
                            .filter(is_active=True, parent__isnull=True)
                            .select_related('author')
                            .annotate(_replies_count=Count('replies', filter=Q(replies__is_active=True)))
                            .prefetch_related(
                                Prefetch(
                                    'replies',
                                    queryset=BlogComment.objects.filter(is_active=True).select_related('author'),
                                    to_attr='_prefetched_replies',
                                )
                            ),
                        to_attr='_prefetched_comments',
                    )
            )
        )
        post = get_object_or_404(qs, slug=slug)
        increment_view_count(post.pk)
        post.views = get_view_count(post.pk)
        post.likes_count = get_like_count(post.pk)

        if request.user.is_authenticated:
            post._is_liked = post.likes.filter(user=request.user).exists()
        else:
            post._is_liked = False

        return Response(BlogPostDetailSerializer(post, context={'request': request}).data)

# ============================================================================
# POSTS — Reject (editor/admin only)
# ============================================================================

class BlogPostRejectView(APIView):
    """
    POST /posts/{id}/reject/  → editor/admin rejects a published post with reason.

    Body: {"rejection_reason": "..."}
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BlogPostRejectSerializer

    @extend_schema(
        summary="Reject Published Post (editor/admin only)",
        operation_id="blog_posts_reject",
        request=BlogPostRejectSerializer,
        responses={
            200: BlogPostListSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request, pk):
        if not CanReviewBlog().has_permission(request, self):
            return Response(
                {'error': 'Only editors or admins can reject posts.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = BlogPostRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        post = get_object_or_404(BlogPost, pk=pk)

        if post.status != BlogPost.Status.PUBLISHED:
            return Response(
                {'error': f'Only published posts can be rejected. Current status: "{post.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        post.status = BlogPost.Status.REJECTED
        post.rejection_reason = serializer.validated_data['rejection_reason']
        post.rejected_by = request.user
        post.rejected_at = timezone.now()
        post.save()

        logger.info(f"Post rejected by {_mask(request.user.phone_number)}: {post.title}")

        return Response({
            'message': 'Post rejected.',
            'post': BlogPostListSerializer(post).data,
        })
# ============================================================================
# POSTS — LIKE (toggle)
# ============================================================================

class ToggleBlogLikeView(APIView):
    """
    POST /posts/{id}/like/  → toggle like on a published post

    Returns: {"liked": true/false, "likes_count": N}
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BlogPostListSerializer

    @extend_schema(
        summary="Toggle Post Like",
        operation_id="blog_posts_like_toggle",
        request=None,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'liked': {'type': 'boolean'},
                    'likes_count': {'type': 'integer'},
                },
            }
        },
    )
    def post(self, request, pk):
        post = get_object_or_404(BlogPost, pk=pk, status=BlogPost.Status.PUBLISHED)

        like, created = BlogLike.objects.get_or_create(post=post, user=request.user)

        if created:
            new_count = increment_like_count(post.pk)
            return Response({'liked': True, 'likes_count': new_count})

        like.delete()
        new_count = decrement_like_count(post.pk)
        return Response({'liked': False, 'likes_count': new_count})


class MyLikedPostsView(APIView):
    """
    GET /my-liked-posts/  → list posts the current user has liked
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BlogPostListSerializer

    @extend_schema(
        summary="Get My Liked Posts",
        operation_id="blog_my_liked_posts",
        responses={200: BlogPostListSerializer(many=True)},
    )
    def get(self, request):
        liked_posts = (
            BlogPost.objects
            .filter(
                likes__user=request.user,
                status=BlogPost.Status.PUBLISHED,
            )
            .select_related('uploaded_by', 'category')
            .order_by('-likes__created_at')
        )

        posts_data = []
        for post in liked_posts:
            post.likes_count = get_like_count(post.pk)
            posts_data.append(BlogPostListSerializer(post).data)

        return Response(posts_data)


# ============================================================================
# COMMENTS
# ============================================================================

class BlogCommentCreateView(APIView):
    """
    POST /posts/{id}/comments/  → add a comment to a published post
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BlogCommentWriteSerializer

    @extend_schema(
        summary="Create Blog Comment",
        operation_id="blog_comments_create",
        request=BlogCommentWriteSerializer,
        responses={201: BlogCommentSerializer},
    )
    def post(self, request, pk):
        post = get_object_or_404(BlogPost, pk=pk, status=BlogPost.Status.PUBLISHED)
        data = {**request.data, 'post': post.id}

        serializer = BlogCommentWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(author=request.user)

        count = BlogComment.objects.filter(post=post, is_active=True).count()
        BlogPost.objects.filter(pk=post.pk).update(comments_count=count)

        return Response(BlogCommentSerializer(comment).data, status=status.HTTP_201_CREATED)


# ============================================================================
# FOLLOW
# ============================================================================

class ToggleTeacherFollowView(APIView):
    """
    POST /api/v1/blog/teachers/{id}/follow/  → toggle follow/unfollow (student only)

    One POST toggles:
    - If not following → follow
    - If following → unfollow

    Returns: {"following": true/false, "message": "..."}
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BlogPostListSerializer

    @extend_schema(
        summary="Toggle Teacher Follow",
        operation_id="blog_teacher_follow_toggle",
        request=None,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'following': {'type': 'boolean'},
                    'message': {'type': 'string'},
                },
            }
        },
    )
    def post(self, request, pk):
        if not request.user.is_student:
            return Response(
                {'error': 'Only students can follow teachers.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            teacher = User.objects.get(pk=pk, role='instructor')
        except User.DoesNotExist:
            return Response(
                {'error': 'Teacher not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Try to delete — if exists, unfollow
        deleted, _ = TeacherFollow.objects.filter(
            student=request.user, teacher=teacher
        ).delete()

        if deleted:
            return Response({
                'following': False,
                'message': 'Unfollowed.',
            })

        # If not found, create — follow
        TeacherFollow.objects.create(
            student=request.user, teacher=teacher,
        )
        return Response({
            'following': True,
            'message': 'Now following.',
        })


# ============================================================================
# FEED
# ============================================================================

class FeedView(APIView):
    """
    GET /feed/  → personalised feed

    Priority:
    1. Followed teachers' posts
    2. Same-faculty posts
    3. Trending (last 7 days)
    4. Latest published
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BlogPostListSerializer

    @extend_schema(
        summary="Personalized Feed",
        operation_id="blog_feed",
        responses={200: BlogPostListSerializer(many=True)},
    )
    def get(self, request):
        user = request.user

        base = BlogPost.objects.filter(
            status=BlogPost.Status.PUBLISHED
        ).select_related('uploaded_by', 'category')

        seen = set()
        ordered = []

        followed_ids = list(
            TeacherFollow.objects.filter(student=user).values_list('teacher_id', flat=True)
        )
        if followed_ids:
            qs = base.filter(uploaded_by_id__in=followed_ids).order_by('-published_at')[:50]
            for post in qs:
                if post.id not in seen:
                    seen.add(post.id)
                    ordered.append(post)

        student_faculty = None
        if hasattr(user, 'student_profile'):
            student_faculty = user.student_profile.faculty_id

        if student_faculty:
            qs = base.filter(
                uploaded_by__teacher_profile__faculty_id=student_faculty
            ).exclude(uploaded_by_id__in=followed_ids).order_by('-published_at')[:50]
            for post in qs:
                if post.id not in seen:
                    seen.add(post.id)
                    ordered.append(post)

        cutoff = timezone.now() - timedelta(days=7)
        qs = base.filter(published_at__gte=cutoff).order_by('-likes_count', '-views')[:50]
        for post in qs:
            if post.id not in seen:
                seen.add(post.id)
                ordered.append(post)

        qs = base.exclude(id__in=seen).order_by('-published_at')[:50]
        for post in qs:
            if post.id not in seen:
                seen.add(post.id)
                ordered.append(post)

        return Response(BlogPostListSerializer(ordered, many=True).data)