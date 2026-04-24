from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.matching.models import DriverOffer
from apps.matching.services.matching import MatchingService
from apps.matching.tests.helpers import MatchingTestDataMixin


class MatchingServiceTests(MatchingTestDataMixin, TestCase):
    @patch("apps.matching.services.matching.MatchingService.create_offer")
    @patch("apps.matching.services.matching.MatchingService.get_best_vehicle")
    @patch("apps.matching.services.matching.MatchingService.find_nearest_drivers")
    def test_match_next_driver_skips_previously_offered_driver(
        self,
        find_nearest_drivers_mock,
        get_best_vehicle_mock,
        create_offer_mock,
    ):
        customer = self.create_user(email="customer-ms1@example.com", role="customer")
        shipment = self.create_shipment(customer, status="matching")

        _, driver1 = self.create_driver_profile(email="driver-ms1@example.com")
        _, driver2 = self.create_driver_profile(email="driver-ms2@example.com")

        vehicle2 = self.create_vehicle(driver2, plate_suffix="ms2")

        DriverOffer.objects.create(
            shipment=shipment,
            driver=driver1,
            vehicle=self.create_vehicle(driver1, plate_suffix="ms1"),
            status="rejected",
            expires_at=shipment.created_at,
        )

        candidate1 = SimpleNamespace(driver=driver1)
        candidate2 = SimpleNamespace(driver=driver2)
        find_nearest_drivers_mock.return_value = [candidate1, candidate2]

        def vehicle_selector(driver, _shipment):
            return vehicle2 if driver.id == driver2.id else None

        get_best_vehicle_mock.side_effect = vehicle_selector

        created_offer = object()
        create_offer_mock.return_value = created_offer

        result = MatchingService.match_next_driver(shipment)

        self.assertIs(result, created_offer)
        find_nearest_drivers_mock.assert_called_once()
        _, kwargs = find_nearest_drivers_mock.call_args
        excluded_ids = set(kwargs["exclude_driver_ids"])
        self.assertIn(driver1.id, excluded_ids)
        create_offer_mock.assert_called_once_with(shipment, driver2, vehicle2, candidate2)

    @patch("apps.matching.services.matching.MatchingService.find_nearest_drivers")
    def test_match_next_driver_returns_none_when_pending_offer_exists(self, find_nearest_drivers_mock):
        customer = self.create_user(email="customer-ms2@example.com", role="customer")
        shipment = self.create_shipment(customer, status="matching")

        _, driver = self.create_driver_profile(email="driver-ms3@example.com")
        DriverOffer.objects.create(
            shipment=shipment,
            driver=driver,
            vehicle=self.create_vehicle(driver, plate_suffix="ms3"),
            status="pending",
            expires_at=shipment.created_at,
        )

        result = MatchingService.match_next_driver(shipment)

        self.assertIsNone(result)
        find_nearest_drivers_mock.assert_not_called()

    @patch("apps.matching.services.matching.MatchingService.mark_no_driver")
    @patch("apps.matching.services.matching.MatchingService.find_nearest_drivers")
    def test_match_next_driver_marks_no_driver_when_no_new_candidates(
        self,
        find_nearest_drivers_mock,
        mark_no_driver_mock,
    ):
        customer = self.create_user(email="customer-ms3@example.com", role="customer")
        shipment = self.create_shipment(customer, status="matching")

        find_nearest_drivers_mock.return_value = []

        result = MatchingService.match_next_driver(shipment)

        self.assertIsNone(result)
        mark_no_driver_mock.assert_called_once_with(shipment)

