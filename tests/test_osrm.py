"""OSRM client error mapping. urllib is mocked; nothing is sent."""

import io
import json
import urllib.error
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from naveera_gpx.data.osrm import OsrmRouter
from naveera_gpx.domain.routing import (
    NoRouteError,
    RoutingHttpError,
    RoutingResponseError,
    RoutingTimeout,
    RoutingUnavailable,
)
from tests.fakes import PICKUP, START


def _body(payload: object) -> bytes:
    return json.dumps(payload).encode()


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def test_ok_response_swaps_geojson_lon_lat():
    payload = {
        "code": "Ok",
        "routes": [
            {
                "distance": 250.5,
                "geometry": {"coordinates": [[-105.08, 39.69], [-105.07, 39.70]]},
            }
        ],
    }
    with patch("naveera_gpx.data.osrm.urllib.request.urlopen", return_value=_Response(_body(payload))):
        route = OsrmRouter().route(START, PICKUP)
    assert route.distance_meters == 250.5
    assert route.points[0] == (39.69, -105.08)
    assert route.points[1] == (39.70, -105.07)


def test_timeout_becomes_routing_timeout():
    with patch(
        "naveera_gpx.data.osrm.urllib.request.urlopen",
        side_effect=TimeoutError("timed out"),
    ):
        with pytest.raises(RoutingTimeout, match="timed out"):
            OsrmRouter().route(START, PICKUP)


def test_url_timeout_reason_becomes_routing_timeout():
    with patch(
        "naveera_gpx.data.osrm.urllib.request.urlopen",
        side_effect=urllib.error.URLError(TimeoutError("The read operation timed out")),
    ):
        with pytest.raises(RoutingTimeout):
            OsrmRouter().route(START, PICKUP)


def test_dns_failure_is_unavailable():
    with patch(
        "naveera_gpx.data.osrm.urllib.request.urlopen",
        side_effect=urllib.error.URLError("nodename nor servname provided"),
    ):
        with pytest.raises(RoutingUnavailable, match="Could not reach"):
            OsrmRouter().route(START, PICKUP)


def test_http_429_is_a_clear_http_error():
    error = HTTPError("https://router.example", 429, "Too Many", hdrs=None, fp=io.BytesIO(b""))
    with patch("naveera_gpx.data.osrm.urllib.request.urlopen", side_effect=error):
        with pytest.raises(RoutingHttpError, match="429") as caught:
            OsrmRouter().route(START, PICKUP)
    assert caught.value.status == 429


def test_http_503_is_a_clear_http_error():
    error = HTTPError("https://router.example", 503, "Unavailable", hdrs=None, fp=io.BytesIO(b""))
    with patch("naveera_gpx.data.osrm.urllib.request.urlopen", side_effect=error):
        with pytest.raises(RoutingHttpError, match="unavailable"):
            OsrmRouter().route(START, PICKUP)


def test_malformed_json_is_a_response_error():
    with patch(
        "naveera_gpx.data.osrm.urllib.request.urlopen",
        return_value=_Response(b"not-json"),
    ):
        with pytest.raises(RoutingResponseError, match="not valid JSON"):
            OsrmRouter().route(START, PICKUP)


def test_no_route_code_is_a_no_route_error():
    payload = {"code": "NoRoute", "routes": []}
    with patch(
        "naveera_gpx.data.osrm.urllib.request.urlopen",
        return_value=_Response(_body(payload)),
    ):
        with pytest.raises(NoRouteError, match="No driving route"):
            OsrmRouter().route(START, PICKUP)


def test_missing_geometry_is_a_response_error():
    payload = {"code": "Ok", "routes": [{"distance": 10, "geometry": {}}]}
    with patch(
        "naveera_gpx.data.osrm.urllib.request.urlopen",
        return_value=_Response(_body(payload)),
    ):
        with pytest.raises(RoutingResponseError, match="missing route geometry"):
            OsrmRouter().route(START, PICKUP)
