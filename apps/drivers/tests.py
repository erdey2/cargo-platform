import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.drivers.models import DriverDocument, DriverEarning, DriverProfile
from apps.shipments.models import Shipment
from apps.vehicles.models import Vehicle, VehicleType

User = get_user_model()


def _unique_email():
    return f"driver-{uuid.uuid4().hex[:12]}@test.example"


def _unique_phone():
    return f"+2519{uuid.uuid4().int % 10**8:08d}"


class DriverProfileModelTests(TestCase):
    def test_defaults_and_one_to_one_user(self):
        user = User.objects.create_user(
            _unique_email(),
            "TestPassw0rd!",
            role="driver",
            phone=_unique_phone(),
        )
        profile = DriverProfile.objects.create(
            user=user,
            national_id="NID-001",
            driver_license="LIC-001",
        )

        self.assertEqual(profile.verification_status, "pending")
        self.assertEqual(profile.rating, 5.0)
        self.assertEqual(profile.total_trips, 0)
        self.assertTrue(profile.is_available)
        self.assertEqual(profile.user_id, user.id)

    def test_user_delete_cascades_to_profile(self):
        user = User.objects.create_user(
            _unique_email(),
            "TestPassw0rd!",
            role="driver",
            phone=_unique_phone(),
        )
        DriverProfile.objects.create(
            user=user,
            national_id="NID-002",
            driver_license="LIC-002",
        )
        user.delete()
        self.assertFalse(DriverProfile.objects.filter(user=user).exists())


class DriverDocumentModelTests(TestCase):
    def test_create_with_file(self):
        user = User.objects.create_user(
            _unique_email(),
            "TestPassw0rd!",
            role="driver",
            phone=_unique_phone(),
        )
        profile = DriverProfile.objects.create(
            user=user,
            national_id="NID-003",
            driver_license="LIC-003",
        )
        doc = DriverDocument.objects.create(
            driver=profile,
            document_type="license",
            file=SimpleUploadedFile(
                "license.pdf", b"%PDF-1.4 test", content_type="application/pdf"
            ),
        )
        self.assertEqual(doc.driver_id, profile.id)
        self.assertFalse(doc.is_verified)


class DriverEarningModelTests(TestCase):
    def test_create_links_driver_and_shipment(self):
        driver_user = User.objects.create_user(
            _unique_email(),
            "TestPassw0rd!",
            role="driver",
            phone=_unique_phone(),
        )
        driver_profile = DriverProfile.objects.create(
            user=driver_user,
            national_id="NID-004",
            driver_license="LIC-004",
        )
        customer = User.objects.create_user(
            _unique_email(),
            "TestPassw0rd!",
            role="customer",
            phone=_unique_phone(),
        )
        shipment = Shipment.objects.create(
            customer=customer,
            pickup_address="Pickup",
            dropoff_address="Dropoff",
            pickup_location=Point(38.75, 9.03),
            dropoff_location=Point(38.80, 9.04),
            weight=10.0,
            volume=1.5,
        )
        earning = DriverEarning.objects.create(
            driver=driver_profile,
            shipment=shipment,
            amount=Decimal("250.50"),
        )
        self.assertFalse(earning.paid)
        self.assertEqual(earning.amount, Decimal("250.50"))


class DriverRegistrationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.vehicle_type = VehicleType.objects.create(
            name=f"Type-{uuid.uuid4().hex[:8]}",
            max_weight=1000.0,
            max_volume=10.0,
        )

    def test_register_driver_creates_user_profile_driver_and_vehicle(self):
        email = _unique_email()
        phone = _unique_phone()
        plate = f"AA-{uuid.uuid4().hex[:8].upper()}"
        url = reverse("driver-register")
        payload = {
            "email": email,
            "password1": "Str0ngPass!xyz",
            "password2": "Str0ngPass!xyz",
            "first_name": "Test",
            "last_name": "Driver",
            "full_name": "Test Driver",
            "phone": phone,
            "address": "Addis Ababa",
            "city": "Addis Ababa",
            "country": "Ethiopia",
            "latitude_input": 9.03,
            "longitude_input": 38.75,
            "national_id": "NID-API-01",
            "driver_license": "LIC-API-01",
            "vehicle": {
                "plate_number": plate,
                "vehicle_type": self.vehicle_type.pk,
            },
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(email=email)
        self.assertEqual(user.role, "driver")
        self.assertEqual(user.phone, phone)

        driver_profile = DriverProfile.objects.get(user=user)
        self.assertEqual(driver_profile.national_id, "NID-API-01")
        self.assertEqual(driver_profile.driver_license, "LIC-API-01")

        vehicle = Vehicle.objects.get(driver=driver_profile)
        self.assertEqual(vehicle.plate_number, plate)
        self.assertEqual(vehicle.vehicle_type_id, self.vehicle_type.pk)

    def test_register_driver_requires_vehicle(self):
        url = reverse("driver-register")
        payload = {
            "email": _unique_email(),
            "password1": "Str0ngPass!xyz",
            "password2": "Str0ngPass!xyz",
            "first_name": "No",
            "last_name": "Vehicle",
            "full_name": "No Vehicle",
            "phone": _unique_phone(),
            "national_id": "NID-MISSING-V",
            "driver_license": "LIC-MISSING-V",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 400)
