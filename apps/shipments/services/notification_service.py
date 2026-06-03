"""
Service for sending OTP resend notifications to customers via email and push.
"""
from apps.notifications.services import notify_user
import logging

logger = logging.getLogger(__name__)


def send_otp_resend_notification(pod, otp, remaining_resends=None):
    """
    Notify customer that OTP has been resent via email and push notification.

    Args:
        pod (ShipmentProofOfDelivery): The POD instance
        otp (ShipmentPODOTP): The newly sent OTP
        remaining_resends (int, optional): Number of remaining resends allowed
    """
    try:
        shipment = pod.shipment
        customer = shipment.customer

        # Build message
        message = (
            f"Your delivery confirmation code has been resent to {otp.phone}. "
            f"Code: {otp.code} (valid for 5 minutes)"
        )

        if remaining_resends is not None:
            if remaining_resends > 0:
                message += f" ({remaining_resends} more resends available)"
            else:
                message += " (this is your last available resend)"

        title = "Delivery Confirmation Code Resent"

        # Additional data for push notification
        data = {
            'type': 'otp_resent',
            'shipment_id': str(shipment.pk),
            'pod_id': str(pod.pk),
            'otp_code': otp.code,
            'otp_phone': otp.phone,
            'remaining_resends': str(remaining_resends) if remaining_resends is not None else 'unknown',
        }

        # Send notification (in-app, push, and email)
        notify_user(
            user=customer,
            title=title,
            message=message,
            data=data
        )

        logger.info(
            f"Sent OTP resend notification to customer {customer.pk} for POD {pod.pk}"
        )

    except Exception as e:
        logger.error(
            f"Failed to send OTP resend notification for POD {pod.pk}: {str(e)}",
            exc_info=True
        )
        # Don't let notification failure break the OTP resend flow
        raise


def send_failed_sms_retry_notification(pod, receipt, retry_count=None):
    """
    Notify driver/executor that a failed SMS is being retried.

    Args:
        pod (ShipmentProofOfDelivery): The POD instance
        receipt (TwilioDeliveryReceipt): The failed receipt being retried
        retry_count (int, optional): Current retry attempt number
    """
    try:
        shipment = pod.shipment
        uploader = pod.uploaded_by

        if not uploader:
            logger.warning(f"POD {pod.pk} has no uploader; skipping retry notification")
            return

        # Build message
        message = (
            f"Failed to deliver OTP code to {receipt.otp.phone}. "
            f"Automatically retrying delivery..."
        )

        if retry_count:
            message = f"Attempt #{retry_count}: {message}"

        if receipt.error_message:
            message += f" (Error: {receipt.error_message})"

        title = "OTP Delivery Retry in Progress"

        data = {
            'type': 'otp_delivery_retry',
            'shipment_id': str(shipment.pk),
            'pod_id': str(pod.pk),
            'receipt_id': str(receipt.pk),
            'error': receipt.error_code or 'unknown',
            'phone': receipt.otp.phone,
        }

        notify_user(
            user=uploader,
            title=title,
            message=message,
            data=data
        )

        logger.info(
            f"Sent SMS retry notification to driver {uploader.pk} for POD {pod.pk}"
        )

    except Exception as e:
        logger.error(
            f"Failed to send SMS retry notification for POD {pod.pk}: {str(e)}",
            exc_info=True
        )
        # Don't let notification failure break the business flow


def send_otp_exhausted_notification(pod):
    """
    Notify customer that they've exhausted all OTP resend attempts.

    Args:
        pod (ShipmentProofOfDelivery): The POD instance
    """
    try:
        shipment = pod.shipment
        customer = shipment.customer

        message = (
            f"Maximum OTP resend attempts reached. "
            f"Please contact support or try again later."
        )

        title = "OTP Resend Limit Reached"

        data = {
            'type': 'otp_exhausted',
            'shipment_id': str(shipment.pk),
            'pod_id': str(pod.pk),
        }

        notify_user(
            user=customer,
            title=title,
            message=message,
            data=data
        )

        logger.info(
            f"Sent OTP exhausted notification to customer {customer.pk} for POD {pod.pk}"
        )

    except Exception as e:
        logger.error(
            f"Failed to send OTP exhausted notification for POD {pod.pk}: {str(e)}",
            exc_info=True
        )


