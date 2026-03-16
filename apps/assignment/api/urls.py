from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AssignmentViewSet,
    AssignmentStatusUpdateView
)

router = DefaultRouter()
router.register("assignments", AssignmentViewSet, basename="assignments")

urlpatterns = [

    path("", include(router.urls)),

    path(
        "assignments/<int:assignment_id>/status/",
        AssignmentStatusUpdateView.as_view(),
        name="assignment-status-update"
    ),

]