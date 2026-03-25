from celery import shared_task
from apps.matching.services.offer_service import OfferService


@shared_task
def expire_offers_task():
    OfferService.expire_and_reassign()