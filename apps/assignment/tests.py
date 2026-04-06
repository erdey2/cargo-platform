from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.assignment.api.views import AssignmentStatusUpdateView
from apps.assignment.services.assignment import AssignmentService


class AssignmentServiceTests(SimpleTestCase):
    @patch("apps.assignment.services.assignment.ShipmentStatusHistory.objects.create")
    def test_rejects_invalid_transition(self, _history_create):
        shipment = SimpleNamespace(
            status="assigned",
            assigned_at=None,
            picked_up_at=None,
            delivered_at=None,
            final_price=None,
            save=MagicMock(),
        )
        assignment = SimpleNamespace(
            status="assigned",
            shipment=shipment,
            picked_up_at=None,
            delivered_at=None,
            save=MagicMock(),
        )
        user = SimpleNamespace(id=1)

        with self.assertRaises(ValidationError):
            AssignmentService.change_status(assignment, "completed", user)

    @patch("apps.assignment.services.assignment.ShipmentStatusHistory.objects.create")
    @patch("apps.assignment.services.assignment.PriceCalculator.calculate_final_price")
    def test_completed_transition_sets_final_price(self, mock_price, mock_history_create):
        mock_price.return_value = 123.45
        shipment = SimpleNamespace(
            status="delivered",
            assigned_at=None,
            picked_up_at=None,
            delivered_at=None,
            final_price=None,
            save=MagicMock(),
        )
        assignment = SimpleNamespace(
            status="delivered",
            shipment=shipment,
            picked_up_at=None,
            delivered_at=None,
            save=MagicMock(),
        )
        user = SimpleNamespace(id=1)

        updated = AssignmentService.change_status(assignment, "completed", user)

        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.shipment.status, "completed")
        self.assertEqual(updated.shipment.final_price, 123.45)
        self.assertTrue(mock_history_create.called)


class AssignmentStatusUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AssignmentStatusUpdateView.as_view()

    @patch("apps.assignment.api.views.AssignmentService.change_status")
    @patch("apps.assignment.api.views.Assignment.objects.select_related")
    def test_forbids_non_owner_non_admin(self, mock_select_related, _change_status):
        owner_user = SimpleNamespace(id=99)
        assignment = SimpleNamespace(driver=SimpleNamespace(user_id=owner_user.id))
        mock_select_related.return_value.get.return_value = assignment

        request_user = SimpleNamespace(
            id=1,
            is_authenticated=True,
            is_staff=False,
            is_superuser=False,
        )
        request = self.factory.post("/api/assignments/1/status/", {"status": "driver_arriving"}, format="json")
        force_authenticate(request, user=request_user)

        response = self.view(request, assignment_id=1)
        self.assertEqual(response.status_code, 403)
