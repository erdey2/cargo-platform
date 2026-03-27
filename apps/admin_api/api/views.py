"""Admin API views - all require IsAdminUser permission."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from django.utils import timezone
from django.db.models import Sum
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model
from apps.drivers.models import DriverProfile
from apps.vehicles.models import Vehicle, VehicleType, VehicleDocument
from apps.shipments.models import Shipment, CargoType, ShipmentStatusHistory
from apps.assignment.models import Assignment
from apps.assignment.services.assignment import AssignmentService
from apps.payments.models import Transaction
from apps.pricing.models import PricingRule
from apps.rating.models import Rating
from apps.notifications.models import Notification
from apps.location.models import Location
from apps.admin_api.models import AuditLog, Dispute

from . import serializers

User = get_user_model()


def log_admin_action(request, action, target_model="", target_id="", details=None):
    """Helper to create audit log entry."""
    AuditLog.objects.create(
        admin_user=request.user,
        action=action,
        target_model=target_model,
        target_id=str(target_id),
        details=details or {},
        ip_address=get_client_ip(request),
    )


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# --- Dashboard ---
@extend_schema(tags=["Admin"])
class AdminDashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()
        stats = {
            "users": {
                "total": User.objects.count(),
                "customers": User.objects.filter(role="customer").count(),
                "drivers": User.objects.filter(role="driver").count(),
            },
            "shipments": {
                "total": Shipment.objects.count(),
                "created": Shipment.objects.filter(status="created").count(),
                "matching": Shipment.objects.filter(status="matching").count(),
                "assigned": Shipment.objects.filter(status="assigned").count(),
                "cancelled": Shipment.objects.filter(status="cancelled").count(),
                "today": Shipment.objects.filter(created_at__date=today).count(),
            },
            "drivers": {
                "total": DriverProfile.objects.count(),
                "verified": DriverProfile.objects.filter(
                    verification_status="verified"
                ).count(),
                "pending": DriverProfile.objects.filter(
                    verification_status="pending"
                ).count(),
                "available": DriverProfile.objects.filter(
                    is_available=True
                ).count(),
            },
            "vehicles": {
                "total": Vehicle.objects.count(),
                "verified": Vehicle.objects.filter(
                    verification_status=True
                ).count(),
            },
            "transactions": {
                "total": Transaction.objects.count(),
                "total_amount": Transaction.objects.aggregate(
                    s=Sum("amount")
                )["s"] or 0,
            },
            "disputes": {
                "open": Dispute.objects.filter(status="open").count(),
                "in_review": Dispute.objects.filter(status="in_review").count(),
            },
        }
        return Response(stats)


# --- Users ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
    update=extend_schema(tags=["Admin"]),
    partial_update=extend_schema(tags=["Admin"]),
    destroy=extend_schema(tags=["Admin"]),
)
class AdminUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("profile").order_by("-created_at")
    permission_classes = [IsAdminUser]
    http_method_names = ["get", "put", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return serializers.AdminUserUpdateSerializer
        return serializers.AdminUserSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_superuser:
            return Response(
                {"detail": "Cannot delete superuser."},
                status=status.HTTP_403_FORBIDDEN,
            )
        log_admin_action(
            request, "user_update", "users.User", instance.id, {"action": "delete"}
        )
        return super().destroy(request, *args, **kwargs)


# --- Drivers ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
    verify=extend_schema(tags=["Admin"]),
    reject=extend_schema(tags=["Admin"]),
    suspend=extend_schema(tags=["Admin"]),
    activate=extend_schema(tags=["Admin"]),
)
class AdminDriverViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DriverProfile.objects.select_related("user").order_by("-created_at")
    serializer_class = serializers.AdminDriverSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        driver = self.get_object()
        driver.verification_status = "verified"
        driver.save()
        log_admin_action(request, "driver_verify", "drivers.DriverProfile", driver.id)
        return Response(
            serializers.AdminDriverSerializer(driver).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        driver = self.get_object()
        driver.verification_status = "rejected"
        driver.save()
        log_admin_action(request, "driver_reject", "drivers.DriverProfile", driver.id)
        return Response(
            serializers.AdminDriverSerializer(driver).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        driver = self.get_object()
        driver.user.is_active = False
        driver.user.save()
        log_admin_action(request, "driver_suspend", "drivers.DriverProfile", driver.id)
        return Response(
            serializers.AdminDriverSerializer(driver).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        driver = self.get_object()
        driver.user.is_active = True
        driver.user.save()
        log_admin_action(request, "driver_activate", "drivers.DriverProfile", driver.id)
        return Response(
            serializers.AdminDriverSerializer(driver).data,
            status=status.HTTP_200_OK,
        )


# --- Vehicles ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
    verify=extend_schema(tags=["Admin"]),
    reject=extend_schema(tags=["Admin"]),
)
class AdminVehicleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vehicle.objects.select_related("driver__user", "vehicle_type").order_by(
        "-id"
    )
    serializer_class = serializers.AdminVehicleSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        vehicle = self.get_object()
        vehicle.verification_status = True
        vehicle.save()
        log_admin_action(request, "vehicle_verify", "vehicles.Vehicle", vehicle.id)
        return Response(
            serializers.AdminVehicleSerializer(vehicle).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        vehicle = self.get_object()
        vehicle.verification_status = False
        vehicle.save()
        log_admin_action(request, "vehicle_reject", "vehicles.Vehicle", vehicle.id)
        return Response(
            serializers.AdminVehicleSerializer(vehicle).data,
            status=status.HTTP_200_OK,
        )


# --- Shipments ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
    assign_driver=extend_schema(tags=["Admin"]),
    cancel=extend_schema(tags=["Admin"]),
)
class AdminShipmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Shipment.objects.select_related(
        "customer", "cargo_type"
    ).order_by("-created_at")
    serializer_class = serializers.AdminShipmentSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=["post"])
    def assign_driver(self, request, pk=None):
        shipment = self.get_object()
        if shipment.status == "assigned":
            return Response(
                {"detail": "Shipment already has an assigned driver."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if shipment.status == "cancelled":
            return Response(
                {"detail": "Cannot assign driver to cancelled shipment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = serializers.AdminAssignDriverSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        driver_id = ser.validated_data["driver_id"]
        vehicle_id = ser.validated_data.get("vehicle_id")
        try:
            driver = DriverProfile.objects.get(id=driver_id)
        except DriverProfile.DoesNotExist:
            return Response(
                {"detail": "Driver not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        vehicle = None
        if vehicle_id:
            vehicle = driver.vehicles.filter(id=vehicle_id).first()
        if not vehicle:
            vehicle = driver.vehicles.first()
        if not vehicle:
            return Response(
                {"detail": "Driver has no vehicles."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        capable_vehicles = driver.vehicles.filter(
            capacity_weight__gte=shipment.weight,
            capacity_volume__gte=shipment.volume,
        )
        if not capable_vehicles.exists():
            return Response(
                {"detail": "No vehicle with sufficient capacity."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if vehicle not in capable_vehicles:
            vehicle = capable_vehicles.first()
        assignment = AssignmentService.assign_driver(shipment, driver, vehicle=vehicle)
        log_admin_action(
            request,
            "shipment_assign",
            "shipments.Shipment",
            shipment.id,
            {"driver_id": driver_id, "vehicle_id": vehicle.id},
        )
        return Response(
            serializers.AdminAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        shipment = self.get_object()
        if shipment.status == "cancelled":
            return Response(
                {"detail": "Shipment already cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        shipment.status = "cancelled"
        shipment.save()
        ShipmentStatusHistory.objects.create(
            shipment=shipment,
            status="cancelled",
            changed_by=request.user,
            notes="Cancelled by admin",
        )
        log_admin_action(request, "shipment_cancel", "shipments.Shipment", shipment.id)
        return Response(
            serializers.AdminShipmentSerializer(shipment).data,
            status=status.HTTP_200_OK,
        )


# --- Assignments ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
)
class AdminAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Assignment.objects.select_related(
        "shipment", "driver__user", "vehicle"
    ).order_by("-created_at")
    serializer_class = serializers.AdminAssignmentSerializer
    permission_classes = [IsAdminUser]


# --- Transactions ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
    refund=extend_schema(tags=["Admin"]),
)
class AdminTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transaction.objects.select_related("shipment__customer").order_by(
        "-created_at"
    )
    serializer_class = serializers.AdminTransactionSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        transaction = self.get_object()
        if transaction.status == "refunded":
            return Response(
                {"detail": "Transaction already refunded."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        transaction.status = "refunded"
        transaction.save()
        log_admin_action(
            request,
            "transaction_refund",
            "payments.Transaction",
            transaction.id,
            {"amount": str(transaction.amount)},
        )
        return Response(
            serializers.AdminTransactionSerializer(transaction).data,
            status=status.HTTP_200_OK,
        )


# --- Pricing ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
    create=extend_schema(tags=["Admin"]),
    update=extend_schema(tags=["Admin"]),
    partial_update=extend_schema(tags=["Admin"]),
    destroy=extend_schema(tags=["Admin"]),
)
class AdminPricingRuleViewSet(viewsets.ModelViewSet):
    queryset = PricingRule.objects.all().order_by("vehicle_type")
    serializer_class = serializers.AdminPricingRuleSerializer
    permission_classes = [IsAdminUser]


# --- Ratings ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
)
class AdminRatingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Rating.objects.select_related(
        "shipment", "driver__user", "customer"
    ).order_by("-created_at")
    serializer_class = serializers.AdminRatingSerializer
    permission_classes = [IsAdminUser]


# --- Notifications ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
    send=extend_schema(tags=["Admin"]),
)
class AdminNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Notification.objects.select_related("user").order_by("-created_at")
    serializer_class = serializers.AdminNotificationSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=["post"])
    def send(self, request):
        ser = serializers.AdminSendNotificationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_id = ser.validated_data.get("user_id")
        user_ids = ser.validated_data.get("user_ids") or []
        title = ser.validated_data["title"]
        message = ser.validated_data["message"]
        if user_id is not None:
            user_ids = [user_id]
        created = []
        for uid in user_ids:
            try:
                user = User.objects.get(id=uid)
                n = Notification.objects.create(
                    user=user, title=title, message=message
                )
                created.append(serializers.AdminNotificationSerializer(n).data)
            except User.DoesNotExist:
                pass
        return Response({"created": created}, status=status.HTTP_201_CREATED)


# --- Locations ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
    create=extend_schema(tags=["Admin"]),
    update=extend_schema(tags=["Admin"]),
    partial_update=extend_schema(tags=["Admin"]),
    destroy=extend_schema(tags=["Admin"]),
)
class AdminLocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all().order_by("region", "city")
    serializer_class = serializers.AdminLocationSerializer
    permission_classes = [IsAdminUser]


# --- Cargo Types ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
    create=extend_schema(tags=["Admin"]),
    update=extend_schema(tags=["Admin"]),
    partial_update=extend_schema(tags=["Admin"]),
    destroy=extend_schema(tags=["Admin"]),
)
class AdminCargoTypeViewSet(viewsets.ModelViewSet):
    queryset = CargoType.objects.all().order_by("name")
    serializer_class = serializers.AdminCargoTypeSerializer
    permission_classes = [IsAdminUser]


# --- Audit Logs ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
)
class AdminAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("admin_user").order_by("-created_at")
    serializer_class = serializers.AdminAuditLogSerializer
    permission_classes = [IsAdminUser]


# --- Disputes ---
@extend_schema_view(
    list=extend_schema(tags=["Admin"]),
    retrieve=extend_schema(tags=["Admin"]),
    create=extend_schema(tags=["Admin"]),
    resolve=extend_schema(tags=["Admin"]),
)
class AdminDisputeViewSet(viewsets.ModelViewSet):
    queryset = Dispute.objects.select_related(
        "shipment", "raised_by", "resolved_by"
    ).order_by("-created_at")
    serializer_class = serializers.AdminDisputeSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        dispute = self.get_object()
        ser = serializers.AdminResolveDisputeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        dispute.resolution = ser.validated_data["resolution"]
        dispute.status = ser.validated_data["status"]
        dispute.resolved_by = request.user
        dispute.resolved_at = timezone.now()
        dispute.save()
        log_admin_action(
            request,
            "dispute_resolve",
            "admin.Dispute",
            dispute.id,
            {"resolution": dispute.resolution[:100]},
        )
        return Response(
            serializers.AdminDisputeSerializer(dispute).data,
            status=status.HTTP_200_OK,
        )
