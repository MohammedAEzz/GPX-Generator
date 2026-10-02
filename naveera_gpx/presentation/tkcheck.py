"""Tk support checks shared by the build script and the packaged self-test."""

from __future__ import annotations

import sys
import tkinter
from dataclasses import dataclass


@dataclass(frozen=True)
class TkInfo:
    python: str
    executable: str
    patchlevel: str
    windowingsystem: str

    def text(self) -> str:
        return (
            f"python={self.python}\n"
            f"executable={self.executable}\n"
            f"tcl_patchlevel={self.patchlevel}\n"
            f"windowingsystem={self.windowingsystem}"
        )


def read_tk_info() -> TkInfo:
    root = tkinter.Tk()
    try:
        root.withdraw()
        patchlevel = str(root.tk.eval("info patchlevel"))
        windowing = str(root.tk.eval("tk windowingsystem"))
    finally:
        root.destroy()
    version = ".".join(str(part) for part in sys.version_info[:3])
    return TkInfo(version, sys.executable, patchlevel, windowing)


def assert_supported(info: TkInfo) -> None:
    parts = [int(piece) for piece in info.patchlevel.split(".")[:3]]
    while len(parts) < 3:
        parts.append(0)
    if tuple(parts) < (8, 6, 0):
        raise SystemExit(
            f"Tcl/Tk {info.patchlevel} is unsupported. Use Python with Tk 8.6 or 9.0 "
            f"(this interpreter is {info.executable})."
        )
    if info.windowingsystem != "aqua":
        raise SystemExit(
            f"Expected Tk windowing system 'aqua' on macOS, got {info.windowingsystem!r}."
        )
