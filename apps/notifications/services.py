from django.db import transaction
from firebase_admin import messaging
import logging

from .models import Notification, NotificationPreference, Device
from .tasks import deliver_notification

logger = logging.getLogger(__name__)

def notify_user(user, message: str, data: dict = None, title: str = None):
    """
    Creates in-app notification AND sends FCM push if user allows it.
    """
    if data is None:
        data = {}

    if title is None:
        title = "Online Car Market"  # ← change to your app name

    # Create in-app notification (inside transaction)
    with transaction.atomic():
        notification = Notification.objects.create(
            recipient=user,
            message=message,
            data=data,
        )

    # Send push asynchronously so request latency stays DB-bound.
    try:
        deliver_notification.delay(notification.id, ["push"])
    except Exception as e:
        # Fallback to sync push if broker is unavailable.
        logger.warning("Celery dispatch failed, falling back to sync push: %s", e, exc_info=True)
        try:
            _send_fcm_push(user, title, message, data, notification.id)
        except Exception as push_error:
            # Never let push failure break the business flow
            logger.error("FCM push failed for user %s: %s", user.id, push_error, exc_info=True)

    return notification


def _send_fcm_push(user, title: str, body: str, data: dict, notification_id: int):
    """Internal helper - sends to all user's devices"""
    # Respect user preference
    pref, _ = NotificationPreference.objects.get_or_create(
        user=user,
        defaults={'push': True, 'in_app': True, 'email': True}
    )
    if not pref.push:
        return

    # Get all registered devices
    devices = Device.objects.filter(user=user).values_list('fcm_token', flat=True)
    tokens = list(devices)
    if not tokens:
        return

    # FCM data payload MUST have string values
    push_data = {k: str(v) for k, v in data.items()}
    push_data.update({
        "notification_id": str(notification_id),
        "type": push_data.get("type", "general"),
        "click_action": "FLUTTER_NOTIFICATION_CLICK"  # useful for Flutter/React Native
    })

    multicast_message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=push_data,
        tokens=tokens,
    )

    response = messaging.send_multicast(multicast_message)

    # Clean up invalid tokens automatically (very important!)
    for idx, resp in enumerate(response.responses):
        if not resp.success:
            err = resp.exception
            if err and (
                err.code in ("UNREGISTERED", "INVALID_ARGUMENT", "NOT_FOUND") or
                "registration-token-not-registered" in str(err).lower()
            ):
                bad_token = tokens[idx]
                Device.objects.filter(fcm_token=bad_token).delete()
                logger.info(f"Removed invalid FCM token for user {user.id}")

    logger.info(
        f"FCM sent to user {user.id} | Success: {response.success_count}/{response.failure_count}"
    )