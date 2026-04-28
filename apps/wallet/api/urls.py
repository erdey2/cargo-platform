from django.urls import path
from .views import (
    DriverWalletView,
    WalletTransactionListView,
    RequestPayoutView,
    ApprovePayoutView,
    RejectPayoutView,
)

urlpatterns = [
    path("wallet/", DriverWalletView.as_view(), name="driver-wallet"),
    path("wallet/transactions/", WalletTransactionListView.as_view(), name="wallet-transactions"),
    path("wallet/payout/request/", RequestPayoutView.as_view(), name="request-payout"),
    path("wallet/payout/<int:payout_id>/approve/", ApprovePayoutView.as_view(), name="approve-payout"),
    path("wallet/payout/<int:payout_id>/reject/", RejectPayoutView.as_view(), name="reject-payout"),
]