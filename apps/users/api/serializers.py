from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import LoginSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model

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