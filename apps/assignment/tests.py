from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.assignment.api.views import AssignmentStatusUpdateView
from apps.assignment.services.assignment import AssignmentService


class AssignmentServiceTests(SimpleTestCase):
    def _build_assignment(self, status="in_transit"):
        shipment = SimpleNamespace(
            status=status,
            driver=SimpleNamespace(user_id=10),
            delivered_at=None,
            proof_of_delivery=None,
            final_price=None,
            is_paid=False,
            customer=SimpleNamespace(id=2),
            save=MagicMock(),
        )
        assignment = SimpleNamespace(
            pk=1,
            id=1,
            status=status,
            shipment=shipment,
            driver=SimpleNamespace(id=10, user=SimpleNamespace(id=10, is_staff=False)),
            picked_up_at=None,
            delivered_at=None,
            save=MagicMock(),
        )
        return assignment

    @patch("apps.assignment.services.assignment.transaction.on_commit", side_effect=lambda func: None)
    @patch("apps.assignment.services.assignment.Assignment.objects.select_for_update")
    def test_rejects_invalid_transition(self, mock_select_for_update, _on_commit):
        assignment = self._build_assignment(status="assigned")
        mock_select_for_update.return_value.get.return_value = assignment
        user = SimpleNamespace(id=1, is_staff=False)

        with self.assertRaises(ValidationError):
            AssignmentService.change_status.__wrapped__(assignment, "completed", user)

    @patch("apps.assignment.services.assignment.transaction.on_commit", side_effect=lambda func: None)
    @patch("apps.assignment.services.assignment.Assignment.objects.create")
    def test_assign_driver_sets_shipment_driver_and_status(self, mock_create, _on_commit):
        shipment = SimpleNamespace(
            id=7,
            customer=SimpleNamespace(id=2),
            status="matching",
            assigned_at=None,
            driver=None,
            save=MagicMock(),
        )
        driver = SimpleNamespace(
            id=11,
            vehicles=SimpleNamespace(first=MagicMock(return_value=SimpleNamespace(id=99))),
            is_available=True,
            save=MagicMock(),
        )
        vehicle = SimpleNamespace(id=99)
        mock_create.return_value = SimpleNamespace(id=1)

        assignment = AssignmentService.assign_driver.__wrapped__(shipment, driver, vehicle=vehicle)

        self.assertEqual(shipment.driver, driver)
        self.assertEqual(shipment.status, "assigned")
        self.assertIsNotNone(shipment.assigned_at)
        shipment.save.assert_called_once()
        driver.save.assert_called_once_with(update_fields=["is_available"])
        self.assertIsNotNone(assignment)

    @patch("apps.assignment.services.assignment.transaction.on_commit", side_effect=lambda func: None)
    @patch("apps.assignment.services.assignment.Assignment.objects.select_for_update")
    def test_delivered_requires_proof_of_delivery(self, mock_select_for_update, _on_commit):
        assignment = self._build_assignment(status="in_transit")
        mock_select_for_update.return_value.get.return_value = assignment
        user = SimpleNamespace(id=1, is_staff=False)

        with self.assertRaises(ValidationError):
            AssignmentService.change_status.__wrapped__(assignment, "delivered", user)

    @patch("apps.assignment.services.assignment.ShipmentStatusHistory.objects.create")
    @patch("apps.assignment.services.assignment.transaction.on_commit", side_effect=lambda func: None)
    @patch("apps.assignment.services.assignment.Assignment.objects.select_for_update")
    def test_delivered_transition_saves_proof_of_delivery(self, mock_select_for_update, _on_commit, _history_create):
        assignment = self._build_assignment(status="in_transit")
        mock_select_for_update.return_value.get.return_value = assignment
        user = SimpleNamespace(id=1, is_staff=False)
        proof = SimpleUploadedFile("proof.jpg", b"fake-image-data", content_type="image/jpeg")

        updated = AssignmentService.change_status.__wrapped__(
            assignment,
            "delivered",
            user,
            proof_of_delivery=proof,
        )

        self.assertEqual(updated.status, "delivered")
        self.assertEqual(updated.shipment.status, "delivered")
        self.assertEqual(updated.shipment.proof_of_delivery, proof)
        self.assertIsNotNone(updated.shipment.delivered_at)
        self.assertTrue(updated.shipment.save.called)
        self.assertTrue(updated.save.called)

    @patch("apps.assignment.services.assignment.async_to_sync", side_effect=lambda fn: fn)
    @patch("apps.assignment.services.assignment.get_channel_layer")
    def test_broadcast_status_update_sends_to_shipment_groups(self, mock_get_channel_layer, _async_to_sync):
        channel_layer = MagicMock()
        channel_layer.group_send = MagicMock()
        mock_get_channel_layer.return_value = channel_layer

        assignment = SimpleNamespace(id=10)
        shipment = SimpleNamespace(id=55, final_price=321.0, updated_at=timezone.now())

        AssignmentService.broadcast_status_update(assignment, shipment, "in_transit")

        self.assertEqual(channel_layer.group_send.call_count, 3)
        called_groups = {call.args[0] for call in channel_layer.group_send.call_args_list}
        self.assertEqual(
            called_groups,
            {
                "shipment_55_customer",
                "shipment_55_driver",
                "shipment_55_admin",
            },
        )


class AssignmentStatusUpdateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = AssignmentStatusUpdateView.as_view()

    @patch("apps.assignment.api.views.AssignmentSerializer")
    @patch("apps.assignment.api.views.AssignmentService.change_status")
    @patch("apps.assignment.api.views.Assignment.objects.select_related")
    def test_forbids_non_owner_non_admin(self, mock_select_related, _change_status, _serializer):
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
        force_authenticate(request, user=request_user)  # type: ignore[arg-type]

        response = self.view(request, assignment_id=1)
        self.assertEqual(response.status_code, 403)

    @patch("apps.assignment.api.views.AssignmentSerializer")
    @patch("apps.assignment.api.views.AssignmentService.change_status")
    @patch("apps.assignment.api.views.Assignment.objects.select_related")
    def test_accepts_delivered_with_proof_upload(self, mock_select_related, mock_change_status, mock_serializer):
        owner_user = SimpleNamespace(id=99)
        assignment = SimpleNamespace(driver=SimpleNamespace(user_id=owner_user.id))
        mock_select_related.return_value.get.return_value = assignment
        mock_change_status.return_value = assignment
        mock_serializer.return_value.data = {"id": 1, "status": "delivered"}

        request_user = SimpleNamespace(
            id=99,
            is_authenticated=True,
            is_staff=False,
            is_superuser=False,
        )
        proof = SimpleUploadedFile("proof.jpg", b"fake-image-data", content_type="image/jpeg")
        request = self.factory.post(
            "/api/assignments/1/status/",
            {"status": "delivered", "proof_of_delivery": proof},
            format="multipart",
        )
        force_authenticate(request, user=request_user)  # type: ignore[arg-type]

        response = self.view(request, assignment_id=1)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_change_status.called)
        self.assertIsNotNone(mock_change_status.call_args.kwargs.get("proof_of_delivery"))

    @patch("apps.assignment.api.views.Assignment.objects.select_related")
    def test_rejects_delivered_without_proof_upload(self, mock_select_related):
        owner_user = SimpleNamespace(id=99)
        assignment = SimpleNamespace(driver=SimpleNamespace(user_id=owner_user.id))
        mock_select_related.return_value.get.return_value = assignment

        request_user = SimpleNamespace(
            id=99,
            is_authenticated=True,
            is_staff=False,
            is_superuser=False,
        )
        request = self.factory.post(
            "/api/assignments/1/status/",
            {"status": "delivered"},
            format="json",
        )
        force_authenticate(request, user=request_user)  # type: ignore[arg-type]

        response = self.view(request, assignment_id=1)

        self.assertEqual(response.status_code, 400)

