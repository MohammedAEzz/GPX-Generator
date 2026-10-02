"""Shared fixtures for generator tests. Coordinates are made up."""

from __future__ import annotations

from naveera_gpx.domain.coordinates import Point
from naveera_gpx.domain.routing import Route

START: Point = (39.690000, -105.080000)
PICKUP: Point = (39.698010, -105.070418)
DROPOFF: Point = (39.710486, -105.064513)
OTHER: Point = (39.720000, -105.060000)


def road(start: Point, end: Point, meters: float = 1609.344) -> Route:
    """A three-point stand-in for a road, with endpoints offset from the request."""
    snapped_start = (start[0] + 0.001, start[1] + 0.001)
    midpoint = ((start[0] + end[0]) / 2 + 0.002, (start[1] + end[1]) / 2 - 0.002)
    snapped_end = (end[0] - 0.001, end[1] - 0.001)
    return Route(distance_meters=meters, points=(snapped_start, midpoint, snapped_end))


class ScriptedRouter:
    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[Point, Point]] = []

    def route(self, start: Point, end: Point) -> Route:
        self.calls.append((start, end))
        if not self._responses:
            raise AssertionError(f"unexpected route request {start} -> {end}")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, Route)
        return item
