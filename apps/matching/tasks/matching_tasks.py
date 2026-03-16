from celery import shared_task



@shared_task
def start_driver_matching(shipment_id):

    MatchingService.match_driver(shipment_id)