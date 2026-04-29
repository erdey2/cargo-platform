from django.urls import path
from .views import CreateRatingView, RatingListView, DriverRatingView

urlpatterns = [
    path("", RatingListView.as_view()),
    path("create/", CreateRatingView.as_view()),
    path("driver/", DriverRatingView.as_view()),
]