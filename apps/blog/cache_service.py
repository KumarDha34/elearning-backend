import logging
from django.core.cache import cache
from django.db.models import F
from .models import BlogPost, BlogLike

logger = logging.getLogger(__name__)

# ── Configuration ──
LIKE_COUNT_KEY = 'blog:likes_count:{post_id}'
LIKE_COUNT_TTL = 300  # 5 minutes
VIEW_COUNT_KEY = 'blog:views_count:{post_id}'


# ============================================================================
# LIKE COUNT
# ============================================================================

def get_like_count(post_id: int) -> int:
    """
    Read like count.

    Source of truth: DB `BlogPost.likes_count` (kept in sync with BlogLike table).
    Redis is just a read cache. If Redis is down, read from DB.
    """
    key = LIKE_COUNT_KEY.format(post_id=post_id)

    try:
        cached = cache.get(key)
        if cached is not None:
            return int(cached)
    except Exception as e:
        logger.warning(f"Redis GET failed for likes_count:{post_id}: {e}")

    # Fallback: DB
    db_count = (
        BlogPost.objects
        .filter(pk=post_id)
        .values_list('likes_count', flat=True)
        .first()
    ) or 0

    try:
        cache.set(key, db_count, timeout=LIKE_COUNT_TTL)
    except Exception:
        pass

    return db_count


def increment_like_count(post_id: int) -> int:
    """
    Increment like count.

    1. Atomically increment DB (source of truth).
    2. Sync Redis cache with the new DB value.
    3. Return the new DB value.
    """
    # Step 1: DB increment (atomic)
    BlogPost.objects.filter(pk=post_id).update(likes_count=F('likes_count') + 1)

    # Step 2: Read the new DB value
    db_count = (
        BlogPost.objects
        .filter(pk=post_id)
        .values_list('likes_count', flat=True)
        .first()
    ) or 0

    # Step 3: Sync Redis cache
    try:
        cache.set(LIKE_COUNT_KEY.format(post_id=post_id), db_count, timeout=LIKE_COUNT_TTL)
    except Exception as e:
        logger.warning(f"Redis SET failed for likes_count:{post_id}: {e}")

    return db_count


def decrement_like_count(post_id: int) -> int:
    """
    Decrement like count.

    1. Atomically decrement DB (guard against negative).
    2. Sync Redis cache with the new DB value.
    3. Return the new DB value.
    """
    # Step 1: DB decrement (atomic, guarded)
    BlogPost.objects.filter(pk=post_id, likes_count__gt=0).update(
        likes_count=F('likes_count') - 1
    )

    # Step 2: Read the new DB value
    db_count = (
        BlogPost.objects
        .filter(pk=post_id)
        .values_list('likes_count', flat=True)
        .first()
    ) or 0

    # Step 3: Sync Redis cache
    try:
        cache.set(LIKE_COUNT_KEY.format(post_id=post_id), db_count, timeout=LIKE_COUNT_TTL)
    except Exception as e:
        logger.warning(f"Redis SET failed for likes_count:{post_id}: {e}")

    return db_count


def invalidate_like_count(post_id: int) -> None:
    """Delete the cached like count. Next read will fetch from DB."""
    try:
        cache.delete(LIKE_COUNT_KEY.format(post_id=post_id))
    except Exception:
        pass


# ============================================================================
# VIEW COUNT
# ============================================================================

def increment_view_count(post_id: int) -> int:
    """
    Increment view count.

    Same pattern as likes: DB is source of truth, Redis is cache.
    """
    # Step 1: DB increment
    BlogPost.objects.filter(pk=post_id).update(views=F('views') + 1)

    # Step 2: Read the new DB value
    db_count = (
        BlogPost.objects
        .filter(pk=post_id)
        .values_list('views', flat=True)
        .first()
    ) or 0

    # Step 3: Sync Redis
    try:
        cache.set(VIEW_COUNT_KEY.format(post_id=post_id), db_count, timeout=None)
    except Exception as e:
        logger.warning(f"Redis SET failed for views:{post_id}: {e}")

    return db_count


def get_view_count(post_id: int) -> int:
    """Read view count. Redis cache first, DB fallback."""
    key = VIEW_COUNT_KEY.format(post_id=post_id)

    try:
        cached = cache.get(key)
        if cached is not None:
            return int(cached)
    except Exception as e:
        logger.warning(f"Redis GET failed for views:{post_id}: {e}")

    db_count = (
        BlogPost.objects
        .filter(pk=post_id)
        .values_list('views', flat=True)
        .first()
    ) or 0

    try:
        cache.set(key, db_count, timeout=None)
    except Exception:
        pass

    return db_count