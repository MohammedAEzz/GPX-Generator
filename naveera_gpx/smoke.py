"""Packaged-app checks: bundled Tk, a mocked GPX run, and an optional live route."""

from __future__ import annotations

import tempfile
from pathlib import Path

from naveera_gpx.domain.generate import generate_run
from naveera_gpx.domain.routing import Route
from naveera_gpx.domain.trip import trip_from_normal_fields
from naveera_gpx.presentation.tkcheck import assert_supported, read_tk_info


class _SmokeRouter:
    def route(self, start, end) -> Route:
        midpoint = ((start[0] + end[0]) / 2 + 0.001, (start[1] + end[1]) / 2 - 0.001)
        return Route(distance_meters=1200.0, points=(start, midpoint, end))


def run_self_test() -> int:
    info = read_tk_info()
    print(info.text(), flush=True)
    try:
        assert_supported(info)
    except SystemExit as exc:
        print(f"self_test=fail {exc}", flush=True)
        return 1
    trip = trip_from_normal_fields(
        name="Smoke Test",
        start="39.690000, -105.080000",
        pickup="39.698010, -105.070418",
        dropoff="39.710486, -105.064513",
        speed="20",
        pause="0",
    )
    with tempfile.TemporaryDirectory(prefix="naveera-smoke-") as folder:
        result = generate_run(trip, folder, _SmokeRouter())
        gpx_files = list(result.directory.glob("*.gpx"))
        manifest = result.directory / "manifest.json"
        if len(gpx_files) != 2 or not manifest.is_file():
            print("self_test=fail generation", flush=True)
            return 1
        if result.legs[0].snapped_start is None or result.legs[1].snapped_end is None:
            print("self_test=fail snapped", flush=True)
            return 1
    print("self_test=ok", flush=True)
    return 0


def run_live_route() -> int:
    from naveera_gpx.data.osrm import OsrmRouter

    start = (39.690000, -105.080000)
    end = (39.698010, -105.070418)
    try:
        route = OsrmRouter().route(start, end)
    except Exception as exc:
        print(f"live_route=fail {exc}", flush=True)
        return 1
    if len(route.points) < 2 or route.distance_meters <= 0:
        print("live_route=fail empty route", flush=True)
        return 1
    print(
        f"live_route=ok points={len(route.points)} distance_m={route.distance_meters:.1f}",
        flush=True,
    )
    return 0


_GUI_TRIP = {
    "type": "pooled",
    "name": "Smoke Pool <A> & \"B\"",
    "start": [39.690000, -105.080000],
    "speed_mph": 20,
    "pause_seconds": 0,
    "steps": [
        {"kind": "pickup", "name": "Ana & Bo", "point": [39.698010, -105.070418]},
        {"kind": "pickup", "name": "Cé", "point": [39.698010, -105.070418]},
        {"kind": "dropoff", "name": "Ana & Bo", "point": [39.710486, -105.064513]},
    ],
}


def run_gui_self_test(live: bool = False) -> int:
    """Build the real window (icons, menus, About), load a pooled trip, and generate
    through the GUI's background job. ``live`` uses real OSRM instead of a mock."""
    import time
    import tkinter as tk
    import xml.etree.ElementTree as ET

    from naveera_gpx.data.osrm import OsrmRouter
    from naveera_gpx.presentation.gui import GpxApp

    root = tk.Tk()
    root.withdraw()
    app = GpxApp(root, dialogs=False)
    try:
        app.about.show()
        app.about.close()
        app.apply_trip_dict(_GUI_TRIP)
        app.router_factory = OsrmRouter if live else _SmokeRouter
        with tempfile.TemporaryDirectory(prefix="naveera-gui-smoke-") as folder:
            app.output.set(folder)
            app.on_generate()
            deadline = time.time() + 90
            while time.time() < deadline and app.last_result is None and app.last_error is None:
                root.update()
                time.sleep(0.02)
            if app.last_error is not None or app.last_result is None:
                print(f"gui_self_test=fail {app.last_error or 'timeout'}", flush=True)
                return 1
            directory = app.last_result.directory
            files = sorted(directory.glob("*.gpx"))
            if len(files) != 2 or not (directory / "manifest.json").is_file():
                print(f"gui_self_test=fail expected 2 GPX files, got {len(files)}", flush=True)
                return 1
            points = 0
            for path in files:
                tree = ET.parse(path)
                points += len(tree.getroot().findall("{http://www.topografix.com/GPX/1/1}wpt"))
            mode = "live" if live else "mock"
            print(f"gui_self_test=ok mode={mode} files={len(files)} points={points}", flush=True)
            return 0
    finally:
        app.request_close()
