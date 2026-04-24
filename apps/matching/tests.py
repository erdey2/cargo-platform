from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.assignment.models import Assignment
from apps.drivers.models import DriverProfile
from apps.matching.models import DriverOffer
from apps.matching.services.offer_service import OfferService
from apps.matching.tasks import expire_offers_task, start_driver_matching
from apps.shipments.models import Shipment, ShipmentStatusHistory
from apps.users.models import User
from apps.vehicles.models import Vehicle, VehicleType


class MatchingTestDataMixin:
    def create_user(self, *, email: str, role: str):
        return User.objects.create_user(email=email, password="pass123", role=role)

    def create_driver_profile(self, *, email: str = "driver@example.com"):
        user = self.create_user(email=email, role="driver")
        driver = DriverProfile.objects.create(
            user=user,
            national_id=f"nid-{user.id}",
            driver_license=f"lic-{user.id}",
            verification_status="verified",
            is_available=True,
        )
        return user, driver

    def create_shipment(self, customer, *, status: str = "matching"):
        return Shipment.objects.create(
            customer=customer,
            pickup_address="Addis Ababa",
            dropoff_address="Adama",
            pickup_location=Point(38.7578, 8.9806, srid=4326),
            dropoff_location=Point(39.2695, 8.5414, srid=4326),
            weight=100,
            volume=2,
            status=status,
        )

    def create_vehicle(self, driver, plate_suffix="1"):
        vtype = VehicleType.objects.create(
            name=f"Truck-{plate_suffix}",
            max_weight=1000,
            max_volume=20,
        )
        return Vehicle.objects.create(
            driver=driver,
            vehicle_type=vtype,
            plate_number=f"A-{plate_suffix}",
            capacity_weight=1000,
            capacity_volume=20,
            verification_status=True,
        )


class MatchingTasksTests(MatchingTestDataMixin, TestCase):
    @patch("apps.matching.tasks.MatchingService.match_driver")
    def test_start_driver_matching_calls_matching_service(self, match_driver_mock):
        customer = self.create_user(email="customer1@example.com", role="customer")
        shipment = self.create_shipment(customer)

        start_driver_matching(shipment.id)

        match_driver_mock.assert_called_once()
        called_shipment = match_driver_mock.call_args[0][0]
        self.assertEqual(called_shipment.id, shipment.id)

    @patch("apps.matching.tasks.MatchingService.match_driver")
    def test_start_driver_matching_ignores_missing_shipment(self, match_driver_mock):
        start_driver_matching(999999)
        match_driver_mock.assert_not_called()

    @patch("apps.matching.tasks.OfferService.expire_and_reassign")
    def test_expire_offers_task_calls_offer_service(self, expire_and_reassign_mock):
        expire_offers_task()
        expire_and_reassign_mock.assert_called_once()


class OfferServiceTests(MatchingTestDataMixin, TestCase):
    @patch("apps.matching.tasks.start_driver_matching.delay")
    @patch("apps.matching.services.offer_service.notify_user")
    def test_expire_and_reassign_expires_offer_and_requeues(
        self, notify_user_mock, start_driver_matching_delay_mock
    ):
        customer = self.create_user(email="customer2@example.com", role="customer")
        _, driver = self.create_driver_profile(email="driver2@example.com")
        shipment = self.create_shipment(customer, status="matching")
        vehicle = self.create_vehicle(driver, plate_suffix="2")

        offer = DriverOffer.objects.create(
            shipment=shipment,
            driver=driver,
            vehicle=vehicle,
            status="pending",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        OfferService.expire_and_reassign()

        offer.refresh_from_db()
        self.assertEqual(offer.status, "expired")
        self.assertEqual(notify_user_mock.call_count, 2)
        start_driver_matching_delay_mock.assert_called_once_with(shipment.id)

    @patch("apps.matching.tasks.start_driver_matching.delay")
    @patch("apps.matching.services.offer_service.notify_user")
    def test_expire_and_reassign_does_not_requeue_when_shipment_not_matching(
        self, notify_user_mock, start_driver_matching_delay_mock
    ):
        customer = self.create_user(email="customer3@example.com", role="customer")
        _, driver = self.create_driver_profile(email="driver3@example.com")
        shipment = self.create_shipment(customer, status="assigned")
        vehicle = self.create_vehicle(driver, plate_suffix="3")

        offer = DriverOffer.objects.create(
            shipment=shipment,
            driver=driver,
            vehicle=vehicle,
            status="pending",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        OfferService.expire_and_reassign()

        offer.refresh_from_db()
        self.assertEqual(offer.status, "expired")
        self.assertEqual(notify_user_mock.call_count, 1)
        start_driver_matching_delay_mock.assert_not_called()


class DriverResponseViewTests(MatchingTestDataMixin, TestCase):
    def setUp(self):
        self.client = APIClient()

    def _url(self, offer_id):
        return f"/api/matching/offers/{offer_id}/respond/"

    def _build_offer(self, *, expires_delta_seconds=60):
        customer = self.create_user(email="customer4@example.com", role="customer")
        driver_user, driver = self.create_driver_profile(email="driver4@example.com")
        shipment = self.create_shipment(customer, status="matching")
        vehicle = self.create_vehicle(driver, plate_suffix="4")
        offer = DriverOffer.objects.create(
            shipment=shipment,
            driver=driver,
            vehicle=vehicle,
            status="pending",
            expires_at=timezone.now() + timedelta(seconds=expires_delta_seconds),
        )
        return customer, driver_user, driver, shipment, offer

    @patch("apps.matching.api.views.get_channel_layer")
    @patch("apps.matching.api.views.async_to_sync")
    def test_accept_offer_updates_assignment_and_shipment(self, async_to_sync_mock, get_layer_mock):
        _, driver_user, driver, shipment, offer = self._build_offer()

        layer = Mock()
        get_layer_mock.return_value = layer
        async_to_sync_mock.side_effect = lambda fn: fn

        self.client.force_authenticate(user=driver_user)
        response = self.client.post(self._url(offer.id), {"action": "accept"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Accepted")

        offer.refresh_from_db()
        shipment.refresh_from_db()
        driver.refresh_from_db()

        self.assertEqual(offer.status, "accepted")
        self.assertIsNotNone(offer.responded_at)
        self.assertEqual(shipment.status, "assigned")
        self.assertEqual(shipment.driver_id, driver.id)
        self.assertFalse(driver.is_available)
        self.assertTrue(Assignment.objects.filter(shipment=shipment, driver=driver).exists())
        self.assertTrue(ShipmentStatusHistory.objects.filter(shipment=shipment, status="assigned").exists())

        layer.group_send.assert_called_once()
        sent_group = layer.group_send.call_args[0][0]
        sent_payload = layer.group_send.call_args[0][1]
        self.assertEqual(sent_group, f"user_{shipment.customer.id}")
        self.assertEqual(sent_payload["type"], "shipment_matched")

    @patch("apps.matching.api.views.get_channel_layer")
    @patch("apps.matching.api.views.async_to_sync")
    @patch("apps.matching.api.views.MatchingService.match_next_driver", create=True)
    def test_reject_offer_triggers_next_driver(
        self, match_next_driver_mock, async_to_sync_mock, get_layer_mock
    ):
        _, driver_user, _, shipment, offer = self._build_offer()

        layer = Mock()
        get_layer_mock.return_value = layer
        async_to_sync_mock.side_effect = lambda fn: fn

        self.client.force_authenticate(user=driver_user)
        response = self.client.post(self._url(offer.id), {"action": "reject"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Rejected")

        offer.refresh_from_db()
        self.assertEqual(offer.status, "rejected")
        self.assertIsNotNone(offer.responded_at)
        match_next_driver_mock.assert_called_once()
        called_shipment = match_next_driver_mock.call_args[0][0]
        self.assertEqual(called_shipment.id, shipment.id)

        layer.group_send.assert_called_once()
        sent_payload = layer.group_send.call_args[0][1]
        self.assertEqual(sent_payload["type"], "shipment_update")

    def test_reject_offer_denies_non_owner_driver(self):
        _, _, _, _, offer = self._build_offer()
        other_driver_user, _ = self.create_driver_profile(email="other-driver@example.com")

        self.client.force_authenticate(user=other_driver_user)
        response = self.client.post(self._url(offer.id), {"action": "reject"}, format="json")

        self.assertEqual(response.status_code, 403)
        offer.refresh_from_db()
        self.assertEqual(offer.status, "pending")

    @patch("apps.matching.api.views.MatchingService.match_next_driver", create=True)
    def test_expired_offer_marks_expired_and_returns_error(self, match_next_driver_mock):
        _, driver_user, _, _, offer = self._build_offer(expires_delta_seconds=-60)

        self.client.force_authenticate(user=driver_user)
        response = self.client.post(self._url(offer.id), {"action": "accept"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Offer expired")

        offer.refresh_from_db()
        self.assertEqual(offer.status, "expired")
        match_next_driver_mock.assert_called_once()
