import requests


class OSRMService:

    BASE_URL = "http://router.project-osrm.org/route/v1/driving/"

    @staticmethod
    def get_road_distance(pickup, dropoff):
        """
        Returns distance in kilometers
        """

        url = (
            f"{OSRMService.BASE_URL}"
            f"{pickup.x},{pickup.y};{dropoff.x},{dropoff.y}"
            f"?overview=false"
        )

        response = requests.get(url)

        if response.status_code != 200:
            raise Exception("OSRM service unavailable")

        data = response.json()

        routes = data.get("routes")
        if not routes:
            raise Exception("No route found")

        distance_m = routes[0]["distance"]

        return distance_m / 1000  # km