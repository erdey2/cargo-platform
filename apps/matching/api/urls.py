from rest_framework.routers import DefaultRouter

from .views import MatchDriversView

router = DefaultRouter()
router.register("shipments", ShipmentViewSet, basename="shipments")

urlpatterns = router.urls




path("shipments/<int:shipment_id>/match/", MatchDriversView.as_view())