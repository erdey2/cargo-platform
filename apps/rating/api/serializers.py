from rest_framework import serializers

from apps.rating.models import Rating
from apps.shipments.models import Shipment
from apps.rating.services import RatingService

class RatingCreateSerializer(serializers.Serializer):
	shipment_id = serializers.IntegerField()
	score = serializers.IntegerField(min_value=1, max_value=5)
	comment = serializers.CharField(required=False, allow_blank=True)

	def validate(self, attrs):
		request = self.context["request"]
		shipment_id = attrs["shipment_id"]

		shipment = Shipment.objects.select_related("customer", "driver").filter(id=shipment_id).first()
		if not shipment:
			raise serializers.ValidationError({"shipment_id": "Shipment not found."})

		if shipment.customer_id != request.user.id:
			raise serializers.ValidationError({"shipment_id": "You can only rate your own shipment."})

		if shipment.status not in {"delivered", "completed"}:
			raise serializers.ValidationError({"shipment_id": "You can rate the driver only after delivery."})

		if not shipment.driver_id:
			raise serializers.ValidationError({"shipment_id": "This shipment has no driver to rate."})

		if Rating.objects.filter(shipment=shipment).exists():
			raise serializers.ValidationError({"shipment_id": "This shipment has already been rated."})

		attrs["shipment"] = shipment
		return attrs

	def create(self, validated_data):
		request = self.context["request"]
		shipment = validated_data["shipment"]

		rating = Rating.objects.create(
			shipment=shipment,
			driver=shipment.driver,
			customer=request.user,
			score=validated_data["score"],
			comment=validated_data.get("comment", ""),
		)

		RatingService.refresh_driver_rating(shipment.driver)
		return rating

class RatingSerializer(serializers.ModelSerializer):
	shipment_id = serializers.IntegerField(read_only=True)
	driver_id = serializers.IntegerField(read_only=True)
	customer_id = serializers.IntegerField(read_only=True)

	class Meta:
		model = Rating
		fields = [
			"id",
			"shipment_id",
			"driver_id",
			"customer_id",
			"score",
			"comment",
			"created_at",
		]



