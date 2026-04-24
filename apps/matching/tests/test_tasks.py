from django.test import TestCase
from unittest.mock import patch

from apps.matching.tasks import expire_offers_task, start_driver_matching
from apps.matching.tests.helpers import MatchingTestDataMixin


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

