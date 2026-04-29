import uuid

from django.contrib.gis.geos import Point
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.rating.api.views import CreateRatingView
from apps.drivers.models import DriverProfile
from apps.rating.models import Rating
from apps.shipments.models import Shipment
from apps.users.models import User


def _unique_email(prefix):
	return f"{prefix}-{uuid.uuid4().hex[:12]}@test.example"


def _create_user(role, prefix):
	return User.objects.create_user(
		_unique_email(prefix),
		"TestPassw0rd!",
		role=role,
		phone=f"+2519{uuid.uuid4().int % 10**8:08d}",
	)


def _create_driver():
	driver_user = _create_user("driver", "driver")
	return DriverProfile.objects.create(
		user=driver_user,
		national_id=f"NID-{uuid.uuid4().hex[:8]}",
		driver_license=f"LIC-{uuid.uuid4().hex[:8]}",
	)


def _create_shipment(customer, driver, status="delivered"):
	return Shipment.objects.create(
		customer=customer,
		driver=driver,
		pickup_address="Pickup Address",
		dropoff_address="Dropoff Address",
		pickup_location=Point(38.75, 9.03),
		dropoff_location=Point(38.80, 9.04),
		weight=10.0,
		volume=1.5,
		status=status,
		assigned_at=None,
		picked_up_at=None,
		delivered_at=None,
	)


class RatingAPITests(TestCase):
	def setUp(self):
		self.factory = APIRequestFactory()
		self.view = CreateRatingView.as_view()

	def _post(self, user, payload):
		request = self.factory.post("/api/ratings/", payload, format="json")
		force_authenticate(request, user=user)
		return self.view(request)

	def test_customer_can_rate_delivered_shipment(self):
		customer = _create_user("customer", "customer")
		driver = _create_driver()
		shipment = _create_shipment(customer, driver, status="delivered")

		response = self._post(customer, {"shipment_id": shipment.pk, "score": 4, "comment": "Great service"})

		self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
		self.assertEqual(Rating.objects.count(), 1)
		rating = Rating.objects.get()
		self.assertEqual(rating.shipment, shipment)
		self.assertEqual(rating.driver, driver)
		self.assertEqual(rating.customer, customer)
		driver.refresh_from_db()
		self.assertEqual(driver.rating, 4.0)

	def test_customer_cannot_rate_before_delivery(self):
		customer = _create_user("customer", "customer")
		driver = _create_driver()
		shipment = _create_shipment(customer, driver, status="assigned")

		response = self._post(customer, {"shipment_id": shipment.pk, "score": 5, "comment": "Too early"})

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(Rating.objects.count(), 0)

	def test_only_shipment_owner_can_rate(self):
		customer = _create_user("customer", "customer")
		other_customer = _create_user("customer", "other")
		driver = _create_driver()
		shipment = _create_shipment(customer, driver, status="completed")

		response = self._post(other_customer, {"shipment_id": shipment.pk, "score": 3, "comment": "Not mine"})

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(Rating.objects.count(), 0)

	def test_one_rating_per_shipment(self):
		customer = _create_user("customer", "customer")
		driver = _create_driver()
		shipment = _create_shipment(customer, driver, status="completed")

		first = self._post(customer, {"shipment_id": shipment.pk, "score": 5, "comment": "Nice"})
		self.assertEqual(first.status_code, status.HTTP_201_CREATED)

		second = self._post(customer, {"shipment_id": shipment.pk, "score": 1, "comment": "Duplicate"})
		self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(Rating.objects.filter(shipment=shipment).count(), 1)

	def test_driver_rating_is_average_of_ratings(self):
		customer1 = _create_user("customer", "customer")
		customer2 = _create_user("customer", "customer")
		driver = _create_driver()
		shipment1 = _create_shipment(customer1, driver, status="delivered")
		shipment2 = _create_shipment(customer2, driver, status="completed")

		response1 = self._post(customer1, {"shipment_id": shipment1.pk, "score": 5, "comment": "Great"})
		self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

		response2 = self._post(customer2, {"shipment_id": shipment2.pk, "score": 3, "comment": "Okay"})
		self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

		driver.refresh_from_db()
		self.assertEqual(driver.rating, 4.0)
