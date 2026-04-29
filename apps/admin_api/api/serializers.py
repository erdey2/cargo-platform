"""Admin API serializers - reuse and extend from other apps."""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from apps.users.models import Profile
from apps.drivers.models import DriverProfile
from apps.vehicles.models import Vehicle
from apps.shipments.models import Shipment, CargoType
from apps.assignment.models import Assignment
from apps.payments.models import Transaction
from apps.pricing.models import PricingRule
from apps.rating.models import Rating
from apps.notifications.models import Notification
from apps.location.models import Location
from apps.admin_api.models import AuditLog, Dispute

User = get_user_model()


# --- User serializers ---
class AdminUserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()
    role = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "role",
            "is_active",
            "is_verified",
            "is_staff",
            "profile",
            "created_at",
        ]
        read_only_fields = ["email", "created_at"]

    def get_profile(self, obj):
        if hasattr(obj, "profile"):
            return {
                "full_name": obj.profile.full_name,
                "address": obj.profile.address,
                "city": obj.profile.city,
                "country": obj.profile.country,
            }
        return None


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["phone", "role", "is_active", "is_verified"]


# --- Driver serializers ---
class AdminDriverSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    vehicle_count = serializers.SerializerMethodField()

    class Meta:
        model = DriverProfile
        fields = [
            "id",
            "user",
            "email",
            "national_id",
            "driver_license",
            "license_expiry",
            "verification_status",
            "total_trips",
            "is_available",
            "is_active",
            "vehicle_count",
            "created_at",
        ]

    def get_vehicle_count(self, obj):
        return obj.vehicles.count()


class AdminVehicleSerializer(serializers.ModelSerializer):
    driver_email = serializers.EmailField(source="driver.user.email", read_only=True)
    vehicle_type_name = serializers.CharField(source="vehicle_type.name", read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "driver",
            "driver_email",
            "vehicle_type",
            "vehicle_type_name",
            "plate_number",
            "capacity_weight",
            "capacity_volume",
            "verification_status",
            "created_at",
        ]


class AdminShipmentSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    cargo_type_name = serializers.CharField(
        source="cargo_type.name", read_only=True, default=None
    )

    class Meta:
        model = Shipment
        fields = [
            "id",
            "customer",
            "customer_email",
            "pickup_address",
            "dropoff_address",
            "pickup_location",
            "dropoff_location",
            "weight",
            "volume",
            "cargo_type",
            "cargo_type_name",
            "description",
            "status",
            "estimated_price",
            "final_price",
            "assigned_at",
            "picked_up_at",
            "delivered_at",
            "created_at",
        ]


class AdminAssignDriverSerializer(serializers.Serializer):
    driver_id = serializers.IntegerField()
    vehicle_id = serializers.IntegerField(required=False)


class AdminAssignmentSerializer(serializers.ModelSerializer):
    shipment_id = serializers.ReadOnlyField(source="shipment.id")
    driver_email = serializers.EmailField(source="driver.user.email", read_only=True)
    vehicle_plate = serializers.CharField(source="vehicle.plate_number", read_only=True)

    class Meta:
        model = Assignment
        fields = [
            "id",
            "shipment_id",
            "driver",
            "driver_email",
            "vehicle",
            "vehicle_plate",
            "status",
            "accepted_at",
            "picked_up_at",
            "delivered_at",
            "created_at",
        ]


class AdminTransactionSerializer(serializers.ModelSerializer):
    shipment_id = serializers.ReadOnlyField(source="shipment.id")
    customer_email = serializers.EmailField(
        source="shipment.customer.email", read_only=True
    )

    class Meta:
        model = Transaction
        fields = [
            "id",
            "shipment",
            "shipment_id",
            "customer_email",
            "amount",
            "payment_method",
            "status",
            "created_at",
        ]


class AdminPricingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingRule
        fields = "__all__"


class AdminRatingSerializer(serializers.ModelSerializer):
    driver_email = serializers.EmailField(source="driver.user.email", read_only=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True)

    class Meta:
        model = Rating
        fields = [
            "id",
            "shipment",
            "driver",
            "driver_email",
            "customer",
            "customer_email",
            "score",
            "comment",
            "created_at",
        ]


class AdminNotificationSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "recipient", "user_email", "message", "data", "is_read", "created_at"]


class AdminSendNotificationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )
    title = serializers.CharField()
    message = serializers.CharField()

    def validate(self, data):
        user_id = data.get("user_id")
        user_ids = data.get("user_ids") or []
        if not user_id and not user_ids:
            raise serializers.ValidationError(
                "Provide either user_id or user_ids"
            )
        return data


class AdminLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = "__all__"


class AdminCargoTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CargoType
        fields = "__all__"


class AdminAuditLogSerializer(serializers.ModelSerializer):
    admin_email = serializers.EmailField(
        source="admin_user.email", read_only=True, default=None
    )

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "admin_user",
            "admin_email",
            "action",
            "target_model",
            "target_id",
            "details",
            "ip_address",
            "created_at",
        ]


class AdminDisputeSerializer(serializers.ModelSerializer):
    raised_by_email = serializers.EmailField(
        source="raised_by.email", read_only=True
    )
    shipment_status = serializers.CharField(
        source="shipment.status", read_only=True
    )

    class Meta:
        model = Dispute
        fields = [
            "id",
            "shipment",
            "raised_by",
            "raised_by_email",
            'shipment_status',
            "subject",
            "description",
            "status",
            "resolution",
            "resolved_by",
            "resolved_at",
            "created_at",
        ]
        read_only_fields = ["status", "resolution", "resolved_by", "resolved_at"]


class AdminResolveDisputeSerializer(serializers.Serializer):
    resolution = serializers.CharField()
    status = serializers.ChoiceField(
        choices=[("resolved", "Resolved"), ("closed", "Closed")]
    )
