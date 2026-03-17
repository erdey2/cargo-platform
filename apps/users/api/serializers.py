from rest_framework import serializers
from apps.users.models import User
from dj_rest_auth.serializers import LoginSerializer

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "phone", "password", "role"]

    def create(self, validated_data):
        role = validated_data.get("role")

        # SECURITY: prevent admin creation
        if role not in ["customer", "driver"]:
            role = "customer"

        user = User.objects.create_user(
            email=validated_data["email"],
            phone=validated_data["phone"],
            password=validated_data["password"],
            role=role,
        )
        return user

class CustomLoginSerializer(LoginSerializer):
    username = None  # remove username
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        attrs["username"] = attrs.get("email")  # map email → username
        return super().validate(attrs)

class CustomRegisterSerializer(RegisterSerializer):
    username = None  # remove username
    phone = serializers.CharField(required=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default="customer")

    def get_cleaned_data(self):
        data = super().get_cleaned_data()
        data["phone"] = self.validated_data.get("phone", "")
        data["role"] = self.validated_data.get("role", "customer")
        return data

    def save(self, request):
        user = super().save(request)

        user.phone = self.validated_data.get("phone")
        user.role = self.validated_data.get("role", "customer")
        user.save()

        return user