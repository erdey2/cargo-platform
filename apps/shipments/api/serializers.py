from django.contrib.gis.geos import Point
from rest_framework import serializers
from ..models import Shipment, CargoType, ShipmentStatusHistory, ShipmentProofOfDelivery
from apps.drivers.api.serializers import DriverSimpleSerializer

class CargoTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CargoType
        fields = "__all__"

class ShipmentSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = [
            "id",
            "driver",
            "pickup_address",
            "dropoff_address",

            "recipient_name",
            "recipient_phone",
            "recipient_alternate_phone",

            "weight",
            "volume",
            "estimated_price",
            "proof_of_delivery",
        ]
        read_only_fields = [
            "id",
            "pickup_address",
            "dropoff_address",
            "weight",
            "volume",
            "estimated_price",
            "proof_of_delivery",
        ]

class ShipmentSerializer(serializers.ModelSerializer):

    customer = serializers.ReadOnlyField(source="customer.id")

    driver = DriverSimpleSerializer(read_only=True)

    # FIXED
    proof_of_delivery = serializers.SerializerMethodField()

    recipient_name = serializers.CharField(required=True)

    recipient_phone = serializers.CharField(required=True)

    recipient_alternate_phone = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True
    )

    # Write-only inputs
    pickup_lat = serializers.FloatField(write_only=True)

    pickup_lng = serializers.FloatField(write_only=True)

    dropoff_lat = serializers.FloatField(write_only=True)

    dropoff_lng = serializers.FloatField(write_only=True)

    pickup_latitude = serializers.SerializerMethodField()

    pickup_longitude = serializers.SerializerMethodField()

    dropoff_latitude = serializers.SerializerMethodField()

    dropoff_longitude = serializers.SerializerMethodField()

    class Meta:

        model = Shipment

        fields = [
            "id",
            "customer",
            "driver",

            "pickup_address",
            "dropoff_address",

            # input
            "pickup_lat",
            "pickup_lng",
            "dropoff_lat",
            "dropoff_lng",

            # output
            "pickup_latitude",
            "pickup_longitude",
            "dropoff_latitude",
            "dropoff_longitude",

            "recipient_name",
            "recipient_phone",
            "recipient_alternate_phone",

            "weight",
            "volume",
            "cargo_type",
            "description",

            "status",
            "estimated_price",
            "final_price",

            "proof_of_delivery",

            "assigned_at",
            "picked_up_at",
            "delivered_at",
            "created_at",
        ]

        read_only_fields = [
            "status",
            "assigned_at",
            "picked_up_at",
            "delivered_at",
            "estimated_price",
            "final_price",
            "proof_of_delivery",
        ]

    # FIXED
    def get_proof_of_delivery(self, obj):

        request = self.context.get("request")

        if obj.proof_of_delivery:

            if request:
                return request.build_absolute_uri(
                    obj.proof_of_delivery.url
                )

            return obj.proof_of_delivery.url

        return None

    def get_pickup_latitude(self, obj):
        return obj.pickup_location.y if obj.pickup_location else None

    def get_pickup_longitude(self, obj):
        return obj.pickup_location.x if obj.pickup_location else None

    def get_dropoff_latitude(self, obj):
        return obj.dropoff_location.y if obj.dropoff_location else None

    def get_dropoff_longitude(self, obj):
        return obj.dropoff_location.x if obj.dropoff_location else None

    def validate(self, data):

        if data["weight"] <= 0:
            raise serializers.ValidationError(
                "Weight must be positive"
            )

        if data["volume"] <= 0:
            raise serializers.ValidationError(
                "Volume must be positive"
            )

        lat = data.get("pickup_lat")
        lng = data.get("pickup_lng")

        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise serializers.ValidationError(
                "Invalid pickup coordinates"
            )

        return data

    def create(self, validated_data):

        pickup = Point(
            validated_data.pop("pickup_lng"),
            validated_data.pop("pickup_lat"),
        )

        dropoff = Point(
            validated_data.pop("dropoff_lng"),
            validated_data.pop("dropoff_lat"),
        )

        if pickup == dropoff:
            raise serializers.ValidationError(
                "Pickup and dropoff cannot be the same location"
            )

        return Shipment.objects.create(
            pickup_location=pickup,
            dropoff_location=dropoff,
            **validated_data
        )

class ShipmentStatusHistorySerializer(serializers.ModelSerializer):
    shipment = ShipmentSimpleSerializer(read_only=True)

    class Meta:
        model = ShipmentStatusHistory
        fields = ["id", "shipment", "status", "is_active", "notes", "changed_by", "created_at", "updated_at"]
        read_only_fields = ["id", "shipment", "status", "created_at", "updated_at"]


class ShipmentProofOfDeliveryUploadSerializer(serializers.Serializer):
    shipment = serializers.IntegerField()
    photo = serializers.ImageField()
    gps_latitude = serializers.FloatField(required=False, allow_null=True)
    gps_longitude = serializers.FloatField(required=False, allow_null=True)
    gps_accuracy_meters = serializers.FloatField(required=False, allow_null=True)


class ShipmentProofOfDeliveryConfirmSerializer(serializers.Serializer):
    confirmation_method = serializers.ChoiceField(
        choices=(
            ("in_app", "In-app"),
            ("otp", "OTP"),
            ("link", "Link"),
        ),
        required=False,
        default="in_app",
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class ShipmentPODOTPSendSerializer(serializers.Serializer):
    pod_id = serializers.IntegerField()
    phone = serializers.CharField(required=False, allow_blank=True)


class ShipmentPODOTPVerifySerializer(serializers.Serializer):
    pod_id = serializers.IntegerField()
    code = serializers.CharField()


class ShipmentPODOTPResendSerializer(serializers.Serializer):
    pod_id = serializers.IntegerField()
    phone = serializers.CharField(required=False, allow_blank=True)


class ShipmentProofOfDeliverySerializer(serializers.ModelSerializer):
    shipment = serializers.SerializerMethodField()
    uploaded_by = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    gps_latitude = serializers.SerializerMethodField()
    gps_longitude = serializers.SerializerMethodField()
    confirmation_status = serializers.SerializerMethodField()

    class Meta:
        model = ShipmentProofOfDelivery
        fields = [
            "id",
            "shipment",
            "uploaded_by",
            "photo_url",
            "image_sha256",
            "gps_latitude",
            "gps_longitude",
            "gps_accuracy_meters",
            "gps_verified",
            "gps_distance_to_dropoff_meters",
            "is_duplicate",
            "duplicate_of",
            "confirmation_status",
            "customer_confirmed",
            "customer_confirmed_at",
            "customer_confirmation_method",
            "verification_notes",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

    def get_shipment(self, obj):
        return {
            "id": obj.shipment_id,
            "status": obj.shipment.status,
            "pickup_address": obj.shipment.pickup_address,
            "dropoff_address": obj.shipment.dropoff_address,
            "customer_id": obj.shipment.customer_id,
            "driver_id": obj.shipment.driver_id,
        }

    def get_uploaded_by(self, obj):
        if not obj.uploaded_by:
            return None
        return {
            "id": obj.uploaded_by_id,
            "email": obj.uploaded_by.email,
            "role": getattr(obj.uploaded_by, "role", None),
        }

    def get_photo_url(self, obj):
        request = self.context.get("request")
        if not obj.photo:
            return None
        if request:
            return request.build_absolute_uri(obj.photo.url)
        return obj.photo.url

    def get_gps_latitude(self, obj):
        return obj.gps_location.y if obj.gps_location else None

    def get_gps_longitude(self, obj):
        return obj.gps_location.x if obj.gps_location else None

    def get_confirmation_status(self, obj):
        return "confirmed" if obj.customer_confirmed else "pending"

