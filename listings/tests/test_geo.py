from django.test import SimpleTestCase
from geopy import Point
from geopy.distance import geodesic

from listings.geo import bounding_box, distance_km


class DistanceTests(SimpleTestCase):
    def test_identical_points_are_zero_distance(self):
        self.assertAlmostEqual(distance_km(6.4550, 3.4350, 6.4550, 3.4350), 0.0, places=6)

    def test_known_city_distance_lagos_to_abuja(self):
        distance = distance_km(6.5244, 3.3792, 9.0765, 7.3986)  # Lagos -> Abuja
        self.assertTrue(500 < distance < 550, distance)

    def test_known_city_distance_london_to_paris(self):
        # Great-circle on the WGS84 ellipsoid: ~343.5 km.
        self.assertAlmostEqual(distance_km(51.5074, -0.1278, 48.8566, 2.3522), 343.5, delta=1.0)

    def test_matches_geopy_directly(self):
        """The helper is a thin wrapper; it must not quietly reshape arguments."""
        expected = geodesic(Point(6.4550, 3.4350), Point(51.5074, -0.1278)).km
        self.assertAlmostEqual(distance_km(6.4550, 3.4350, 51.5074, -0.1278), expected, places=9)


class BoundingBoxTests(SimpleTestCase):
    """Each of these guards a bug that a naive implementation actually had."""

    def test_box_contains_points_inside_the_radius(self):
        south, north, west, east = bounding_box(6.4550, 3.4350, radius_km=2)
        # ~1.1 km north and ~0.9 km east of the centre.
        self.assertLessEqual(south, 6.4650)
        self.assertGreaterEqual(north, 6.4650)
        self.assertLessEqual(west, 3.4450)
        self.assertGreaterEqual(east, 3.4450)

    def test_box_corners_are_far_enough_from_the_centre(self):
        """Every corner must lie outside the circle (or the box is not minimal)."""
        south, north, west, east = bounding_box(6.4550, 3.4350, radius_km=2)
        corners = [(south, west), (south, east), (north, west), (north, east)]
        for lat, lng in corners:
            self.assertGreaterEqual(
                distance_km(6.4550, 3.4350, lat, lng),
                2.0,
                f"corner ({lat}, {lng}) is inside the circle",
            )

    def test_box_away_from_the_pole_is_not_whole_globe_wide(self):
        west, east = bounding_box(6.4550, 3.3900, radius_km=5)[2:]
        self.assertLess(east - west, 1.0)

    def test_box_crossing_the_antimeridian_stays_small(self):
        south, north, west, east = bounding_box(0, 179.98, radius_km=10)
        # Longitudes are unwrapped, so the box spans ~0.2 degrees, not the globe.
        self.assertGreater(west, 179.0)
        self.assertGreater(east, 180.0)

    def test_box_near_pole_spans_every_longitude_and_reaches_the_pole(self):
        south, north, west, east = bounding_box(89.999, 0, radius_km=50)
        self.assertEqual((west, east), (-180.0, 180.0))
        self.assertEqual(north, 90.0)
        self.assertLess(south, 89.6)  # walked 50 km north, over the top
