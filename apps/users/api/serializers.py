from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import LoginSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..models import Profile
from django.contrib.gis.geos import Point

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

class CustomLoginSerializer(LoginSerializer):
    username = None
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        return super().validate(attrs)

from rest_framework import serializers
from django.contrib.gis.geos import Point
from ..models import Profile


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