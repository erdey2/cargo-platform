# Twilio Delivery Webhook Handler

## Overview

The Twilio delivery webhook handler receives SMS delivery status notifications from Twilio and records them in the database. This allows you to:
- Track whether OTP messages were successfully delivered
- Capture delivery errors and retry logic
- Audit SMS delivery for disputes
- Monitor OTP send success rates

## Setup

### 1. Configure Twilio Credentials

Set the following environment variables:

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+15551234567
```

Or in Django settings:

```python
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")
```

### 2. Run Migrations

```bash
python manage.py migrate
```

This creates:
- `ShipmentPODOTP` model (if not already created)
- `TwilioDeliveryReceipt` model for storing webhook receipts

### 3. Configure Webhook in Twilio Console

In your Twilio account:
1. Go to **Messaging** → **Settings** → **Webhooks**
2. Set the **Status Callback URL** to:
   ```
   https://your-domain.com/api/webhooks/twilio/
   ```
3. Choose **POST** method
4. Save

## How It Works

### OTP Sending Flow

1. Customer requests OTP via `POST /api/pod-otp/send/`
2. System generates a 6-digit code with 5-minute TTL
3. SMS is sent via Twilio (if configured) or printed (if not configured)
4. **Twilio message SID is stored in OTP metadata** for webhook linkage

### Webhook Receiving Flow

1. Twilio sends POST to `/api/webhooks/twilio/` with:
   - `MessageSid`: Twilio unique message identifier
   - `MessageStatus`: delivery status (queued, sent, delivered, undelivered, failed)
   - `ErrorCode` (optional): error code if failed
   - `ErrorMessage` (optional): error description
   - `X-Twilio-Signature` header: signature for validation

2. Server validates the Twilio signature using the `TWILIO_AUTH_TOKEN`

3. If valid, server:
   - Finds the OTP record by matching the message SID
   - Creates/updates a `TwilioDeliveryReceipt` record
   - Stores the delivery status and any error codes

4. Returns 200 OK to Twilio

## API Endpoints

### Send OTP

```http
POST /api/pod-otp/send/
Content-Type: application/json
Authorization: Bearer <token>

{
  "pod_id": 123,
  "phone": "+251900000000"  # optional; uses shipment.recipient_phone if not provided
}
```

**Response:**
```json
{
  "otp_id": 456,
  "expires_at": "2026-06-02T12:34:56Z"
}
```

### Verify OTP

```http
POST /api/pod-otp/verify/
Content-Type: application/json
Authorization: Bearer <token>

{
  "pod_id": 123,
  "code": "123456"
}
```

**Response:**
```json
{
  "detail": "POD confirmed via OTP",
  "pod_id": 123
}
```

### Twilio Webhook (Automatic)

```http
POST /api/webhooks/twilio/
Content-Type: application/x-www-form-urlencoded
X-Twilio-Signature: <signature>

MessageSid=SMxxx&MessageStatus=delivered&ErrorCode=&...
```

**Response:**
```json
{
  "detail": "Webhook processed",
  "receipt_id": 789
}
```

## Delivery Receipt Model

Stored in `TwilioDeliveryReceipt`:

```python
{
  "id": 789,
  "otp_id": 456,  # Links back to ShipmentPODOTP
  "message_sid": "SMxxx",
  "status": "delivered",  # queued, sent, delivered, undelivered, failed
  "error_code": None,
  "error_message": "",
  "raw_webhook_data": {...},  # Full webhook data for audit
  "created_at": "2026-06-02T12:34:56Z",
  "updated_at": "2026-06-02T12:34:56Z"
}
```

## Delivery Status Codes

- **queued**: Message is queued for delivery
- **sent**: Message left Twilio's platform
- **delivered**: Message was delivered to the recipient
- **undelivered**: Twilio was unable to deliver the message
- **failed**: Message delivery failed (usually due to invalid number or network issue)

## Error Handling

### Signature Validation Fails

If the signature validation fails, the endpoint returns:
```json
HTTP 403 Forbidden
{
  "detail": "Invalid signature"
}
```

This could mean:
- The request didn't come from Twilio
- The `TWILIO_AUTH_TOKEN` is incorrect
- Someone is trying to forge a delivery receipt

### OTP Not Found

If the message SID doesn't match any OTP, the webhook is processed but logged:
```
[Twilio] Could not find OTP for message SID SMxxx
```

This could happen if:
- OTP has already been verified and marked as used
- OTP was created outside Twilio (e.g., in development)
- There's a sync issue between OTP storage and webhook receipt

### Missing Twilio Credentials

In development, if `TWILIO_*` settings are not configured:
- SMS sending falls back to printing: `[SMS] To=<number> Message=<text>`
- Webhook signature validation is skipped (returns True)
- Tests don't require Twilio credentials

## Testing

Run the test suite:

```bash
python manage.py test apps.shipments.tests.ShipmentProofOfDeliveryTests
```

Tests include:
- `test_twilio_is_used_when_configured`: Verifies Twilio client is called with correct credentials (mocked)
- `test_twilio_delivery_webhook_with_invalid_signature`: Ensures invalid signatures are rejected
- `test_twilio_delivery_webhook_processes_status`: Verifies delivery status is recorded
- `test_twilio_delivery_webhook_handles_failed_status`: Tests failure status with error codes

## Monitoring

### View Delivery Receipts

```python
from apps.shipments.models import TwilioDeliveryReceipt

# All receipts for an OTP
receipts = TwilioDeliveryReceipt.objects.filter(otp_id=456)

# Failed deliveries
failed = TwilioDeliveryReceipt.objects.filter(status="failed")

# Filter by status
delivered = TwilioDeliveryReceipt.objects.filter(status="delivered")
```

### Django Admin

Add to `apps/shipments/admin.py`:

```python
from apps.shipments.models import ShipmentPODOTP, TwilioDeliveryReceipt

admin.site.register(ShipmentPODOTP)
admin.site.register(TwilioDeliveryReceipt)
```

## Security Considerations

1. **Signature Validation**: Always enabled if `TWILIO_AUTH_TOKEN` is configured
2. **Single-Use Tokens**: OTP codes can only be verified once (`used` flag)
3. **Token Expiry**: OTPs expire after the configured TTL (default 5 minutes)
4. **Rate Limiting**: Consider adding throttles to `/pod-otp/send/` and `/pod-otp/verify/` to prevent abuse
5. **HTTPS Required**: Webhook endpoint should only accept HTTPS to prevent MITM attacks

## Troubleshooting

### Webhook Not Received

1. Verify the webhook URL is correct in Twilio console
2. Check firewall/network allows inbound traffic on the webhook port
3. Verify SSL certificate is valid (if using HTTPS)
4. Check Twilio logs in the console for failed webhook attempts

### Signature Validation Fails

1. Verify `TWILIO_AUTH_TOKEN` is set correctly (no extra spaces)
2. Ensure the webhook URL in Twilio console exactly matches the endpoint

### OTP Not Found When Webhook Arrives

1. Check if OTP was marked as used/verified (can only have one delivery receipt)
2. Verify message SID is being stored in OTP metadata during creation
3. Check OTP TTL hasn't expired

### SMS Not Sending

1. Check Twilio credentials are set and valid
2. Verify phone number format is correct (E.164 format: +country_code_phone_number)
3. Check Twilio account balance and permissions
4. Review Twilio console error logs

## Next Steps

- Implement rate limiting on OTP endpoints
- Add admin dashboard to view delivery metrics
- Create retry logic for failed deliveries
- Add SMS template management for different languages
- Integrate additional SMS providers (Africa's Talking, etc.) as fallback

