from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AdminDashboardView,
    AdminUserViewSet,
    AdminDriverViewSet,
    AdminVehicleViewSet,
    AdminShipmentViewSet,
    AdminAssignmentViewSet,
    AdminTransactionViewSet,
    AdminPricingRuleViewSet,
    AdminRatingViewSet,
    AdminNotificationViewSet,
    AdminLocationViewSet,
    AdminCargoTypeViewSet,
    AdminAuditLogViewSet,
    AdminDisputeViewSet,
)

router = DefaultRouter()
router.register("users", AdminUserViewSet, basename="admin-users")
router.register("drivers", AdminDriverViewSet, basename="admin-drivers")
router.register("vehicles", AdminVehicleViewSet, basename="admin-vehicles")
router.register("shipments", AdminShipmentViewSet, basename="admin-shipments")
router.register("assignments", AdminAssignmentViewSet, basename="admin-assignments")
router.register("transactions", AdminTransactionViewSet, basename="admin-transactions")
router.register("pricing-rules", AdminPricingRuleViewSet, basename="admin-pricing-rules")
router.register("ratings", AdminRatingViewSet, basename="admin-ratings")
router.register("notifications", AdminNotificationViewSet, basename="admin-notifications")
router.register("locations", AdminLocationViewSet, basename="admin-locations")
router.register("cargo-types", AdminCargoTypeViewSet, basename="admin-cargo-types")
router.register("logs", AdminAuditLogViewSet, basename="admin-logs")
router.register("disputes", AdminDisputeViewSet, basename="admin-disputes")

urlpatterns = [
    path("dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("", include(router.urls)),
]
