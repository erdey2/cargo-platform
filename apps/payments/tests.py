from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.payments.api.views import CreatePaymentView


class CreatePaymentViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CreatePaymentView.as_view()

    @patch("apps.payments.api.views.Transaction.objects.filter")
    @patch("apps.payments.api.views.Transaction.objects.create")
    @patch("apps.payments.api.views.Shipment.objects.get")
    def test_rejects_non_owner_payment(self, mock_get_shipment, _create_txn, _filter_txn):
        shipment = SimpleNamespace(id=1, customer_id=200, final_price=1500)
        mock_get_shipment.return_value = shipment

        request_user = SimpleNamespace(
            id=100,
            is_authenticated=True,
            is_staff=False,
            is_superuser=False,
        )
        request = self.factory.post(
            "/api/shipments/1/payments/",
            {"payment_method": "cash"},
            format="json",
        )
        force_authenticate(request, user=request_user)

        response = self.view(request, shipment_id=1)
        self.assertEqual(response.status_code, 400)
