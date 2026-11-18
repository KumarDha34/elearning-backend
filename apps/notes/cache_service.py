
import logging

from django.core.cache import cache
from django.db.models import F

from .models import Note

logger = logging.getLogger(__name__)

VIEW_COUNT_KEY = "note:views_count:{note_id}"
VIEW_COUNT_TTL = 3600


def increment_view_count(note_id: int) -> int:
    """
    Increment note views atomically in the database
    and update the Redis cache.
    """

    updated = Note.objects.filter(pk=note_id).update(
        views=F("views") + 1
    )

    if not updated:
        return 0

    db_count = (
        Note.objects.filter(pk=note_id)
        .values_list("views", flat=True)
        .first()
    )

    key = VIEW_COUNT_KEY.format(note_id=note_id)

    try:
        cache.set(key, db_count, timeout=VIEW_COUNT_TTL)
    except Exception as e:
        logger.warning(
            "Redis SET failed for note %s: %s",
            note_id,
            e
        )

    return db_count


def get_view_count(note_id: int) -> int:
    """
    Retrieve note views from Redis.
    Fall back to the database if cache is missing.
    """

    key = VIEW_COUNT_KEY.format(note_id=note_id)

    try:
        cached = cache.get(key)

        if cached is not None:
            return int(cached)

    except Exception as e:
        logger.warning(
            "Redis GET failed for note %s: %s",
            note_id,
            e
        )

    db_count = (
        Note.objects.filter(pk=note_id)
        .values_list("views", flat=True)
        .first()
    )

    if db_count is None:
        return 0

    try:
        cache.set(key, db_count, timeout=VIEW_COUNT_TTL)
    except Exception as e:
        logger.warning(
            "Redis cache population failed for note %s: %s",
            note_id,
            e
        )

    return db_count
