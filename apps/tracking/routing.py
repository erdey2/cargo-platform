from django.urls import path
from .consumers import DriverLocationConsumer

websocket_urlpatterns = [
    path("ws/shipment/<int:shipment_id>/", DriverLocationConsumer.as_asgi()),
]