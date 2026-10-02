#!/usr/bin/env python3
"""Desktop entry point. ``python app.py`` opens the window.

``--self-test`` checks the bundled Tcl/Tk and writes a mocked GPX run.
``--live-route`` requests one real OSRM route (proves TLS from a frozen app).
``--gui-self-test [--live]`` builds the window and generates a pooled trip through it.
"""

from __future__ import annotations

import argparse
import sys
import tkinter as _tkinter

# Touch TkVersion so the import is a real use. PyInstaller collects Tcl/Tk from it.
_TK_MAJOR = _tkinter.TkVersion


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Naveera GPX Generator")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Check bundled Tk and generate a GPX with a mock router.",
    )
    parser.add_argument(
        "--live-route",
        action="store_true",
        help="Request one real OSRM route and print the result.",
    )
    parser.add_argument(
        "--gui-self-test",
        action="store_true",
        help="Build the window and generate a pooled trip through it (mock router).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="With --gui-self-test, route through real OSRM.",
    )
    args = parser.parse_args(argv)
    if args.gui_self_test:
        from naveera_gpx.smoke import run_gui_self_test

        return run_gui_self_test(live=args.live)
    if args.self_test:
        from naveera_gpx.smoke import run_self_test

        return run_self_test()
    if args.live_route:
        from naveera_gpx.smoke import run_live_route

        return run_live_route()
    from naveera_gpx.presentation.gui import run_app

    return run_app()


if __name__ == "__main__":
    sys.exit(main())
