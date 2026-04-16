from django.urls import path
from .consumers import DriverLocationConsumer

websocket_urlpatterns = [
    path("ws/drivers/", DriverLocationConsumer.as_asgi()),
]