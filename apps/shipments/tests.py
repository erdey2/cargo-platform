from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.shipments.models import Shipment, ShipmentStatusHistory
from apps.users.models import User


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

		response = self.client.delete(reverse("shipments-detail", args=[shipment.id]))

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

		response = self.client.delete(reverse("shipments-detail", args=[shipment.id]))

		self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
		shipment.refresh_from_db()
		self.assertEqual(shipment.status, "cancelled")

	def test_customer_cannot_cancel_assigned_shipment(self):
		shipment = self._create_shipment("assigned")

		response = self.client.delete(reverse("shipments-detail", args=[shipment.id]))

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		shipment.refresh_from_db()
		self.assertEqual(shipment.status, "assigned")
