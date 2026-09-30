"""The files in /payloads are part of the contract with the API.

They hold the sample data — every listing payload must POST cleanly and every
search example must return the status it advertises — so the docs cannot drift
away from the schema.
"""

import json
from pathlib import Path

from django.conf import settings
from django.test import TestCase

from listings.models import Listing

LISTINGS_URL = "/api/listings/"
SEARCH_URL = "/api/listings/search/"
PAYLOAD_DIR = Path(settings.BASE_DIR) / "payloads"


def load(name):
    return json.loads((PAYLOAD_DIR / name).read_text(encoding="utf-8"))


def listing_rows():
    return load("listings.json")


def create_listings_from_payloads():
    """Load the payload file straight into the database (no HTTP round trip)."""
    for payload in listing_rows():
        location = payload["location"]
        Listing.objects.create(
            title=payload["title"],
            description=payload.get("description", ""),
            price=payload["price"],
            type=payload["type"],
            bedrooms=payload["bedrooms"],
            agent_id=payload["agent_id"],
            location_name=location.get("name", ""),
            latitude=location["lat"],
            longitude=location["lng"],
        )


class ListingPayloadTests(TestCase):
    """Every sample listing is a valid create request."""

    @classmethod
    def setUpTestData(cls):
        cls.payloads = listing_rows()

    def test_every_payload_creates_a_listing(self):
        for index, payload in enumerate(self.payloads):
            with self.subTest(payload=index):
                response = self.client.post(
                    LISTINGS_URL, payload, content_type="application/json"
                )
                self.assertEqual(response.status_code, 201, response.content)
                self.assertEqual(response.json()["title"], payload["title"])

        self.assertEqual(Listing.objects.count(), len(self.payloads))

    def test_payloads_only_use_keys_the_api_accepts(self):
        """A typo in the file would otherwise be silently ignored by the API."""
        allowed = {"title", "description", "price", "type", "bedrooms", "agent_id", "location"}
        for index, payload in enumerate(self.payloads):
            with self.subTest(payload=index):
                self.assertLessEqual(set(payload), allowed)

    def test_payloads_support_a_radius_search(self):
        create_listings_from_payloads()

        response = self.client.get(
            SEARCH_URL, {"lat": 6.4550, "lng": 3.3900, "radius_km": 5}
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertGreater(body["count"], 0)
        self.assertLess(body["count"], len(self.payloads))  # some are far away


class SearchRequestPayloadTests(TestCase):
    """Every sample search behaves the way its file entry claims."""

    @classmethod
    def setUpTestData(cls):
        cls.requests = load("search_requests.json")
        create_listings_from_payloads()

    def test_search_examples_return_the_expected_status(self):
        for example in self.requests:
            with self.subTest(example=example["name"]):
                response = self.client.get(f"{SEARCH_URL}{example['query']}")
                expected = example.get("expect_status", 200)
                self.assertEqual(response.status_code, expected, response.content)
                self.assertIn("error" if expected >= 400 else "results", response.json())