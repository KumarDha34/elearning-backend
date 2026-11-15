# apps/blog/cache_service.py

from django.core.cache import cache
from .models import BlogPost


# ── Configuration ──
LIKE_COUNT_KEY = 'blog:likes_count:{post_id}'
LIKE_COUNT_TTL = 300    # 5 minutes


def get_like_count(post_id: int) -> int:
    """
    Read like count for a post.

    Strategy:
        1. Try Redis (fast path, ~0.2ms)
        2. On cache miss, load from PostgreSQL, cache it, return

    Args:
        post_id: The post's primary key

    Returns:
        The current likes_count
    """
    key = LIKE_COUNT_KEY.format(post_id=post_id)
    count = cache.get(key)

    if count is not None:
        return count  

    count = (
        BlogPost.objects
        .filter(pk=post_id)
        .values_list('likes_count', flat=True)
        .first()
    ) or 0

    cache.set(key, count, timeout=LIKE_COUNT_TTL)
    return count


def increment_like_count(post_id: int) -> int:
    """
    Atomically increment cached count (on like).

    Returns:
        New count after increment
    """
    key = LIKE_COUNT_KEY.format(post_id=post_id)

    try:
        return cache.incr(key, 1)
    except ValueError:
        current = get_like_count(post_id)
        new_val = current + 1
        cache.set(key, new_val, timeout=LIKE_COUNT_TTL)
        return new_val


def decrement_like_count(post_id: int) -> int:
    """
    Atomically decrement cached count (on unlike).

    Never goes below 0 (guards against drift).
    """
    key = LIKE_COUNT_KEY.format(post_id=post_id)

    try:
        new_val = cache.decr(key, 1)
        if new_val < 0:
            cache.set(key, 0, timeout=LIKE_COUNT_TTL)
            return 0
        return new_val
    except ValueError:
        current = get_like_count(post_id)
        new_val = max(0, current - 1)
        cache.set(key, new_val, timeout=LIKE_COUNT_TTL)
        return new_val


def invalidate_like_count(post_id: int) -> None:
    """
    Delete cache entry so next read fetches fresh DB value.

    Use cases:
        - After background sync corrects the DB
        - When debugging drift
        - Manual admin actions
    """
    cache.delete(LIKE_COUNT_KEY.format(post_id=post_id))