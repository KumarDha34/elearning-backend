import logging
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .models import BlogCategory, BlogPost, BlogComment, BlogLike, TeacherFollow
from .permissions import CanWriteBlog, CanModerateBlog
from .serializers import (
    BlogCategorySerializer,
    BlogCategoryWriteSerializer,
    BlogPostListSerializer,
    BlogPostDetailSerializer,
    BlogPostWriteSerializer,
    BlogPostStatusSerializer,
    BlogCommentSerializer,
    BlogCommentWriteSerializer,
)
from .cache_service import increment_like_count,decrement_like_count,get_like_count,get_view_count,increment_view_count
logger = logging.getLogger(__name__)


def _mask(phone):
    return f"{phone[:2]}******{phone[-2:]}" if phone else ""


# ============================================================================
# CATEGORIES (2 endpoints)
# ============================================================================

class BlogCategoryListCreateView(APIView):
    """
    GET  /categories/  → list (anyone)
    POST /categories/  → create (instructor/editor/admin)
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
        summary="Create Blog Category",
        operation_id="blog_categories_create",
        request=BlogCategoryWriteSerializer,
        responses={201: BlogCategorySerializer},
    )
    def post(self, request):
        if not CanModerateBlog().has_permission(request, self):
            return Response(
                {'error': 'Only editors or admins can create categories.'}, 
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = BlogCategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        logger.info(f"Category created by {_mask(request.user.phone_number)}: {category.name}")
        return Response(
            BlogCategorySerializer(category).data,
            status=status.HTTP_201_CREATED,
        )


class BlogCategoryDetailView(APIView):
    """
    GET    /categories/{id}/  → detail (anyone)
    PATCH  /categories/{id}/  → update (instructor/editor/admin)
    DELETE /categories/{id}/  → delete (instructor/editor/admin)
    """
    serializer_class = BlogCategorySerializer

    def get_object(self, pk):
        return get_object_or_404(BlogCategory, pk=pk)

    def get(self, request, pk):
        cat = self.get_object(pk)
        return Response(BlogCategorySerializer(cat).data)

    def patch(self, request, pk):
        if not CanModerateBlog().has_permission(request, self):
            return Response({'error': 'Only editors or admins can update categories.'}, status=status.HTTP_403_FORBIDDEN)
        cat = self.get_object(pk)
        serializer = BlogCategoryWriteSerializer(cat, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BlogCategorySerializer(cat).data)

    def delete(self, request, pk):
        if not CanModerateBlog().has_permission(request, self):
            return Response({'error': 'Only editors or admins can delete categories.'}, status=status.HTTP_403_FORBIDDEN)
        cat = self.get_object(pk)
        cat.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# POSTS — LIST / CREATE (1 endpoint, 2 methods)
# ============================================================================

class BlogPostListCreateView(APIView):
    """
    GET  /posts/  → list (public, or ?mine=1, or ?status=pending for moderators)
    POST /posts/  → create (instructor/editor/admin)
    """
    serializer_class = BlogPostListSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="List Blog Posts",
        operation_id="blog_posts_list",
        description=(
            "Public list of published posts. Use filters:\n"
            "- `?mine=1` → your own posts (auth required)\n"
            "- `?status=pending` → pending posts (moderator only)\n"
            "- `?all=1` → view all posts (Admin/Editor only)\n"
            "- `?category=news` → filter by category slug\n"
            "- `?tag=physics` → filter by tag\n"
            "- `?search=newton` → search by title or content"
        ),
        parameters=[
            OpenApiParameter('mine', OpenApiTypes.INT, description='1 = my posts'),
            OpenApiParameter('status', OpenApiTypes.STR, description='draft|pending|published|rejected'),
            OpenApiParameter('all', OpenApiTypes.INT, description='1 = view all posts (Admin/Editor only)'), 
            OpenApiParameter('category', OpenApiTypes.STR, description='Category slug'),
            OpenApiParameter('tag', OpenApiTypes.STR, description='Tag'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Search by title or content'),
        ],
        responses={200: BlogPostListSerializer(many=True)},
    )
    def get(self, request):
        qs = (
            BlogPost.objects
            .select_related('uploaded_by', 'category')
        )

        # ── Status Filtering Logic ──
        status_param = request.query_params.get('status')
        show_all = request.query_params.get('all') == '1'
        is_moderator = CanModerateBlog().has_permission(request, self)
        is_admin = request.user.is_authenticated and request.user.is_admin

        if show_all:
            # Admin sees EVERYTHING. Editor sees everything EXCEPT drafts.
            if not is_moderator:
                return Response(
                    {'error': 'Only editors or admins can view all posts.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if is_admin:
                # Admin: no status filter
                pass
            else:
                # Editor: exclude drafts
                qs = qs.exclude(status=BlogPost.Status.DRAFT)

        elif status_param:
            if status_param == 'pending':
                if not is_moderator:
                    return Response(
                        {'error': 'Only moderators can view pending posts.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            qs = qs.filter(status=status_param)

        else:
            # Default: public sees only published
            qs = qs.filter(status=BlogPost.Status.PUBLISHED)

        # My posts filter
        if request.query_params.get('mine') == '1':
            if not request.user.is_authenticated:
                return Response({'error': 'Login required.'}, status=status.HTTP_401_UNAUTHORIZED)
            qs = qs.filter(uploaded_by=request.user)

        # Category / tag
        if cat := request.query_params.get('category'):
            qs = qs.filter(category__slug=cat)
        if tag := request.query_params.get('tag'):
            qs = qs.filter(tags__contains=[tag])

        search_query = request.query_params.get('search')
        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(content__icontains=search_query)
            )

        qs = qs.order_by('-published_at', '-created_at')
        return Response(BlogPostListSerializer(qs, many=True).data)

    @extend_schema(
        summary="Create Blog Post",
        operation_id="blog_posts_create",
        request=BlogPostWriteSerializer,
        responses={201: BlogPostListSerializer},
    )
    def post(self, request):
        if not CanWriteBlog().has_permission(request, self):
            return Response(
                {'error': 'Only instructors, editors, or admins can write blog posts.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = BlogPostWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = serializer.save(uploaded_by=request.user)
        logger.info(f"Post created by {_mask(request.user.phone_number)}: {post.title}")
        return Response(
            BlogPostListSerializer(post).data,
            status=status.HTTP_201_CREATED,
        )


# ============================================================================
# POSTS — DETAIL (1 endpoint)
# ============================================================================

class BlogPostDetailView(APIView):
    """
    GET /posts/{slug}/  → published post with inline comments + is_liked
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
                        .annotate(_replies_count=Count('replies', filter=Q(replies__is_active=True))),
                    to_attr='_prefetched_comments',
                )
            )
        )
        post = get_object_or_404(qs, slug=slug)
        increment_view_count(post.pk)
        post.views = get_view_count(post.pk)
        post.likes_count = get_like_count(post.pk)

        # ── is_liked flag ──
        if request.user.is_authenticated:
            post._is_liked = post.likes.filter(user=request.user).exists()
        else:
            post._is_liked = False

        return Response(BlogPostDetailSerializer(post, context={'request': request}).data)


# ============================================================================
# POSTS — UPDATE / DELETE (2 endpoints)
# ============================================================================

class BlogPostUpdateView(APIView):
    """
    PATCH /posts/{id}/  → edit content OR change status

    Status transitions:
    - Author: {status: "pending"} → submit for review (only from draft/rejected)
    - Moderator: {status: "published"} → approve
    - Moderator: {status: "rejected", rejection_reason: "..."} → reject
    - Author: {title: "...", content: "..."} → edit (only draft/pending)
    """
    permission_classes = [IsAuthenticated, CanWriteBlog]
    serializer_class = BlogPostWriteSerializer

    @extend_schema(
        summary="Update Blog Post or Change Status",
        operation_id="blog_posts_update",
        description="Send {status: 'pending'} to submit, or {status: 'published'/'rejected'} to moderate, or partial fields to edit.",
        request=BlogPostWriteSerializer,
        responses={200: BlogPostListSerializer},
    )
    def patch(self, request, pk):
        if not request.data:
            return Response(
                {'error': 'Request body cannot be empty. Provide fields to edit or a status to change.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        post = get_object_or_404(BlogPost, pk=pk)
        is_author = post.uploaded_by == request.user
        is_moderator = request.user.is_editor or request.user.is_admin

        # Handle status change
        if 'status' in request.data:
            status_serializer = BlogPostStatusSerializer(data=request.data)
            status_serializer.is_valid(raise_exception=True)
            new_status = status_serializer.validated_data['status']

            # Author submits
            if new_status == 'pending':
                if not is_author:
                    return Response({'error': 'Only the author can submit.'}, status=status.HTTP_403_FORBIDDEN)
                if post.status not in (BlogPost.Status.DRAFT, BlogPost.Status.REJECTED):
                    return Response(
                        {'error': f'Cannot submit from "{post.status}" status.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                post.status = BlogPost.Status.PENDING
                post.rejection_reason = ''
                post.rejected_by = None
                post.rejected_at = None
                post.save()
                return Response({'message': 'Submitted for review.'})

            # Moderator approves/rejects
            if new_status in ('published', 'rejected'):
                if not is_moderator:
                    return Response({'error': 'Only moderators can approve/reject.'}, status=status.HTTP_403_FORBIDDEN)
                if post.status != BlogPost.Status.PENDING:
                    return Response(
                        {'error': f'Cannot moderate a post in "{post.status}" status.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if new_status == 'published':
                    post.status = BlogPost.Status.PUBLISHED
                    post.published_at = timezone.now()
                    logger.info(f"Post approved by {_mask(request.user.phone_number)}: {post.title}")
                else:
                    post.status = BlogPost.Status.REJECTED
                    post.rejection_reason = status_serializer.validated_data.get('rejection_reason', '')
                    post.rejected_by = request.user
                    post.rejected_at = timezone.now()
                post.save()
                return Response({'message': f'Post {new_status}.'})

        # Otherwise: edit content
        if not (is_author or is_moderator):
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        if post.status == BlogPost.Status.PUBLISHED:
            return Response({'error': 'Cannot edit a published post.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = BlogPostWriteSerializer(post, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BlogPostListSerializer(post).data)


class BlogPostDeleteView(APIView):
    """
    DELETE /posts/{id}/  → delete (author or admin)
    """
    permission_classes = [IsAuthenticated, CanWriteBlog]

    def delete(self, request, pk):
        post = get_object_or_404(BlogPost, pk=pk)
        if post.uploaded_by != request.user and not request.user.is_admin:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# POSTS — LIKE (1 endpoint)
# ============================================================================

class ToggleBlogLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        post = get_object_or_404(BlogPost, pk=pk, status=BlogPost.Status.PUBLISHED)

        like, created = BlogLike.objects.get_or_create(post=post, user=request.user)

        if created:
            BlogPost.objects.filter(pk=post.pk).update(
                likes_count=post.likes_count + 1
            )
            new_count = increment_like_count(post.pk)
            return Response({'liked': True, 'likes_count': new_count})

        like.delete()

        new_db_count = max(0, post.likes_count - 1)
        BlogPost.objects.filter(pk=post.pk).update(
            likes_count=new_db_count
        )
        new_count = decrement_like_count(post.pk)
        return Response({'liked': False, 'likes_count': new_count})

class MyLikedPostsView(APIView):
    """
    GET /my-liked-posts/  → list of posts the current user has liked

    YouTube-style 'Liked Videos' page for the profile.
    Ordered by most recently liked first.

    Data source: PostgreSQL (blog_likes table) — NOT cached because
    it's personalized per user. Redis cache would have ~0% hit rate
    and cause memory bloat. This is exactly how YouTube, Twitter,
    and Instagram handle their "Liked" pages.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = BlogPostListSerializer

    @extend_schema(
        summary="Get My Liked Posts",
        operation_id="blog_my_liked_posts",
        description=(
            "Returns all blog posts the current user has liked, ordered by "
            "most recently liked first. Like YouTube's 'Liked Videos' page."
        ),
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

        # Refresh like counts from cache
        posts_data = []
        for post in liked_posts:
            post.likes_count = get_like_count(post.pk)
            posts_data.append(BlogPostListSerializer(post).data)

        return Response(posts_data)
# ============================================================================
# COMMENTS — CREATE (1 endpoint, list is inline in detail)
# ============================================================================

class BlogCommentCreateView(APIView):
    """
    POST /posts/{id}/comments/  → add comment
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

        # Update comment count atomically
        count = BlogComment.objects.filter(post=post, is_active=True).count()
        BlogPost.objects.filter(pk=post.pk).update(comments_count=count)

        return Response(
            BlogCommentSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )


# ============================================================================
# FOLLOW (1 endpoint — POST follow, DELETE unfollow)
# ============================================================================

class TeacherFollowView(APIView):
    """
    POST   /teachers/{id}/follow/  → follow (student only)
    DELETE /teachers/{id}/follow/  → unfollow
    """
    permission_classes = [IsAuthenticated]

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
            return Response({'error': 'Teacher not found.'}, status=status.HTTP_404_NOT_FOUND)

        follow, created = TeacherFollow.objects.get_or_create(
            student=request.user,
            teacher=teacher,
        )

        return Response({
            'message': 'Now following.' if created else 'Already following.',
            'following': True,
        })

    def delete(self, request, pk):
        if not request.user.is_student:
            return Response({'error': 'Only students can unfollow.'}, status=status.HTTP_403_FORBIDDEN)

        deleted, _ = TeacherFollow.objects.filter(student=request.user, teacher_id=pk).delete()
        return Response({'message': 'Unfollowed.', 'following': False, 'deleted': deleted})


# ============================================================================
# FEED (1 endpoint — optimized with a single query)
# ============================================================================

class FeedView(APIView):
    """
    GET /feed/  → personalized feed

    Priority order:
    1. Followed teachers' posts (newest first)
    2. Same-faculty teachers (excluding followed)
    3. Trending posts (last 7 days, sorted by likes then views)
    4. Latest published posts (excluding the above)
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

        # Base: published posts, all fields needed
        base = BlogPost.objects.filter(
            status=BlogPost.Status.PUBLISHED
        ).select_related('uploaded_by', 'category')

        # IDs already used
        seen = set()
        ordered = []

        # 1. Followed teachers
        followed_ids = list(
            TeacherFollow.objects.filter(student=user).values_list('teacher_id', flat=True)
        )
        if followed_ids:
            qs = base.filter(uploaded_by_id__in=followed_ids).order_by('-published_at')[:50]
            for post in qs:
                if post.id not in seen:
                    seen.add(post.id)
                    ordered.append(post)

        # 2. Same faculty
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

        # 3. Trending (last 7 days)
        cutoff = timezone.now() - timedelta(days=7)
        qs = base.filter(published_at__gte=cutoff).order_by('-likes_count', '-views')[:50]
        for post in qs:
            if post.id not in seen:
                seen.add(post.id)
                ordered.append(post)

        # 4. Latest fallback
        qs = base.exclude(id__in=seen).order_by('-published_at')[:50]
        for post in qs:
            if post.id not in seen:
                seen.add(post.id)
                ordered.append(post)

        return Response(BlogPostListSerializer(ordered, many=True).data)