from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Notification(models.Model):
    # recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    message = models.TextField(null=True, blank=True)
    data = models.JSONField(default=dict, blank=True)  # for structured info
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Notification to {self.recipient}: {self.message[:50]}"

class Device(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    fcm_token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=32, choices=(('web','web'),('android','android'),('ios','ios')))
    created_at = models.DateTimeField(auto_now_add=True)

class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email = models.BooleanField(default=True)
    push = models.BooleanField(default=True)
    in_app = models.BooleanField(default=True)
