from django.urls import path
from .views import DriverRegistrationView

urlpatterns = [
    path("register/", DriverRegistrationView.as_view(), name="driver-register"),
]