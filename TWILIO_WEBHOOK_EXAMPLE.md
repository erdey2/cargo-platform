# Twilio Delivery Webhook - Quick Example

## Real-World Workflow

### Scenario

A driver delivers a package and confirms the delivery using OTP. Here's step-by-step what happens:

### 1. Driver Uploads Proof of Delivery

**cURL:**
```bash
curl -X POST http://localhost:8000/api/shipment-proof-of-delivery/ \
  -H "Authorization: Bearer <driver_token>" \
  -F "shipment=123" \
  -F "photo=@/path/to/delivery.jpg" \
  -F "gps_latitude=9.0505" \
  -F "gps_longitude=38.7605" \
  -F "gps_accuracy_meters=15"
```

**Response:**
```json
{
  "id": 456,
  "image_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "gps_verified": true,
  "gps_distance_to_dropoff_meters": 45.2,
  "is_duplicate": false,
  "customer_confirmed": false,
  "confirmation_status": "pending"
}
```

### 2. System Initiates OTP

**Customer requests OTP:**
```bash
curl -X POST http://localhost:8000/api/pod-otp/send/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <customer_token>" \
  -d '{
    "pod_id": 456,
    "phone": "+251900000000"
  }'
```

**Django calls `send_sms()`:**
- If Twilio configured: Sends via Twilio API, returns message SID
- If not configured: Prints to console: `[SMS] To=+251900000000 Message=Your delivery confirmation code is: 123456. It expires in 5 minutes.`

**OTP stored in DB:**
```python
ShipmentPODOTP(
  id=789,
  pod_id=456,
  phone="+251900000000",
  code="123456",
  expires_at="2026-06-02T12:05:00Z",
  metadata={"twilio_message_sid": "SMxxx123xyz"}  # Only if Twilio sent it
)
```

**Response:**
```json
{
  "otp_id": 789,
  "expires_at": "2026-06-02T12:05:00Z"
}
```

### 3. Twilio Sends the SMS

Twilio's API returns:
```json
{
  "sid": "SMxxx123xyz",
  "status": "queued",
  "to": "+251900000000",
  ...
}
```

If Twilio fails to send:
```json
{
  "error_code": "21211",
  "error_message": "The number +251900000000 is not a valid phone number."
}
```

### 4. Twilio Forwards Delivery Updates

Over the next few seconds, Twilio makes POST requests to your webhook:

#### 4a. Message Queued
```
POST /api/webhooks/twilio/
X-Twilio-Signature: <computed_signature>

MessageSid=SMxxx123xyz&MessageStatus=queued
```

**Server Response:**
```json
{
  "detail": "Webhook processed",
  "receipt_id": 100
}
```

**DB Updated:**
```python
TwilioDeliveryReceipt(
  id=100,
  otp_id=789,
  message_sid="SMxxx123xyz",
  status="queued"
)
```

#### 4b. Message Sent
```
POST /api/webhooks/twilio/
X-Twilio-Signature: <computed_signature>

MessageSid=SMxxx123xyz&MessageStatus=sent
```

**DB Updated:**
```python
# Receipt(id=100) updated to status="sent"
```

#### 4c. Message Delivered
```
POST /api/webhooks/twilio/
X-Twilio-Signature: <computed_signature>

MessageSid=SMxxx123xyz&MessageStatus=delivered
```

**DB Updated:**
```python
# Receipt(id=100) updated to status="delivered"
```

**Customer receives SMS:**
```
Your delivery confirmation code is: 123456. It expires in 5 minutes.
```

#### 4d. (If Failed)
```
POST /api/webhooks/twilio/
X-Twilio-Signature: <computed_signature>

MessageSid=SMxxx123xyz&MessageStatus=failed&ErrorCode=21211&ErrorMessage=Invalid+number
```

**DB Updated:**
```python
TwilioDeliveryReceipt(
  id=100,
  status="failed",
  error_code="21211",
  error_message="Invalid number"
)
```

### 5. Customer Receives Code & Verifies

**Customer enters code in app and submits:**
```bash
curl -X POST http://localhost:8000/api/pod-otp/verify/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <customer_token>" \
  -d '{
    "pod_id": 456,
    "code": "123456"
  }'
```

**Server validates:**
- ✅ OTP exists for pod_id=456
- ✅ Code matches ("123456")
- ✅ Not expired (created 2 min ago, expires in 3 min)
- ✅ Not already used

**OTP marked as used:**
```python
ShipmentPODOTP(id=789, used=True, attempts=1)
```

**POD marked as confirmed:**
```python
ShipmentProofOfDelivery(
  id=456,
  customer_confirmed=True,
  customer_confirmed_at="2026-06-02T12:02:00Z",
  customer_confirmation_method="otp"
)
```

**Response:**
```json
{
  "detail": "POD confirmed via OTP",
  "pod_id": 456
}
```

### 6. Support Dashboard View

Later, support staff queries the POD:
```bash
curl -X GET "http://localhost:8000/api/shipments/123/proof-of-delivery/" \
  -H "Authorization: Bearer <staff_token>"
```

**Response shows full audit trail:**
```json
[
  {
    "id": 456,
    "shipment": {
      "id": 123,
      "status": "delivered",
      "pickup_address": "...",
      "dropoff_address": "..."
    },
    "uploaded_by": {
      "id": 2,
      "email": "driver@example.com",
      "role": "driver"
    },
    "photo_url": "https://cdn.example.com/shipment_proofs/pod.jpg",
    "image_sha256": "e3b0c44...",
    "gps_latitude": 9.0505,
    "gps_longitude": 38.7605,
    "gps_verified": true,
    "gps_distance_to_dropoff_meters": 45.2,
    "is_duplicate": false,
    "customer_confirmed": true,
    "customer_confirmed_at": "2026-06-02T12:02:00Z",
    "customer_confirmation_method": "otp",
    "confirmation_status": "confirmed",
    "verification_notes": "GPS distance to dropoff: 45.20m (verified=true)"
  }
]
```

### 7. (Optional) Query Delivery Receipt Details

```bash
curl -X GET "http://localhost:8000/admin/shipments/twiliodeliveryreceipt/100/" \
  -H "Authorization: Bearer <staff_token>"
```

**Shows:**
```json
{
  "id": 100,
  "otp_id": 789,
  "message_sid": "SMxxx123xyz",
  "status": "delivered",
  "error_code": null,
  "error_message": "",
  "raw_webhook_data": {
    "MessageSid": "SMxxx123xyz",
    "MessageStatus": "delivered",
    "AccountSid": "ACxxx...",
    "From": "+15551234567",
    "To": "+251900000000",
    "SmsStatus": "received",
    ...
  },
  "created_at": "2026-06-02T12:00:05Z",
  "updated_at": "2026-06-02T12:00:15Z"
}
```

---

## Key Points

### OTP Metadata Storage
```python
otp.metadata = {
  "twilio_message_sid": "SMxxx123xyz"  # Allows webhook to find the OTP
}
```

### Twilio Signature Validation
Each webhook is signed with HMAC-SHA1 using your `TWILIO_AUTH_TOKEN`. Server validates:
1. Takes URL + POST parameters
2. Signs with token
3. Compares to `X-Twilio-Signature` header
4. Rejects if mismatch (prevents forgery)

### Error Scenarios

**Invalid signature:**
```
Server: Rejects webhook, returns 403
Twilio: Retries up to 3 times, then gives up
```

**Code expired:**
```
OTP database shows expires_at < now()
Server: Rejects verification, returns 400
Customer: Must request new OTP
```

**Code already used:**
```
OTP.used = True (set after first successful verification)
Server: Rejects re-verification, returns 400
```

**Phone number invalid:**
```
Twilio API returns error code 21211
Webhook received with status="failed", error_code="21211"
Support can see in TwilioDeliveryReceipt
```

---

## Testing Without Twilio

If Twilio not configured:

```bash
# OTP send falls back to printing
[SMS] To=+251900000000 Message=Your delivery confirmation code is: 123456...

# Webhook signature validation skipped (returns True)
# Tests use DB-stored codes directly
```

Run tests:
```bash
python manage.py test apps.shipments.tests.ShipmentProofOfDeliveryTests.test_twilio_delivery_webhook_processes_status
```

---

## Monitoring Script

```python
# Check delivery success rates
from apps.shipments.models import TwilioDeliveryReceipt

receipts = TwilioDeliveryReceipt.objects.all()

delivered = receipts.filter(status="delivered").count()
failed = receipts.filter(status="failed").count()
undelivered = receipts.filter(status="undelivered").count()
queued = receipts.filter(status="queued").count()
sent = receipts.filter(status="sent").count()

total = delivered + failed + undelivered + queued + sent

print(f"Total: {total}")
print(f"Delivered: {delivered} ({100*delivered/total:.1f}%)")
print(f"Failed: {failed} ({100*failed/total:.1f}%)")
print(f"Undelivered: {undelivered} ({100*undelivered/total:.1f}%)")
print(f"Queued: {queued} ({100*queued/total:.1f}%)")
print(f"Sent: {sent} ({100*sent/total:.1f}%)")
```

