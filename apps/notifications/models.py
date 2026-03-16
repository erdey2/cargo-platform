from django.db import models
from core.models import BaseModel
from apps.users.models import User

class Notification(BaseModel):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    title = models.CharField(max_length=255)

    message = models.TextField()

    is_read = models.BooleanField(default=False)
