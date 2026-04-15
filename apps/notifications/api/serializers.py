from rest_framework import serializers
from ..models import Notification, Device, NotificationPreference

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'recipient', 'message', 'data', 'is_read', 'created_at']
        read_only_fields = ['id', 'recipient', 'created_at']

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ('id','fcm_token','platform')


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ["id", "email", "push", "in_app"]
        read_only_fields = ["id"]