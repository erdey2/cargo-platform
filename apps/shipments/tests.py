from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase
from PIL import Image

from apps.shipments.models import Shipment, ShipmentStatusHistory, ShipmentProofOfDelivery
from apps.shipments.models import ShipmentPODOTP
from apps.shipments.models import TwilioDeliveryReceipt
from apps.users.models import User
from unittest.mock import patch


class ShipmentCancellationTests(APITestCase):

	def setUp(self):
		self.customer = User.objects.create_user(
			email="customer@example.com",
			password="pass1234",
			role="customer",
		)
		self.client.force_authenticate(user=self.customer)

	def _create_shipment(self, status_value):
		return Shipment.objects.create(
			customer=self.customer,
			status=status_value,
			pickup_address="Bole",
			dropoff_address="Piassa",
			pickup_location=Point(38.74, 9.03, srid=4326),
			dropoff_location=Point(38.76, 9.05, srid=4326),
			weight=10,
			volume=1,
			recipient_name="Receiver",
			recipient_phone="+251900000000",
		)

	def test_customer_can_cancel_created_shipment(self):
		shipment = self._create_shipment("created")

		response = self.client.delete(reverse("shipments-detail", args=[shipment.pk]))

		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		shipment.refresh_from_db()
		self.assertEqual(shipment.status, "cancelled")
		self.assertTrue(
			ShipmentStatusHistory.objects.filter(
				shipment=shipment,
				status="cancelled",
				changed_by=self.customer,
			).exists()
		)

	def test_customer_can_cancel_matching_shipment(self):
		shipment = self._create_shipment("matching")

		response = self.client.delete(reverse("shipments-detail", args=[shipment.pk]))

		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		shipment.refresh_from_db()
		self.assertEqual(shipment.status, "cancelled")

	def test_customer_cannot_cancel_assigned_shipment(self):
		shipment = self._create_shipment("assigned")

		response = self.client.delete(reverse("shipments-detail", args=[shipment.pk]))

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		shipment.refresh_from_db()
		self.assertEqual(shipment.status, "assigned")


class ShipmentProofOfDeliveryTests(APITestCase):

	def setUp(self):
		self.customer = User.objects.create_user(
			email="customer2@example.com",
			password="pass1234",
			role="customer",
		)
		self.client.force_authenticate(user=self.customer)
		self.shipment = Shipment.objects.create(
			customer=self.customer,
			status="in_transit",
			pickup_address="Bole",
			dropoff_address="Piassa",
			pickup_location=Point(38.74, 9.03, srid=4326),
			dropoff_location=Point(38.76, 9.05, srid=4326),
			weight=10,
			volume=1,
			recipient_name="Receiver",
			recipient_phone="+251900000000",
		)

	def _photo(self, color=b"fake-image-bytes"):
		buffer = BytesIO()
		image = Image.new("RGB", (32, 32), color=(255, 0, 0))
		image.save(buffer, format="JPEG")
		return SimpleUploadedFile("pod.jpg", buffer.getvalue(), content_type="image/jpeg")

	def test_customer_can_upload_proof_of_delivery_and_get_metadata(self):
		response = self.client.post(
			reverse("shipment-proof-of-delivery-list"),
			{
				"shipment": self.shipment.pk,
				"photo": self._photo(),
				"gps_latitude": 9.0505,
				"gps_longitude": 38.7605,
				"gps_accuracy_meters": 12,
			},
			format="multipart",
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertIn("image_sha256", response.data)
		self.assertIn("gps_verified", response.data)
		self.assertIn("is_duplicate", response.data)
		self.assertTrue(response.data["gps_verified"])
		self.assertFalse(response.data["is_duplicate"])
		self.assertEqual(ShipmentProofOfDelivery.objects.count(), 1)

	def test_duplicate_upload_is_flagged(self):
		first = self.client.post(
			reverse("shipment-proof-of-delivery-list"),
			{
				"shipment": self.shipment.pk,
				"photo": self._photo(b"same-bytes"),
				"gps_latitude": 9.0505,
				"gps_longitude": 38.7605,
			},
			format="multipart",
		)
		self.assertEqual(first.status_code, status.HTTP_201_CREATED)

		second = self.client.post(
			reverse("shipment-proof-of-delivery-list"),
			{
				"shipment": self.shipment.pk,
				"photo": self._photo(b"same-bytes"),
				"gps_latitude": 9.0505,
				"gps_longitude": 38.7605,
			},
			format="multipart",
		)

		self.assertEqual(second.status_code, status.HTTP_201_CREATED)
		self.assertTrue(second.data["is_duplicate"])
		self.assertEqual(ShipmentProofOfDelivery.objects.count(), 2)

	def test_send_and_verify_otp_confirms_pod(self):
		# create a POD record directly
		image_buf = BytesIO()
		image = Image.new("RGB", (32, 32), color=(0, 255, 0))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("pod2.jpg", image_buf.getvalue(), content_type="image/jpeg")

		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="dummyhash",
		)

		# send OTP
		send_resp = self.client.post(reverse("pod-otp-send"), {"pod_id": pod.pk}, format="json")
		self.assertEqual(send_resp.status_code, status.HTTP_201_CREATED)
		# OTP record should be created
		otp = ShipmentPODOTP.objects.filter(pod=pod).first()
		self.assertIsNotNone(otp)

		# verify OTP using actual code from DB (since send_sms is a stub)
		verify_resp = self.client.post(reverse("pod-otp-verify"), {"pod_id": pod.pk, "code": otp.code}, format="json")
		self.assertEqual(verify_resp.status_code, status.HTTP_200_OK)
		pod.refresh_from_db()
		self.assertTrue(pod.customer_confirmed)

	def test_twilio_is_used_when_configured(self):
		image_buf = BytesIO()
		image = Image.new("RGB", (32, 32), color=(0, 0, 255))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("pod3.jpg", image_buf.getvalue(), content_type="image/jpeg")

		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="dummyhash2",
		)

		with self.settings(TWILIO_ACCOUNT_SID="AC123", TWILIO_AUTH_TOKEN="token123", TWILIO_FROM_NUMBER="+1000"):
			with patch("twilio.rest.Client") as mock_client_cls:
				resp = self.client.post(reverse("pod-otp-send"), {"pod_id": pod.pk}, format="json")
				self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
				# Twilio client should have been instantiated and messages.create called
				mock_client_cls.assert_called_with("AC123", "token123")
				client_instance = mock_client_cls.return_value
				self.assertTrue(client_instance.messages.create.called)
				kwargs = client_instance.messages.create.call_args.kwargs
				self.assertEqual(kwargs.get("from_"), "+1000")
				self.assertEqual(kwargs.get("to"), self.shipment.recipient_phone)

	def test_twilio_delivery_webhook_with_invalid_signature(self):
		image_buf = BytesIO()
		image = Image.new("RGB", (32, 32), color=(0, 0, 128))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("pod4.jpg", image_buf.getvalue(), content_type="image/jpeg")

		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="dummyhash3",
		)

		# Create OTP with a message SID in metadata
		otp = ShipmentPODOTP.objects.create(
			pod=pod,
			phone="+251900000000",
			code="123456",
			expires_at=timezone.now() + timedelta(minutes=5),
			metadata={"twilio_message_sid": "SMxxx123"},
		)

		# Send webhook with invalid signature
		with self.settings(TWILIO_AUTH_TOKEN="wrong_token"):
			resp = self.client.post(
				reverse("twilio-delivery-webhook"),
				{
					"MessageSid": "SMxxx123",
					"MessageStatus": "delivered",
					"ErrorCode": "",
				},
				format="json" if False else "form",  # Twilio sends as form data
			)
			# Request should be rejected due to invalid signature
			self.assertIn(resp.status_code, [403, 400])

	def test_twilio_delivery_webhook_processes_status(self):
		from apps.shipments.services.twilio_webhook import process_twilio_delivery_webhook
		from django.utils import timezone

		image_buf = BytesIO()
		image = Image.new("RGB", (32, 32), color=(128, 128, 0))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("pod5.jpg", image_buf.getvalue(), content_type="image/jpeg")

		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="dummyhash4",
		)

		# Create OTP with message SID in metadata
		otp = ShipmentPODOTP.objects.create(
			pod=pod,
			phone="+251900000000",
			code="234567",
			expires_at=timezone.now() + timedelta(minutes=5),
			metadata={"twilio_message_sid": "SMyyy456"},
		)

		# Process webhook (without signature validation)
		receipt = process_twilio_delivery_webhook(
			message_sid="SMyyy456",
			status="delivered",
			error_code=None,
			error_message="",
			webhook_data={"MessageSid": "SMyyy456", "MessageStatus": "delivered"},
		)

		self.assertIsNotNone(receipt)
		self.assertEqual(receipt.status, "delivered")
		self.assertEqual(receipt.otp_id, otp.pk)

	def test_twilio_delivery_webhook_handles_failed_status(self):
		from apps.shipments.services.twilio_webhook import process_twilio_delivery_webhook
		from django.utils import timezone

		image_buf = BytesIO()
		image = Image.new("RGB", (32, 32), color=(255, 128, 0))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("pod6.jpg", image_buf.getvalue(), content_type="image/jpeg")

		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="dummyhash5",
		)

		otp = ShipmentPODOTP.objects.create(
			pod=pod,
			phone="+251900000000",
			code="345678",
			expires_at=timezone.now() + timedelta(minutes=5),
			metadata={"twilio_message_sid": "SMzzz789"},
		)

		# Process failed delivery webhook
		receipt = process_twilio_delivery_webhook(
			message_sid="SMzzz789",
			status="failed",
			error_code="21211",
			error_message="The number +251900000000 is not a valid phone number.",
			webhook_data={"MessageSid": "SMzzz789", "MessageStatus": "failed", "ErrorCode": "21211"},
		)

		self.assertIsNotNone(receipt)
		self.assertEqual(receipt.status, "failed")
		self.assertEqual(receipt.error_code, "21211")
		self.assertIn("not a valid phone number", receipt.error_message)


class ResendOTPTests(APITestCase):

	def setUp(self):
		self.customer = User.objects.create_user(
			email="customer@example.com",
			password="pass1234",
			role="customer",
		)
		self.client.force_authenticate(user=self.customer)
		self.shipment = Shipment.objects.create(
			customer=self.customer,
			status="in_transit",
			pickup_address="Bole",
			dropoff_address="Piassa",
			pickup_location=Point(38.74, 9.03, srid=4326),
			dropoff_location=Point(38.76, 9.05, srid=4326),
			weight=10,
			volume=1,
			recipient_name="Receiver",
			recipient_phone="+251900000000",
		)

	def _photo(self, color=b"fake-image-bytes"):
		buffer = BytesIO()
		image = Image.new("RGB", (32, 32), color=(255, 0, 0))
		image.save(buffer, format="JPEG")
		return SimpleUploadedFile("pod.jpg", buffer.getvalue(), content_type="image/jpeg")

	def test_resend_otp_increments_counter(self):
		image_buf = BytesIO()
		image = Image.new("RGB", (64, 64), color=(128, 0, 128))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("pod7.jpg", image_buf.getvalue(), content_type="image/jpeg")

		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="dummyhash6",
		)

		# Send initial OTP
		send_resp = self.client.post(reverse("pod-otp-send"), {"pod_id": pod.pk}, format="json")
		self.assertEqual(send_resp.status_code, status.HTTP_201_CREATED)
		pod.refresh_from_db()
		self.assertEqual(pod.otp_resend_count, 0)  # Initial send doesn't increment

		# With POD_OTP_RESEND_DELAY_SECONDS=0, we can resend immediately (for testing)
		with self.settings(POD_OTP_RESEND_DELAY_SECONDS=0):
			resend_resp = self.client.post(reverse("pod-otp-resend"), {"pod_id": pod.pk}, format="json")
			self.assertEqual(resend_resp.status_code, status.HTTP_201_CREATED)
			self.assertIn("resend_count", resend_resp.data)
			self.assertEqual(resend_resp.data["resend_count"], 1)
			self.assertEqual(resend_resp.data["remaining_resends"], 2)  # 3 max - 1 used = 2 remaining

	def test_resend_otp_respects_max_limit(self):
		image_buf = BytesIO()
		image = Image.new("RGB", (64, 64), color=(0, 128, 128))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("pod8.jpg", image_buf.getvalue(), content_type="image/jpeg")

		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="dummyhash7",
		)

		# Set resend count to max already
		pod.otp_resend_count = 3
		pod.save(update_fields=["otp_resend_count"])

		# Try to resend; should fail
		with self.settings(POD_OTP_RESEND_DELAY_SECONDS=0):
			resend_resp = self.client.post(reverse("pod-otp-resend"), {"pod_id": pod.pk}, format="json")
			self.assertEqual(resend_resp.status_code, status.HTTP_400_BAD_REQUEST)
			self.assertIn("Maximum OTP resends", resend_resp.data["detail"])

	def test_resend_otp_rate_limited_by_time(self):
		image_buf = BytesIO()
		image = Image.new("RGB", (64, 64), color=(128, 128, 0))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("pod9.jpg", image_buf.getvalue(), content_type="image/jpeg")

		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="dummyhash8",
		)

		# Send initial OTP
		self.client.post(reverse("pod-otp-send"), {"pod_id": pod.pk}, format="json")

		# Try to resend immediately (with min delay of 60s)
		resend_resp = self.client.post(reverse("pod-otp-resend"), {"pod_id": pod.pk}, format="json")
		self.assertEqual(resend_resp.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn("Please wait", resend_resp.data["detail"])
		self.assertIn("seconds", resend_resp.data["detail"])

		# With delay set to 0, resend should succeed
		with self.settings(POD_OTP_RESEND_DELAY_SECONDS=0):
			resend_resp = self.client.post(reverse("pod-otp-resend"), {"pod_id": pod.pk}, format="json")
			self.assertEqual(resend_resp.status_code, status.HTTP_201_CREATED)

	def test_resend_otp_needs_authentication(self):
		image_buf = BytesIO()
		image = Image.new("RGB", (64, 64), color=(255, 255, 128))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("pod10.jpg", image_buf.getvalue(), content_type="image/jpeg")

		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="dummyhash9",
		)

		# Logout and try resend
		self.client.force_authenticate(user=None)
		resend_resp = self.client.post(reverse("pod-otp-resend"), {"pod_id": pod.pk}, format="json")
		self.assertEqual(resend_resp.status_code, status.HTTP_401_UNAUTHORIZED)


class BatchRetryFailedSMSTests(TestCase):
	"""Tests for batch retry of failed SMS messages"""
	
	def setUp(self):
		self.customer = User.objects.create_user(phone='+251912345678', email='test@example.com')
		self.shipment = Shipment.objects.create(
			customer=self.customer,
			pickup_address='Pickup',
			dropoff_address='Dropoff',
			pickup_location=Point(9.0, 38.0),
			dropoff_location=Point(9.01, 38.01),
			weight=10.0,
			volume=1.0,
		)
	
	def test_get_retryable_failed_receipts_filters_correctly(self):
		"""Verify retryable receipts are filtered by status and retry count"""
		from apps.shipments.services.batch_retry_service import get_retryable_failed_receipts
		
		# Create POD and OTP
		image_buf = BytesIO()
		image = Image.new("RGB", (64, 64), color=(200, 200, 200))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("retry_test.jpg", image_buf.getvalue(), content_type="image/jpeg")
		
		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="retrytesthash1",
		)
		
		otp = ShipmentPODOTP.objects.create(
			pod=pod,
			phone='+251912345678',
			code='123456',
			expires_at=timezone.now() + timedelta(minutes=5),
		)
		
		# Create receipts
		receipt_failed = TwilioDeliveryReceipt.objects.create(
			otp=otp,
			message_sid='SM1234567890failed',
			status='failed',
			retry_count=0,
			eligible_for_retry=True,
		)
		
		receipt_old_sent = TwilioDeliveryReceipt.objects.create(
			otp=otp,
			message_sid='SM1234567890sent',
			status='sent',
			retry_count=0,
			eligible_for_retry=True,
		)
		
		receipt_max_retries = TwilioDeliveryReceipt.objects.create(
			otp=otp,
			message_sid='SM1234567890maxed',
			status='failed',
			retry_count=3,
			eligible_for_retry=True,
		)
		
		receipt_ineligible = TwilioDeliveryReceipt.objects.create(
			otp=otp,
			message_sid='SM1234567890ineligible',
			status='failed',
			retry_count=0,
			eligible_for_retry=False,
		)
		
		# Get retryable
		retryable = get_retryable_failed_receipts(limit=100)
		retryable_ids = [r.pk for r in retryable]
		
		# Verify
		self.assertIn(receipt_failed.pk, retryable_ids)
		self.assertNotIn(receipt_old_sent.pk, retryable_ids)  # Status is 'sent', not failed
		self.assertNotIn(receipt_max_retries.pk, retryable_ids)  # Retry count at max
		self.assertNotIn(receipt_ineligible.pk, retryable_ids)  # Not eligible
	
	def test_batch_retry_failed_sms_increments_retry_count(self):
		"""Verify batch retry increments retry_count and updates last_retry_at"""
		from apps.shipments.services.batch_retry_service import batch_retry_failed_sms
		from unittest.mock import patch
		
		# Create POD, OTP, and failed receipt
		image_buf = BytesIO()
		image = Image.new("RGB", (64, 64), color=(200, 200, 200))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("batch_retry_test.jpg", image_buf.getvalue(), content_type="image/jpeg")
		
		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="batchretryhash1",
		)
		
		otp = ShipmentPODOTP.objects.create(
			pod=pod,
			phone='+251912345678',
			code='123456',
			expires_at=timezone.now() + timedelta(minutes=5),
		)
		
		receipt = TwilioDeliveryReceipt.objects.create(
			otp=otp,
			message_sid='SM1234567890batchtest',
			status='failed',
			retry_count=0,
			eligible_for_retry=True,
		)
		
		with patch('apps.shipments.services.batch_retry_service.send_sms', return_value='SMnewsid123'):
			with patch('apps.shipments.services.batch_retry_service.send_failed_sms_retry_notification'):
				results = batch_retry_failed_sms(limit=100, dry_run=False)
		
		# Verify receipt updated
		receipt.refresh_from_db()
		self.assertEqual(receipt.retry_count, 1)
		self.assertIsNotNone(receipt.last_retry_at)
		self.assertEqual(receipt.status, 'queued')
		
		# Verify results
		self.assertEqual(results['successful_retries'], 1)
		self.assertEqual(results['total_processed'], 1)
	
	def test_batch_retry_marks_ineligible_after_max(self):
		"""Verify receipt marked ineligible after max retry attempts"""
		from apps.shipments.services.batch_retry_service import retry_failed_sms
		from unittest.mock import patch
		
		image_buf = BytesIO()
		image = Image.new("RGB", (64, 64), color=(200, 200, 200))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("ineligible_test.jpg", image_buf.getvalue(), content_type="image/jpeg")
		
		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="ineligiblehash1",
		)
		
		otp = ShipmentPODOTP.objects.create(
			pod=pod,
			phone='+251912345678',
			code='123456',
			expires_at=timezone.now() + timedelta(minutes=5),
		)
		
		# Receipt at max-1 retries
		receipt = TwilioDeliveryReceipt.objects.create(
			otp=otp,
			message_sid='SM1234567890ineligtest',
			status='failed',
			retry_count=2,  # Default max is 3, so this is max-1
			eligible_for_retry=True,
		)
		
		with patch('apps.shipments.services.batch_retry_service.send_sms', side_effect=Exception("Network error")):
			with patch('apps.shipments.services.batch_retry_service.send_failed_sms_retry_notification'):
				result = retry_failed_sms(receipt)
		
		# Verify marked ineligible
		receipt.refresh_from_db()
		self.assertFalse(receipt.eligible_for_retry)
		self.assertFalse(result['success'])
	
	def test_batch_retry_dry_run_no_changes(self):
		"""Verify dry-run doesn't modify data"""
		from apps.shipments.services.batch_retry_service import batch_retry_failed_sms
		
		image_buf = BytesIO()
		image = Image.new("RGB", (64, 64), color=(200, 200, 200))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("dryrun_test.jpg", image_buf.getvalue(), content_type="image/jpeg")
		
		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="dryrunhash1",
		)
		
		otp = ShipmentPODOTP.objects.create(
			pod=pod,
			phone='+251912345678',
			code='123456',
			expires_at=timezone.now() + timedelta(minutes=5),
		)
		
		receipt = TwilioDeliveryReceipt.objects.create(
			otp=otp,
			message_sid='SM1234567890dryrun',
			status='failed',
			retry_count=0,
			eligible_for_retry=True,
		)
		
		# Run dry-run
		results = batch_retry_failed_sms(limit=100, dry_run=True)
		
		# Verify no changes
		receipt.refresh_from_db()
		self.assertEqual(receipt.retry_count, 0)
		self.assertIsNone(receipt.last_retry_at)
		
		# Verify details show action
		self.assertEqual(len(results['details']), 1)
		self.assertEqual(results['details'][0]['action'], 'WOULD_RETRY')


class ResendNotificationTests(TestCase):
	"""Tests for OTP resend notifications"""
	
	def setUp(self):
		self.customer = User.objects.create_user(phone='+251912345678', email='test@example.com')
		self.shipment = Shipment.objects.create(
			customer=self.customer,
			pickup_address='Pickup',
			dropoff_address='Dropoff',
			pickup_location=Point(9.0, 38.0),
			dropoff_location=Point(9.01, 38.01),
			weight=10.0,
			volume=1.0,
		)
	
	def test_send_otp_resend_notification_called_on_resend(self):
		"""Verify send_otp_resend_notification is called from resend endpoint"""
		from unittest.mock import patch
		
		self.client.force_authenticate(user=self.customer)
		
		# Create POD
		image_buf = BytesIO()
		image = Image.new("RGB", (64, 64), color=(100, 100, 100))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("notif_test.jpg", image_buf.getvalue(), content_type="image/jpeg")
		
		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="notifhash1",
		)
		
		# Send initial OTP
		with patch('apps.shipments.services.otp_service.send_sms', return_value='SMinitialsid'):
			self.client.post(reverse("pod-otp-send"), {"pod_id": pod.pk}, format="json")
		
		# Mock notification service
		with patch('apps.shipments.api.views.send_otp_resend_notification') as mock_notify:
			with patch('apps.shipments.services.otp_service.send_sms', return_value='SMresendid'):
				with self.settings(POD_OTP_RESEND_DELAY_SECONDS=0):
					self.client.post(reverse("pod-otp-resend"), {"pod_id": pod.pk}, format="json")
		
		# Verify notification called
		self.assertTrue(mock_notify.called)
		call_kwargs = mock_notify.call_args[1]
		self.assertEqual(call_kwargs['pod'].pk, pod.pk)
		self.assertEqual(call_kwargs['remaining_resends'], 2)  # Default max 3, so 2 left
	
	def test_notification_service_gracefully_handles_failures(self):
		"""Verify notification failures don't break OTP resend"""
		from unittest.mock import patch
		
		self.client.force_authenticate(user=self.customer)
		
		image_buf = BytesIO()
		image = Image.new("RGB", (64, 64), color=(100, 100, 100))
		image.save(image_buf, format="JPEG")
		image_file = SimpleUploadedFile("notification_fail.jpg", image_buf.getvalue(), content_type="image/jpeg")
		
		pod = ShipmentProofOfDelivery.objects.create(
			shipment=self.shipment,
			uploaded_by=self.customer,
			photo=image_file,
			image_sha256="notiffailhash",
		)
		
		# Send initial OTP
		with patch('apps.shipments.services.otp_service.send_sms', return_value='SMinitialsid'):
			self.client.post(reverse("pod-otp-send"), {"pod_id": pod.pk}, format="json")
		
		# Mock notification to raise error
		with patch('apps.shipments.api.views.send_otp_resend_notification', side_effect=Exception("Firebase down")):
			with patch('apps.shipments.services.otp_service.send_sms', return_value='SMresendid'):
				with self.settings(POD_OTP_RESEND_DELAY_SECONDS=0):
					# Should still return 201
					resend_resp = self.client.post(reverse("pod-otp-resend"), {"pod_id": pod.pk}, format="json")
		
		# Verify OTP resend succeeded despite notification failure
		self.assertEqual(resend_resp.status_code, status.HTTP_201_CREATED)
		self.assertIn("resend_count", resend_resp.data)


