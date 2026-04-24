from django.contrib.gis.geos import Point

from apps.drivers.models import DriverProfile
from apps.shipments.models import Shipment
from apps.users.models import User
from apps.vehicles.models import Vehicle, VehicleType


class MatchingTestDataMixin:
    def create_user(self, *, email: str, role: str):
        return User.objects.create_user(email=email, password="pass123", role=role)

    def create_driver_profile(self, *, email: str = "driver@example.com"):
        user = self.create_user(email=email, role="driver")
        driver = DriverProfile.objects.create(
            user=user,
            national_id=f"nid-{user.id}",
            driver_license=f"lic-{user.id}",
            verification_status="verified",
            is_available=True,
        )
        return user, driver

    def create_shipment(self, customer, *, status: str = "matching"):
        return Shipment.objects.create(
            customer=customer,
            pickup_address="Addis Ababa",
            dropoff_address="Adama",
            pickup_location=Point(38.7578, 8.9806, srid=4326),
            dropoff_location=Point(39.2695, 8.5414, srid=4326),
            weight=100,
            volume=2,
            status=status,
        )

    def create_vehicle(self, driver, plate_suffix="1"):
        vtype = VehicleType.objects.create(
            name=f"Truck-{plate_suffix}",
            max_weight=1000,
            max_volume=20,
        )
        return Vehicle.objects.create(
            driver=driver,
            vehicle_type=vtype,
            plate_number=f"A-{plate_suffix}",
            capacity_weight=1000,
            capacity_volume=20,
            verification_status=True,
        )

