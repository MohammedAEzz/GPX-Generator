#!/usr/bin/env python3
"""Print the interpreter's Tcl/Tk and exit if it is not a supported Aqua Tk."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from naveera_gpx.presentation.tkcheck import assert_supported, read_tk_info


def main() -> int:
    info = read_tk_info()
    print(info.text())
    assert_supported(info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
