"""Shared test helpers."""

from listings.models import Listing, ListingType

LAGOS_IKOYI = (6.4550, 3.4350)

DEFAULTS = {
    "title": "2 Bedroom Apartment in Lekki",
    "description": "Bright and airy.",
    "price": "250000.00",
    "type": ListingType.RENT,
    "bedrooms": 2,
    "agent_id": "agent-001",
    "location_name": "Ikoyi",
    "latitude": LAGOS_IKOYI[0],
    "longitude": LAGOS_IKOYI[1],
}


def make_listing(**overrides):
    values = {**DEFAULTS, **overrides}
    return Listing.objects.create(**values)


def payload(**overrides):
    """A valid API request body; override anything to break it."""
    values = {
        "title": DEFAULTS["title"],
        "description": DEFAULTS["description"],
        "price": "250000.00",
        "type": "rent",
        "bedrooms": 2,
        "agent_id": "agent-001",
        "location": {"name": "Ikoyi", "lat": 6.4550, "lng": 3.4350},
    }
    values.update(overrides)
    return values
