from django.urls import path
from apps.rating.api.views import CreateRatingView

urlpatterns = [
	path("ratings/", CreateRatingView.as_view(), name="create-rating"),
]

