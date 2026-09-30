"""Integration tests for the CRUD endpoints, pagination and error handling."""

from unittest import mock

from django.test import TestCase, override_settings

from listings.models import Listing, ListingType
from listings.tests.factories import make_listing, payload

LISTINGS_URL = "/api/listings/"


class HealthTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class CreateListingTests(TestCase):
    def test_create_returns_201_and_the_created_resource(self):
        response = self.client.post(LISTINGS_URL, payload(), content_type="application/json")

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(Listing.objects.count(), 1)
        self.assertEqual(body["title"], payload()["title"])
        self.assertEqual(body["type"], "rent")
        self.assertEqual(body["location"], {"name": "Ikoyi", "lat": 6.4550, "lng": 3.4350})
        self.assertIn("id", body)
        self.assertIn("created_at", body)

    def test_location_is_required(self):
        body = payload()
        body.pop("location")
        response = self.client.post(LISTINGS_URL, body, content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertIn("location", response.json()["error"]["details"])
        self.assertEqual(Listing.objects.count(), 0)

    def test_invalid_field_reports_the_offending_field(self):
        response = self.client.post(
            LISTINGS_URL, payload(price="-5"), content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        error = response.json()["error"]
        self.assertEqual(error["status"], 400)
        self.assertEqual(error["code"], "validation_error")
        self.assertIn("price", error["details"])

    def test_malformed_and_unsupported_requests_use_the_error_envelope(self):
        cases = {
            # Malformed JSON, a body sent as text/plain, and an empty body: all
            # framework-level failures that must still return our envelope.
            "parse_error": ("{not json", "application/json"),
            "unsupported_media_type": (payload(), "text/plain"),
        }
        for code, (body, content_type) in cases.items():
            with self.subTest(code=code):
                response = self.client.post(LISTINGS_URL, body, content_type=content_type)
                self.assertEqual(response.status_code, 400 if code == "parse_error" else 415)
                self.assertEqual(response.json()["error"]["code"], code)
        self.assertEqual(Listing.objects.count(), 0)


class ListListingTests(TestCase):
    def test_empty_database_returns_an_empty_envelope(self):
        response = self.client.get(LISTINGS_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"count": 0, "next": None, "previous": None, "results": []},
        )

    def test_list_is_paginated_newest_first(self):
        first = make_listing(title="First")
        second = make_listing(title="Second")

        body = self.client.get(LISTINGS_URL).json()
        self.assertEqual(body["count"], 2)
        self.assertEqual([row["title"] for row in body["results"]], ["Second", "First"])
        self.assertEqual(body["results"][0]["id"], second.id)
        self.assertEqual(body["results"][1]["id"], first.id)

    def test_page_size_is_honoured_and_capped(self):
        for index in range(30):
            make_listing(title=f"Listing {index}")

        body = self.client.get(LISTINGS_URL, {"page_size": 10}).json()
        self.assertEqual(body["count"], 30)
        self.assertEqual(len(body["results"]), 10)
        self.assertIsNotNone(body["next"])
        self.assertIn("page=2", body["next"])

        capped = self.client.get(LISTINGS_URL, {"page_size": 5000}).json()
        self.assertEqual(len(capped["results"]), 30)  # below the 100 cap

    def test_second_page_is_reachable(self):
        for index in range(25):
            make_listing(title=f"Listing {index}")

        body = self.client.get(LISTINGS_URL, {"page_size": 10, "page": 3}).json()
        self.assertEqual(len(body["results"]), 5)
        self.assertIsNotNone(body["previous"])

    def test_unusable_pagination_parameters_are_rejected(self):
        cases = {"page": 99, "page": 0, "page_size": "many", "page_size": -5}
        for param, value in cases.items():
            with self.subTest(param=param, value=value):
                response = self.client.get(LISTINGS_URL, {param: value})
                self.assertEqual(response.status_code, 404 if param == "page" else 400)
                self.assertIn("error", response.json())


class RetrieveListingTests(TestCase):
    def test_retrieve_returns_the_listing(self):
        listing = make_listing(title="Retrieve me")
        response = self.client.get(f"{LISTINGS_URL}{listing.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Retrieve me")

    def test_missing_listing_returns_404_with_envelope(self):
        response = self.client.get(f"{LISTINGS_URL}999999/")
        self.assertEqual(response.status_code, 404)
        error = response.json()["error"]
        self.assertEqual(error["status"], 404)
        self.assertEqual(error["code"], "not_found")


class UpdateListingTests(TestCase):
    def setUp(self):
        self.listing = make_listing(title="Before")

    def test_put_replaces_fields(self):
        response = self.client.put(
            f"{LISTINGS_URL}{self.listing.pk}/",
            payload(title="After", type="sale"),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, "After")
        self.assertEqual(self.listing.type, ListingType.SALE)

    def test_put_requires_the_full_body(self):
        response = self.client.put(
            f"{LISTINGS_URL}{self.listing.pk}/", {"title": "After"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("price", response.json()["error"]["details"])

    def test_patch_updates_only_the_given_fields(self):
        response = self.client.patch(
            f"{LISTINGS_URL}{self.listing.pk}/",
            {"title": "Patched"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, "Patched")
        self.assertEqual(self.listing.bedrooms, 2)

    def test_patch_with_invalid_value_is_rejected_and_changes_nothing(self):
        response = self.client.patch(
            f"{LISTINGS_URL}{self.listing.pk}/", {"price": "free"}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        self.listing.refresh_from_db()
        self.assertEqual(str(self.listing.price), "250000.00")


class DeleteListingTests(TestCase):
    def test_delete_returns_204_and_removes_the_row(self):
        listing = make_listing()
        response = self.client.delete(f"{LISTINGS_URL}{listing.pk}/")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertFalse(Listing.objects.filter(pk=listing.pk).exists())


class HttpErrorHandlingTests(TestCase):
    def test_method_not_allowed_returns_405(self):
        response = self.client.post("/api/health/", {}, content_type="application/json")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()["error"]["code"], "method_not_allowed")

    def test_unknown_api_route_returns_a_json_404(self):
        response = self.client.get("/api/does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_unknown_page_outside_the_api_still_returns_html(self):
        response = self.client.get("/definitely-not-a-page/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("text/html", response["Content-Type"])

    @override_settings(DEBUG=False)
    def test_unhandled_exception_returns_a_json_500_not_a_traceback(self):
        with mock.patch(
            "listings.views.ListingViewSet.get_queryset", side_effect=RuntimeError("boom")
        ):
            self.client.raise_request_exception = False
            response = self.client.get(LISTINGS_URL)

        self.assertEqual(response.status_code, 500)
        error = response.json()["error"]
        self.assertEqual(error["code"], "server_error")
        self.assertNotIn("boom", response.content.decode())