import hashlib
import hmac
from base64 import b64encode
from urllib.parse import urlencode

from django.conf import settings


def validate_twilio_signature(request, webhook_action_url):
    """Validate that the request came from Twilio using the X-Twilio-Signature header.

    Args:
        request: Django request object
        webhook_action_url: full URL endpoint that received the webhook

    Returns:
        True if signature is valid, False otherwise
    """
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    if not auth_token:
        # If no auth token configured, skip validation (dev mode)
        return True

    twilio_signature = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
    if not twilio_signature:
        return False

    # Twilio signature validation:
    # 1. Take the full URL of the request
    # 2. If the request is a POST, sort the POST parameters by key
    # 3. Append the parameters to the URL as a query string (in sorted order)
    # 4. Take the auth token and sign the resulting string with HMAC-SHA1
    # 5. Base64 encode the resulting hash value
    # 6. Compare it to the X-Twilio-Signature header value from Twilio

    # Start with the URL
    url = webhook_action_url

    # Get parameters (POST for webhook)
    params = request.POST.dict() if request.method == "POST" else {}

    # Sort and append to URL
    if params:
        sorted_params = sorted(params.items())
        url = url + urlencode(sorted_params)

    # Sign with auth token
    mac = hmac.new(
        auth_token.encode("utf-8"),
        url.encode("utf-8"),
        hashlib.sha1
    )
    expected_signature = b64encode(mac.digest()).decode("utf-8")

    return hmac.compare_digest(expected_signature, twilio_signature)


def process_twilio_delivery_webhook(message_sid, status, error_code=None, error_message=None, webhook_data=None):
    """Process a Twilio delivery status webhook and update the OTP record.

    Args:
        message_sid: Twilio message SID
        status: delivery status (delivered, failed, undelivered, queued, sent)
        error_code: optional error code from Twilio
        error_message: optional error message from Twilio
        webhook_data: raw webhook data for audit
    """
    from apps.shipments.models import ShipmentPODOTP, TwilioDeliveryReceipt

    # Find the OTP that sent this message by looking up the message SID in metadata
    # We store it as "twilio_message_sid" key during OTP creation
    otp = None
    for otp_record in ShipmentPODOTP.objects.filter(used=False).order_by("-created_at")[:100]:
        if otp_record.metadata and otp_record.metadata.get("twilio_message_sid") == message_sid:
            otp = otp_record
            break

    if not otp:
        # Could not find OTP for this message, just log (or create orphan receipt)
        print(f"[Twilio] Could not find OTP for message SID {message_sid}")
        return None


    # Create or update delivery receipt
    receipt, created = TwilioDeliveryReceipt.objects.get_or_create(
        otp=otp,
        message_sid=message_sid,
        defaults={
            "status": status,
            "error_code": error_code,
            "error_message": error_message or "",
            "raw_webhook_data": webhook_data or {},
        }
    )

    if not created:
        # Update existing receipt
        receipt.status = status
        receipt.error_code = error_code
        receipt.error_message = error_message or ""
        receipt.raw_webhook_data = webhook_data or {}
        receipt.save()

    return receipt


