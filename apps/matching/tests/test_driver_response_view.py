from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.assignment.models import Assignment
from apps.matching.models import DriverOffer
from apps.shipments.models import ShipmentStatusHistory
from apps.matching.tests.helpers import MatchingTestDataMixin


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

