from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.drivers.models import DriverProfile
from apps.vehicles.models import Vehicle, VehicleType

User = get_user_model()

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ["plate_number", "vehicle_type"]


class DriverRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    # Profile fields
    full_name = serializers.CharField()
    phone = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    location = serializers.CharField()  # expect "POINT(lon lat)"

    # DriverProfile fields
    national_id = serializers.CharField()
    driver_license = serializers.CharField()

    # Vehicle
    vehicle = VehicleSerializer()

    def create(self, validated_data):
        vehicle_data = validated_data.pop("vehicle")

        # Extract profile fields
        full_name = validated_data.pop("full_name")
        phone = validated_data.pop("phone")
        address = validated_data.pop("address")
        city = validated_data.pop("city")
        location = validated_data.pop("location")

        # Extract driver profile fields
        national_id = validated_data.pop("national_id")
        driver_license = validated_data.pop("driver_license")

        # Vehicle type
        vehicle_type = vehicle_data["vehicle_type"]

        from django.db import transaction
        with transaction.atomic():
            # Create User
            user = User.objects.create_user(
                email=validated_data["email"],
                password=validated_data["password"],
                role="driver",
                phone=phone
            )

            # Update Profile
            profile = user.profile
            profile.full_name = full_name
            profile.address = address
            profile.city = city
            # convert location string to Point
            from django.contrib.gis.geos import Point
            if location:
                lon, lat = map(float, location.strip().split())
                profile.location = Point(lon, lat)
            profile.save()

            # Create DriverProfile
            driver_profile, created = DriverProfile.objects.get_or_create(
                user=user,
                defaults={
                    "national_id": national_id,
                    "driver_license": driver_license
                }
            )
            if not created:
                driver_profile.national_id = national_id
                driver_profile.driver_license = driver_license
                driver_profile.save()

            # Create Vehicle
            Vehicle.objects.create(
                driver=driver_profile,
                vehicle_type=vehicle_type,
                plate_number=vehicle_data["plate_number"],
                capacity_weight=vehicle_type.max_weight,
                capacity_volume=vehicle_type.max_volume,
                verification_status=False
            )

        return user