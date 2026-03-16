import re, bleach
from rest_framework import serializers
from dj_rest_auth.serializers import LoginSerializer
from django.contrib.auth import get_user_model
from rolepermissions.checkers import has_role
from dj_rest_auth.registration.serializers import RegisterSerializer

User = get_user_model()
class CustomLoginSerializer(LoginSerializer):
    username = None
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        return super().validate(attrs)

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=50, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'confirm_password', 'first_name', 'last_name', 'description']
        extra_kwargs = {
            'email': {'required': True},
        }

    def validate_email(self, value):
        cleaned = bleach.clean(value.strip(), tags=[], strip=True)
        if User.objects.filter(email=cleaned).exists():
            raise serializers.ValidationError("This email is already in use.")
        return cleaned

    def validate_password(self, value):
        cleaned = bleach.clean(value.strip(), tags=[], strip=True)
        if not any(char.isupper() for char in cleaned):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        if not any(char.isdigit() for char in cleaned):
            raise serializers.ValidationError("Password must contain at least one digit.")
        return cleaned

    def validate_description(self, value):
        if value:
            cleaned = bleach.clean(value.strip(), tags=[], strip=True)
            if len(cleaned) > 500:
                raise serializers.ValidationError("Description cannot exceed 500 characters.")
            return cleaned
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data

class UserMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='profile.get_full_name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name']

class CustomRegisterSerializer(RegisterSerializer):
    username = None
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=50, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=50, required=False, allow_blank=True)

    @property
    def _has_phone_field(self):
        return False

    def validate_email(self, value):
        cleaned = bleach.clean(value.strip(), tags=[], strip=True)
        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(email_regex, cleaned):
            raise serializers.ValidationError("Email must be a valid email address.")
        if len(cleaned) > 254:
            raise serializers.ValidationError("Email cannot exceed 254 characters.")
        if User.objects.filter(email=cleaned).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return cleaned

    def validate_description(self, value):
        if value:
            cleaned = bleach.clean(value.strip(), tags=[], strip=True)
            if len(cleaned) > 500:
                raise serializers.ValidationError("Description cannot exceed 500 characters.")
            return cleaned
        return value

    def validate(self, data):
        user = self.context['request'].user
        if user.is_authenticated and not has_role(user, ['super_admin', 'admin']) and not user.is_superuser:
            raise serializers.ValidationError("Only super admins or admins can create users via this endpoint.")
        return data