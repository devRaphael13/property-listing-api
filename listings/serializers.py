"""Serializers: write/read validation and the API's public JSON shape."""

from rest_framework import serializers

from listings.models import Listing, ListingType

MAX_RADIUS_KM = 200
MAX_BEDROOMS = 50

SORT_CHOICES = ("newest", "price_asc", "price_desc", "bedrooms_desc", "distance")


class LocationSerializer(serializers.Serializer):
    """Nested location object accepted on write and returned on read."""

    name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)


class ListingSerializer(serializers.ModelSerializer):
    location = LocationSerializer()

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "description",
            "price",
            "type",
            "bedrooms",
            "agent_id",
            "location",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "description": {"required": False, "allow_blank": True},
            "bedrooms": {"required": False, "min_value": 0, "max_value": MAX_BEDROOMS},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["location"] = instance.location
        return data

    def create(self, validated_data):
        location = validated_data.pop("location")
        validated_data.update(
            location_name=location.get("name", ""),
            latitude=location["lat"],
            longitude=location["lng"],
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        location = validated_data.pop("location", None)
        if location:
            # Partial location objects are allowed: unspecified parts stay put.
            instance.location_name = location.get("name", instance.location_name)
            instance.latitude = location.get("lat", instance.latitude)
            instance.longitude = location.get("lng", instance.longitude)
        return super().update(instance, validated_data)


class SearchResultSerializer(ListingSerializer):
    """Adds the computed distance so clients can rank results themselves."""

    distance_km = serializers.SerializerMethodField()

    class Meta(ListingSerializer.Meta):
        fields = ListingSerializer.Meta.fields + ["distance_km"]

    def get_distance_km(self, obj) -> float | None:
        distance = getattr(obj, "distance_km", None)
        return round(distance, 3) if distance is not None else None


class SearchQuerySerializer(serializers.Serializer):
    """Validates the ?query parameters of GET /api/listings/search/.

    Doubles as the OpenAPI source of truth for those parameters: drf-spectacular
    turns each field below into a documented query parameter, so the docs cannot
    drift from the validation rules.
    """

    type = serializers.ChoiceField(
        choices=ListingType.choices,
        required=False,
        help_text="Restrict to one kind of listing.",
    )
    min_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        help_text="Lowest acceptable price, inclusive.",
    )
    max_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        help_text="Highest acceptable price, inclusive. Must not be below min_price.",
    )
    bedrooms = serializers.IntegerField(
        min_value=0, max_value=MAX_BEDROOMS, required=False, help_text="Exact bedroom count."
    )
    min_bedrooms = serializers.IntegerField(
        min_value=0,
        max_value=MAX_BEDROOMS,
        required=False,
        help_text="Minimum bedroom count, inclusive.",
    )
    max_bedrooms = serializers.IntegerField(
        min_value=0,
        max_value=MAX_BEDROOMS,
        required=False,
        help_text="Maximum bedroom count, inclusive. Must not be below min_bedrooms.",
    )
    lat = serializers.FloatField(
        min_value=-90,
        max_value=90,
        required=False,
        help_text="Latitude of the search centre. Requires lng and radius_km.",
    )
    lng = serializers.FloatField(
        min_value=-180,
        max_value=180,
        required=False,
        help_text="Longitude of the search centre. Requires lat and radius_km.",
    )
    radius_km = serializers.FloatField(
        min_value=0,
        max_value=MAX_RADIUS_KM,
        required=False,
        help_text=f"Search radius in km (0-{MAX_RADIUS_KM}). Requires lat and lng.",
    )
    sort = serializers.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        help_text=(
            "Result order. Defaults to `distance` when lat/lng/radius_km are given, "
            "otherwise `newest`."
        ),
    )

    def validate(self, attrs):
        min_price, max_price = attrs.get("min_price"), attrs.get("max_price")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise serializers.ValidationError(
                {"min_price": ["min_price cannot be greater than max_price."]}
            )

        min_bed, max_bed = attrs.get("min_bedrooms"), attrs.get("max_bedrooms")
        if min_bed is not None and max_bed is not None and min_bed > max_bed:
            raise serializers.ValidationError(
                {"min_bedrooms": ["min_bedrooms cannot be greater than max_bedrooms."]}
            )

        geo = {"lat": "lat" in attrs, "lng": "lng" in attrs, "radius_km": "radius_km" in attrs}
        if any(geo.values()) and not all(geo.values()):
            missing = [name for name, present in geo.items() if not present]
            raise serializers.ValidationError(
                {name: ["This parameter is required for distance search."] for name in missing}
            )

        if attrs.get("sort") == "distance" and not all(geo.values()):
            raise serializers.ValidationError(
                {"sort": ["sort=distance requires lat, lng and radius_km."]}
            )

        return attrs


class ErrorBodySerializer(serializers.Serializer):
    """Documentation only: mirrors listings.exceptions.error_payload."""

    status = serializers.IntegerField(help_text="HTTP status code, repeated for convenience.")
    code = serializers.CharField(help_text="Machine-readable code, e.g. validation_error.")
    message = serializers.CharField(help_text="Human-readable summary of the failure.")
    details = serializers.DictField(
        required=False,
        help_text="Per-field messages, nested like the request that caused them.",
    )


class ErrorEnvelopeSerializer(serializers.Serializer):
    """Documentation only: the single error shape every endpoint returns."""

    error = ErrorBodySerializer()
