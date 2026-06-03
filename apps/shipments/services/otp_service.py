from datetime import timedelta
import random

from django.conf import settings


def generate_otp_code(length=6):
    # numeric code
    start = 10 ** (length - 1)
    end = (10 ** length) - 1
    return str(random.randint(start, end))


def send_sms(phone: str, message: str):
    """Send SMS using Twilio when configured, otherwise fallback to stdout.

    Configuration (set these in Django settings or env):
    - TWILIO_ACCOUNT_SID
    - TWILIO_AUTH_TOKEN
    - TWILIO_FROM_NUMBER

    For tests this function can be patched or Twilio Client can be mocked.
    """
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", None)

    if account_sid and auth_token and from_number:
        try:
            # import here so tests can patch twilio.rest.Client
            from twilio.rest import Client

            client = Client(account_sid, auth_token)
            msg = client.messages.create(body=message, from_=from_number, to=phone)
            return msg.sid  # Return the message SID for webhook linking
        except Exception as exc:
            # fall back to printing but surface the error in logs
            print(f"[SMS][Twilio Error] {exc}; falling back to stdout")

    # Fallback (development / tests without Twilio configured) - return None
    print(f"[SMS] To={phone} Message={message}")
    return None


def default_otp_ttl_seconds():
    return getattr(settings, "POD_OTP_TTL_SECONDS", 300)  # 5 minutes


def default_otp_resend_max():
    return getattr(settings, "POD_OTP_RESEND_MAX", 3)  # Max 3 resends (+ original = 4 total)


def default_otp_resend_delay_seconds():
    return getattr(settings, "POD_OTP_RESEND_DELAY_SECONDS", 60)  # Min 60 seconds between sends


def create_and_send_otp(pod, phone, code=None, ttl_seconds=None):
    from apps.shipments.models import ShipmentPODOTP
    from django.utils import timezone

    ttl_seconds = ttl_seconds or default_otp_ttl_seconds()
    code = code or generate_otp_code()
    expires_at = timezone.now() + timedelta(seconds=ttl_seconds)

    otp = ShipmentPODOTP.objects.create(
        pod=pod,
        phone=phone,
        code=code,
        expires_at=expires_at,
    )

    # send SMS and capture message SID for webhook linking
    message = f"Your delivery confirmation code is: {code}. It expires in {ttl_seconds//60} minutes."
    message_sid = send_sms(phone, message)
    if message_sid:
        if not otp.metadata:
            otp.metadata = {}
        otp.metadata["twilio_message_sid"] = message_sid
        otp.save(update_fields=["metadata"])

    # Update POD to track last OTP send time
    pod.last_otp_sent_at = timezone.now()
    pod.save(update_fields=["last_otp_sent_at"])

    return otp

