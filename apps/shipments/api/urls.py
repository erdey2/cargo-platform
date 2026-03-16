from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .views import (
    ShipmentViewSet,
    CargoTypeViewSet,
)

router = DefaultRouter()

router.register("shipments", ShipmentViewSet, basename="shipments")
router.register("cargo-types", CargoTypeViewSet, basename="cargo-types")

urlpatterns = [
    path("", include(router.urls)),
]