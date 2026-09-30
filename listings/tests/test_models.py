from django.core.exceptions import ValidationError
from django.test import TestCase

from listings.models import Listing, ListingType
from listings.tests.factories import make_listing


class ListingModelTests(TestCase):
    def test_defaults_are_applied(self):
        listing = Listing.objects.create(
            title="Bare minimum",
            price="10.00",
            type=ListingType.SALE,
            agent_id="agent-009",
            latitude=0,
            longitude=0,
        )
        self.assertEqual(listing.bedrooms, 0)
        self.assertEqual(listing.description, "")
        self.assertEqual(listing.location_name, "")

    def test_default_ordering_is_newest_first(self):
        first = make_listing(title="First")
        second = make_listing(title="Second")
        self.assertEqual(list(Listing.objects.all()), [second, first])

    def test_full_clean_rejects_out_of_range_latitude(self):
        listing = make_listing(latitude=91.0)
        with self.assertRaises(ValidationError) as ctx:
            listing.full_clean()
        self.assertIn("latitude", ctx.exception.message_dict)

    def test_full_clean_rejects_out_of_range_longitude(self):
        listing = make_listing(longitude=-181.0)
        with self.assertRaises(ValidationError) as ctx:
            listing.full_clean()
        self.assertIn("longitude", ctx.exception.message_dict)


class ListingQuerySetTests(TestCase):
    def setUp(self):
        self.rent_cheap = make_listing(title="Rent cheap", price="100.00", bedrooms=1)
        self.rent_pricey = make_listing(title="Rent pricey", price="900.00", bedrooms=3)
        self.sale = make_listing(
            title="Sale", price="50.00", type=ListingType.SALE, bedrooms=4
        )

    def test_of_type(self):
        self.assertQuerySetEqual(
            Listing.objects.of_type("sale"), [self.sale], ordered=False
        )
        self.assertQuerySetEqual(
            Listing.objects.of_type(None),
            [self.rent_cheap, self.rent_pricey, self.sale],
            ordered=False,
        )

    def test_price_between_is_inclusive(self):
        results = Listing.objects.price_between("100.00", "900.00")
        self.assertQuerySetEqual(results, [self.rent_cheap, self.rent_pricey], ordered=False)

    def test_with_bedrooms(self):
        results = Listing.objects.with_bedrooms(min_bedrooms=3)
        self.assertQuerySetEqual(results, [self.rent_pricey, self.sale], ordered=False)

    def test_in_bounding_box(self):
        near = make_listing(title="Near", latitude=6.4600, longitude=3.4400)
        far = make_listing(title="Far", latitude=6.4550, longitude=3.5000)  # ~7 km east

        results = Listing.objects.in_bounding_box(6.4550, 3.4350, radius_km=2)

        self.assertIn(near, results)
        self.assertNotIn(far, results)