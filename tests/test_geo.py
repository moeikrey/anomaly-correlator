"""Unit tests for the great-circle primitive, independent of any rule."""

import math

from ghostbadge.generator.org import BENIGN_CITIES, DISTANT_CITIES
from ghostbadge.geo import HQ_LAT, HQ_LON, haversine_km, km_from_hq


def test_zero_distance_to_self():
    assert haversine_km(HQ_LAT, HQ_LON, HQ_LAT, HQ_LON) == 0.0


def test_known_pair_sf_to_new_york():
    # SF -> NYC is ~4130 km; allow 1% for radius/rounding choices.
    d = haversine_km(37.7749, -122.4194, 40.7128, -74.0060)
    assert math.isclose(d, 4130, rel_tol=0.01)


def test_symmetry():
    a = haversine_km(37.7749, -122.4194, 51.5074, -0.1278)
    b = haversine_km(51.5074, -0.1278, 37.7749, -122.4194)
    assert a == b


def test_benign_cities_are_commute_range():
    # The whole premise of GB-002: benign geo is near HQ, distant geo is not.
    for lat, lon in BENIGN_CITIES.values():
        assert km_from_hq(lat, lon) < 100
    for lat, lon in DISTANT_CITIES.values():
        assert km_from_hq(lat, lon) > 2000
