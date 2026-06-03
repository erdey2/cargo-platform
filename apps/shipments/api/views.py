import hashlib
import math

from django.contrib.gis.geos import Point
from django.db.models import Q, F
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, status as http_status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.decorators import action
from ..models import Shipment, CargoType, ShipmentStatusHistory, ShipmentProofOfDelivery, ShipmentPODOTP
from .serializers import (
    ShipmentSerializer,
    CargoTypeSerializer,
    ShipmentStatusHistorySerializer,
    ShipmentProofOfDeliverySerializer,
    ShipmentProofOfDeliveryUploadSerializer,
    ShipmentProofOfDeliveryConfirmSerializer,
    ShipmentPODOTPSendSerializer,
    ShipmentPODOTPVerifySerializer,
    ShipmentPODOTPResendSerializer,
)
from rest_framework.views import APIView
from apps.shipments.services.otp_service import (
    create_and_send_otp,
    default_otp_resend_max,
    default_otp_resend_delay_seconds,
)
from apps.shipments.services.notification_service import send_otp_resend_notification, send_otp_exhausted_notification
from apps.pricing.services.pricing_service import PriceCalculator
from core.permissions import IsAdminOrReadOnly
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiExample
from apps.matching.tasks import start_driver_matching
from django.contrib.auth import get_user_model

User = get_user_model()
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from apps.shipments.services.twilio_webhook import validate_twilio_signature, process_twilio_delivery_webhook

@extend_schema(
    tags=["Shipments"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List shipments",
        description=(
            "Retrieve shipments.\n\n"
            "- Admins: see all shipments\n"
            "- Customers: see only their own shipments"
        ),
        responses={200: ShipmentSerializer(many=True)},
    ),

    create=extend_schema(
        summary="Create shipment",
        description=(
            "Create a new shipment.\n\n"
            "System automatically:\n"
            "- Assigns current user as customer\n"
            "- Sets status to `matching`\n"
            "- Calculates estimated price\n"
            "- Creates status history\n"
            "- Triggers driver matching"
        ),
        examples=[
            OpenApiExample(
                "Shipment Request Example",
                value={
                    "pickup_address": "Bole, Addis Ababa",
                    "dropoff_address": "Piassa, Addis Ababa",
                    "pickup_lat": 9.03,
                    "pickup_lng": 38.74,
                    "dropoff_lat": 9.05,
                    "dropoff_lng": 38.76,
                    "weight": 50,
                    "volume": 2.5,
                    "cargo_type": 1,
                    "description": "Electronics",
                    "recipient_name": "Abel Tesfaye",
                    "recipient_phone": "+251912345678",
                    "recipient_alternate_phone": "+251987654321"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Shipment Response Example",
                value={
                    "id": 1,
                    "customer": 5,
                    "pickup_address": "Bole, Addis Ababa",
                    "dropoff_address": "Piassa, Addis Ababa",
                    "pickup_latitude": 9.03,
                    "pickup_longitude": 38.74,
                    "dropoff_latitude": 9.05,
                    "dropoff_longitude": 38.76,
                    "weight": 50,
                    "volume": 2.5,
                    "cargo_type": 1,
                    "description": "Electronics",
                    "status": "matching",
                    "estimated_price": "1500.00",
                    "final_price": None,
                    "assigned_at": None,
                    "picked_up_at": None,
                    "delivered_at": None,
                    "created_at": "2026-03-23T10:00:00Z"
                },
                response_only=True,
            ),
        ],
        responses={201: ShipmentSerializer},
    ),

    retrieve=extend_schema(
        summary="Retrieve shipment",
        description="Get detailed information about a specific shipment.",
        responses={200: ShipmentSerializer},
    ),

    update=extend_schema(
        summary="Update shipment",
        description="Update shipment details (only allowed before assignment).",
        request=ShipmentSerializer,
        responses={200: ShipmentSerializer},
    ),

    partial_update=extend_schema(
        summary="Partially update shipment",
        description="Update specific fields of a shipment.",
        request=ShipmentSerializer,
        responses={200: ShipmentSerializer},
    ),

    destroy=extend_schema(
        summary="Delete shipment",
        description=(
            "Cancel a shipment by setting status to `cancelled`.\n\n"
            "- Customers: only allowed when status is `created` or `matching`\n"
            "- Admins: allowed to cancel from this endpoint"
        ),
        responses={204: None},
    ),
)
class ShipmentViewSet(viewsets.ModelViewSet):
    serializer_class = ShipmentSerializer
    permission_classes = [IsAuthenticated]

    CUSTOMER_CANCELLABLE_STATUSES = {"created", "matching"}

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Shipment.objects.all()

        return Shipment.objects.filter(customer=user)

    def perform_create(self, serializer):
        shipment_status = "matching"
        shipment = serializer.save(
            customer=self.request.user,
            status=shipment_status
        )

        try:
            shipment.estimated_price = PriceCalculator.calculate_estimated_price(shipment)
            shipment.save()
        except Exception:
            raise ValidationError("Failed to calculate price")

        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            status=shipment_status,
            changed_by=self.request.user
        )
        start_driver_matching.delay(shipment.pk)

        # MatchingService.match_driver(shipment)

    def destroy(self, request, *args, **kwargs):
        shipment = self.get_object()

        if shipment.status == "cancelled":
            return Response(
                {"detail": "Shipment already cancelled."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.is_staff and shipment.status not in self.CUSTOMER_CANCELLABLE_STATUSES:
            return Response(
                {"detail": "Customers can cancel only when shipment is in created or matching status."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        cancelled_by = "admin" if request.user.is_staff else "customer"
        shipment.status = "cancelled"
        shipment.save(update_fields=["status", "updated_at"])

        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            status="cancelled",
            changed_by=request.user,
            notes=f"Cancelled by {cancelled_by}",
        )

        return Response(status=http_status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="proof-of-delivery")
    def proof_of_delivery(self, request, pk=None):
        shipment = self.get_object()
        serializer = ShipmentProofOfDeliverySerializer(
            shipment.proofs_of_delivery.all(),
            many=True,
            context={"request": request},
        )
        return Response(serializer.data, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["Shipment Proof of Delivery"],
)
@extend_schema_view(
    create=extend_schema(
        summary="Upload proof of delivery photo",
        description=(
            "Upload a delivery photo and receive verification metadata. "
            "The endpoint computes SHA-256, checks GPS distance against the shipment dropoff, and flags duplicates."
        ),
        request=ShipmentProofOfDeliveryUploadSerializer,
        responses={201: ShipmentProofOfDeliverySerializer},
    ),
    list=extend_schema(
        summary="List proof of delivery records for a shipment",
        responses={200: ShipmentProofOfDeliverySerializer(many=True)},
    ),
)
class ShipmentProofOfDeliveryViewSet(viewsets.ModelViewSet):
    serializer_class = ShipmentProofOfDeliverySerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        shipment_id = self.kwargs.get("shipment_pk") or self.request.query_params.get("shipment_id")
        if not shipment_id:
            raise ValidationError("shipment_id query param or shipment_pk is required")

        queryset = ShipmentProofOfDelivery.objects.filter(shipment_id=shipment_id)
        user = self.request.user
        if user.is_staff:
            return queryset
        return queryset.filter(Q(shipment__customer=user) | Q(shipment__driver__user=user))

    def _get_shipment(self):
        shipment_id = self.request.data.get("shipment") or self.kwargs.get("shipment_pk") or self.request.query_params.get("shipment_id")
        if not shipment_id:
            raise ValidationError({"shipment": "shipment is required"})

        try:
            shipment = Shipment.objects.get(pk=shipment_id)
        except Shipment.DoesNotExist:
            raise ValidationError({"shipment": "Shipment not found"})

        if not self.request.user.is_staff:
            is_customer = shipment.customer_id == self.request.user.pk
            is_driver = getattr(shipment.driver, "user_id", None) == self.request.user.pk
            if not (is_customer or is_driver):
                raise ValidationError({"shipment": "You do not have permission to upload POD for this shipment"})

        return shipment

    def _confirm_from_payload(self, pod):
        confirmation_method = self.request.data.get("confirmation_method")
        customer_confirmed = str(self.request.data.get("customer_confirmed", "")).lower() in {"1", "true", "yes", "on"}

        if customer_confirmed or confirmation_method:
            pod.customer_confirmed = True
            pod.customer_confirmed_at = timezone.now()
            pod.customer_confirmation_method = confirmation_method or "in_app"

        return pod

    def _gps_to_point(self, gps_latitude, gps_longitude):
        if gps_latitude is None or gps_longitude is None:
            return None
        if not (-90 <= gps_latitude <= 90 and -180 <= gps_longitude <= 180):
            raise ValidationError({"gps": "Invalid GPS coordinates"})
        return Point(gps_longitude, gps_latitude, srid=4326)

    def _distance_meters(self, point_a, point_b):
        if not point_a or not point_b:
            return None
        # Haversine distance in meters for a lightweight POC check.
        lat1 = math.radians(point_a.y)
        lon1 = math.radians(point_a.x)
        lat2 = math.radians(point_b.y)
        lon2 = math.radians(point_b.x)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return 6371000 * c

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        shipment = self._get_shipment()
        upload_serializer = ShipmentProofOfDeliveryUploadSerializer(data=request.data)
        upload_serializer.is_valid(raise_exception=True)

        photo = upload_serializer.validated_data["photo"]
        gps_latitude = upload_serializer.validated_data.get("gps_latitude")
        gps_longitude = upload_serializer.validated_data.get("gps_longitude")
        gps_accuracy_meters = upload_serializer.validated_data.get("gps_accuracy_meters")

        file_bytes = photo.read()
        photo.seek(0)
        image_sha256 = hashlib.sha256(file_bytes).hexdigest()

        gps_point = self._gps_to_point(gps_latitude, gps_longitude)

        duplicate = ShipmentProofOfDelivery.objects.filter(image_sha256=image_sha256).order_by("created_at").first()
        is_duplicate = duplicate is not None

        dropoff_point = shipment.dropoff_location
        gps_distance_to_dropoff_meters = None
        gps_verified = False
        notes = []

        if gps_point and dropoff_point:
            gps_distance_to_dropoff_meters = self._distance_meters(gps_point, dropoff_point)
            gps_verified = gps_distance_to_dropoff_meters <= 500
            notes.append(
                f"GPS distance to dropoff: {gps_distance_to_dropoff_meters:.2f}m (verified={gps_verified})"
            )
        else:
            notes.append("GPS metadata missing or dropoff location unavailable")

        if is_duplicate:
            notes.append(f"Duplicate image detected from POD #{duplicate.id}")

        pod = ShipmentProofOfDelivery.objects.create(
            shipment=shipment,
            uploaded_by=request.user,
            photo=photo,
            image_sha256=image_sha256,
            gps_location=gps_point,
            gps_accuracy_meters=gps_accuracy_meters,
            gps_verified=gps_verified,
            gps_distance_to_dropoff_meters=gps_distance_to_dropoff_meters,
            is_duplicate=is_duplicate,
            duplicate_of=duplicate,
            verification_notes="; ".join(notes),
            metadata={
                "shipment_id": shipment.pk,
                "gps_latitude": gps_latitude,
                "gps_longitude": gps_longitude,
                "gps_accuracy_meters": gps_accuracy_meters,
                "uploaded_by": request.user.pk,
                "confirmation_method": request.data.get("confirmation_method", "in_app"),
            },
        )

        pod = self._confirm_from_payload(pod)
        pod.save(update_fields=["customer_confirmed", "customer_confirmed_at", "customer_confirmation_method", "updated_at"])

        serializer = self.get_serializer(pod)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=http_status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=["post"], url_path="confirm")
    @extend_schema(
        summary="Confirm proof of delivery from customer",
        request=ShipmentProofOfDeliveryConfirmSerializer,
        responses={200: ShipmentProofOfDeliverySerializer},
    )
    def confirm(self, request, *args, **kwargs):
        pod = self.get_object()
        if pod.shipment.customer_id != request.user.pk and not request.user.is_staff:
            raise ValidationError({"detail": "Only the customer or staff can confirm POD"})

        serializer = ShipmentProofOfDeliveryConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pod.customer_confirmed = True
        pod.customer_confirmed_at = timezone.now()
        pod.customer_confirmation_method = serializer.validated_data.get("confirmation_method", "in_app")
        if serializer.validated_data.get("notes"):
            pod.verification_notes = f"{pod.verification_notes}; Customer note: {serializer.validated_data['notes']}".strip("; ")
        pod.save(update_fields=["customer_confirmed", "customer_confirmed_at", "customer_confirmation_method", "verification_notes", "updated_at"])

        return Response(self.get_serializer(pod).data, status=http_status.HTTP_200_OK)


class ShipmentPODOTPSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ShipmentPODOTPSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pod_id = serializer.validated_data["pod_id"]
        phone = serializer.validated_data.get("phone")

        try:
            pod = ShipmentProofOfDelivery.objects.get(pk=pod_id)
        except ShipmentProofOfDelivery.DoesNotExist:
            raise ValidationError({"pod_id": "POD not found"})

        # Only allow customer or staff to request an OTP
        shipment = pod.shipment
        if not request.user.is_staff and shipment.customer_id != request.user.pk:
            raise ValidationError({"detail": "Only customer or staff may request OTP"})

        phone_to_use = phone or shipment.recipient_phone or getattr(shipment.customer, "phone", None)
        if not phone_to_use:
            raise ValidationError({"phone": "No phone available for OTP delivery"})

        otp = create_and_send_otp(pod=pod, phone=phone_to_use)

        return Response({"otp_id": otp.pk, "expires_at": otp.expires_at}, status=http_status.HTTP_201_CREATED)


class ShipmentPODOTPVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ShipmentPODOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pod_id = serializer.validated_data["pod_id"]
        code = serializer.validated_data["code"].strip()

        try:
            pod = ShipmentProofOfDelivery.objects.get(pk=pod_id)
        except ShipmentProofOfDelivery.DoesNotExist:
            raise ValidationError({"pod_id": "POD not found"})

        # Find recent OTP for this pod and phone
        now = timezone.now()
        otp_qs = ShipmentPODOTP.objects.filter(pod=pod, code=code, used=False, expires_at__gte=now).order_by("-created_at")
        otp = otp_qs.first()
        if not otp:
            # increment attempt counters for recent OTPs for this pod
            ShipmentPODOTP.objects.filter(pod=pod, used=False, expires_at__gte=now).update(attempts=models.F('attempts') + 1)
            raise ValidationError({"code": "Invalid or expired code"})

        # mark used
        otp.used = True
        otp.attempts = otp.attempts + 1
        otp.save(update_fields=["used", "attempts", "updated_at"])

        # mark pod confirmed
        pod.customer_confirmed = True
        pod.customer_confirmed_at = timezone.now()
        pod.customer_confirmation_method = "otp"
        pod.save(update_fields=["customer_confirmed", "customer_confirmed_at", "customer_confirmation_method", "updated_at"])

        return Response({"detail": "POD confirmed via OTP", "pod_id": pod.pk}, status=http_status.HTTP_200_OK)


class ShipmentPODOTPResendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ShipmentPODOTPResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pod_id = serializer.validated_data["pod_id"]
        phone = serializer.validated_data.get("phone")

        try:
            pod = ShipmentProofOfDelivery.objects.get(pk=pod_id)
        except ShipmentProofOfDelivery.DoesNotExist:
            raise ValidationError({"pod_id": "POD not found"})

        # Only allow customer or staff to request resend
        shipment = pod.shipment
        if not request.user.is_staff and shipment.customer_id != request.user.pk:
            raise ValidationError({"detail": "Only customer or staff may request OTP resend"})

        # Check resend limit
        max_resends = default_otp_resend_max()
        if pod.otp_resend_count >= max_resends:
            raise ValidationError({
                "detail": f"Maximum OTP resends ({max_resends}) reached. Please contact support."
            })

        # Check time since last OTP send
        if pod.last_otp_sent_at:
            min_delay = default_otp_resend_delay_seconds()
            time_since_last = (timezone.now() - pod.last_otp_sent_at).total_seconds()
            if time_since_last < min_delay:
                wait_time = int(min_delay - time_since_last)
                raise ValidationError({
                    "detail": f"Please wait {wait_time} seconds before requesting another OTP."
                })

        # Get phone to use
        phone_to_use = phone or shipment.recipient_phone or getattr(shipment.customer, "phone", None)
        if not phone_to_use:
            raise ValidationError({"phone": "No phone available for OTP delivery"})

        # Create new OTP
        otp = create_and_send_otp(pod=pod, phone=phone_to_use)

        # Increment resend count
        pod.otp_resend_count += 1
        pod.save(update_fields=["otp_resend_count"])

        # Calculate remaining resends
        remaining_resends = max(0, max_resends - pod.otp_resend_count)
        
        # Send resend notification to customer (email/push)
        try:
            send_otp_resend_notification(pod=pod, otp=otp, remaining_resends=remaining_resends)
        except Exception as e:
            # Log but don't fail the API response on notification errors
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send OTP resend notification for POD {pod.pk}: {str(e)}")

        return Response({
            "otp_id": otp.pk,
            "expires_at": otp.expires_at,
            "resend_count": pod.otp_resend_count,
            "remaining_resends": remaining_resends,
            "message": f"OTP resent. You have {remaining_resends} more resend(s) available."
        }, status=http_status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def twilio_delivery_webhook(request):
    """Webhook endpoint for Twilio delivery status notifications.
    
    Twilio will POST to this endpoint with the following parameters:
    - MessageSid: Twilio message SID
    - MessageStatus: delivery status (queued, sent, delivered, undelivered, failed)
    - ErrorCode (optional): error code if delivery failed
    
    The X-Twilio-Signature header is used to validate the request.
    """
    # Validate Twilio signature
    webhook_url = request.build_absolute_uri(request.path)
    if not validate_twilio_signature(request, webhook_url):
        return Response({"detail": "Invalid signature"}, status=http_status.HTTP_403_FORBIDDEN)

    message_sid = request.data.get("MessageSid")
    status = request.data.get("MessageStatus")
    error_code = request.data.get("ErrorCode")

    if not message_sid or not status:
        return Response({"detail": "Missing MessageSid or MessageStatus"}, status=http_status.HTTP_400_BAD_REQUEST)

    # Process the webhook
    receipt = process_twilio_delivery_webhook(
        message_sid=message_sid,
        status=status,
        error_code=error_code,
        error_message=request.data.get("ErrorMessage", ""),
        webhook_data=dict(request.data),
    )

    return Response({"detail": "Webhook processed", "receipt_id": receipt.pk if receipt else None}, status=http_status.HTTP_200_OK)


@extend_schema(
    tags=["Cargo Types"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List cargo types",
        description="Retrieve all cargo types.",
        responses={200: CargoTypeSerializer(many=True)}
    ),
    create=extend_schema(
        summary="Create cargo type",
        description="Create a new cargo type (Admin only).",
        request=CargoTypeSerializer,
        responses={201: CargoTypeSerializer}
    ),
    retrieve=extend_schema(
        summary="Retrieve cargo type",
        responses={200: CargoTypeSerializer}
    ),
    update=extend_schema(
        summary="Update cargo type",
        request=CargoTypeSerializer,
        responses={200: CargoTypeSerializer}
    ),
    partial_update=extend_schema(
        summary="Partially update cargo type",
        request=CargoTypeSerializer,
        responses={200: CargoTypeSerializer}
    ),
    destroy=extend_schema(
        summary="Delete cargo type",
        responses={204: None}
    ),
)
class CargoTypeViewSet(viewsets.ModelViewSet):
    queryset = CargoType.objects.all()
    serializer_class = CargoTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

@extend_schema(
    tags=["Shipment History"]
)
@extend_schema_view(
    list=extend_schema(
        summary="List shipment status history",
        description="Retrieve status history for a specific shipment using shipment_id.",
        responses={200: ShipmentStatusHistorySerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Retrieve status record",
        description="Get a specific status history record.",
        responses={200: ShipmentStatusHistorySerializer}
    ),
)
class ShipmentStatusHistoryViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = ShipmentStatusHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        shipment_id = self.request.query_params.get("shipment_id")
        if not shipment_id:
            raise ValidationError("shipment_id query param is required")

        queryset = ShipmentStatusHistory.objects.filter(shipment_id=shipment_id)
        user = self.request.user
        if user.is_staff:
            return queryset
        return queryset.filter(shipment__customer=user)