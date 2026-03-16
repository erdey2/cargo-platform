from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VehicleTypeViewSet, VehicleViewSet, VehicleDocumentViewSet

router = DefaultRouter()

router.register("vehicle-types", VehicleTypeViewSet)
router.register("vehicles", VehicleViewSet, basename="vehicles")
router.register("vehicle-documents", VehicleDocumentViewSet, basename="vehicle-documents")

urlpatterns = [
    path("", include(router.urls)),
]