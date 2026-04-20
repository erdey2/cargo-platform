import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cargo_platform.settings")

django.setup()

from core.middleware import JWTAuthMiddleware
import apps.tracking.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter(
            apps.tracking.routing.websocket_urlpatterns
        )
    ),
})