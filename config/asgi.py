import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
import apps.tracking.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cargo_platform.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            apps.tracking.routing.websocket_urlpatterns
        )
    ),
})
