from rest_framework import serializers
from apps.rating.models import Rating
from apps.shipments.models import Shipment
from apps.shipments.api.serializers import ShipmentSimpleSerializer
from apps.drivers.api.serializers import DriverSimpleSerializer

class RatingCreateSerializer(serializers.Serializer):
    shipment_id = serializers.IntegerField()
    score = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context["request"]
        shipment_id = attrs["shipment_id"]

        shipment = Shipment.objects.select_related(
            "customer", "driver"
        ).filter(id=shipment_id).first()

        if not shipment:
            raise serializers.ValidationError({"shipment_id": "Shipment not found."})

        if shipment.customer_id != request.user.id:
            raise serializers.ValidationError({"shipment_id": "Not your shipment."})

        if shipment.status not in {"delivered", "completed"}:
            raise serializers.ValidationError({"shipment_id": "Cannot rate yet."})

        if not shipment.driver_id:
            raise serializers.ValidationError({"shipment_id": "No driver assigned."})

        if Rating.objects.filter(shipment=shipment).exists():
            raise serializers.ValidationError({"shipment_id": "Already rated."})

        attrs["shipment"] = shipment
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        shipment = validated_data["shipment"]

        return Rating.objects.create(
            shipment=shipment,
            driver=shipment.driver,
            customer=request.user,
            score=validated_data["score"],
            comment=validated_data.get("comment", ""),
        )

class RatingSerializer(serializers.ModelSerializer):
    shipment = ShipmentSimpleSerializer(read_only=True)
    driver = DriverSimpleSerializer(read_only=True)

    class Meta:
        model = Rating
        fields = [
			"id",
			"shipment",
			"driver",
			"customer_id",
			"score",
			"comment",
			"created_at",
		]
        read_only_fields = ["shipment", "driver", "customer_id", "created_at"]



