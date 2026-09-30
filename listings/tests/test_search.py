"""Integration tests for GET /api/listings/search/."""

from django.test import TestCase

from listings.geo import bounding_box
from listings.models import Listing, ListingType
from listings.tests.factories import make_listing

SEARCH_URL = "/api/listings/search/"

CENTRE_LAT = 6.4550  # Lagos Island
CENTRE_LNG = 3.3900


class SearchFilterTests(TestCase):
    def setUp(self):
        self.rent_cheap = make_listing(title="Rent 1 bed", price="100.00", bedrooms=1)
        self.rent_pricey = make_listing(title="Rent 3 bed", price="900.00", bedrooms=3)
        self.sale = make_listing(
            title="Sale 4 bed", price="50.00", type=ListingType.SALE, bedrooms=4
        )
        self.shortlet = make_listing(
            title="Shortlet 2 bed", price="300.00", type=ListingType.SHORTLET, bedrooms=2
        )

    def search(self, **params):
        response = self.client.get(SEARCH_URL, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def titles(self, **params):
        return [row["title"] for row in self.search(**params)["results"]]

    def test_no_filters_returns_everything(self):
        self.assertEqual(self.search()["count"], 4)

    def test_filter_by_type(self):
        self.assertEqual(self.titles(type="sale"), ["Sale 4 bed"])
        self.assertCountEqual(self.titles(type="rent"), ["Rent 1 bed", "Rent 3 bed"])

    def test_filter_by_price_range_is_inclusive(self):
        self.assertCountEqual(
            self.titles(min_price="100", max_price="300"), ["Rent 1 bed", "Shortlet 2 bed"]
        )

    def test_filter_by_min_price_only(self):
        self.assertCountEqual(self.titles(min_price="900"), ["Rent 3 bed"])

    def test_filter_by_bedroom_count(self):
        self.assertEqual(self.titles(bedrooms=3), ["Rent 3 bed"])
        self.assertCountEqual(
            self.titles(min_bedrooms=3, max_bedrooms=4), ["Rent 3 bed", "Sale 4 bed"]
        )

    def test_filters_combine(self):
        self.assertEqual(self.titles(type="rent", min_price="500", bedrooms=3), ["Rent 3 bed"])

    def test_no_matches_returns_an_empty_page(self):
        body = self.search(type="sale", min_price="999999")
        self.assertEqual(body, {"count": 0, "next": None, "previous": None, "results": []})

    def test_results_are_paginated(self):
        body = self.search(page_size=2)
        self.assertEqual(body["count"], 4)
        self.assertEqual(len(body["results"]), 2)
        self.assertIsNotNone(body["next"])

    def test_distance_is_null_without_a_geo_query(self):
        self.assertIsNone(self.search()["results"][0]["distance_km"])


class SearchSortTests(TestCase):
    def setUp(self):
        make_listing(title="Cheap", price="10.00", bedrooms=1)
        make_listing(title="Mid", price="200.00", bedrooms=3)
        make_listing(title="Expensive", price="5000.00", bedrooms=2)

    def titles(self, **params):
        body = self.client.get(SEARCH_URL, params).json()
        return [row["title"] for row in body["results"]]

    def test_every_sort_option_orders_the_results(self):
        cases = {
            "price_asc": ["Cheap", "Mid", "Expensive"],
            "price_desc": ["Expensive", "Mid", "Cheap"],
            "bedrooms_desc": ["Mid", "Expensive", "Cheap"],
            None: ["Expensive", "Mid", "Cheap"],  # default: newest first
        }
        for sort, expected in cases.items():
            with self.subTest(sort=sort):
                self.assertEqual(self.titles(**({"sort": sort} if sort else {})), expected)


class DistanceSearchTests(TestCase):
    def setUp(self):
        # ~0.56 km north and ~0.55 km east of the centre; ~16 km north of it.
        self.north = make_listing(
            title="North", price="500.00", bedrooms=1, latitude=6.4600, longitude=CENTRE_LNG
        )
        self.east = make_listing(
            title="East", price="900.00", bedrooms=2, latitude=CENTRE_LAT, longitude=3.3950
        )
        self.far = make_listing(
            title="Far",
            price="100000.00",
            bedrooms=3,
            latitude=6.6000,
            longitude=CENTRE_LNG,
        )

    def search(self, **params):
        params.setdefault("lat", CENTRE_LAT)
        params.setdefault("lng", CENTRE_LNG)
        params.setdefault("radius_km", 1)
        response = self.client.get(SEARCH_URL, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_returns_only_listings_inside_the_radius_ordered_nearest_first(self):
        body = self.search()
        titles = [row["title"] for row in body["results"]]
        distances = [row["distance_km"] for row in body["results"]]

        self.assertCountEqual(titles, ["North", "East"])
        self.assertEqual(distances, sorted(distances))
        self.assertLess(max(distances), 1.0)

    def test_zero_radius_returns_only_the_exact_point(self):
        make_listing(title="Here", latitude=CENTRE_LAT, longitude=CENTRE_LNG)
        titles = [row["title"] for row in self.search(radius_km=0)["results"]]
        self.assertEqual(titles, ["Here"])

    def test_bounding_box_corners_outside_the_circle_are_excluded(self):
        """The SQL box is a rectangle; the exact distance check must still apply."""
        south, north, west, east = bounding_box(CENTRE_LAT, CENTRE_LNG, radius_km=1)
        corner = make_listing(title="Corner", latitude=north, longitude=east)

        titles = [row["title"] for row in self.search(radius_km=1)["results"]]

        self.assertNotIn("Corner", titles)
        # Sanity check: the point really was inside the SQL pre-filter box.
        in_box = Listing.objects.in_bounding_box(CENTRE_LAT, CENTRE_LNG, 1)
        self.assertTrue(in_box.filter(pk=corner.pk).exists())

    def test_distance_search_combines_with_other_filters(self):
        cases = {
            "bedrooms": ({"bedrooms": 1}, ["North"]),
            "max_price": ({"max_price": "1000"}, ["North", "East"]),
        }
        for name, (params, expected) in cases.items():
            with self.subTest(filter=name):
                body = self.search(radius_km=20, **params)
                titles = [row["title"] for row in body["results"]]
                self.assertNotIn("Far", titles)  # outside the price/bedroom filter
                self.assertCountEqual(titles, expected)

    def test_distance_keeps_working_on_later_pages(self):
        for index in range(5):
            make_listing(
                title=f"Extra {index}",
                latitude=CENTRE_LAT + 0.0002 * (index + 1),
                longitude=CENTRE_LNG,
            )
        first = self.search(radius_km=5, page_size=3)
        second = self.search(radius_km=5, page_size=3, page=2)

        # North, East and the 5 extras are inside 5 km; "Far" is not.
        self.assertEqual(first["count"], 7)
        self.assertEqual(len(first["results"]), 3)
        self.assertEqual(len(second["results"]), 3)
        first_ids = {row["id"] for row in first["results"]}
        second_ids = {row["id"] for row in second["results"]}
        self.assertEqual(first_ids & second_ids, set())

    def test_explicit_sort_overrides_the_distance_ordering(self):
        self.far.price = "5.00"
        self.far.save()
        titles = [row["title"] for row in self.search(radius_km=20, sort="price_asc")["results"]]
        self.assertEqual(titles, ["Far", "North", "East"])


class AntimeridianSearchTests(TestCase):
    """Longitudes either side of +/-180 are ~5 km apart, not half the globe."""

    def test_search_box_wraps_around_the_antimeridian(self):
        make_listing(title="East side", latitude=0, longitude=179.97)
        make_listing(title="West side", latitude=0, longitude=-179.97)
        make_listing(title="Far away", latitude=0, longitude=0.0)

        response = self.client.get(SEARCH_URL, {"lat": 0, "lng": 179.98, "radius_km": 10})

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            [row["title"] for row in response.json()["results"]],
            ["East side", "West side"],
        )


class DistanceSearchValidationTests(TestCase):
    def test_incomplete_geo_query_names_the_missing_parameter(self):
        cases = [
            ({"lat": CENTRE_LAT, "lng": CENTRE_LNG}, "radius_km"),
            ({"lng": CENTRE_LNG, "radius_km": 5}, "lat"),
        ]
        for params, missing in cases:
            with self.subTest(missing=missing):
                response = self.client.get(SEARCH_URL, params)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(set(response.json()["error"]["details"]), {missing})

    def test_radius_beyond_the_cap_is_rejected(self):
        response = self.client.get(
            SEARCH_URL, {"lat": CENTRE_LAT, "lng": CENTRE_LNG, "radius_km": 500}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("radius_km", response.json()["error"]["details"])

    def test_multiple_errors_are_reported_together(self):
        response = self.client.get(SEARCH_URL, {"type": "lease", "min_price": "-5"})
        details = response.json()["error"]["details"]
        self.assertEqual(set(details), {"type", "min_price"})