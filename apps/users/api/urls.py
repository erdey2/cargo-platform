from django.urls import path
from .views import RegisterView, ProfileView, ProfileListView


urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profiles/", ProfileListView.as_view(), name="profiles"),
]