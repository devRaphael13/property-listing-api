"""Geospatial helpers, backed by geopy.

geopy is the de-facto Python geo library and wraps GeographicLib's geodesic
algorithms (the same WGS84 maths PROJ and PostGIS use), so distances are
ellipsoidal rather than spherical-approximate.

SQLite has no spatial extension, so filtering happens in SQL via a bounding box
and the exact distance check runs in Python. See README ("what I'd improve") for
the PostGIS upgrade path.
"""

from geopy import Point
from geopy.distance import geodesic

#: Cardinal bearings, used to walk the corners of a bounding box.
_BEARINGS = (0, 90, 180, 270)

#: Mean length of a WGS84 meridian degree; used only to detect pole reach.
MEAN_MERIDIONAL_DEGREE_KM = 111.195

#: Floating-point slack for box edges (~0.1 mm), so a point sitting exactly on
#: the boundary is not excluded by rounding in geopy's geodesic maths.
_EPSILON_DEGREES = 1e-9


def distance_km(lat1, lon1, lat2, lon2):
    """Return the WGS84 geodesic distance in kilometres between two points."""
    return geodesic((lat1, lon1), (lat2, lon2)).km


def _longitude_delta(longitude, centre):
    """Signed offset from `centre`, wrapped into (-180, 180].

    Without this, a box crossing the antimeridian looks like a box spanning the
    entire globe: +179.98 and -179.93 are 0.09 degrees apart, not 359.91.
    """
    return (longitude - centre + 180.0) % 360.0 - 180.0


def bounding_box(lat, lng, radius_km):
    """Return (south, north, west, east) degrees covering the radius box.

    Corners are found by walking `radius_km` along each cardinal bearing from the
    centre — the standard way to project a circle onto a rectangle — and longitudes
    are unwrapped relative to the centre so antimeridian boxes stay small. The box
    is the smallest rectangle containing the circle, which makes it a cheap SQL
    pre-filter ahead of the exact distance check.

    `west`/`east` may fall outside [-180, 180] when the box crosses the
    antimeridian; `ListingQuerySet.in_bounding_box` handles that.
    """
    origin = Point(lat, lng)  # geopy orders points as (latitude, longitude)
    ring = geodesic(kilometers=radius_km)
    corners = [ring.destination(origin, bearing) for bearing in _BEARINGS]

    south = min(corner.latitude for corner in corners) - _EPSILON_DEGREES
    north = max(corner.latitude for corner in corners) + _EPSILON_DEGREES

    if radius_km >= (90.0 - abs(lat)) * MEAN_MERIDIONAL_DEGREE_KM:
        # The circle swallows a pole, so longitude stops meaning anything and the
        # box reaches all the way to 90 degrees.
        west, east = -180.0, 180.0
        if lat >= 0:
            north = 90.0
        else:
            south = -90.0
    else:
        deltas = [_longitude_delta(corner.longitude, lng) for corner in corners]
        west = lng + min(deltas) - _EPSILON_DEGREES
        east = lng + max(deltas) + _EPSILON_DEGREES

    return south, north, west, east
