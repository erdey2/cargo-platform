from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import ShipmentViewSet, CargoTypeViewSet, ShipmentStatusHistoryViewSet

router = DefaultRouter()

router.register("shipments", ShipmentViewSet, basename="shipments")
router.register("cargo-types", CargoTypeViewSet, basename="cargo-types")
router.register("shipment-status-history", ShipmentStatusHistoryViewSet, basename="shipment-status-history")

urlpatterns = [
    path("", include(router.urls)),
]