import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# NOTE: plain ASGI for now. Once Django Channels is introduced for
# /ws/notifications/ and /ws/live-class/{id}/, this file will wrap
# application with ProtocolTypeRouter as described in the design document.
application = get_asgi_application()
