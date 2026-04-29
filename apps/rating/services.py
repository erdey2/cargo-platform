from decimal import Decimal

class RatingService:

    @staticmethod
    def update_driver_rating(driver, new_score):
        total = driver.total_ratings
        current_avg = driver.average_rating or Decimal("0")

        new_total = total + 1

        new_avg = ((current_avg * total) + Decimal(new_score)) / new_total

        driver.average_rating = round(new_avg, 2)
        driver.total_ratings = new_total

        driver.save(update_fields=["average_rating", "total_ratings"])