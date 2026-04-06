from django.urls import path
from .views import CreatePaymentView


urlpatterns = [
    path("shipments/<int:shipment_id>/payments/", CreatePaymentView.as_view(), name="create-payment"),
]
