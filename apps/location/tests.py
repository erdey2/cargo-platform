from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.location.models import Location


class LocationModelTests(TestCase):
    def test_create_with_required_fields_only(self):
        loc = Location.objects.create(
            region="Addis Ababa",
            latitude=9.032,
            longitude=38.7469,
        )
        self.assertIsNotNone(loc.id)
        self.assertEqual(loc.region, "Addis Ababa")
        self.assertEqual(loc.latitude, 9.032)
        self.assertEqual(loc.longitude, 38.7469)
        self.assertIsNone(loc.zone)
        self.assertIsNone(loc.woreda)
        self.assertIsNone(loc.city)
        self.assertIsNone(loc.description)

    def test_create_with_all_fields(self):
        loc = Location.objects.create(
            region="Oromia",
            zone="East Shewa",
            woreda="Bishoftu",
            city="Bishoftu",
            latitude=8.7525,
            longitude=38.9785,
            description="Industrial corridor",
        )
        self.assertEqual(loc.zone, "East Shewa")
        self.assertEqual(loc.woreda, "Bishoftu")
        self.assertEqual(loc.city, "Bishoftu")
        self.assertEqual(loc.description, "Industrial corridor")

    def test_str_uses_city_and_region(self):
        loc = Location.objects.create(
            region="Amhara",
            city="Bahir Dar",
            latitude=11.6,
            longitude=37.3833,
        )
        self.assertEqual(str(loc), "Bahir Dar - Amhara")

    def test_str_when_city_is_null(self):
        loc = Location.objects.create(
            region="Tigray",
            latitude=14.1628,
            longitude=38.2904,
        )
        self.assertEqual(str(loc), "None - Tigray")

    def test_full_clean_rejects_region_over_max_length(self):
        loc = Location(
            region="x" * 101,
            latitude=0.0,
            longitude=0.0,
        )
        with self.assertRaises(ValidationError) as ctx:
            loc.full_clean()
        self.assertIn("region", ctx.exception.error_dict)
