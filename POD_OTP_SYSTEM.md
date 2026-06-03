# Proof of Delivery (POD) with OTP Confirmation System

## Overview

This system implements a multi-layered proof-of-delivery mechanism that combines:
1. **Photo-based delivery proof** - Driver uploads photo with GPS metadata
2. **Hash-based duplicate detection** - SHA-256 fingerprinting + Haversine distance verification
3. **OTP-based customer confirmation** - One-time password sent via SMS
4. **Twilio delivery tracking** - Webhook receipts for SMS delivery status
5. **Support dashboard** - Clean, dashboard-friendly API responses

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Proof of Delivery Flow                        │
└─────────────────────────────────────────────────────────────────┘

1. Driver Uploads POD
   └─ POST /api/shipment-proof-of-delivery/
      ├─ Photo (multipart)
      ├─ GPS coordinates (optional)
      └─ Generates SHA-256 hash

2. System Verifies POD
   ├─ GPS distance check (against shipment dropoff)
   ├─ Duplicate detection (hash comparison)
   └─ Metadata collection (hash, GPS accuracy, etc.)

3. Customer Confirms via OTP
   ├─ POST /api/pod-otp/send/ → Generate OTP
   ├─ SMS sent via Twilio
   └─ OTP stored in DB with message SID

4. Twilio Sends Delivery Receipt
   ├─ POST /api/webhooks/twilio/ → Webhook callback
   ├─ Signature validated
   └─ Receipt stored (delivered/failed/etc.)

5. Customer Verifies Code
   ├─ POST /api/pod-otp/verify/ → Submit code
   ├─ Code validated (not expired, not used)
   └─ POD marked confirmed

6. Support Dashboard
   └─ GET /api/shipments/{id}/proof-of-delivery/
      └─ List all PODs with delivery metadata
```

## Database Schema

```
Shipment
├─ id, customer_id, driver_id, status, recipient_phone, ...
├─ pickup_location (GPS)
└─ dropoff_location (GPS)

ShipmentProofOfDelivery
├─ id, shipment_id, uploaded_by_id, photo
├─ image_sha256 (hash)
├─ gps_location, gps_verified, gps_distance_to_dropoff_meters
├─ is_duplicate, duplicate_of_id
├─ customer_confirmed, customer_confirmed_at, customer_confirmation_method
└─ verification_notes, metadata

ShipmentPODOTP
├─ id, pod_id, phone, code, expires_at
├─ attempts, used
└─ metadata (stores twilio_message_sid)

TwilioDeliveryReceipt
├─ id, otp_id, message_sid
├─ status (queued/sent/delivered/undelivered/failed)
├─ error_code, error_message
└─ raw_webhook_data
```

## API Endpoints

### 1. Upload Proof of Delivery

```http
POST /api/shipment-proof-of-delivery/
Content-Type: multipart/form-data
Authorization: Bearer <customer_or_driver_token>

{
  "shipment": 123,
  "photo": <file>,
  "gps_latitude": 9.0505,
  "gps_longitude": 38.7605,
  "gps_accuracy_meters": 12,
  "confirmation_method": "otp"  # optional
}
```

**Response (201 Created):**
```json
{
  "id": 456,
  "shipment": {
    "id": 123,
    "status": "in_transit",
    "customer_id": 1,
    "driver_id": 2
  },
  "photo_url": "https://cdn.example.com/shipment_proofs/pod.jpg",
  "image_sha256": "abc123def456...",
  "gps_latitude": 9.0505,
  "gps_longitude": 38.7605,
  "gps_verified": true,
  "gps_distance_to_dropoff_meters": 45.23,
  "is_duplicate": false,
  "customer_confirmed": false,
  "confirmation_status": "pending",
  "verification_notes": "GPS distance to dropoff: 45.23m (verified=true)",
  "created_at": "2026-06-02T12:00:00Z"
}
```

### 2. List PODs for Shipment

```http
GET /api/shipments/123/proof-of-delivery/
Authorization: Bearer <customer_or_driver_token>
```

**Response (200 OK):**
```json
[
  {
    "id": 456,
    "shipment": {...},
    "photo_url": "https://...",
    "confirmation_status": "pending",
    "customer_confirmed": false,
    "customer_confirmed_at": null,
    "customer_confirmation_method": ""
  }
]
```

### 3. Request OTP for POD

```http
POST /api/pod-otp/send/
Content-Type: application/json
Authorization: Bearer <customer_or_staff_token>

{
  "pod_id": 456,
  "phone": "+251900000000"  # optional
}
```

**Response (201 Created):**
```json
{
  "otp_id": 789,
  "expires_at": "2026-06-02T12:05:00Z"
}
```

### 4. Verify OTP and Confirm POD

```http
POST /api/pod-otp/verify/
Content-Type: application/json
Authorization: Bearer <customer_or_staff_token>

{
  "pod_id": 456,
  "code": "123456"
}
```

**Response (200 OK):**
```json
{
  "detail": "POD confirmed via OTP",
  "pod_id": 456
}
```

### 5. In-App Confirmation (Alternative)

```http
POST /api/shipment-proof-of-delivery/456/confirm/
Content-Type: application/json
Authorization: Bearer <customer_or_staff_token>

{
  "confirmation_method": "in_app",
  "notes": "Received and in good condition"
}
```

**Response (200 OK):**
```json
{
  "id": 456,
  "customer_confirmed": true,
  "customer_confirmed_at": "2026-06-02T12:01:00Z",
  "customer_confirmation_method": "in_app",
  "confirmation_status": "confirmed",
  "verification_notes": "GPS distance...; Customer note: Received and in good condition"
}
```

### 6. Twilio Webhook (Automatic)

```http
POST /api/webhooks/twilio/
Content-Type: application/x-www-form-urlencoded
X-Twilio-Signature: <signature>

MessageSid=SMxxx&MessageStatus=delivered&ErrorCode=&...
```

**Response (200 OK):**
```json
{
  "detail": "Webhook processed",
  "receipt_id": 100
}
```

## Installation & Setup

### 1. Install Dependencies

```bash
pip install -r requirements/base.txt
```

(Includes: `twilio==8.0.0`, `pillow==11.3.0`, Django, DRF, etc.)

### 2. Configure Environment

```bash
# .env or environment variables
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+15551234567
POD_OTP_TTL_SECONDS=300  # 5 minutes (optional)
```

### 3. Run Migrations

```bash
python manage.py migrate
```

### 4. Verify Cloudinary (for Photo Storage)

POD photos are stored via Cloudinary (configured in the example). Ensure `CLOUDINARY_*` env vars are set.

### 5. Configure Twilio Webhook

In Twilio Console:
- Go to **Messaging** → **Settings** → **Webhooks**
- Set Status Callback URL: `https://your-domain.com/api/webhooks/twilio/`
- Method: POST
- Save

### 6. Run Tests

```bash
python manage.py test apps.shipments.tests
```

Expected tests:
- Shipment cancellation
- POD upload with GPS & hash verification
- Duplicate detection
- OTP send/verify flow
- Twilio integration (mocked)
- Twilio webhook processing

## Confirmation Flows (Options)

### Option 1: In-App (Simple)

**UX:**
1. Customer opens app
2. Sees delivery photo
3. Taps "Confirm Delivery"
4. POD marked confirmed immediately

**Pro:** Simple, instant
**Con:** Easy to exploit if account compromised

### Option 2: OTP via SMS (Secure)

**UX:**
1. Customer taps "Confirm via OTP"
2. 6-digit code sent to recipient phone via SMS
3. Customer enters code in app (5-minute window)
4. On correct code, POD confirmed

**Pro:** Phone ownership verification, harder to exploit
**Con:** Requires SMS, slightly slower

### Option 3: Signed Link (Contactless)

**UX (Future):**
1. Link emailed/SMS'd to recipient
2. Customer clicks link
3. Single-page view shows photo + one-tap confirm
4. Signature verified server-side, POD confirmed

**Pro:** Works for non-app users, email-friendly
**Con:** Link can be forwarded (single-use ttl needed)

## Verification & Disputes

### Support Dashboard View

When a dispute arises:
1. Support pulls up POD record
2. Sees:
   - Photo + URL
   - GPS location (on map)
   - GPS distance to dropoff (verified if <500m)
   - SHA-256 hash (detect if reused)
   - Duplicate status + link to original POD
   - Delivery timestamp + uploader
   - Customer confirmation status + method + timestamp
   - OTP delivery receipt (sent/delivered/failed)
   - Verification notes & metadata

### Resolution Rules

- ✅ **Auto-resolve (delivered):**
  - Photo uploaded to correct shipment
  - GPS verified (within 500m of dropoff)
  - Hash unique (no duplicates)
  - Customer confirmed (OTP or in-app)

- 🚨 **Manual review (escalate):**
  - Duplicate image detected
  - GPS unverified (>500m from dropoff)
  - No customer confirmation
  - OTP delivery failed
  - Dispute raised by customer despite confirmation

## Security Highlights

1. **Photo Integrity:** SHA-256 hash prevents reuse
2. **Location Verification:** Haversine distance check (500m radius)
3. **Duplicate Detection:** Hash + DB lookup prevents same photo multiple shipments
4. **OTP Security:**
   - Numeric code (100k possibilities)
   - 5-minute expiry
   - Single-use (marked used after verify)
   - Rate-limited attempts
5. **Webhook Signature:** Twilio signature validation prevents forged receipts
6. **Access Control:** Only customer/driver/staff can upload/confirm PODs
7. **Audit Trail:** Metadata stores timestamps, uploader, confirmation method

## Monitoring & Metrics

```python
# Dashboard queries
from apps.shipments.models import ShipmentProofOfDelivery, TwilioDeliveryReceipt

# POD confirmation rate
confirmed = ShipmentProofOfDelivery.objects.filter(customer_confirmed=True).count()
total = ShipmentProofOfDelivery.objects.count()
confirmation_rate = (confirmed / total) * 100  # %

# SMS delivery success
delivered = TwilioDeliveryReceipt.objects.filter(status="delivered").count()
failed = TwilioDeliveryReceipt.objects.filter(status="failed").count()
sms_success_rate = (delivered / (delivered + failed)) * 100  # %

# Duplicate detections
duplicates = ShipmentProofOfDelivery.objects.filter(is_duplicate=True).count()

# GPS verification success
gps_verified = ShipmentProofOfDelivery.objects.filter(gps_verified=True).count()
```

## Files & Modules

- `apps/shipments/models.py` — `Shipment`, `ShipmentProofOfDelivery`, `ShipmentPODOTP`, `TwilioDeliveryReceipt`
- `apps/shipments/api/serializers.py` — Request/response schemas
- `apps/shipments/api/views.py` — Endpoints & viewsets
- `apps/shipments/api/urls.py` — URL routing
- `apps/shipments/services/otp_service.py` — OTP generation & SMS sending
- `apps/shipments/services/twilio_webhook.py` — Twilio signature validation & webhook processing
- `apps/shipments/tests.py` — Unit & integration tests
- `apps/shipments/migrations/` — Schema migrations

## Next Steps / Future Work

1. **Rate Limiting** — Add throttles to OTP endpoints
2. **Resend OTP** — Endpoint with limits (max 3 resends)
3. **Admin Dashboard** — Compact table view of PODs for support
4. **SMS Templates** — Internationalization for OTP messages
5. **Fallback Providers** — Add Africa's Talking, Nexmo as SMS providers
6. **Delivery Notifications** — Real-time updates to driver/customer
7. **Audit Logging** — Full history of OTP sends/verifies for disputes
8. **Link-based Confirmation** — Signed, single-use email/SMS links

## Support

For questions or issues:
- Check `TWILIO_WEBHOOK_SETUP.md` for webhook configuration details
- Review test cases in `apps/shipments/tests.py` for usage examples
- Contact Twilio support at https://support.twilio.com for SMS issues

