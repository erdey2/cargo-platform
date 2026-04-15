from celery import shared_task
from apps.matching.services.matching import MatchingService


@shared_task
def start_driver_matching(shipment_id):

    MatchingService.match_driver(shipment_id)