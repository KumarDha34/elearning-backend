import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("elearning")

# Read CELERY_* settings from Django settings.py (namespaced by "CELERY_").
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in every installed app (apps.accounts.tasks, etc.).
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
