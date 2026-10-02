#!/usr/bin/env python3
"""Command-line entry for the Naveera GPX generator.

Normal JSON:
{"type":"normal","name":"Passenger A","start":[39.69,-105.08],
 "pickup":[39.698010,-105.070418],"dropoff":[39.710486,-105.064513]}

Pooled JSON (steps MUST be in the intended driving order):
{"type":"pooled","name":"Pool A","start":[39.69,-105.08],"steps":[
 {"kind":"pickup","name":"Passenger A","point":[39.698010,-105.070418]},
 {"kind":"pickup","name":"Passenger B","point":[39.698010,-105.070418]},
 {"kind":"dropoff","name":"Passenger A","point":[39.710486,-105.064513]},
 {"kind":"dropoff","name":"Passenger B","point":[39.72,-105.06]}]}

Optional JSON fields: speed_mph (default 20), pause_seconds (default 0).
Only consecutive identical coordinates are merged. Each run writes a new
timestamped folder. A failed run is renamed with a .failed suffix.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from naveera_gpx.data.osrm import DEFAULT_BASE, OsrmRouter
from naveera_gpx.domain.coordinates import parse_coordinate_text
from naveera_gpx.domain.generate import generate_run
from naveera_gpx.domain.trip import trip_from_dict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", type=Path, help="JSON trip file. Omit for interactive prompts.")
    parser.add_argument("--output", default="gpx_output", help="Parent directory for run folders.")
    parser.add_argument("--osrm-base", default=DEFAULT_BASE, help="OSRM driving route endpoint.")
    args = parser.parse_args(argv)
    try:
        config = (
            json.loads(args.input.read_text(encoding="utf-8"))
            if args.input
            else _interactive()
        )
        trip = trip_from_dict(config)
        result = generate_run(trip, args.output, OsrmRouter(args.osrm_base))
    except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        failed = getattr(error, "failed_directory", None)
        if failed:
            print(f"Partial run: {failed}", file=sys.stderr)
        return 1
    except Exception as error:
        # Routing failures and anything else raised at the boundary.
        from naveera_gpx.domain.routing import RoutingError

        if not isinstance(error, RoutingError):
            raise
        print(f"Error: {error}", file=sys.stderr)
        failed = getattr(error, "failed_directory", None)
        if failed:
            print(f"Partial run: {failed}", file=sys.stderr)
        return 1
    print(result.summary())
    return 0


def _interactive() -> dict:
    kind = input("Trip type (1 = normal, 2 = pooled): ").strip()
    if kind not in ("1", "2", "normal", "pooled"):
        raise ValueError("Select 1 or 2.")
    pooled = kind in ("2", "pooled")
    name = input("Passenger / trip / pool name: ").strip()
    start = _ask_point("Current location / start")
    speed = input("Speed mph [20]: ").strip() or "20"
    pause = input("Pause at each stop in seconds [0]: ").strip() or "0"
    config: dict = {
        "type": "pooled" if pooled else "normal",
        "name": name,
        "start": list(start),
        "speed_mph": speed,
        "pause_seconds": pause,
    }
    if not pooled:
        config["pickup"] = list(_ask_point("Pickup"))
        config["dropoff"] = list(_ask_point("Drop-off"))
        return config
    count = int(input("Number of ordered steps: ").strip())
    steps = []
    for index in range(count):
        print(f"Step {index + 1}")
        step_kind = input("Kind (pickup/dropoff): ").strip().lower()
        passenger = input("Passenger name: ").strip()
        steps.append(
            {"kind": step_kind, "name": passenger, "point": list(_ask_point("Stop"))}
        )
    config["steps"] = steps
    return config


def _ask_point(label: str) -> tuple[float, float]:
    while True:
        try:
            return parse_coordinate_text(input(f"{label} (latitude, longitude): "))
        except ValueError as error:
            print(error)


if __name__ == "__main__":
    sys.exit(main())
