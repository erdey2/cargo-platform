"""
Batch retry service for failed Twilio SMS messages.

Handles automatic retries for failed OTP deliveries with configurable
limits and exponential backoff timing.
"""
from django.utils import timezone
from django.conf import settings
from django.db import models
from datetime import timedelta
from ..models import TwilioDeliveryReceipt, ShipmentPODOTP
import logging

logger = logging.getLogger(__name__)


def default_sms_retry_max_attempts():
    """Max retry attempts for failed SMS deliveries (default: 3)"""
    return getattr(settings, 'SMS_RETRY_MAX_ATTEMPTS', 3)


def default_sms_retry_backoff_minutes():
    """Backoff delay between retries in minutes (default: 5)"""
    return getattr(settings, 'SMS_RETRY_BACKOFF_MINUTES', 5)


def default_sms_retry_max_age_hours():
    """Max age of failed message before giving up (default: 24 hours)"""
    return getattr(settings, 'SMS_RETRY_MAX_AGE_HOURS', 24)


def get_retryable_failed_receipts(limit=100):
    """
    Find failed SMS receipts eligible for retry.

    Criteria:
    - Status is 'failed' or 'undelivered'
    - Retry count < max attempts
    - Last retry was > backoff minutes ago
    - Created < max age hours ago
    - eligible_for_retry=True

    Returns:
        QuerySet of TwilioDeliveryReceipt objects
    """
    max_retries = default_sms_retry_max_attempts()
    backoff_minutes = default_sms_retry_backoff_minutes()
    max_age_hours = default_sms_retry_max_age_hours()

    now = timezone.now()
    min_time_since_last_retry = now - timedelta(minutes=backoff_minutes)
    max_creation_time = now - timedelta(hours=max_age_hours)

    receipts = TwilioDeliveryReceipt.objects.filter(
        status__in=['failed', 'undelivered'],
        retry_count__lt=max_retries,
        eligible_for_retry=True,
        created_at__gte=max_creation_time,
    ).filter(
        # Either never retried, or last retry is old enough
        models.Q(last_retry_at__isnull=True) |
        models.Q(last_retry_at__lte=min_time_since_last_retry)
    ).order_by('created_at')[:limit]

    return receipts


def retry_failed_sms(receipt):
    """
    Retry sending a failed OTP SMS.

    Args:
        receipt (TwilioDeliveryReceipt): The failed receipt to retry

    Returns:
        dict: {
            'success': bool,
            'message_sid': str or None,
            'error': str or None,
            'retry_count': int
        }
    """
    from .otp_service import send_sms
    from .notification_service import send_failed_sms_retry_notification

    try:
        otp = receipt.otp
        pod = otp.pod
        phone = otp.phone

        # Generate retry attempt message
        message = (
            f"Your delivery confirmation code is: {otp.code}. "
            f"Valid for 5 minutes. (Retry attempt {receipt.retry_count + 1})"
        )

        # Attempt to resend
        new_message_sid = send_sms(phone, message)

        # Update receipt
        receipt.retry_count += 1
        receipt.last_retry_at = timezone.now()
        receipt.status = 'queued'  # Reset to queued for retry
        receipt.save(update_fields=['retry_count', 'last_retry_at', 'status'])

        logger.info(
            f"Retried SMS for OTP {otp.pk} (phone={phone}). "
            f"Retry #{receipt.retry_count}, new message_sid={new_message_sid}"
        )

        # Send notification to driver about retry (optional, best effort)
        try:
            send_failed_sms_retry_notification(pod=pod, receipt=receipt, retry_count=receipt.retry_count)
        except Exception as notif_err:
            logger.warning(f"Failed to send retry notification for POD {pod.pk}: {str(notif_err)}")

        return {
            'success': True,
            'message_sid': new_message_sid,
            'error': None,
            'retry_count': receipt.retry_count,
        }

    except Exception as e:
        logger.error(f"Failed to retry SMS for receipt {receipt.pk}: {str(e)}", exc_info=True)

        # Mark as ineligible after too many failures
        if receipt.retry_count >= default_sms_retry_max_attempts() - 1:
            receipt.eligible_for_retry = False
            receipt.save(update_fields=['eligible_for_retry'])

        return {
            'success': False,
            'message_sid': None,
            'error': str(e),
            'retry_count': receipt.retry_count,
        }


def batch_retry_failed_sms(limit=100, dry_run=False):
    """
    Process batch retry of all eligible failed SMS messages.

    Args:
        limit (int): Maximum number of receipts to retry
        dry_run (bool): If True, only report without making changes

    Returns:
        dict: {
            'total_processed': int,
            'successful_retries': int,
            'failed_retries': int,
            'marked_ineligible': int,
            'details': [...]
        }
    """
    receipts = get_retryable_failed_receipts(limit=limit)

    results = {
        'total_processed': 0,
        'successful_retries': 0,
        'failed_retries': 0,
        'marked_ineligible': 0,
        'details': [],
    }

    for receipt in receipts:
        if dry_run:
            results['details'].append({
                'receipt_id': receipt.pk,
                'otp_id': receipt.otp_id,
                'phone': receipt.otp.phone,
                'status': receipt.status,
                'retry_count': receipt.retry_count,
                'action': 'WOULD_RETRY'
            })
            continue

        result = retry_failed_sms(receipt)
        results['total_processed'] += 1

        if result['success']:
            results['successful_retries'] += 1
        else:
            results['failed_retries'] += 1
            if not receipt.eligible_for_retry:
                results['marked_ineligible'] += 1

        results['details'].append({
            'receipt_id': receipt.pk,
            'otp_id': receipt.otp_id,
            'phone': receipt.otp.phone,
            'status': receipt.status,
            'retry_count': receipt.retry_count,
            'success': result['success'],
            'error': result['error'],
        })

    logger.info(
        f"Batch retry completed: {results['successful_retries']}/{results['total_processed']} successful, "
        f"{results['marked_ineligible']} marked ineligible"
    )

    return results
