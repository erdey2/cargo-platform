from firebase_admin import messaging


def send_fcm_message(tokens, notification):
    if not tokens:
        return None

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title="Online Car Market",
            body=notification.message or "You have a new notification.",
        ),
        data={k: str(v) for k, v in (notification.data or {}).items()},
        tokens=tokens
    )
    response = messaging.send_multicast(message)
    return response