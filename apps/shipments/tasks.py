"""
Celery tasks for shipments app, including batch OTP retry.
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def batch_retry_failed_otp_sms(limit=100):
    """
    Scheduled task to batch retry failed OTP SMS deliveries.

    Can be scheduled via celery beat (e.g., every 10 minutes).

    Args:
        limit (int): Maximum number of failed SMS to retry per run

    Returns:
        dict: Summary of retry results
    """
    from apps.shipments.services.batch_retry_service import batch_retry_failed_sms

    try:
        results = batch_retry_failed_sms(limit=limit, dry_run=False)
        logger.info(f"Batch retry task completed: {results}")
        return results
    except Exception as e:
        logger.error(f"Batch retry task failed: {str(e)}", exc_info=True)
        raise

