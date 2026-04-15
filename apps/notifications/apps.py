from django.apps import AppConfig
import logging
from .firebase import init_firebase

logger = logging.getLogger(__name__)


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"

    def ready(self):
        import apps.notifications.signals
        try:
            init_firebase()
        except Exception as exc:
            # Firebase should not prevent the Django app from booting.
            logger.warning("Firebase initialization skipped: %s", exc)
