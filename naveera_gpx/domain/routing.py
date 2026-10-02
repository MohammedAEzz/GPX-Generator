"""Routing port. The data layer implements this; tests supply a fake."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from naveera_gpx.domain.coordinates import Point


@dataclass(frozen=True)
class Route:
    """A driving route. ``points`` are (latitude, longitude) in travel order."""

    distance_meters: float
    points: tuple[Point, ...]


class Router(Protocol):
    def route(self, start: Point, end: Point) -> Route:
        """Return the road geometry from ``start`` to ``end``."""


class RoutingError(Exception):
    """Base type for failures raised at the routing boundary."""

    failed_directory: Path | None = None


class RoutingTimeout(RoutingError):
    def __init__(self) -> None:
        super().__init__(
            "Routing timed out before the service returned a route. "
            "Check the network connection and try again."
        )


class RoutingUnavailable(RoutingError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            f"Could not reach the routing service ({reason}). "
            "Check the network connection and try again."
        )


class RoutingHttpError(RoutingError):
    def __init__(self, status: int) -> None:
        self.status = status
        if status == 429:
            detail = "HTTP 429 (too many requests). Wait a moment and try again."
        elif 500 <= status <= 599:
            detail = f"HTTP {status}. The routing service is unavailable right now."
        else:
            detail = f"HTTP {status}."
        super().__init__(f"The routing service returned {detail}")


class RoutingResponseError(RoutingError):
    """The service responded, but the body was not a usable route."""


class NoRouteError(RoutingError):
    def __init__(self, start: Point, end: Point) -> None:
        super().__init__(
            "No driving route from "
            f"{start[0]:.6f}, {start[1]:.6f} to {end[0]:.6f}, {end[1]:.6f}."
        )
