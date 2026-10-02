"""Leg planning, manifests, and run folders."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from naveera_gpx.domain.generate import generate_run
from naveera_gpx.domain.routing import (
    NoRouteError,
    RoutingHttpError,
    RoutingResponseError,
    RoutingTimeout,
)
from naveera_gpx.domain.trip import trip_from_normal_fields, trip_from_pooled_fields
from tests.fakes import DROPOFF, OTHER, PICKUP, START, ScriptedRouter, road

STARTED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _normal():
    return trip_from_normal_fields(
        name="Passenger A",
        start=START,
        pickup=PICKUP,
        dropoff=DROPOFF,
        speed=20,
        pause=0,
    )


def _gpx_count(folder: Path) -> int:
    return len(list(folder.rglob("*.gpx")))


def test_normal_trip_writes_two_gpx_files_and_snapped_endpoints(tmp_path: Path):
    first = road(START, PICKUP)
    second = road(PICKUP, DROPOFF)
    router = ScriptedRouter([first, second])
    result = generate_run(_normal(), tmp_path, router, started_at=STARTED, run_stamp="normal")
    assert router.calls == [(START, PICKUP), (PICKUP, DROPOFF)]
    assert [leg.file for leg in result.legs] == ["01_to_stop_1.gpx", "02_to_stop_2.gpx"]
    manifest = json.loads((result.directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["stops"][0]["snapped_start"] == list(first.points[0])
    assert manifest["stops"][0]["snapped_end"] == list(first.points[-1])
    assert manifest["stops"][1]["snapped_end"] == list(second.points[-1])
    assert "Snapped" in result.summary()


def test_pooled_distinct_stops_follow_entered_order(tmp_path: Path):
    trip = trip_from_pooled_fields(
        name="Pool",
        start=START,
        steps=[
            {"kind": "pickup", "name": "A", "point": list(PICKUP)},
            {"kind": "dropoff", "name": "B", "point": list(OTHER)},
            {"kind": "dropoff", "name": "A", "point": list(DROPOFF)},
        ],
        speed=20,
        pause=0,
    )
    router = ScriptedRouter(
        [road(START, PICKUP), road(PICKUP, OTHER), road(OTHER, DROPOFF)]
    )
    result = generate_run(trip, tmp_path, router, started_at=STARTED, run_stamp="order")
    assert router.calls == [(START, PICKUP), (PICKUP, OTHER), (OTHER, DROPOFF)]
    assert len(list(result.directory.glob("*.gpx"))) == 3


def test_shared_pickup_is_one_incoming_gpx(tmp_path: Path):
    trip = trip_from_pooled_fields(
        name="Pool",
        start=START,
        steps=[
            {"kind": "pickup", "name": "A", "point": list(PICKUP)},
            {"kind": "pickup", "name": "B", "point": list(PICKUP)},
            {"kind": "dropoff", "name": "A", "point": list(DROPOFF)},
        ],
        speed=20,
        pause=0,
    )
    router = ScriptedRouter([road(START, PICKUP), road(PICKUP, DROPOFF)])
    result = generate_run(trip, tmp_path, router, started_at=STARTED, run_stamp="share-pu")
    assert len(router.calls) == 2
    manifest = json.loads((result.directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["stops"][0]["actions"] == [
        {"kind": "pickup", "name": "A"},
        {"kind": "pickup", "name": "B"},
    ]
    assert manifest["stops"][0]["file"] == "01_to_stop_1.gpx"


def test_driver_already_at_the_first_stop_writes_no_fake_route(tmp_path: Path):
    trip = trip_from_pooled_fields(
        name="Pool",
        start=PICKUP,
        steps=[
            {"kind": "pickup", "name": "A", "point": list(PICKUP)},
            {"kind": "dropoff", "name": "A", "point": list(DROPOFF)},
        ],
        speed=20,
        pause=0,
    )
    router = ScriptedRouter([road(PICKUP, DROPOFF)])
    result = generate_run(trip, tmp_path, router, started_at=STARTED, run_stamp="here")
    assert router.calls == [(PICKUP, DROPOFF)]
    assert result.legs[0].file is None
    assert result.legs[0].note == "Already at this stop; no driving leg."
    manifest = json.loads((result.directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["stops"][0]["file"] is None
    assert manifest["stops"][0]["actions"] == [{"kind": "pickup", "name": "A"}]
    assert "already at this stop" in result.summary()
    assert len(list(result.directory.glob("*.gpx"))) == 1


def test_same_stamp_does_not_overwrite_an_existing_run(tmp_path: Path):
    router = ScriptedRouter([road(START, PICKUP), road(PICKUP, DROPOFF)])
    first = generate_run(_normal(), tmp_path, router, started_at=STARTED, run_stamp="same")
    marker = first.directory / "01_to_stop_1.gpx"
    original = marker.read_bytes()
    router2 = ScriptedRouter([road(START, PICKUP), road(PICKUP, DROPOFF)])
    second = generate_run(_normal(), tmp_path, router2, started_at=STARTED, run_stamp="same")
    assert first.directory != second.directory
    assert marker.read_bytes() == original
    assert second.directory.exists()


def test_retry_after_partial_failure_writes_a_new_folder(tmp_path: Path):
    failing = ScriptedRouter([road(START, PICKUP), RoutingHttpError(503)])
    with pytest.raises(RoutingHttpError) as caught:
        generate_run(_normal(), tmp_path, failing, started_at=STARTED, run_stamp="retry")
    failed = caught.value.failed_directory
    assert failed is not None
    assert failed.name.endswith(".failed")
    assert "HTTP 503" in (failed / "ERROR.txt").read_text(encoding="utf-8")
    assert len(list(failed.glob("*.gpx"))) == 1
    success = generate_run(
        _normal(),
        tmp_path,
        ScriptedRouter([road(START, PICKUP), road(PICKUP, DROPOFF)]),
        started_at=STARTED,
        run_stamp="retry-ok",
    )
    assert success.directory.exists()
    assert failed.exists()
    assert len(list(success.directory.glob("*.gpx"))) == 2


def _assert_failure_writes_no_straight_line(tmp_path: Path, error: Exception, stamp: str):
    router = ScriptedRouter([error])
    with pytest.raises(type(error)):
        generate_run(_normal(), tmp_path, router, started_at=STARTED, run_stamp=stamp)
    for path in tmp_path.rglob("*.gpx"):
        text = path.read_text(encoding="utf-8")
        assert f'lat="{START[0]:.7f}"' not in text or f'lat="{PICKUP[0]:.7f}"' not in text
    assert _gpx_count(tmp_path) == 0


def test_timeout_does_not_write_a_straight_line(tmp_path: Path):
    _assert_failure_writes_no_straight_line(tmp_path, RoutingTimeout(), "timeout")


def test_http_error_does_not_write_a_straight_line(tmp_path: Path):
    _assert_failure_writes_no_straight_line(tmp_path, RoutingHttpError(429), "http")


def test_malformed_response_does_not_write_a_straight_line(tmp_path: Path):
    _assert_failure_writes_no_straight_line(
        tmp_path,
        RoutingResponseError("The routing service returned a response that is not valid JSON."),
        "json",
    )


def test_no_route_does_not_write_a_straight_line(tmp_path: Path):
    _assert_failure_writes_no_straight_line(tmp_path, NoRouteError(START, PICKUP), "noroute")


def test_missing_geometry_does_not_write_a_straight_line(tmp_path: Path):
    _assert_failure_writes_no_straight_line(
        tmp_path,
        RoutingResponseError("The routing service response is missing route geometry."),
        "geom",
    )
