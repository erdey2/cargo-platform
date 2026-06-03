# Quick Start: OTP Metrics, Batch Retry & Notifications

This guide shows how to use the three new features added to the cargo platform.

## Feature Overview

| Feature | Purpose | Usage |
|---------|---------|-------|
| **Admin Dashboard** | View OTP/POD metrics with filters & bulk actions | Navigate to Django admin → Shipments |
| **Batch Retry** | Automatically retry failed SMS at configurable intervals | Run command or Celery task |
| **Resend Notifications** | Notify customers/drivers of OTP events | Automatic when OTP resent or retry occurs |

---

## 1. Admin Dashboard

### Access the Dashboard

1. Login to Django admin: `http://localhost:8000/admin/`
2. Navigate to **Shipments** app
3. Available models with enhanced admin:
   - **Shipments** - View POD confirmation status
   - **Shipments → Proofs of Delivery** - Track POD verification & customer confirmation
   - **Shipments → SMS Delivery Receipts** - Monitor Twilio delivery status & retry attempts
   - **Shipments → OTP Codes** - View OTP codes & delivery status

### Example: Check Failed SMS

```
1. Go to: Admin → Shipments → SMS Delivery Receipts
2. Filter by Status: "failed"
3. Check error codes:
   - 21211 = Invalid phone number
   - 21610 = Invalid message
   - 30003 = Unreachable destination
4. Select failed receipts
5. Action: "Mark as eligible for retry" OR "Mark as ineligible"
```

### Example: Track Customer Confirmations

```
1. Go to: Admin → Shipments → Shipments
2. Column "POD Status" shows:
   - ✓ All Confirmed - Order ready to complete
   - ⚠ Partial - Some PODs waiting for confirmation
   - ✗ Pending - No confirmations yet
3. Click on shipment → View related PODs
4. Each POD shows confirmation method (OTP/In-App)
```

---

## 2. Batch Retry for Failed SMS

### Run Manual Retry

**Dry-run (preview what will be retried):**
```bash
python manage.py retry_failed_sms --dry-run
```

**Execute retry:**
```bash
python manage.py retry_failed_sms --limit 50 --verbose
```

**Output example:**
```
======================================================================
Batch Retry Summary:
  Total Processed: 15
  Successful Retries: 12
  Failed Retries: 3
  Marked Ineligible: 1
======================================================================
```

### Schedule Automatic Retry

Add to `config/settings/base.py`:

```python
from celery.schedules import crontab
from datetime import timedelta

CELERY_BEAT_SCHEDULE = {
    'retry-failed-sms': {
        'task': 'apps.shipments.tasks.batch_retry_failed_otp_sms',
        'schedule': timedelta(minutes=10),  # Every 10 minutes
        'kwargs': {'limit': 100}
    },
}
```

Start Celery Beat:
```bash
celery -A config beat -l info
```

### Configuration

Set in `.env` or `settings`:

```bash
# Max retry attempts for a failed SMS
SMS_RETRY_MAX_ATTEMPTS=3

# Minutes to wait between retry attempts
SMS_RETRY_BACKOFF_MINUTES=5

# Hours before giving up on a failed SMS
SMS_RETRY_MAX_AGE_HOURS=24
```

---

## 3. Resend Notifications

### Automatic Triggers

**When does a customer get notified?**

1. **OTP Resend Requested** (Notification sent)
   - Customer clicks "Resend Code"
   - Receives: Email, Push, In-App notification
   - Example: "Your code has been resent to +251912345678. Valid for 5 minutes. (2 more available)"

2. **SMS Failed, Retry Started** (Driver notified)
   - Batch retry automatically retries failed SMS
   - Driver receives: Push, In-App notification
   - Example: "Attempt #2: Failed to deliver OTP code to +251912345678. Automatically retrying delivery..."

3. **OTP Attempts Exhausted** (Customer notified)
   - Customer has resent OTP max times
   - Receives: Email, Push, In-App notification
   - Example: "Maximum OTP resend attempts reached. Please contact support or try again later."

### Notification Data Payload

Notification includes metadata useful for frontend:

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

Frontend can use `type` to route notification to appropriate handler.

### Check Notification Delivery

**Verify notifications sent:**

```python
# In Django shell:
from apps.notifications.models import Notification

# Find recent notifications
notifications = Notification.objects.filter(
    recipient__email='customer@example.com'
).order_by('-created_at')[:10]

# Check if notification was sent
for n in notifications:
    print(f"{n.message} | Devices: {n.recipient.device_set.count()}")
```

**Monitor Firebase delivery:**

Check Firebase Console → Cloud Messaging → Message Logs

---

## API Workflow

Complete flow: Upload POD → Send OTP → Resend → Verify

```
1. Driver uploads POD photo
   GET /api/shipments/{id}/proof-of-delivery/
   ← Returns POD details with hash, GPS verification

2. Customer receives SMS with OTP code
   POST /api/pod-otp/send/ {"pod_id": 128}
   ← SMS sent via Twilio, in-app notification shown

3. Twilio reports delivery status
   POST /api/webhooks/twilio/ (webhook from Twilio)
   ← Delivery receipt updated (queued/sent/delivered/failed)

4. Customer didn't receive code, requests resend
   POST /api/pod-otp/resend/ {"pod_id": 128}
   ← SMS resent, customer notified ("2 more available")

5. After 5 minutes, if still failed, batch retry picks it up
   python manage.py retry_failed_sms
   ← Driver notified of retry attempt

6. Customer finally enters code
   POST /api/pod-otp/verify/ {"pod_id": 128, "code": "123456"}
   ← POD marked confirmed, order progresses
```

---

## Monitoring & Troubleshooting

### Check OTP Status

```python
from apps.shipments.models import ShipmentPODOTP, TwilioDeliveryReceipt

# Find recent failed OTPs
failed_otps = ShipmentPODOTP.objects.filter(used=False).filter(
    delivery_receipts__status='failed'
).distinct()

for otp in failed_otps[:5]:
    receipt = otp.delivery_receipts.first()
    print(f"OTP #{otp.pk} | Phone: {otp.phone} | Error: {receipt.error_code}")
```

### Check Resend Limits

```python
from apps.shipments.models import ShipmentProofOfDelivery

# PODs that hit resend limit
max_resends = ShipmentProofOfDelivery.objects.filter(
    otp_resend_count__gte=3  # Default max is 3
)

print(f"PODs at max resends: {max_resends.count()}")
```

### Monitor Batch Retry

```python
from apps.shipments.models import TwilioDeliveryReceipt
from django.utils import timezone
from datetime import timedelta

# Retried in last hour
now = timezone.now()
one_hour_ago = now - timedelta(hours=1)

retried = TwilioDeliveryReceipt.objects.filter(
    last_retry_at__gte=one_hour_ago
)

print(f"SMS retried in last hour: {retried.count()}")
print(f"Success rate: {retried.filter(status='delivered').count()}/{retried.count()}")
```

---

## Testing

Run tests:

```bash
# All shipments tests
python manage.py test apps.shipments.tests

# Specific test class
python manage.py test apps.shipments.tests.BatchRetryFailedSMSTests

# Specific test method
python manage.py test apps.shipments.tests.BatchRetryFailedSMSTests.test_batch_retry_dry_run_no_changes
```

---

## Common Issues

### Q: Notifications not being sent

**Check:**
1. Firebase configured? `GOOGLE_APPLICATION_CREDENTIALS` environment variable set?
2. Celery running? `celery -A config worker`
3. Notification preferences? User may have disabled push
4. Logs: `tail -f logs/app.log | grep notification`

**Solution:**
```python
# In Django shell, re-enable all notifications
from apps.notifications.models import NotificationPreference
NotificationPreference.objects.filter(user__id=123).update(push=True, email=True)
```

### Q: Batch retry not finding failed SMS

**Check:**
1. Are there actually failed SMS? 
   ```python
   TwilioDeliveryReceipt.objects.filter(status__in=['failed','undelivered']).count()
   ```
2. Are they old enough? (Default: > 5 minutes)
3. Haven't hit max retries yet?
   ```python
   TwilioDeliveryReceipt.objects.filter(retry_count__gte=3).count()
   ```

**Debug:**
```bash
python manage.py retry_failed_sms --dry-run --verbose
```

### Q: Admin dashboard showing "No POD" for all shipments

**Check:**
1. PODs created? `ShipmentProofOfDelivery.objects.count()`
2. Associated with shipments? Check foreign key `shipment_id`

**Solution:**
```python
# Find shipments without PODs
from apps.shipments.models import Shipment
Shipment.objects.filter(proofs_of_delivery__isnull=True)
```

---

## Production Deployment

### Pre-deployment Checklist

- [ ] Run migrations: `python manage.py migrate`
- [ ] Collect static files: `python manage.py collectstatic`
- [ ] Run tests: `python manage.py test apps.shipments`
- [ ] Configure Celery Beat schedule
- [ ] Set environment variables (Twilio, Firebase, retry settings)
- [ ] Configure log shipping for monitoring

### Post-deployment

1. **Monitor first batch retry:**
   ```bash
   python manage.py retry_failed_sms --limit 10 --verbose
   ```

2. **Check admin dashboard:**
   - Login to admin
   - Verify SMS Delivery Receipts showing delivery status
   - No errors in admin interface

3. **Monitor notifications:**
   - Trigger a resend in production
   - Verify customer receives notification
   - Check logs for any delivery errors

---

## Next Steps

- [ ] Setup SMS alerting when retry failures spike
- [ ] Configure Celery Beat to run batch retry every 10 minutes
- [ ] Create support dashboard view for SMS delivery metrics
- [ ] Add fallback SMS provider (Nexmo, AfricasTalking)
- [ ] Implement customer notification preferences UI


