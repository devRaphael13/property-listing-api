"""Turns validated search parameters into an ordered queryset."""

from django.db.models import Case, IntegerField, When

from listings.geo import distance_km

SORT_MAP = {
    "newest": ["-created_at", "-id"],
    "price_asc": ["price", "id"],
    "price_desc": ["-price", "id"],
    "bedrooms_desc": ["-bedrooms", "id"],
}


def apply_filters(queryset, params):
    """Apply the type / price / bedroom filters."""
    return (
        queryset.of_type(params.get("type"))
        .price_between(params.get("min_price"), params.get("max_price"))
        .with_bedrooms(params.get("min_bedrooms"), params.get("max_bedrooms"))
    )


def apply_exact_bedrooms(queryset, params):
    bedrooms = params.get("bedrooms")
    return queryset.filter(bedrooms=bedrooms) if bedrooms is not None else queryset


def rank_by_distance(queryset, lat, lng, radius_km):
    """Return (queryset ordered nearest-first, {pk: distance_km}).

    SQLite has no spatial index, so this does a bounding-box pre-filter in SQL,
    computes the exact haversine distance in Python, then rebuilds the ordering
    with a CASE expression so DRF can still paginate and count in SQL.
    """
    candidates = queryset.in_bounding_box(lat, lng, radius_km).values_list(
        "id", "latitude", "longitude"
    )

    scored = []
    for pk, candidate_lat, candidate_lng in candidates.iterator():
        distance = distance_km(lat, lng, candidate_lat, candidate_lng)
        if distance <= radius_km:
            scored.append((distance, pk))
    if not scored:
        return queryset.none(), {}

    scored.sort(key=lambda pair: (pair[0], pair[1]))
    ids = [pk for _, pk in scored]
    distances = {pk: distance for distance, pk in scored}

    order = Case(
        *[When(pk=pk, then=position) for position, pk in enumerate(ids)],
        output_field=IntegerField(),
    )
    return queryset.filter(pk__in=ids).order_by(order), distances


def order_queryset(queryset, sort):
    """Apply a named sort. `distance` ordering is already applied upstream."""
    if sort == "distance":
        return queryset
    return queryset.order_by(*SORT_MAP.get(sort, SORT_MAP["newest"]))
