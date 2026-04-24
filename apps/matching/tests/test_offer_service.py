from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.matching.models import DriverOffer
from apps.matching.services.offer_service import OfferService
from apps.matching.tests.helpers import MatchingTestDataMixin


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

