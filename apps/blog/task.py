from celery import shared_task

from .models import BlogPost
from .cache_service import invalidate_like_count


@shared_task
def sync_like_counts():
    """
    Recompute likes_count from blog_likes table.

    Runs every 5 minutes via Celery Beat.
    Fixes any drift between PostgreSQL and Redis.
    """
    posts = BlogPost.objects.filter(
        status=BlogPost.Status.PUBLISHED
    ).only('id', 'likes_count')

    fixed = 0
    for post in posts.iterator(chunk_size=500):
        real_count = post.likes.count()
        if post.likes_count != real_count:
            BlogPost.objects.filter(pk=post.pk).update(
                likes_count=real_count
            )
            invalidate_like_count(post.pk)
            fixed += 1

    return f"Fixed {fixed} posts"