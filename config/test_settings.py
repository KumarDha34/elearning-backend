"""
Test-only settings: swaps Postgres for SQLite and makes Celery run tasks
synchronously (in-process) so the full test suite runs with zero external
services. Use with: DJANGO_SETTINGS_MODULE=config.test_settings pytest
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

SMS_PRIMARY_PROVIDER = "console"
SMS_FALLBACK_PROVIDER = "none"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast hashing for tests
