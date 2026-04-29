from django.test import TestCase
from decimal import Decimal

from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework import status

from apps.users.models import User
from apps.drivers.models import DriverProfile
from apps.wallet.services.wallet_service import WalletService
from apps.wallet.models import DriverWallet, WalletTransaction, DriverPayout
from apps.wallet.api.views import RequestPayoutView


class WalletServiceTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(email="driver@example.com", password="pass", role="driver")
		self.driver = DriverProfile.objects.create(user=self.user, national_id="nid", driver_license="lic")

	def test_credit_driver_creates_wallet_and_transaction(self):
		WalletService.credit_driver(
			driver=self.driver,
			amount=Decimal("100.00"),
			reference="ref-test-1",
			description="Test credit",
			platform_fee=Decimal("10.00"),
		)

		wallet = DriverWallet.objects.get(driver=self.driver)
		self.assertEqual(wallet.balance, Decimal("90.00"))

		tx = WalletTransaction.objects.get(reference="ref-test-1", type="credit")
		self.assertEqual(tx.amount, Decimal("100.00"))
		self.assertEqual(tx.driver_earning, Decimal("90.00"))

	def test_credit_idempotency(self):
		WalletService.credit_driver(
			driver=self.driver,
			amount=Decimal("50.00"),
			reference="ref-idemp",
			platform_fee=Decimal("5.00"),
		)

		# second call should be a no-op
		WalletService.credit_driver(
			driver=self.driver,
			amount=Decimal("50.00"),
			reference="ref-idemp",
			platform_fee=Decimal("5.00"),
		)

		wallet = DriverWallet.objects.get(driver=self.driver)
		self.assertEqual(wallet.balance, Decimal("45.00"))

		txs = WalletTransaction.objects.filter(reference="ref-idemp", type="credit")
		self.assertEqual(txs.count(), 1)


class RequestPayoutViewTests(TestCase):
	def setUp(self):
		self.factory = APIRequestFactory()
		self.user = User.objects.create_user(email="driver2@example.com", password="pass", role="driver")
		self.driver = DriverProfile.objects.create(user=self.user, national_id="nid2", driver_license="lic2")

	def test_request_payout_insufficient_when_no_wallet(self):
		request = self.factory.post("/wallet/payout/request/", {"amount": "150.00"}, format="json")
		force_authenticate(request, user=self.user)

		response = RequestPayoutView.as_view()(request)
		# Expect 400 due to insufficient balance
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_request_payout_success(self):
		# seed wallet
		WalletService.credit_driver(
			driver=self.driver,
			amount=Decimal("200.00"),
			reference="seed-1",
			platform_fee=Decimal("0"),
		)

		request = self.factory.post("/wallet/payout/request/", {"amount": "150.00"}, format="json")
		force_authenticate(request, user=self.user)

		response = RequestPayoutView.as_view()(request)
		self.assertEqual(response.status_code, status.HTTP_200_OK)

		payout_id = response.data.get("payout_id")
		payout = DriverPayout.objects.get(id=payout_id)
		self.assertEqual(payout.amount, Decimal("150.00"))
