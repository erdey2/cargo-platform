from django.urls import path
from .views import ProfileView, ProfileListView, CustomerRegistrationView, DriverRegistrationView


urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profiles/", ProfileListView.as_view(), name="profiles"),
    path("register/customer/", CustomerRegistrationView.as_view(), name="customer-register"),
    path("register/driver/", DriverRegistrationView.as_view(), name="driver-register"),
]