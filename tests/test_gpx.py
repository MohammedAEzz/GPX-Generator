"""GPX structure, escaping, and timestamps."""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from naveera_gpx.domain.generate import generate_run
from naveera_gpx.domain.gpx import NS, write_gpx
from naveera_gpx.domain.trip import trip_from_normal_fields
from tests.fakes import DROPOFF, PICKUP, START, ScriptedRouter, road

STARTED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _times(folder: Path) -> list[datetime]:
    found: list[datetime] = []
    for path in sorted(folder.glob("*.gpx")):
        root = ET.parse(path).getroot()
        for node in root.findall(f"{{{NS}}}wpt/{{{NS}}}time"):
            assert node.text is not None
            found.append(datetime.fromisoformat(node.text.replace("Z", "+00:00")))
    return found


def test_gpx_is_waypoint_only_with_metadata_name(tmp_path: Path):
    trip = trip_from_normal_fields(
        name="Passenger A",
        start=START,
        pickup=PICKUP,
        dropoff=DROPOFF,
        speed=20,
        pause=0,
    )
    router = ScriptedRouter([road(START, PICKUP), road(PICKUP, DROPOFF)])
    result = generate_run(trip, tmp_path, router, started_at=STARTED, run_stamp="stamp")
    root = ET.parse(next(result.directory.glob("*.gpx"))).getroot()
    assert root.tag == f"{{{NS}}}gpx"
    assert root.get("version") == "1.1"
    assert root.find(f"{{{NS}}}metadata/{{{NS}}}name") is not None
    assert root.find(f"{{{NS}}}trk") is None
    names = [node.text for node in root.findall(f"{{{NS}}}wpt/{{{NS}}}name")]
    assert names == ["Route Point 1", "Route Point 2", "Route Point 3"]


def test_timestamps_strictly_increase_across_points_and_legs(tmp_path: Path):
    trip = trip_from_normal_fields(
        name="Passenger A",
        start=START,
        pickup=PICKUP,
        dropoff=DROPOFF,
        speed=20,
        pause=0,
    )
    router = ScriptedRouter([road(START, PICKUP), road(PICKUP, DROPOFF)])
    result = generate_run(
        trip, tmp_path, router, started_at=STARTED, run_stamp="times"
    )
    times = _times(result.directory)
    assert len(times) == 6
    assert times == sorted(times)
    assert len(set(times)) == len(times)


def test_pause_is_applied_between_legs(tmp_path: Path):
    trip = trip_from_normal_fields(
        name="Passenger A",
        start=START,
        pickup=PICKUP,
        dropoff=DROPOFF,
        speed=20,
        pause=5,
    )
    router = ScriptedRouter([road(START, PICKUP), road(PICKUP, DROPOFF)])
    result = generate_run(trip, tmp_path, router, started_at=STARTED, run_stamp="pause")
    first = ET.parse(result.directory / "01_to_stop_1.gpx").getroot()
    second = ET.parse(result.directory / "02_to_stop_2.gpx").getroot()
    last = datetime.fromisoformat(
        first.findall(f"{{{NS}}}wpt/{{{NS}}}time")[-1].text.replace("Z", "+00:00")
    )
    nxt = datetime.fromisoformat(
        second.findall(f"{{{NS}}}wpt/{{{NS}}}time")[0].text.replace("Z", "+00:00")
    )
    assert (nxt - last).total_seconds() >= 5


def test_xml_special_characters_round_trip(tmp_path: Path):
    name = "A & B <tag> \"q\" 's' café"
    path = tmp_path / "special.gpx"
    write_gpx(path, name, (START, DROPOFF), STARTED, 20)
    root = ET.parse(path).getroot()
    assert root.find(f"{{{NS}}}metadata/{{{NS}}}name").text == name
    raw = path.read_text(encoding="utf-8")
    assert "<tag>" not in raw
    assert "&amp;" in raw
    assert "café" in raw
