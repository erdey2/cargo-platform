# Deployment Checklist: OTP Metrics, Batch Retry & Notifications

Complete step-by-step guide to deploy the three new features to production.

---

## Pre-Deployment Phase

### ✅ 1. Code Review & Testing

- [ ] All new code reviewed for security issues
- [ ] Run full test suite:
  ```bash
  python manage.py test apps.shipments.tests -v 2
  ```
- [ ] Verify test count increased by ~6 new tests
- [ ] No import errors or circular dependencies:
  ```bash
  python manage.py shell
  >>> from apps.shipments.services.batch_retry_service import batch_retry_failed_sms
  >>> from apps.shipments.services.notification_service import send_otp_resend_notification
  ```

### ✅ 2. Database Migration Testing

- [ ] Test migration on local database:
  ```bash
  python manage.py migrate
  ```
- [ ] Verify migration creates 3 new fields on TwilioDeliveryReceipt:
  ```bash
  python manage.py dbshell
  \d shipments_twiliodeliveryreceipt
  ```
  Should show:
  - `retry_count` (integer, default 0)
  - `last_retry_at` (datetime, nullable)
  - `eligible_for_retry` (boolean, default true)

- [ ] Verify no data loss (test on copy of production DB)
- [ ] Estimate migration time (typically < 1 second)

### ✅ 3. Configuration Preparation

- [ ] Document current SMS settings:
  ```bash
  # Create config_backup.md with:
  TWILIO_ACCOUNT_SID=*****
  TWILIO_AUTH_TOKEN=*****
  TWILIO_FROM_NUMBER=+****
  ```

- [ ] Prepare new config values for deployment:
  ```bash
  POD_OTP_TTL_SECONDS=300
  POD_OTP_RESEND_MAX=3
  POD_OTP_RESEND_DELAY_SECONDS=60
  SMS_RETRY_MAX_ATTEMPTS=3
  SMS_RETRY_BACKOFF_MINUTES=5
  SMS_RETRY_MAX_AGE_HOURS=24
  ```

- [ ] Update `config/settings/production.py`:
  ```python
  # Add or update in production settings
  SMS_RETRY_MAX_ATTEMPTS = int(env("SMS_RETRY_MAX_ATTEMPTS", 3))
  SMS_RETRY_BACKOFF_MINUTES = int(env("SMS_RETRY_BACKOFF_MINUTES", 5))
  SMS_RETRY_MAX_AGE_HOURS = int(env("SMS_RETRY_MAX_AGE_HOURS", 24))
  ```

### ✅ 4. Celery Configuration (if using scheduled retry)

- [ ] Verify Celery Beat is running:
  ```bash
  ps aux | grep celery
  ```

- [ ] Prepare Celery Beat schedule in `config/settings/production.py`:
  ```python
  from datetime import timedelta
  from celery.schedules import crontab
  
  CELERY_BEAT_SCHEDULE = {
      'retry-failed-sms': {
          'task': 'apps.shipments.tasks.batch_retry_failed_otp_sms',
          'schedule': timedelta(minutes=10),
          'kwargs': {'limit': 100}
      },
  }
  ```

- [ ] Test Celery task locally:
  ```bash
  # In one terminal
  celery -A config worker -l info
  
  # In another terminal
  python manage.py shell
  >>> from apps.shipments.tasks import batch_retry_failed_otp_sms
  >>> batch_retry_failed_otp_sms.delay(limit=10)
  ```

### ✅ 5. Notifications Configuration

- [ ] Verify Firebase configured:
  ```bash
  echo $GOOGLE_APPLICATION_CREDENTIALS
  # Should point to valid service account key
  ```

- [ ] Test notification sending locally:
  ```bash
  python manage.py shell
  >>> from apps.notifications.services import notify_user
  >>> from apps.users.models import User
  >>> user = User.objects.first()
  >>> notify_user(user, "Test", "Testing notifications")
  ```

### ✅ 6. File Inventory

Verify all files are in place:

```bash
# New files
ls -la apps/shipments/services/batch_retry_service.py
ls -la apps/shipments/services/notification_service.py
ls -la apps/shipments/management/commands/retry_failed_sms.py
ls -la apps/shipments/tasks.py
ls -la apps/shipments/migrations/0016_*.py

# Updated files
grep "send_otp_resend_notification" apps/shipments/api/views.py

# Documentation
ls -la OTP_METRICS_BATCH_RETRY_NOTIFICATIONS.md
ls -la QUICK_START_METRICS_RETRY_NOTIFICATIONS.md
ls -la IMPLEMENTATION_SUMMARY.md
```

---

## Staging Deployment Phase

### ✅ 7. Deploy to Staging

- [ ] Tag release in Git:
  ```bash
  git tag -a v1.0-otp-metrics-retry "Release: OTP metrics, batch retry, notifications"
  git push origin v1.0-otp-metrics-retry
  ```

- [ ] Deploy code to staging:
  ```bash
  git checkout v1.0-otp-metrics-retry
  pip install -r requirements/production.txt
  python manage.py collectstatic --noinput
  ```

- [ ] Run migrations on staging:
  ```bash
  python manage.py migrate --noinput
  ```

- [ ] Verify admin interface loads:
  ```bash
  # Check logs for errors
  tail -f logs/django.log
  curl http://staging.example.com/admin/shipments/
  ```

### ✅ 8. Smoke Tests on Staging

- [ ] Login to admin and navigate to each model:
  - [ ] Shipments (verify POD status column)
  - [ ] Proofs of Delivery (verify GP verification columns)
  - [ ] SMS Delivery Receipts (verify retry columns)
  - [ ] OTP Codes (verify delivery status display)

- [ ] Test batch retry on staging data:
  ```bash
  # Dry run first
  python manage.py retry_failed_sms --dry-run
  
  # If any failed SMS, execute retry
  python manage.py retry_failed_sms --limit 10 --verbose
  ```

- [ ] Test OTP resend notification:
  ```bash
  # In Django shell
  from apps.shipments.models import ShipmentProofOfDelivery
  pod = ShipmentProofOfDelivery.objects.first()
  
  # Check recent notifications
  from apps.notifications.models import Notification
  Notification.objects.filter(
      recipient=pod.shipment.customer
  ).order_by('-created_at')[:5]
  ```

### ✅ 9. Performance Testing

- [ ] Admin dashboard load time:
  ```bash
  curl -w "@curl-format.txt" http://staging.example.com/admin/shipments/
  # Acceptable: < 500ms
  ```

- [ ] Batch retry performance with 100 records:
  ```bash
  time python manage.py retry_failed_sms --limit 100 --verbose
  # Acceptable: < 5 seconds
  ```

- [ ] Database query count (DEBUG=True):
  ```python
  from django.test.utils import override_settings
  with override_settings(DEBUG=True):
      # Check queries
  ```

### ✅ 10. Rollback Plan

Create rollback script if needed:

```bash
# rollback.sh
#!/bin/bash
set -e

echo "Rolling back to previous version..."
git checkout main
pip install -r requirements/production.txt

# Reverse migration (if needed)
python manage.py migrate shipments 0015

echo "Rollback complete"
```

---

## Production Deployment Phase

### ✅ 11. Pre-Production Backup

- [ ] Backup production database:
  ```bash
  pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql
  ```

- [ ] Verify backup integrity:
  ```bash
  psql -h localhost -U postgres < backup_*.sql
  ```

- [ ] Store backup in secure location:
  ```bash
  # Copy to backup server
  scp backup_*.sql backup-server:/backups/
  ```

### ✅ 12. Deploy to Production

- [ ] Enable maintenance mode:
  ```bash
  # If using maintenance mode middleware
  touch MAINTENANCE_MODE_ON
  ```

- [ ] Deploy code:
  ```bash
  git checkout v1.0-otp-metrics-retry
  pip install -r requirements/production.txt
  python manage.py collectstatic --noinput
  ```

- [ ] Run migrations (low-impact for added fields):
  ```bash
  python manage.py migrate --noinput
  
  # Monitor progress - should take < 30 seconds
  ```

- [ ] Disable maintenance mode:
  ```bash
  rm MAINTENANCE_MODE_ON
  ```

- [ ] Verify deployment:
  ```bash
  curl http://production.example.com/admin/shipments/
  ```

### ✅ 13. Post-Deployment Verification

- [ ] Check application logs for errors:
  ```bash
  tail -n 100 /var/log/django.log | grep -i error
  tail -n 100 /var/log/celery.log | grep -i error
  ```

- [ ] Verify admin interface:
  - [ ] Login works
  - [ ] POD metrics display correctly
  - [ ] SMS Delivery Receipts show retry fields
  - [ ] Bulk actions available

- [ ] Test batch retry in production:
  ```bash
  # Dry run first
  python manage.py retry_failed_sms --dry-run
  
  # Summary output should show "Total Processed: X"
  ```

- [ ] Verify Celery task is scheduled:
  ```bash
  celery -A config inspect scheduled
  # Should show 'retry-failed-sms' task
  ```

- [ ] Monitor notifications:
  ```bash
  # Tail notification logs
  tail -f /var/log/notifications.log
  ```

### ✅ 14. Create Monitoring Alerts

Set up alerts for:

- [ ] Batch retry failures:
  ```
  Alert if: SMS_RETRY_FAILED_COUNT > 10 in 1 hour
  Action: PagerDuty notification
  ```

- [ ] High retry volume:
  ```
  Alert if: FAILED_SMS_COUNT > 100 in 1 hour
  Action: Email to ops team
  ```

- [ ] Notification delivery failures:
  ```
  Alert if: NOTIFICATION_FAILED_COUNT > 50 in 1 hour
  Action: Email to ops team
  ```

### ✅ 15. Documentation Update

- [ ] Push documentation to confluence/wiki:
  - [ ] OTP_METRICS_BATCH_RETRY_NOTIFICATIONS.md
  - [ ] QUICK_START_METRICS_RETRY_NOTIFICATIONS.md
  - [ ] IMPLEMENTATION_SUMMARY.md

- [ ] Update runbook:
  ```
  Title: How to troubleshoot failed OTP SMS
  
  1. Login to admin → SMS Delivery Receipts
  2. Filter by Status = "failed"
  3. Check error codes
  4. Run: python manage.py retry_failed_sms --dry-run
  5. If problems persist, escalate to SMS provider
  ```

- [ ] Update incident response procedures

---

## Post-Deployment Monitoring (First 24 Hours)

### ✅ 16. Real-Time Monitoring

- [ ] Watch for errors in first 1 hour:
  ```bash
  watch -n 5 'tail -20 /var/log/django.log | grep -i error'
  ```

- [ ] Monitor database connections:
  ```bash
  # Verify no connection pools exhausted
  SELECT * FROM pg_stat_activity;
  ```

- [ ] Check Celery queue depth:
  ```bash
  celery -A config inspect active
  # Should be processing tasks normally
  ```

### ✅ 17. Feature Testing in Production

- [ ] Create test POD and trigger OTP resend:
  ```python
  # In production Django shell
  from apps.shipments.models import ShipmentProofOfDelivery
  pod = ShipmentProofOfDelivery.objects.filter(
      shipment__customer__email='test@example.com'
  ).last()
  
  # Check that notification was sent
  from apps.notifications.models import Notification
  Notification.objects.filter(
      recipient=pod.shipment.customer
  ).order_by('-created_at').first()
  ```

- [ ] Verify batch retry processes failed SMS:
  ```bash
  # Next scheduled run (e.g., 10 minutes from now)
  # Or trigger manually:
  python manage.py retry_failed_sms --limit 10 --verbose
  ```

### ✅ 18. Metrics Collection

Capture baseline metrics:

```python
# Run in Django shell
from apps.shipments.models import ShipmentProofOfDelivery, ShipmentPODOTP, TwilioDeliveryReceipt

# POD metrics
print(f"Total PODs: {ShipmentProofOfDelivery.objects.count()}")
print(f"Confirmed PODs: {ShipmentProofOfDelivery.objects.filter(customer_confirmed=True).count()}")

# OTP metrics
print(f"Total OTPs: {ShipmentPODOTP.objects.count()}")
print(f"Used OTPs: {ShipmentPODOTP.objects.filter(used=True).count()}")

# SMS metrics
receipts = TwilioDeliveryReceipt.objects
print(f"Total receipts: {receipts.count()}")
print(f"Delivered: {receipts.filter(status='delivered').count()}")
print(f"Failed: {receipts.filter(status='failed').count()}")
print(f"Retried: {receipts.filter(retry_count__gt=0).count()}")
```

Record these values for comparison.

### ✅ 19. Scale Testing (if high traffic)

If expecting high OTP volume:

- [ ] Load test batch retry:
  ```bash
  # Create 1000 failed SMS in test environment
  python manage.py shell << 'EOF'
  from apps.shipments.models import ShipmentPODOTP, TwilioDeliveryReceipt, ShipmentProofOfDelivery, Shipment
  from apps.users.models import User
  from django.contrib.gis.geos import Point
  
  # Create test data
  user = User.objects.first()
  shipment = Shipment.objects.create(
    customer=user,
    pickup_address='Test',
    dropoff_address='Test',
    pickup_location=Point(9, 38),
    dropoff_location=Point(9.01, 38.01),
    weight=1, volume=1
  )
  
  # Create 1000 failed SMS
  for i in range(1000):
      pod = ShipmentProofOfDelivery.objects.create(
          shipment=shipment,
          photo=f'test{i}.jpg'
      )
      otp = ShipmentPODOTP.objects.create(
          pod=pod,
          phone=f'+251{i:09d}',
          code='123456'
      )
      TwilioDeliveryReceipt.objects.create(
          otp=otp,
          message_sid=f'SM{i}',
          status='failed'
      )
  EOF
  
  # Time the batch
  time python manage.py retry_failed_sms --limit 1000 --verbose
  ```

- [ ] Verify performance is acceptable (< 30 seconds for 1000)

---

## Rollback Procedures

### If Issues Found

**Step 1: Immediate Rollback**
```bash
# Revert code
git checkout main
pip install -r requirements/production.txt
python manage.py collectstatic --noinput

# Restart services
systemctl restart django
systemctl restart celery

# Restart Celery Beat if applicable
systemctl restart celery-beat
```

**Step 2: Restore Database (if migrations corrupted)**
```bash
# Stop application
systemctl stop django

# Restore from backup
pg_restore < backup_YYYYMMDD_HHMMSS.sql

# Start application
systemctl start django
```

**Step 3: Verify Rollback**
```bash
# Confirm previous version running
curl http://production.example.com/api/health/
# Should respond with "OK"
```

**Step 4: Post-Mortem**
- [ ] Document what went wrong
- [ ] Update deployment procedures
- [ ] Fix issues locally
- [ ] Re-test in staging
- [ ] Plan next deployment

---

## Long-Term Maintenance

### ✅ 20. Ongoing Monitoring

Set up recurring checks (daily):

```bash
#!/bin/bash
# daily_checks.sh

echo "=== OTP/SMS Health Check ==="
python manage.py shell << 'EOF'
from apps.shipments.models import TwilioDeliveryReceipt
from django.utils import timezone
from datetime import timedelta

now = timezone.now()
yesterday = now - timedelta(days=1)

failed = TwilioDeliveryReceipt.objects.filter(
    status__in=['failed', 'undelivered'],
    created_at__gte=yesterday
)

print(f"Failed SMS in last 24h: {failed.count()}")
if failed.count() > 50:
    print("WARNING: High failure rate!")
    
# Check retry success
retried = TwilioDeliveryReceipt.objects.filter(
    retry_count__gt=0,
    created_at__gte=yesterday
)

success = retried.filter(status='delivered').count()
print(f"Retry success rate: {success}/{retried.count()}")
EOF
```

Schedule with cron:
```bash
# /etc/cron.d/otp-health-check
0 8 * * * root /opt/cargo_platform/daily_checks.sh >> /var/log/otp_health.log 2>&1
```

### ✅ 21. Version Control & Tags

Document deployment:

```bash
# Create annotated tag
git tag -a v1.0-otp-metrics-prod \
  -m "Production deployment: OTP metrics, batch retry, notifications
  
  Features:
  - Admin dashboard with OTP/POD metrics
  - Batch retry for failed SMS
  - Resend notifications
  
  Migration: 0016_twiliodeliveryreceipt_retry_fields
  Deployment Date: $(date)
  Deployed By: $(git config user.name)"

git push origin v1.0-otp-metrics-prod
```

---

## Success Criteria

Deployment successful if:

- [ ] All tests pass (local & CI/CD)
- [ ] Admin interface loads without errors
- [ ] POD confirmation status displays correctly
- [ ] SMS Delivery Receipts show retry fields
- [ ] Batch retry command executes without errors
- [ ] Notifications sent when OTP resent
- [ ] Celery task scheduled (if applicable)
- [ ] No errors in logs for 24 hours
- [ ] Metrics baseline established
- [ ] Documentation updated

---

## Support Contact

For deployment issues:

1. **Primary:** Deployment team lead
2. **Escalation:** Engineering manager
3. **Reference:** IMPLEMENTATION_SUMMARY.md

Emergency rollback: `./rollback.sh`


