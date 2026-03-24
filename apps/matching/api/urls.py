from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MatchDriversView, DriverResponseView, DriverOfferViewSet

router = DefaultRouter()
router.register(r"offers", DriverOfferViewSet, basename="driver-offers")

urlpatterns = [
    path("shipments/<int:shipment_id>/match/", MatchDriversView.as_view(), name="match-drivers"),
    path("offers/<int:offer_id>/respond/", DriverResponseView.as_view(), name="driver-respond"),
]

urlpatterns += router.urls