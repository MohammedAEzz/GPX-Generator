"""Trip model, JSON mapping, and consecutive-stop merging."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from naveera_gpx.domain.coordinates import Point, parse_point

_KINDS = ("pickup", "dropoff")


@dataclass(frozen=True)
class Step:
    kind: str
    name: str
    point: Point


@dataclass(frozen=True)
class PhysicalStop:
    """One driving target. Consecutive steps at the same coordinates share a stop."""

    point: Point
    steps: tuple[Step, ...]

    def label(self) -> str:
        return " + ".join(f"{step.kind}: {step.name}" for step in self.steps)


@dataclass(frozen=True)
class Trip:
    type: str
    name: str
    start: Point
    steps: tuple[Step, ...]
    speed_mph: float
    pause_seconds: float


def merge_consecutive(steps: Sequence[Step]) -> tuple[PhysicalStop, ...]:
    """Merge only back-to-back steps that share a coordinate.

    A later visit to a coordinate that already appeared is a new stop.
    """
    merged: list[PhysicalStop] = []
    for step in steps:
        if merged and merged[-1].point == step.point:
            previous = merged[-1]
            merged[-1] = PhysicalStop(previous.point, previous.steps + (step,))
        else:
            merged.append(PhysicalStop(step.point, (step,)))
    return tuple(merged)


def slugify(name: str) -> str:
    slug = re.sub(r"[^\w-]+", "_", name, flags=re.UNICODE).strip("_")[:80]
    return slug or "trip"


def trip_from_normal_fields(
    *,
    name: str,
    start: Any,
    pickup: Any,
    dropoff: Any,
    speed: Any,
    pause: Any,
) -> Trip:
    passenger = _require_name(name, "Enter a passenger or trip name.")
    return Trip(
        type="normal",
        name=passenger,
        start=_labeled("Driver start", start),
        steps=(
            Step("pickup", passenger, _labeled("Pickup", pickup)),
            Step("dropoff", passenger, _labeled("Drop-off", dropoff)),
        ),
        speed_mph=_positive_speed(speed),
        pause_seconds=_non_negative(pause, "Pause"),
    )


def trip_from_pooled_fields(
    *,
    name: str,
    start: Any,
    steps: Sequence[Mapping[str, Any]],
    speed: Any,
    pause: Any,
) -> Trip:
    pool = _require_name(name, "Enter a pool name.")
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)):
        raise ValueError("Pooled trips need an ordered list of stops.")
    if len(steps) == 0:
        raise ValueError("Add at least one pickup or drop-off stop.")
    parsed: list[Step] = []
    for index, raw in enumerate(steps, start=1):
        parsed.append(_parse_step(raw, index, fallback_name=None))
    return Trip(
        type="pooled",
        name=pool,
        start=_labeled("Driver start", start),
        steps=tuple(parsed),
        speed_mph=_positive_speed(speed),
        pause_seconds=_non_negative(pause, "Pause"),
    )


def trip_from_dict(data: Mapping[str, Any]) -> Trip:
    if not isinstance(data, Mapping):
        raise ValueError("Trip file must be a JSON object.")
    kind = data.get("type")
    speed = data.get("speed_mph", 20)
    pause = data.get("pause_seconds", 0)
    if kind == "normal":
        return trip_from_normal_fields(
            name=str(data.get("name", "")),
            start=data.get("start"),
            pickup=data.get("pickup"),
            dropoff=data.get("dropoff"),
            speed=speed,
            pause=pause,
        )
    if kind == "pooled":
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list):
            raise ValueError("Pooled trips need an ordered, nonempty steps list.")
        return trip_from_pooled_fields(
            name=str(data.get("name", "")),
            start=data.get("start"),
            steps=raw_steps,
            speed=speed,
            pause=pause,
        )
    raise ValueError("Trip type must be normal or pooled.")


def trip_to_dict(trip: Trip) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": trip.type,
        "name": trip.name,
        "start": [trip.start[0], trip.start[1]],
        "speed_mph": trip.speed_mph,
        "pause_seconds": trip.pause_seconds,
    }
    if trip.type == "normal":
        pickup, dropoff = trip.steps
        payload["pickup"] = [pickup.point[0], pickup.point[1]]
        payload["dropoff"] = [dropoff.point[0], dropoff.point[1]]
        return payload
    payload["steps"] = [
        {"kind": step.kind, "name": step.name, "point": [step.point[0], step.point[1]]}
        for step in trip.steps
    ]
    return payload


def _parse_step(raw: Mapping[str, Any], index: int, fallback_name: str | None) -> Step:
    if not isinstance(raw, Mapping):
        raise ValueError(f"Stop {index} must be an object with kind, name, and point.")
    kind = str(raw.get("kind", "")).strip().lower()
    if kind not in _KINDS:
        raise ValueError(f"Stop {index}: kind must be pickup or dropoff.")
    name = str(raw.get("name", "")).strip()
    if not name:
        if fallback_name:
            name = fallback_name
        else:
            raise ValueError(f"Stop {index}: enter a passenger name.")
    try:
        point = parse_point(raw.get("point"))
    except ValueError as exc:
        raise ValueError(f"Stop {index}: {exc}") from exc
    return Step(kind, name, point)


def _labeled(label: str, value: Any) -> Point:
    if value is None:
        raise ValueError(f"{label}: enter latitude and longitude.")
    try:
        return parse_point(value)
    except ValueError as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _require_name(value: str, message: str) -> str:
    name = str(value).strip()
    if not name:
        raise ValueError(message)
    return name


def _positive_speed(value: Any) -> float:
    number = _as_float(value, "Speed must be a number of miles per hour greater than 0.")
    if not math.isfinite(number) or number <= 0:
        raise ValueError("Speed must be a number of miles per hour greater than 0.")
    return number


def _non_negative(value: Any, label: str) -> float:
    number = _as_float(value, f"{label} must be a number of seconds greater than or equal to 0.")
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a number of seconds greater than or equal to 0.")
    return number


def _as_float(value: Any, message: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(message)
    if isinstance(value, str) and not value.strip():
        raise ValueError(message)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(message) from exc
