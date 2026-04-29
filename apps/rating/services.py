from django.db.models import Avg

from apps.drivers.models import DriverProfile
from apps.rating.models import Rating


class RatingService:
    @staticmethod
    def refresh_driver_rating(driver: DriverProfile):
        average = Rating.objects.filter(driver=driver).aggregate(avg=Avg("score"))["avg"]
        driver.rating = float(average) if average is not None else 5.0
        driver.save(update_fields=["rating"])

