from django.urls import path
from .views import UpdateDriverLocationView, DriverLocationView, NearbyDriversView

urlpatterns = [
    path("driver-location/update/", UpdateDriverLocationView.as_view()),
    path("driver-location/<int:driver_id>/", DriverLocationView.as_view()),
    path("drivers/nearby/", NearbyDriversView.as_view()),
]