"""Distance helper used only to space GPX timestamps."""

from __future__ import annotations

import math

from naveera_gpx.domain.coordinates import Point

# Original generator constant (statute miles, spherical Earth).
_EARTH_DIAMETER_MILES = 7917.5226
METERS_PER_MILE = 1609.344


def distance_miles(start: Point, end: Point) -> float:
    lat1, lon1 = map(math.radians, start)
    lat2, lon2 = map(math.radians, end)
    hav = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return _EARTH_DIAMETER_MILES * math.asin(math.sqrt(min(1.0, max(0.0, hav))))


def travel_seconds(start: Point, end: Point, speed_mph: float) -> float:
    """Seconds at ``speed_mph``, never less than one second."""
    return max(1.0, distance_miles(start, end) / speed_mph * 3600.0)
