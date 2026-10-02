"""OSRM HTTP client. Network errors are mapped to typed routing exceptions."""

from __future__ import annotations

import json
import math
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlencode

import certifi

from naveera_gpx.domain.coordinates import Point, parse_point
from naveera_gpx.domain.routing import (
    NoRouteError,
    Route,
    RoutingHttpError,
    RoutingResponseError,
    RoutingTimeout,
    RoutingUnavailable,
)

DEFAULT_BASE = "https://router.project-osrm.org/route/v1/driving"
_USER_AGENT = "NaveeraGPX/1.0"


class OsrmRouter:
    """Driving routes from an OSRM ``route/v1/driving`` endpoint.

    Uses ``urllib`` plus the certifi CA bundle so a frozen app can verify TLS
    without shelling out to ``curl`` or depending on a system Python.
    """

    def __init__(self, base_url: str = DEFAULT_BASE, timeout: float = 45.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def route(self, start: Point, end: Point) -> Route:
        url = self._url(start, end)
        body = self._fetch(url)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RoutingResponseError(
                "The routing service returned a response that is not valid JSON."
            ) from exc
        return _parse_payload(payload, start, end)

    def _url(self, start: Point, end: Point) -> str:
        coordinates = (
            f"{start[1]:.7f},{start[0]:.7f};{end[1]:.7f},{end[0]:.7f}"
        )
        query = urlencode(
            {"overview": "full", "geometries": "geojson", "steps": "false"}
        )
        return f"{self.base_url}/{coordinates}?{query}"

    def _fetch(self, url: str) -> bytes:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )
        context = ssl.create_default_context(cafile=certifi.where())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=context) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise RoutingHttpError(exc.code) from exc
        except TimeoutError as exc:
            raise RoutingTimeout() from exc
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise RoutingTimeout() from exc
            raise RoutingUnavailable(str(reason)) from exc


def _parse_payload(payload: object, start: Point, end: Point) -> Route:
    if not isinstance(payload, dict):
        raise RoutingResponseError("The routing service returned JSON that is not an object.")
    code = payload.get("code")
    routes = payload.get("routes")
    if code == "NoRoute":
        raise NoRouteError(start, end)
    if code != "Ok" or not isinstance(routes, list) or not routes:
        raise RoutingResponseError(
            f"The routing service did not return a route (code={code!r})."
        )
    route = routes[0]
    if not isinstance(route, dict):
        raise RoutingResponseError("The routing service route entry was not an object.")
    geometry = route.get("geometry")
    if not isinstance(geometry, dict) or "coordinates" not in geometry:
        raise RoutingResponseError("The routing service response is missing route geometry.")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise RoutingResponseError(
            "The routing service returned a route with too few points to write a GPX file."
        )
    points: list[Point] = []
    for pair in coordinates:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            raise RoutingResponseError("The routing service returned a malformed coordinate.")
        try:
            longitude = float(pair[0])
            latitude = float(pair[1])
        except (TypeError, ValueError) as exc:
            raise RoutingResponseError(
                "The routing service returned a malformed coordinate."
            ) from exc
        if not math.isfinite(latitude) or not math.isfinite(longitude):
            raise RoutingResponseError(
                "The routing service returned a non-finite coordinate."
            )
        points.append(parse_point([latitude, longitude]))
    try:
        distance = float(route["distance"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RoutingResponseError(
            "The routing service response is missing route distance."
        ) from exc
    if not math.isfinite(distance) or distance < 0:
        raise RoutingResponseError("The routing service returned an invalid route distance.")
    return Route(distance_meters=distance, points=tuple(points))
