"""Tests for the write/read serializers and search-query validation."""

from decimal import Decimal

from django.test import TestCase

from listings.models import Listing
from listings.serializers import ListingSerializer, SearchQuerySerializer
from listings.tests.factories import payload


class ListingSerializerTests(TestCase):
    def test_create_maps_nested_location_onto_flat_columns(self):
        serializer = ListingSerializer(data=payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        listing = serializer.save()

        self.assertIsInstance(listing, Listing)
        self.assertEqual(listing.location_name, "Ikoyi")
        self.assertEqual(listing.latitude, 6.4550)
        self.assertEqual(listing.longitude, 3.4350)
        self.assertEqual(listing.agent_id, "agent-001")
        self.assertEqual(listing.price, Decimal("250000.00"))

    def test_representation_uses_a_nested_location_object(self):
        listing = Listing.objects.create(**{
            "title": "T",
            "price": "1.00",
            "type": "rent",
            "bedrooms": 1,
            "agent_id": "a-1",
            "location_name": "Yaba",
            "latitude": 6.5095,
            "longitude": 3.3711,
        })
        data = ListingSerializer(listing).data

        self.assertEqual(data["location"], {"name": "Yaba", "lat": 6.5095, "lng": 3.3711})
        self.assertEqual(data["type"], "rent")
        self.assertIn("created_at", data)

    def test_location_name_is_optional(self):
        body = payload(location={"lat": 6.4550, "lng": 3.4350})
        serializer = ListingSerializer(data=body)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.save().location_name, "")

    def test_partial_update_of_a_single_location_field(self):
        listing = Listing.objects.create(**{
            "title": "T",
            "price": "1.00",
            "type": "rent",
            "agent_id": "a-1",
            "location_name": "Yaba",
            "latitude": 6.5095,
            "longitude": 3.3711,
        })
        serializer = ListingSerializer(listing, data={"location": {"lat": 7.0}}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()

        self.assertEqual(updated.latitude, 7.0)
        self.assertEqual(updated.longitude, 3.3711)
        self.assertEqual(updated.location_name, "Yaba")

    def test_out_of_range_coordinates_are_reported_under_location(self):
        for location in ({"lat": 95.0, "lng": 3.4}, {"lat": 6.4, "lng": 200.0}):
            with self.subTest(location=location):
                serializer = ListingSerializer(data=payload(location=location))
                self.assertFalse(serializer.is_valid())
                self.assertIn("location", serializer.errors)
                offending = "lat" if "lat" in serializer.errors["location"] else "lng"
                self.assertIn(offending, serializer.errors["location"])

    def test_invalid_choices_and_negative_numbers_are_rejected(self):
        cases = {
            "type": payload(type="lease"),
            "price": payload(price="-10"),
            "bedrooms": payload(bedrooms=-1),
        }
        for field, body in cases.items():
            with self.subTest(field=field):
                serializer = ListingSerializer(data=body)
                self.assertFalse(serializer.is_valid())
                self.assertIn(field, serializer.errors)


class SearchQuerySerializerTests(TestCase):
    def test_full_geo_query_parses(self):
        serializer = SearchQuerySerializer(
            data={"type": "rent", "min_price": "100", "lat": "6.45", "lng": "3.43", "radius_km": "5"}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["radius_km"], 5.0)
        self.assertEqual(serializer.validated_data["min_price"], Decimal("100"))

    def test_min_price_greater_than_max_price_is_rejected(self):
        serializer = SearchQuerySerializer(data={"min_price": "900", "max_price": "100"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("min_price", serializer.errors)

    def test_partial_geo_query_names_the_missing_parameter(self):
        serializer = SearchQuerySerializer(data={"lat": "6.45", "lng": "3.43"})
        self.assertFalse(serializer.is_valid())
        self.assertEqual(set(serializer.errors), {"radius_km"})

    def test_radius_above_the_maximum_is_rejected(self):
        serializer = SearchQuerySerializer(
            data={"lat": "6.45", "lng": "3.43", "radius_km": "5000"}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("radius_km", serializer.errors)

    def test_sort_distance_without_geo_is_rejected(self):
        serializer = SearchQuerySerializer(data={"sort": "distance"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("sort", serializer.errors)