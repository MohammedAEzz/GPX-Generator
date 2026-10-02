"""Latitude/longitude parsing shared by the CLI, GUI, and JSON loader."""

from __future__ import annotations

import math
from typing import Any

Point = tuple[float, float]


def parse_point(value: Any) -> Point:
    """Accept ``[lat, lon]``, ``(lat, lon)``, or ``\"lat, lon\"``."""
    if isinstance(value, str):
        return parse_coordinate_text(value)
    if isinstance(value, bool) or not isinstance(value, (list, tuple)):
        raise ValueError(
            "Each point must be latitude and longitude, as two numbers or as "
            "'latitude, longitude'."
        )
    if len(value) != 2:
        raise ValueError(
            f"Expected two numbers (latitude, longitude); got {len(value)} value(s)."
        )
    if any(isinstance(item, bool) for item in value):
        raise ValueError("Coordinates must be numbers, not true/false.")
    try:
        latitude = float(value[0])
        longitude = float(value[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Coordinates must be numbers. Could not read {value!r}."
        ) from exc
    return _validated(latitude, longitude)


def parse_coordinate_text(text: str) -> Point:
    raw = text.strip()
    if not raw:
        raise ValueError(
            "Enter latitude and longitude separated by a comma, for example 39.690000, -105.080000."
        )
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        raise ValueError(
            "Expected two numbers separated by a comma (latitude, longitude); "
            f"got {len(parts)} value(s): {raw!r}."
        )
    try:
        latitude = float(parts[0])
        longitude = float(parts[1])
    except ValueError as exc:
        raise ValueError(
            f"Coordinates must be numbers. Could not read {raw!r}."
        ) from exc
    return _validated(latitude, longitude)


def _validated(latitude: float, longitude: float) -> Point:
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("Coordinates must be finite numbers (not NaN or infinity).")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError(
            "Latitude must be between -90 and 90 and longitude between -180 and 180 "
            f"(got {latitude}, {longitude})."
        )
    return (latitude, longitude)
