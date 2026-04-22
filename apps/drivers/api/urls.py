from rest_framework.routers import DefaultRouter
from .views import DriverShipmentViewSet

router = DefaultRouter()
router.register(r"driver/shipments", DriverShipmentViewSet, basename="driver-shipments")

urlpatterns = router.urls