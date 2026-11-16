import logging
from django.core.cache import cache
from django.db.models import F
from .models import BlogPost

logger = logging.getLogger(__name__)

# ── Configuration ──
LIKE_COUNT_KEY = 'blog:likes_count:{post_id}'
LIKE_COUNT_TTL = 300  # 5 minutes
VIEW_COUNT_KEY = 'blog:views_count:{post_id}'


def get_like_count(post_id: int) -> int:
    """Read like count. Falls back to DB if Redis is down."""
    try:
        key = LIKE_COUNT_KEY.format(post_id=post_id)
        count = cache.get(key)
        if count is not None:
            return count
    except Exception as e:
        logger.warning(f"Redis GET failed for likes_count:{post_id}: {e}")

    # Fallback: DB
    count = (
        BlogPost.objects
        .filter(pk=post_id)
        .values_list('likes_count', flat=True)
        .first()
    ) or 0

    try:
        cache.set(LIKE_COUNT_KEY.format(post_id=post_id), count, timeout=LIKE_COUNT_TTL)
    except Exception:
        pass  # Redis still down, ignore
    return count


def increment_like_count(post_id: int) -> int:
    """Atomically increment. Falls back to DB if Redis is down."""
    key = LIKE_COUNT_KEY.format(post_id=post_id)
    try:
        return cache.incr(key, 1)
    except ValueError:
        current = get_like_count(post_id)
        new_val = current + 1
        try:
            cache.set(key, new_val, timeout=LIKE_COUNT_TTL)
        except Exception:
            pass
        return new_val
    except Exception as e:
        logger.warning(f"Redis INCR failed for likes_count:{post_id}: {e}")
        # Fallback: DB
        BlogPost.objects.filter(pk=post_id).update(likes_count=F('likes_count') + 1)
        return BlogPost.objects.filter(pk=post_id).values_list('likes_count', flat=True).first() or 0


def decrement_like_count(post_id: int) -> int:
    """Atomically decrement. Falls back to DB if Redis is down."""
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
        try:
            cache.set(key, new_val, timeout=LIKE_COUNT_TTL)
        except Exception:
            pass
        return new_val
    except Exception as e:
        logger.warning(f"Redis DECR failed for likes_count:{post_id}: {e}")
        # Fallback: DB
        BlogPost.objects.filter(pk=post_id, likes_count__gt=0).update(
            likes_count=F('likes_count') - 1
        )
        return BlogPost.objects.filter(pk=post_id).values_list('likes_count', flat=True).first() or 0


def invalidate_like_count(post_id: int) -> None:
    try:
        cache.delete(LIKE_COUNT_KEY.format(post_id=post_id))
    except Exception:
        pass


def increment_view_count(post_id: int) -> int:
    """Fast view increment. Falls back to DB if Redis is down."""
    key = VIEW_COUNT_KEY.format(post_id=post_id)
    try:
        return cache.incr(key, 1)
    except ValueError:
        current = BlogPost.objects.filter(pk=post_id).values_list('views', flat=True).first() or 0
        new_val = current + 1
        try:
            cache.set(key, new_val, timeout=None)
        except Exception:
            pass
        return new_val
    except Exception as e:
        logger.warning(f"Redis INCR (views) failed for post {post_id}: {e}")
        # Fallback: DB
        BlogPost.objects.filter(pk=post_id).update(views=F('views') + 1)
        return BlogPost.objects.filter(pk=post_id).values_list('views', flat=True).first() or 0


def get_view_count(post_id: int) -> int:
    """Read views. Falls back to DB if Redis is down."""
    key = VIEW_COUNT_KEY.format(post_id=post_id)
    try:
        count = cache.get(key)
        if count is None:
            count = BlogPost.objects.filter(pk=post_id).values_list('views', flat=True).first() or 0
            try:
                cache.set(key, count, timeout=None)
            except Exception:
                pass
        return count
    except Exception as e:
        logger.warning(f"Redis GET (views) failed for post {post_id}: {e}")
        return BlogPost.objects.filter(pk=post_id).values_list('views', flat=True).first() or 0