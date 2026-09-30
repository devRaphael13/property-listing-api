"""The OpenAPI schema is generated from the code, so these tests keep it honest.

`--fail-on-warn` is the important one: drf-spectacular reports every unresolvable
type hint or undocumented operation as a warning, and this makes that a test
failure rather than something a reader of the docs discovers.
"""

import json
from io import StringIO

from django.core.management import call_command
from django.test import Client, TestCase

from listings.serializers import SearchQuerySerializer

SCHEMA_URL = "/api/schema/"


class SchemaTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The schema is generated from code, so one snapshot serves every test.
        cls.schema = json.loads(Client().get(SCHEMA_URL, {"format": "json"}).content)

    def test_schema_generates_without_warnings(self):
        call_command("spectacular", "--fail-on-warn", stdout=StringIO())

    def test_schema_is_served_as_openapi_json(self):
        response = self.client.get(SCHEMA_URL, {"format": "json"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/vnd.oai.openapi+json", response["Content-Type"])
        self.assertTrue(self.schema["openapi"].startswith("3."))

    def test_every_endpoint_is_documented(self):
        self.assertEqual(
            set(self.schema["paths"]),
            {
                "/api/listings/",
                "/api/listings/search/",
                "/api/listings/{id}/",
                "/api/health/",
            },
        )

    def test_schema_is_available_as_json_and_yaml_files(self):
        """Stable paths for tooling, e.g. committing or diffing a schema."""
        self.assertEqual(json.loads(self.client.get("/api/schema.json").content), self.schema)
        self.assertIn(b"openapi: 3", self.client.get("/api/schema.yaml").content)

    def test_listing_schema_documents_the_api_contract(self):
        listing = self.schema["components"]["schemas"]["Listing"]

        # Money is a decimal string, not a JSON float.
        self.assertEqual(listing["properties"]["price"]["format"], "decimal")

        # Location is one nested object, required with lat and lng.
        location_name = listing["properties"]["location"]["$ref"].split("/")[-1]
        self.assertIn("location", listing["required"])
        self.assertEqual(
            sorted(self.schema["components"]["schemas"][location_name]["required"]),
            ["lat", "lng"],
        )

    def test_list_responses_are_wrapped_in_the_pagination_envelope(self):
        schema_name = self.schema["paths"]["/api/listings/"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]["$ref"].split("/")[-1]
        envelope = self.schema["components"]["schemas"][schema_name]

        self.assertEqual(set(envelope["required"]), {"count", "results"})
        self.assertIn("next", envelope["properties"])
        self.assertIn("previous", envelope["properties"])
        self.assertIn("page_size", json.dumps(self.schema["paths"]["/api/listings/"]["get"]))

    def test_errors_are_documented_with_the_shared_envelope(self):
        created = self.schema["paths"]["/api/listings/"]["post"]
        ref = created["responses"]["400"]["content"]["application/json"]["schema"]["$ref"]
        self.assertEqual(ref.split("/")[-1], "ErrorEnvelope")
        self.assertIn(
            "error", self.schema["components"]["schemas"]["ErrorEnvelope"]["required"]
        )

    def test_search_documents_every_query_parameter(self):
        """The serializer that validates the request is also the docs' source."""
        parameters = {
            parameter["name"]
            for parameter in self.schema["paths"]["/api/listings/search/"]["get"]["parameters"]
        }
        self.assertEqual(parameters, set(SearchQuerySerializer().fields) | {"page", "page_size"})

    def test_search_response_includes_distance_km(self):
        ref = self.schema["paths"]["/api/listings/search/"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]["$ref"].split("/")[-1]
        item_ref = (
            self.schema["components"]["schemas"][ref]["properties"]["results"]["items"]
            ["$ref"]
            .split("/")[-1]
        )
        distance = self.schema["components"]["schemas"][item_ref]["properties"]["distance_km"]

        self.assertEqual(distance["type"], "number")
        self.assertTrue(distance["nullable"])

    def test_docs_pages_are_served(self):
        for url in ("/api/docs/", "/api/redoc/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response["Content-Type"])
        self.assertIn(SCHEMA_URL, self.client.get("/api/docs/").content.decode())