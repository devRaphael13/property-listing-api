"""Data model for the property listings API."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from listings.geo import bounding_box, distance_km


class ListingType(models.TextChoices):
    """Kind of transaction a listing represents."""

    RENT = "rent", "Rent"
    SALE = "sale", "Sale"
    SHORTLET = "shortlet", "Shortlet"


class ListingQuerySet(models.QuerySet):
    """Reusable, composable filters.

    Keeping them here (rather than in the view) means the same predicates back
    the search endpoint, the admin and any future management command.
    """

    def of_type(self, value):
        if not value:
            return self
        return self.filter(type=value)

    def price_between(self, min_price=None, max_price=None):
        if min_price is not None:
            self = self.filter(price__gte=min_price)
        if max_price is not None:
            self = self.filter(price__lte=max_price)
        return self

    def with_bedrooms(self, min_bedrooms=None, max_bedrooms=None):
        if min_bedrooms is not None:
            self = self.filter(bedrooms__gte=min_bedrooms)
        if max_bedrooms is not None:
            self = self.filter(bedrooms__lte=max_bedrooms)
        return self

    def in_bounding_box(self, lat, lng, radius_km):
        """Cheap SQL pre-filter; the exact distance check happens in Python."""
        south, north, west, east = bounding_box(lat, lng, radius_km)

        # Boxes near the antimeridian spill past +/-180. Stored longitudes can
        # only be in [-180, 180], so the main span clips at the edge and the
        # wrapped remainder is unioned back in.
        lons = Q(longitude__gte=west, longitude__lte=east)
        if west < -180:
            lons |= Q(longitude__gte=west + 360, longitude__lte=180)
        if east > 180:
            lons |= Q(longitude__gte=-180, longitude__lte=east - 360)

        return self.filter(Q(latitude__gte=south, latitude__lte=north) & lons)


class Listing(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Asking price, in the listing currency.",
    )
    type = models.CharField(max_length=10, choices=ListingType.choices, db_index=True)
    bedrooms = models.PositiveSmallIntegerField(default=0, db_index=True)
    agent_id = models.CharField(
        max_length=64,
        db_index=True,
        help_text="External identifier of the agent/agency handling the listing.",
    )

    # Location is stored flat so it can be indexed and filtered in SQL; the API
    # exposes it as a nested "location" object.
    location_name = models.CharField(max_length=200, blank=True, default="")
    latitude = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ListingQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["type", "price"], name="listing_type_price_idx"),
            models.Index(fields=["latitude", "longitude"], name="listing_lat_lng_idx"),
        ]

    def __str__(self):
        return self.title

    @property
    def location(self):
        return {"name": self.location_name, "lat": self.latitude, "lng": self.longitude}

    def distance_from(self, lat, lng):
        return distance_km(lat, lng, self.latitude, self.longitude)
