from celery import shared_task
from apps.shipments.models import Shipment
from apps.matching.services.matching import MatchingService
from apps.matching.services.offer_service import OfferService

@shared_task
def start_driver_matching(shipment_id):
    shipment = Shipment.objects.get(id=shipment_id)
    MatchingService.match_driver(shipment)

@shared_task
def expire_offers_task():
    print("Running expire_offers_task")
    OfferService.expire_and_reassign()