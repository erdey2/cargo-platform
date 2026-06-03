from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    ShipmentViewSet,
    CargoTypeViewSet,
    ShipmentStatusHistoryViewSet,
    ShipmentProofOfDeliveryViewSet,
    ShipmentPODOTPSendView,
    ShipmentPODOTPVerifyView,
    ShipmentPODOTPResendView,
    twilio_delivery_webhook,
)

router = DefaultRouter()

router.register("shipments", ShipmentViewSet, basename="shipments")
router.register("cargo-types", CargoTypeViewSet, basename="cargo-types")
router.register("shipment-status-history", ShipmentStatusHistoryViewSet, basename="shipment-status-history")
router.register("shipment-proof-of-delivery", ShipmentProofOfDeliveryViewSet, basename="shipment-proof-of-delivery")

urlpatterns = [
    path("", include(router.urls)),
    path("pod-otp/send/", ShipmentPODOTPSendView.as_view(), name="pod-otp-send"),
    path("pod-otp/verify/", ShipmentPODOTPVerifyView.as_view(), name="pod-otp-verify"),
    path("pod-otp/resend/", ShipmentPODOTPResendView.as_view(), name="pod-otp-resend"),
    path("webhooks/twilio/", twilio_delivery_webhook, name="twilio-delivery-webhook"),
]