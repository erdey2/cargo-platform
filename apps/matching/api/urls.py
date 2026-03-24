from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MatchDriversView, DriverResponseView


router = DefaultRouter()

urlpatterns = [
    path("", include(router.urls)),
    path("shipments/<int:shipment_id>/match/", MatchDriversView.as_view()),
    path("offers/<int:offer_id>/respond/", DriverResponseView.as_view()),
]