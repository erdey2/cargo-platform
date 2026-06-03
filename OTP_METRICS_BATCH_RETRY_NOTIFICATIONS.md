# OTP System: Metrics Dashboard, Batch Retry, & Notifications

Complete guide to the enhanced OTP/SMS system with admin dashboard, batch retry logic, and customer notifications.

---

## Table of Contents

1. [Admin Dashboard & Metrics](#admin-dashboard--metrics)
2. [Batch Retry for Failed SMS](#batch-retry-for-failed-sms)
3. [Resend Notifications](#resend-notifications)
4. [Configuration](#configuration)
5. [Usage & Examples](#usage--examples)

---

## Admin Dashboard & Metrics

### Overview

The Django admin interface now includes comprehensive POD and OTP metrics dashboards with rich visualization, filtering, and bulk actions.

### Admin Models

#### 1. **ShipmentProofOfDeliveryAdmin**

**Features:**
- List view with color-coded status indicators
- Filters: GPS verified, duplicate, customer confirmation status, date range
- Quick search by POD ID, shipment ID, or image hash
- Detailed view with all verification metadata

**Key Columns:**
- `gpd_verified_display` - Visual indicator (✓ Verified / ✗ Not Verified)
- `is_duplicate_display` - Duplicate status with badge
- `customer_confirmed_display` - Confirmation status
- `confirmation_method_display` - How confirmed (OTP icon, In-App icon)
- OTP summary showing total, used, and resend counts

**Example:**
```
POD #42 | GPS Verified ✓ | Not Duplicate ✓ | Customer Confirmed ✓ | OTP Confirmed (Total: 3 | Used: 1 | Resends: 1)
```

#### 2. **ShipmentPODOTPAdmin**

**Features:**
- List with OTP status (Used / Expired / Pending)
- Time-to-expiry display (e.g., "5 min" or "Expired 120 seconds ago")
- Delivery receipt status inline
- Search by OTP code, phone, or shipment ID

**Key Columns:**
- `status_display` - Used ✓ / Expired ✗ / Pending ⏳
- `expires_at_display` - Minutes remaining or "Expired Xmin ago"
- `delivery_status_display` - Shows last 3 delivery receipts with status badges

**Example:**
```
OTP #128 | +251912345678 | Code: 123456 | Status: Pending ⏳ | Expires: 5 min | Delivery: [Sent (blue)][Queued (orange)]
```

#### 3. **TwilioDeliveryReceiptAdmin**

**Features:**
- SMS delivery status tracking with color-coded badges
- Error code and message display
- Retry tracking with attempt count and last retry timestamp
- Bulk actions to mark eligible/ineligible for retry
- Raw webhook data inspection

**Key Columns:**
- `status_display` - Queued/Sent/Delivered/Undelivered/Failed (color-coded)
- `retry_status_display` - Eligible ✓ / Not Eligible ✗ / Retry #X
- `error_display` - Error code and message if present

**List Filters:**
- Status (queued, sent, delivered, undelivered, failed)
- Eligible for retry (Yes / No)
- Retry count
- Date range

**Bulk Actions:**
- Mark as eligible for retry
- Mark as ineligible for retry

**Example:**
```
Receipt #789 | OTP #128 | SID: SM1234ab...cdef | Status: FAILED (red) | Error: 21211 | Retry #2 Eligible ✓
```

#### 4. **ShipmentAdmin (Enhanced)**

**New POD Status Column:**
- All Confirmed ✓ - All PODs confirmed by customer
- Partial ⚠ - Some PODs confirmed
- Pending ✗ - No PODs confirmed
- No POD - N/A

Shows confirmation ratio, e.g., "⚠ Partial (2/3)"

---

## Batch Retry for Failed SMS

### Overview

Automatically retries failed SMS deliveries with configurable limits and exponential backoff.

### Models & Fields

**TwilioDeliveryReceipt additions:**
```python
retry_count = IntegerField(default=0)  # Number of retry attempts
last_retry_at = DateTimeField(null=True)  # Timestamp of last retry
eligible_for_retry = BooleanField(default=True)  # Flag for manual control
```

### Retry Logic

**Eligibility Criteria:**

A failed SMS is eligible for retry if:
1. Status is `failed` or `undelivered`
2. Retry count < max attempts (configurable, default 3)
3. Last retry was > backoff minutes ago (default 5 minutes)
4. Created < max age hours ago (default 24 hours)
5. `eligible_for_retry=True` (not manually disabled)

**Backoff Timeline (default settings):**

```
Initial Send (failed)
  ↓
5 minute wait
  ↓
Retry 1 (failed)
  ↓
5 minute wait
  ↓
Retry 2 (failed)
  ↓
5 minute wait
  ↓
Retry 3 (failed)
  ↓
Marked ineligible (after max 3 retries)
```

### Services

#### `batch_retry_service.py`

**Functions:**

1. **`get_retryable_failed_receipts(limit=100)`**
   - Returns QuerySet of failed SMS eligible for retry
   - Filters by status, retry count, age, and last retry time

2. **`retry_failed_sms(receipt)`**
   - Attempts resend of single failed SMS
   - Increments `retry_count` and updates `last_retry_at`
   - Marks as ineligible if max retries exceeded
   - Returns: `{'success': bool, 'message_sid': str or None, 'error': str, 'retry_count': int}`

3. **`batch_retry_failed_sms(limit=100, dry_run=False)`**
   - Processes batch retry of up to `limit` failed SMS
   - `dry_run=True` shows what would be retried without making changes
   - Returns summary: `{'total_processed', 'successful_retries', 'failed_retries', 'marked_ineligible', 'details'}`

### Management Command

**Command:** `python manage.py retry_failed_sms`

**Usage:**
```bash
# Dry run (show what would be retried)
python manage.py retry_failed_sms --dry-run

# Retry up to 50 failed SMS
python manage.py retry_failed_sms --limit 50

# Verbose output with detailed results
python manage.py retry_failed_sms --limit 100 --verbose

# Example output:
# ======================================================================
# Batch Retry Summary:
#   Total Processed: 15
#   Successful Retries: 12
#   Failed Retries: 3
#   Marked Ineligible: 1
# ======================================================================
```

### Celery Task

**Task:** `batch_retry_failed_otp_sms(limit=100)`

Located in: `apps/shipments/tasks.py`

**Schedule via Celery Beat** (example, in settings):
```python
CELERY_BEAT_SCHEDULE = {
    'retry-failed-sms': {
        'task': 'apps.shipments.tasks.batch_retry_failed_otp_sms',
        'schedule': timedelta(minutes=10),  # Every 10 minutes
        'kwargs': {'limit': 100}
    },
}
```

---

## Resend Notifications

### Overview

When an OTP is resent (or batch retry fails), the customer and driver are automatically notified via email, push (FCM), and in-app notifications.

### Notification Types

#### 1. **OTP Resend Notification (to Customer)**

**When:** Customer or staff initiates OTP resend via `POST /api/pod-otp/resend/`

**Message:**
```
Title: "Delivery Confirmation Code Resent"

Message: "Your delivery confirmation code has been resent to +251912345678. 
Code: 123456 (valid for 5 minutes) (2 more resends available)"
```

**Channels:** In-app, Push (FCM), Email

**Data Payload:**
```json
{
  "type": "otp_resent",
  "shipment_id": "42",
  "pod_id": "128",
  "otp_code": "123456",
  "otp_phone": "+251912345678",
  "remaining_resends": "2"
}
```

#### 2. **SMS Retry Notification (to Driver)**

**When:** Batch retry automatically resends a failed SMS

**Message:**
```
Title: "OTP Delivery Retry in Progress"

Message: "Attempt #2: Failed to deliver OTP code to +251912345678. 
Automatically retrying delivery... (Error: 21211 - No deliverability)"
```

**Channels:** In-app, Push (FCM)

**Data Payload:**
```json
{
  "type": "otp_delivery_retry",
  "shipment_id": "42",
  "pod_id": "128",
  "receipt_id": "789",
  "error": "21211",
  "phone": "+251912345678"
}
```

#### 3. **OTP Exhausted Notification (to Customer)**

**When:** Customer exhausts all resend attempts

**Message:**
```
Title: "OTP Resend Limit Reached"

Message: "Maximum OTP resend attempts reached. 
Please contact support or try again later."
```

**Channels:** In-app, Push (FCM), Email

**Data Payload:**
```json
{
  "type": "otp_exhausted",
  "shipment_id": "42",
  "pod_id": "128"
}
```

### Services

**File:** `apps/shipments/services/notification_service.py`

**Functions:**

1. **`send_otp_resend_notification(pod, otp, remaining_resends=None)`**
   - Notifies customer that OTP was resent
   - Called automatically in OTP resend endpoint
   - Best-effort (doesn't fail the API response)

2. **`send_failed_sms_retry_notification(pod, receipt, retry_count=None)`**
   - Notifies driver that failed SMS is being retried
   - Called from batch retry service
   - Best-effort to avoid breaking retry flow

3. **`send_otp_exhausted_notification(pod)`**
   - Notifies customer that resend limit exhausted
   - Could be called from OTP resend endpoint when max reached

### Integration Points

**OTP Resend Endpoint:**
```python
# In ShipmentPODOTPResendView.post()
otp = create_and_send_otp(pod=pod, phone=phone_to_use)
pod.otp_resend_count += 1
pod.save()

# NEW: Send notification
try:
    send_otp_resend_notification(pod=pod, otp=otp, remaining_resends=remaining_resends)
except Exception as e:
    logger.warning(f"Notification failed: {e}")  # Don't fail API response
```

**Batch Retry Service:**
```python
# In retry_failed_sms()
new_message_sid = send_sms(phone, message)
receipt.save()

# NEW: Send driver notification
try:
    send_failed_sms_retry_notification(pod=pod, receipt=receipt, retry_count=receipt.retry_count)
except Exception as e:
    logger.warning(f"Notification failed: {e}")
```

---

## Configuration

### Django Settings

**Basic Settings (config/settings/base.py):**
```python
# OTP Configuration
POD_OTP_TTL_SECONDS = 300  # 5 minutes
POD_OTP_RESEND_MAX = 3  # Max 3 resends (4 total attempts)
POD_OTP_RESEND_DELAY_SECONDS = 60  # 60 second minimum between resends

# SMS Retry Configuration (NEW)
SMS_RETRY_MAX_ATTEMPTS = 3  # Max 3 retry attempts
SMS_RETRY_BACKOFF_MINUTES = 5  # Wait 5 minutes between retries
SMS_RETRY_MAX_AGE_HOURS = 24  # Only retry messages < 24 hours old

# Twilio Configuration
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_FROM_NUMBER = env('TWILIO_FROM_NUMBER', default='')

# Celery Beat Schedule (for automatic batch retry)
from celery.schedules import crontab
from datetime import timedelta

CELERY_BEAT_SCHEDULE = {
    'retry-failed-sms': {
        'task': 'apps.shipments.tasks.batch_retry_failed_otp_sms',
        'schedule': timedelta(minutes=10),
        'kwargs': {'limit': 100}
    },
    # Run batch retry every hour
    'retry-failed-sms-hourly': {
        'task': 'apps.shipments.tasks.batch_retry_failed_otp_sms',
        'schedule': crontab(minute=0),  # Every hour at :00
        'kwargs': {'limit': 500}
    },
}
```

### Environment Variables

```bash
# .env file
TWILIO_ACCOUNT_SID=AC123456789abcdefghijklmnopqrs
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+1234567890

# Optional: override defaults
SMS_RETRY_MAX_ATTEMPTS=5
SMS_RETRY_BACKOFF_MINUTES=3
SMS_RETRY_MAX_AGE_HOURS=48
```

---

## Usage & Examples

### Admin Dashboard Examples

#### Viewing POD Metrics

1. **Login to Django Admin**
2. **Navigate:** Shipments → Shipments
3. **Use Filters:**
   - Filter by status (Matching, In Transit, etc.)
   - Filter POD status shows all with confirmed/pending PODs
   - Use date range to find recent shipments

4. **View POD Details:**
   - Click on shipment ID → View PODs
   - Each POD shows GPS verification, duplicate status, customer confirmation method

#### Investigating Failed SMS

1. **Navigate:** Shipments → Twilio Delivery Receipts
2. **Filter by Status:** "failed" or "undelivered"
3. **Identify Pattern:**
   - Check error codes (e.g., 21211 = invalid number)
   - Group by phone number prefix (e.g., all +251 failures)
   - Check time pattern (e.g., all failed between 8-10 AM)

4. **Manual Actions:**
   - Select receipts and "Mark as ineligible for retry" if number is fake
   - Or "Mark as eligible for retry" to force retry

#### OTP Confirmation Tracking

1. **Navigate:** Shipments → Shipments
2. **Column: "POD Status"**
   - All Confirmed ✓ - Order can proceed to completion
   - Partial ⚠ - Some PODs pending confirmation
   - Pending ✗ - No confirmation yet; may need follow-up

3. **Click Shipment → View OTPs:**
   - See all OTP codes sent
   - View delivery status for each OTP
   - Track resend count

### Batch Retry Usage

#### Manual Retry

**Dry run (preview what would be retried):**
```bash
python manage.py retry_failed_sms --dry-run

# Output:
# Batch Retry Summary:
#   Total Processed: 0
#   Successful Retries: 0
#   Failed Retries: 0
#   Marked Ineligible: 0
# 
# Detailed Results:
# Receipt #1001 | OTP #42 | Phone: +251912345678 | Retry #0 | WOULD_RETRY
# Receipt #1002 | OTP #43 | Phone: +251912345679 | Retry #0 | WOULD_RETRY
# Receipt #1003 | OTP #44 | Phone: +251912345680 | Retry #1 | WOULD_RETRY
```

**Execute retry (process failed SMS):**
```bash
python manage.py retry_failed_sms --limit 50 --verbose

# Output:
# Batch Retry Summary:
#   Total Processed: 15
#   Successful Retries: 12
#   Failed Retries: 3
#   Marked Ineligible: 1
# 
# Detailed Results:
# Receipt #1001 | OTP #42 | Phone: +251912345678 | Retry #1 | Success
# Receipt #1002 | OTP #43 | Phone: +251912345679 | Retry #1 | Error: Network timeout
# Receipt #1003 | OTP #44 | Phone: +251912345680 | Retry #2 | Success
```

#### Automatic Scheduled Retry

1. **Ensure Celery Beat is running:**
   ```bash
   celery -A config beat -l info
   ```

2. **Monitor in logs:**
   ```bash
   tail -f /var/log/celery/beat.log | grep "batch_retry"
   
   # Output:
   # [2026-06-02 10:00:00] Task batch_retry_failed_otp_sms scheduled
   # [2026-06-02 10:00:15] Task completed: 15 successful, 3 failed, 1 marked ineligible
   ```

### Notification Examples

#### Customer Receives Resend Notification

1. **Customer requests OTP resend:** `POST /api/pod-otp/resend/`
2. **Response:**
   ```json
   {
     "otp_id": 42,
     "expires_at": "2026-06-02T10:05:00Z",
     "resend_count": 1,
     "remaining_resends": 2,
     "message": "OTP resent. You have 2 more resend(s) available."
   }
   ```

3. **Customer sees notification:**
   - In-app: Banner "Delivery Confirmation Code Resent"
   - Push notification: "Code: 123456 (valid for 5 minutes) (2 more resends available)"
   - Email: "Your delivery confirmation code has been resent..."

#### Driver Receives Retry Notification

1. **Batch retry runs:** `python manage.py retry_failed_sms`
2. **Failed SMS resent:** Driver receives push notification
   ```
   Title: "OTP Delivery Retry in Progress"
   Body: "Attempt #2: Failed to deliver OTP code to +251912345678. 
   Automatically retrying delivery..."
   ```
   
3. **Driver can monitor:**
   - Navigate to Twilio Delivery Receipts in admin
   - See retry attempts and timestamps
   - If still failing, can investigate customer's phone number

---

## Troubleshooting

### No Notifications Sent

**Check:**
1. Firebase configured? Verify `GOOGLE_APPLICATION_CREDENTIALS` set
2. Celery running? `celery -A config worker -l info`
3. Notification preferences? User may have disabled push/email
4. Check logs: `tail -f logs/app.log | grep notification`

### Batch Retry Not Working

**Check:**
1. Are there failed SMS? Query: `TwilioDeliveryReceipt.objects.filter(status__in=['failed', 'undelivered']).count()`
2. Are they old enough? Must be > 5 min old (default backoff)
3. Check retry count: `receipt.retry_count < SMS_RETRY_MAX_ATTEMPTS`
4. Is `eligible_for_retry=True`?
5. Run dry-run: `python manage.py retry_failed_sms --dry-run`

### Admin Dashboard Not Loading

**Check:**
1. All model admin classes registered? Check `admin.py` end of file
2. Import errors? Run: `python manage.py shell`
3. Database migrations? `python manage.py migrate`
4. Admin templates? `python manage.py collectstatic`

---

## API Integration Summary

### OTP Endpoints

```
POST /api/pod-otp/send/          → Send initial OTP
POST /api/pod-otp/verify/        → Verify OTP code
POST /api/pod-otp/resend/        → Resend OTP (with notification)
POST /api/webhooks/twilio/       → Twilio delivery webhook
```

### Example: Full OTP Flow with Notifications

```
1. Driver uploads POD with photo
   GET /api/shipments/{id}/proof-of-delivery/ 
   → POD created, ready for customer OTP

2. Customer receives OTP via SMS
   POST /api/pod-otp/send/ {"pod_id": 128, "phone": "+251912345678"}
   → SMS sent, in-app notification shown

3. Twilio reports delivery status
   POST /api/webhooks/twilio/ (webhook from Twilio)
   → TwilioDeliveryReceipt updated with "delivered" or "failed"

4. Customer misses code, requests resend
   POST /api/pod-otp/resend/ {"pod_id": 128}
   → SMS resent, notification sent ("2 more available")

5. If SMS fails, batch retry picks it up
   python manage.py retry_failed_sms
   → SMS retried, driver notified of retry attempt

6. Customer confirms OTP code
   POST /api/pod-otp/verify/ {"otp_id": 42, "code": "123456"}
   → POD confirmed, order completes
```

---

## Performance Notes

- **Admin dashboard:** Indexed queries on `pod_id`, `status`, `customer_confirmed`, `image_sha256`
- **Batch retry:** Efficient QuerySet with early termination at `limit`
- **Notifications:** Async via Celery, fallback to sync if broker down
- **Twilio webhooks:** Lightweight signature verification (no DB lookups for validation)

---

## Future Enhancements

- [ ] SMS delivery failure analytics dashboard
- [ ] A/B testing for OTP code length (4 vs 6 digits)
- [ ] Support for multiple SMS providers (Nexmo, Africa's Talking)
- [ ] Rate limiting per customer/phone number
- [ ] Fallback to email confirmation if SMS fails 3x
- [ ] OTP code patterns (numeric, alphanumeric, words)
- [ ] Webhook replay mechanism for failed Twilio callbacks


