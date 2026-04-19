from django.urls import path
from .consumers import DriverLocationConsumer

websocket_urlpatterns = [
    path("ws/shipment/", DriverLocationConsumer.as_asgi()),
]