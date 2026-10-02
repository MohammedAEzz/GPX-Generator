"""Plan driving legs and write a run folder. Routing is injected."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable

from naveera_gpx.domain.coordinates import Point
from naveera_gpx.domain.geo import METERS_PER_MILE
from naveera_gpx.domain.gpx import advance_clock, write_gpx
from naveera_gpx.domain.routing import Route, Router
from naveera_gpx.domain.trip import PhysicalStop, Trip, merge_consecutive, slugify


@dataclass(frozen=True)
class LegRecord:
    step: int
    label: str
    actions: tuple[dict[str, str], ...]
    point: Point
    file: str | None
    note: str | None
    distance_miles: float | None
    snapped_start: Point | None
    snapped_end: Point | None


@dataclass(frozen=True)
class RunResult:
    directory: Path
    trip_name: str
    trip_type: str
    legs: tuple[LegRecord, ...]

    def summary(self) -> str:
        written = sum(1 for leg in self.legs if leg.file)
        lines = [f"Saved {written} GPX file(s) to {self.directory}"]
        for leg in self.legs:
            if leg.file is None:
                lines.append(f"{leg.step}. {leg.label}: already at this stop (no driving leg).")
                continue
            assert leg.distance_miles is not None
            assert leg.snapped_start is not None and leg.snapped_end is not None
            lines.append(
                f"{leg.step}. {leg.label}: {leg.file} ({leg.distance_miles:.2f} mi). "
                f"Snapped {_fmt(leg.snapped_start)} → {_fmt(leg.snapped_end)}."
            )
        return "\n".join(lines)


def generate_run(
    trip: Trip,
    output_parent: Path | str,
    router: Router,
    *,
    started_at: datetime | None = None,
    run_stamp: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> RunResult:
    """Write one new run folder. A failed attempt is renamed ``*.failed`` and left in place."""
    parent = Path(output_parent)
    parent.mkdir(parents=True, exist_ok=True)
    moment = started_at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise ValueError("started_at must be timezone-aware.")
    stamp = run_stamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    leaf = _unique_leaf(parent, f"{slugify(trip.name)}-{stamp}")
    partial = parent / f".{leaf}.partial"
    final = parent / leaf
    partial.mkdir()
    try:
        legs, _cursor = _write_legs(trip, partial, router, moment, on_progress)
        manifest = {
            "name": trip.name,
            "type": trip.type,
            "start": [trip.start[0], trip.start[1]],
            "speed_mph": trip.speed_mph,
            "pause_seconds": trip.pause_seconds,
            "stops": [_leg_dict(leg) for leg in legs],
        }
        (partial / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(partial, final)
    except Exception as exc:
        failed = _mark_failed(parent, partial, leaf, exc)
        exc.failed_directory = failed  # type: ignore[attr-defined]
        raise
    return RunResult(final, trip.name, trip.type, tuple(legs))


def _write_legs(
    trip: Trip,
    folder: Path,
    router: Router,
    moment: datetime,
    on_progress: Callable[[str], None] | None,
) -> tuple[list[LegRecord], datetime]:
    stops = merge_consecutive(trip.steps)
    total = len(stops)
    current = trip.start
    cursor = moment
    legs: list[LegRecord] = []
    for index, stop in enumerate(stops, start=1):
        label = stop.label()
        if current == stop.point:
            if on_progress:
                on_progress(f"Leg {index} of {total}: already at this stop.")
            legs.append(_already(index, stop, label))
            cursor = advance_clock(cursor, trip.pause_seconds)
            continue
        if on_progress:
            on_progress(f"Routing leg {index} of {total}: {label}")
        route = router.route(current, stop.point)
        _reject_unusable_route(route)
        filename = f"{index:02d}_to_stop_{index}.gpx"
        cursor = write_gpx(
            folder / filename,
            f"{trip.name}: {label}",
            route.points,
            cursor,
            trip.speed_mph,
        )
        miles = route.distance_meters / METERS_PER_MILE
        legs.append(
            LegRecord(
                step=index,
                label=label,
                actions=_actions(stop),
                point=stop.point,
                file=filename,
                note=None,
                distance_miles=miles,
                snapped_start=route.points[0],
                snapped_end=route.points[-1],
            )
        )
        cursor = advance_clock(cursor, trip.pause_seconds)
        current = stop.point
    return legs, cursor


def _reject_unusable_route(route: Route) -> None:
    if len(route.points) < 2:
        raise ValueError("Routing returned too few points to write a GPX file.")


def _already(index: int, stop: PhysicalStop, label: str) -> LegRecord:
    return LegRecord(
        step=index,
        label=label,
        actions=_actions(stop),
        point=stop.point,
        file=None,
        note="Already at this stop; no driving leg.",
        distance_miles=None,
        snapped_start=None,
        snapped_end=None,
    )


def _actions(stop: PhysicalStop) -> tuple[dict[str, str], ...]:
    return tuple({"kind": step.kind, "name": step.name} for step in stop.steps)


def _leg_dict(leg: LegRecord) -> dict[str, object]:
    payload: dict[str, object] = {
        "step": leg.step,
        "label": leg.label,
        "actions": [dict(action) for action in leg.actions],
        "point": [leg.point[0], leg.point[1]],
        "file": leg.file,
        "note": leg.note,
        "distance_miles": leg.distance_miles,
        "snapped_start": _point_list(leg.snapped_start),
        "snapped_end": _point_list(leg.snapped_end),
    }
    return payload


def _point_list(point: Point | None) -> list[float] | None:
    if point is None:
        return None
    return [point[0], point[1]]


def _fmt(point: Point) -> str:
    return f"{point[0]:.6f}, {point[1]:.6f}"


def _unique_leaf(parent: Path, leaf: str) -> str:
    if not (parent / leaf).exists() and not (parent / f".{leaf}.partial").exists():
        return leaf
    number = 2
    while True:
        candidate = f"{leaf}-{number}"
        if not (parent / candidate).exists() and not (parent / f".{candidate}.partial").exists():
            return candidate
        number += 1


def _mark_failed(parent: Path, partial: Path, leaf: str, exc: BaseException) -> Path:
    message = f"{exc}\n"
    try:
        if partial.exists():
            (partial / "ERROR.txt").write_text(message, encoding="utf-8")
    except OSError:
        return partial
    failed_leaf = leaf if leaf.endswith(".failed") else f"{leaf}.failed"
    destination = parent / failed_leaf
    number = 2
    while destination.exists():
        destination = parent / f"{leaf}.failed-{number}"
        number += 1
    try:
        os.replace(partial, destination)
    except OSError:
        return partial
    return destination
