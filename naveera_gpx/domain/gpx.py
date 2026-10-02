"""GPX 1.1 writer. Waypoint track matching the simulator's expected shape."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

from naveera_gpx.domain.coordinates import Point
from naveera_gpx.domain.geo import travel_seconds

NS = "http://www.topografix.com/GPX/1/1"
ET.register_namespace("", NS)


def format_timestamp(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("GPX timestamps must be timezone-aware.")
    return (
        moment.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def write_gpx(
    path: Path,
    name: str,
    points: tuple[Point, ...] | list[Point],
    when: datetime,
    speed_mph: float,
) -> datetime:
    """Write timestamped ``wpt`` elements. Returns the time of the last point."""
    if when.tzinfo is None:
        raise ValueError("GPX timestamps must be timezone-aware.")
    if len(points) < 2:
        raise ValueError("A GPX route needs at least two points.")
    root = ET.Element(
        f"{{{NS}}}gpx",
        version="1.1",
        creator="Naveera GPX Test Generator",
    )
    metadata = ET.SubElement(root, f"{{{NS}}}metadata")
    ET.SubElement(metadata, f"{{{NS}}}name").text = name
    cursor = when
    for index, point in enumerate(points):
        if index:
            cursor += timedelta(seconds=travel_seconds(points[index - 1], point, speed_mph))
        waypoint = ET.SubElement(
            root,
            f"{{{NS}}}wpt",
            lat=f"{point[0]:.7f}",
            lon=f"{point[1]:.7f}",
        )
        ET.SubElement(waypoint, f"{{{NS}}}name").text = f"Route Point {index + 1}"
        ET.SubElement(waypoint, f"{{{NS}}}time").text = format_timestamp(cursor)
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return cursor


def advance_clock(when: datetime, pause_seconds: float) -> datetime:
    """Move the clock forward by the stop pause, and always past ``when``."""
    if when.tzinfo is None:
        raise ValueError("GPX timestamps must be timezone-aware.")
    nxt = when + timedelta(seconds=pause_seconds)
    if nxt <= when:
        nxt = when + timedelta(milliseconds=1)
    return nxt
