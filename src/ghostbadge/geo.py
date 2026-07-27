"""Great-circle distance math, shared and unit-tested in isolation.

Impossible-presence detection (GB-002) is fundamentally a physics claim —
"no traveler covers this distance in this time" — so the distance primitive
lives here, apart from any rule, where it can be tested against known
city pairs without spinning up an event window. Coordinates are city-level
only (never precise enough to locate a person), consistent with the
project's hard boundary against real personal geo data.
"""

import math

# The fictional Bay Area headquarters. Every badge read is physical presence
# here; GB-002 measures whether a near-simultaneous VPN login came from a
# geo too far away to be the same body. Sited in San Francisco so that the
# benign commute cities (Oakland/Berkeley/San Jose, all <70 km) stay well
# under any impossible-speed threshold while the distant-city injections
# (>2000 km) blow past it.
HQ_LAT = 37.7749
HQ_LON = -122.4194

_EARTH_RADIUS_KM = 6371.0088  # IUGG mean radius


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def km_from_hq(lat: float, lon: float) -> float:
    """Distance from the fictional HQ to a point — GB-002's core measurement."""
    return haversine_km(HQ_LAT, HQ_LON, lat, lon)
