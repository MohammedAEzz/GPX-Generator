"""App icon, menu bar, and About window. Presentation only."""

from __future__ import annotations

import platform
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from collections.abc import Callable

from naveera_gpx import __version__

APP_NAME = "Naveera GPX"
ASSETS = Path(__file__).resolve().parent / "assets"


def load_icon(root: tk.Misc, size: int) -> tk.PhotoImage:
    """Load a bundled icon PNG. ``size`` is 64, 128, or 1024."""
    return tk.PhotoImage(master=root, file=str(ASSETS / f"app_icon_{size}.png"))


def apply_window_icon(root: tk.Tk) -> list[tk.PhotoImage]:
    """Set the Dock / window icon. Keep the returned images alive."""
    images = [load_icon(root, 1024), load_icon(root, 128)]
    root.iconphoto(True, *images)
    return images


class AboutWindow:
    """A small, single-instance About window with the app icon and versions."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.window: tk.Toplevel | None = None
        self._icon: tk.PhotoImage | None = None

    def show(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return
        window = tk.Toplevel(self.root)
        self.window = window
        window.title(f"About {APP_NAME}")
        window.resizable(False, False)
        window.transient(self.root)
        body = ttk.Frame(window, padding=(36, 28, 36, 24))
        body.pack(fill="both", expand=True)
        self._icon = load_icon(window, 128)
        ttk.Label(body, image=self._icon).pack()
        ttk.Label(body, text=APP_NAME, font="systemAlertHeaderFont").pack(pady=(12, 2))
        ttk.Label(body, text=f"Version {__version__}", style="Secondary.TLabel").pack()
        ttk.Label(
            body,
            text="Real-road GPX routes for simulator trip testing.",
            wraplength=300,
            justify="center",
        ).pack(pady=(14, 4))
        tk_version = str(self.root.tk.eval("info patchlevel"))
        ttk.Label(
            body,
            text=f"Python {platform.python_version()} · Tcl/Tk {tk_version}",
            style="Secondary.TLabel",
        ).pack()
        ttk.Label(
            body,
            text="Routing: OSRM · Map data © OpenStreetMap contributors",
            style="Secondary.TLabel",
        ).pack(pady=(2, 16))
        ttk.Button(body, text="OK", default="active", command=self.close).pack()
        window.bind("<Return>", lambda _event: self.close())
        window.bind("<Escape>", lambda _event: self.close())
        window.protocol("WM_DELETE_WINDOW", self.close)

    def close(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()
        self.window = None


def build_menubar(
    root: tk.Tk,
    *,
    about: Callable[[], None],
    new_trip: Callable[[], None],
    open_trip: Callable[[], None],
    save_trip: Callable[[], None],
    generate: Callable[[], None],
    open_output: Callable[[], None],
    quit_app: Callable[[], None],
) -> tk.Menu:
    """macOS menu bar: app menu (About), File, Edit, Window. Shortcuts use Command."""
    menubar = tk.Menu(root)
    app_menu = tk.Menu(menubar, name="apple", tearoff=False)
    app_menu.add_command(label=f"About {APP_NAME}", command=about)
    app_menu.add_separator()
    menubar.add_cascade(menu=app_menu)

    file_menu = tk.Menu(menubar, tearoff=False)
    file_menu.add_command(label="New Trip", accelerator="Command-N", command=new_trip)
    file_menu.add_command(label="Open Trip…", accelerator="Command-O", command=open_trip)
    file_menu.add_command(label="Save Trip…", accelerator="Command-S", command=save_trip)
    file_menu.add_separator()
    file_menu.add_command(label="Generate GPX", accelerator="Command-Return", command=generate)
    file_menu.add_command(
        label="Open Output Folder", accelerator="Command-Shift-O", command=open_output
    )
    menubar.add_cascade(label="File", menu=file_menu)

    edit_menu = tk.Menu(menubar, tearoff=False)
    for label, event, key in (
        ("Cut", "<<Cut>>", "Command-X"),
        ("Copy", "<<Copy>>", "Command-C"),
        ("Paste", "<<Paste>>", "Command-V"),
        ("Select All", "<<SelectAll>>", "Command-A"),
    ):
        edit_menu.add_command(
            label=label,
            accelerator=key,
            command=lambda e=event: _send_to_focus(root, e),
        )
    menubar.add_cascade(label="Edit", menu=edit_menu)

    window_menu = tk.Menu(menubar, name="window", tearoff=False)
    menubar.add_cascade(label="Window", menu=window_menu)

    root.configure(menu=menubar)
    # Standard macOS hooks: About in the app menu and Command-Q / Quit.
    root.createcommand("tkAboutDialog", about)
    root.createcommand("::tk::mac::Quit", quit_app)

    root.bind_all("<Command-n>", lambda _event: new_trip())
    root.bind_all("<Command-o>", lambda _event: open_trip())
    root.bind_all("<Command-s>", lambda _event: save_trip())
    root.bind_all("<Command-Return>", lambda _event: generate())
    root.bind_all("<Command-O>", lambda _event: open_output())
    return menubar


def _send_to_focus(root: tk.Tk, event: str) -> None:
    widget = root.focus_get()
    if widget is not None:
        widget.event_generate(event)


def configure_styles(root: tk.Tk) -> ttk.Style:
    """Native aqua theme plus a few semantic text styles that follow Dark Mode."""
    style = ttk.Style(root)
    if "aqua" in style.theme_names():
        style.theme_use("aqua")
    secondary = _color(root, "systemSecondaryLabelColor", "#6e6e73")
    error = _color(root, "systemSystemRedColor", "#d70015")
    style.configure("Title.TLabel", font="systemAlertHeaderFont")
    style.configure("Secondary.TLabel", foreground=secondary, font="systemSmallSystemFont")
    style.configure("Valid.TLabel", foreground=secondary, font="systemSmallSystemFont")
    style.configure("Error.TLabel", foreground=error, font="systemSmallSystemFont")
    style.configure("Section.TLabel", font="systemEmphasizedSystemFont")
    return style


def _color(root: tk.Misc, name: str, fallback: str) -> str:
    try:
        root.winfo_rgb(name)
    except tk.TclError:
        return fallback
    return name
