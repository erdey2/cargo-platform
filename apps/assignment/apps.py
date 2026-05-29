from django.apps import AppConfig


class AssignmentConfig(AppConfig):
    name = 'apps.assignment'
    def ready(self):
        # Import signals to ensure post-save sync between Assignment and Shipment
        from . import signals  # noqa: F401
