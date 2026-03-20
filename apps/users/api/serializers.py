from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import LoginSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import Profile
from django.contrib.gis.geos import Point
from apps.drivers.models import DriverProfile
from apps.vehicles.models import Vehicle, VehicleType

User = get_user_model()

class CustomRegisterSerializer(RegisterSerializer):
    username = None
    phone = serializers.CharField(required=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)

    @property
    def _has_phone_field(self):
        return False

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Phone already exists.")
        return value

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data["phone"] = self.validated_data.get("phone")
        data["role"] = self.validated_data.get("role")
        return data

    def save(self, request):
        user = super().save(request)
        user.phone = self.validated_data.get("phone")
        user.role = self.validated_data.get("role")

        user.save()
        return user

class CustomLoginSerializer(LoginSerializer):
    username = None
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        return super().validate(attrs)

class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    latitude_input = serializers.FloatField(write_only=True, required=False)
    longitude_input = serializers.FloatField(write_only=True, required=False)

    class Meta:
        model = Profile
        fields = [
            "id",
            "email",
            "role",
            "full_name",
            "profile_image",
            "address",
            "city",
            "country",
            "location",
            "latitude",
            "longitude",
            "latitude_input",
            "longitude_input"
        ]
        read_only_fields = ["location"]

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

    def update(self, instance, validated_data):
        lat = validated_data.pop("latitude_input", None)
        lng = validated_data.pop("longitude_input", None)

        # update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # update location
        if lat is not None and lng is not None:
            instance.location = Point(lng, lat)

        instance.save()
        return instance

class CustomerRegisterSerializer(RegisterSerializer):
    username = None
    phone = serializers.CharField(required=True)
    full_name = serializers.CharField(required=True)
    address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=False, allow_blank=True)
    latitude_input = serializers.FloatField(write_only=True, required=False)
    longitude_input = serializers.FloatField(write_only=True, required=False)

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data.update({
            "phone": self.validated_data.get("phone"),
            "full_name": self.validated_data.get("full_name"),
            "address": self.validated_data.get("address"),
            "city": self.validated_data.get("city"),
            "country": self.validated_data.get("country"),
            "latitude_input": self.validated_data.get("latitude_input"),
            "longitude_input": self.validated_data.get("longitude_input"),
        })
        return data

    def save(self, request):
        user = super().save(request)
        user.phone = self.validated_data.get("phone")
        user.role = "customer"  # force role
        user.save()

        profile = user.profile
        profile.full_name = self.validated_data.get("full_name")
        profile.address = self.validated_data.get("address", "")
        profile.city = self.validated_data.get("city", "")
        profile.country = self.validated_data.get("country", "")
        lat = self.validated_data.get("latitude_input")
        lng = self.validated_data.get("longitude_input")
        if lat is not None and lng is not None:
            profile.location = Point(lng, lat)
        profile.save()
        return user

class VehicleNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ["plate_number", "vehicle_type"]

class DriverRegisterSerializer(RegisterSerializer):
    username = None
    phone = serializers.CharField(required=True)
    full_name = serializers.CharField(required=True)
    address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=False, allow_blank=True)
    latitude_input = serializers.FloatField(write_only=True, required=False)
    longitude_input = serializers.FloatField(write_only=True, required=False)
    national_id = serializers.CharField(required=True)
    driver_license = serializers.CharField(required=True)
    vehicle = VehicleNestedSerializer(required=True)

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data.update({
            "phone": self.validated_data.get("phone"),
            "full_name": self.validated_data.get("full_name"),
            "address": self.validated_data.get("address"),
            "city": self.validated_data.get("city"),
            "country": self.validated_data.get("country"),
            "latitude_input": self.validated_data.get("latitude_input"),
            "longitude_input": self.validated_data.get("longitude_input"),
            "national_id": self.validated_data.get("national_id"),
            "driver_license": self.validated_data.get("driver_license"),
            "vehicle": self.validated_data.get("vehicle")
        })
        return data

    def save(self, request):
        from django.db import transaction
        data = self.get_cleaned_data()
        vehicle_data = data.pop("vehicle")
        vehicle_type = vehicle_data["vehicle_type"]

        with transaction.atomic():
            # 1️⃣ Create User
            user = super().save(request)
            user.phone = data["phone"]
            user.role = "driver"
            user.save()

            # 2️⃣ Update Profile
            profile = user.profile
            profile.full_name = data.get("full_name")
            profile.address = data.get("address", "")
            profile.city = data.get("city", "")
            profile.country = data.get("country", "")
            lat = data.get("latitude_input")
            lng = data.get("longitude_input")
            if lat is not None and lng is not None:
                profile.location = Point(lng, lat)
            profile.save()

            # 3️⃣ Create DriverProfile
            driver_profile, _ = DriverProfile.objects.get_or_create(
                user=user,
                defaults={
                    "national_id": data["national_id"],
                    "driver_license": data["driver_license"]
                }
            )
            # 4️⃣ Create Vehicle
            Vehicle.objects.create(
                driver=driver_profile,
                vehicle_type=vehicle_type,
                plate_number=vehicle_data["plate_number"],
                capacity_weight=vehicle_type.max_weight,
                capacity_volume=vehicle_type.max_volume,
                verification_status=False
            )

        return user
