import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.matching.models import DriverOffer
from django.contrib.auth import get_user_model
from .models import Notification
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

User = get_user_model()

logger = logging.getLogger(__name__)

""" @receiver(post_save, sender=Car)
def notify_new_car(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "cars",
            {
                "type": "new_car",
                "car_id": instance.id,
            }
        )
    except Exception as e:
        logger.warning(f"Redis notification failed: {e}")



    channel_layer = get_channel_layer()
    if channel_layer is None:
        print("Channel layer not configured")
        return

    admin_users = User.objects.filter(is_superuser=True)

    for user in admin_users:
        n = Notification.objects.create(recipient=user, message=f"A new car '{instance.vin}' has been posted." )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "send_notification",
                "data": {
                    "id": n.id,
                    "message": n.message,
                    "created_at": str(n.created_at)
                }
            }
        )

@receiver(post_save, sender=Bid)
def notify_seller_on_bid(sender, instance, created, **kwargs):
    if not created:
        return

    car = instance.car
    seller = car.user

    notification = Notification.objects.create(
        recipient=seller,
        actor=instance.user,
        verb="placed a bid",
        description=f"New bid of {instance.amount} on {car}",
        data={
            "car_id": car.id,
            "bid_id": instance.id,
            "amount": str(instance.amount),
        }
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{seller.id}",
        {
            "type": "send_notification",
            "data": {
                "id": notification.id,
                "message": notification.description,
                "created_at": notification.created_at.isoformat(),
            }
        }
    ) """