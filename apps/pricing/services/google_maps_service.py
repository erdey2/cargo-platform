import requests
from django.conf import settings


class GoogleMapsService:

    BASE_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

    @staticmethod
    def get_distance_and_duration(origin, destination):
        """
        origin, destination = (lat, lng)
        returns: (distance_km, duration_minutes)
        """

        params = {
            "origins": f"{origin[0]},{origin[1]}",
            "destinations": f"{destination[0]},{destination[1]}",
            "key": settings.GOOGLE_MAPS_API_KEY,
        }

        response = requests.get(GoogleMapsService.BASE_URL, params=params)
        data = response.json()

        if data["status"] != "OK":
            raise Exception("Google Maps API error")

        element = data["rows"][0]["elements"][0]

        if element["status"] != "OK":
            raise Exception("No route found")

        distance_m = element["distance"]["value"]
        duration_s = element["duration"]["value"]

        distance_km = distance_m / 1000
        duration_min = duration_s / 60

        return distance_km, duration_min