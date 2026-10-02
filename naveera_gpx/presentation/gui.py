"""macOS desktop window. Widgets and event wiring only; trip rules live in domain."""

from __future__ import annotations

import json
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from collections.abc import Callable

from naveera_gpx.data.osrm import OsrmRouter
from naveera_gpx.domain.coordinates import parse_point
from naveera_gpx.domain.routing import Router
from naveera_gpx.domain.trip import Step, Trip, merge_consecutive, trip_from_dict, trip_to_dict
from naveera_gpx.domain.trip import trip_from_normal_fields, trip_from_pooled_fields
from naveera_gpx.presentation.branding import (
    APP_NAME,
    AboutWindow,
    apply_window_icon,
    build_menubar,
    configure_styles,
    load_icon,
)
from naveera_gpx.presentation.controller import GenerationJob

_COORD_HINT = "Latitude, longitude — for example 39.690000, -105.080000"


class StopRow:
    """One pooled stop editor: number, kind, passenger, coordinates, reorder, remove.

    Widgets are gridded into the shared stops table so columns line up.
    """

    def __init__(self, parent: ttk.Frame, on_action: Callable[[str, StopRow], None]) -> None:
        self.parent = parent
        self.kind = tk.StringVar(value="pickup")
        self.name = tk.StringVar()
        self.point = tk.StringVar()
        self.number = ttk.Label(parent, width=3, anchor="e", style="Secondary.TLabel")
        self.kind_box = ttk.Combobox(
            parent,
            textvariable=self.kind,
            values=("pickup", "dropoff"),
            state="readonly",
            width=9,
        )
        self.name_entry = ttk.Entry(parent, textvariable=self.name, width=20)
        self.point_entry = ttk.Entry(parent, textvariable=self.point, width=26)
        self.check = ttk.Label(parent, width=8, style="Valid.TLabel")
        self.up = ttk.Button(parent, text="Up", width=4, command=lambda: on_action("up", self))
        self.down = ttk.Button(
            parent, text="Down", width=5, command=lambda: on_action("down", self)
        )
        self.remove = ttk.Button(
            parent, text="Remove", width=7, command=lambda: on_action("remove", self)
        )
        self.widgets = (
            self.number,
            self.kind_box,
            self.name_entry,
            self.point_entry,
            self.check,
            self.up,
            self.down,
            self.remove,
        )

    def place(self, grid_row: int, number: int) -> None:
        self.number.configure(text=f"{number}.")
        pads = (0, 6)
        self.number.grid(row=grid_row, column=0, padx=pads, pady=3, sticky="e")
        self.kind_box.grid(row=grid_row, column=1, padx=pads, pady=3, sticky="w")
        self.name_entry.grid(row=grid_row, column=2, padx=pads, pady=3, sticky="ew")
        self.point_entry.grid(row=grid_row, column=3, padx=pads, pady=3, sticky="ew")
        self.check.grid(row=grid_row, column=4, padx=pads, pady=3, sticky="w")
        self.up.grid(row=grid_row, column=5, padx=2, pady=3)
        self.down.grid(row=grid_row, column=6, padx=2, pady=3)
        self.remove.grid(row=grid_row, column=7, padx=(2, 0), pady=3)

    def forget(self) -> None:
        for widget in self.widgets:
            widget.grid_forget()

    def destroy(self) -> None:
        for widget in self.widgets:
            widget.destroy()


class GpxApp:
    def __init__(self, root: tk.Tk, *, dialogs: bool = True) -> None:
        self.root = root
        self.dialogs = dialogs
        self.job = GenerationJob()
        self._closed = False
        self._after_id: str | None = None
        self.last_result = None
        self.last_error: BaseException | None = None
        self.last_output_dir: Path | None = None
        self.router_factory: Callable[[], Router] = OsrmRouter

        root.title(APP_NAME)
        root.minsize(860, 680)
        root.geometry("940x800")
        root.protocol("WM_DELETE_WINDOW", self.request_close)
        configure_styles(root)
        self._icons = apply_window_icon(root)
        self._header_icon = load_icon(root, 64)
        self.about = AboutWindow(root)
        build_menubar(
            root,
            about=self.about.show,
            new_trip=self.new_trip,
            open_trip=self.load_dialog,
            save_trip=self.save_dialog,
            generate=self.on_generate,
            open_output=self.open_output,
            quit_app=self.request_close,
        )

        self.mode = tk.StringVar(value="normal")
        self.normal_name = tk.StringVar()
        self.normal_start = tk.StringVar()
        self.normal_pickup = tk.StringVar()
        self.normal_dropoff = tk.StringVar()
        self.pool_name = tk.StringVar()
        self.pool_start = tk.StringVar()
        self.speed = tk.StringVar(value="20")
        self.pause = tk.StringVar(value="0")
        self.output = tk.StringVar(value=str(Path.home() / "Documents" / "NaveeraGPX"))
        self.status = tk.StringVar(value="Ready. Real-road routing needs an internet connection.")
        self.preview = tk.StringVar()
        self.rows: list[StopRow] = []

        outer = ttk.Frame(root, padding=(20, 16, 20, 16))
        outer.pack(fill="both", expand=True)
        self._build_header(outer)

        self.normal_frame = ttk.LabelFrame(outer, text="Normal trip", padding=(14, 10))
        self._add_field(self.normal_frame, 0, "Passenger / trip name", self.normal_name)
        self._add_coordinate_field(
            self.normal_frame, 1, "Driver start (latitude, longitude)", self.normal_start
        )
        self._add_coordinate_field(
            self.normal_frame, 3, "Pickup (latitude, longitude)", self.normal_pickup
        )
        self._add_coordinate_field(
            self.normal_frame, 5, "Drop-off (latitude, longitude)", self.normal_dropoff
        )
        ttk.Label(
            self.normal_frame,
            text="Creates two GPX files: start → pickup, then pickup → drop-off.",
            style="Secondary.TLabel",
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.normal_frame.columnconfigure(1, weight=1)

        self.pooled_frame = ttk.LabelFrame(outer, text="Pooled trip", padding=(14, 10))
        self._build_pooled(self.pooled_frame)

        self.settings = ttk.LabelFrame(outer, text="Settings", padding=(14, 10))
        self._build_settings(self.settings)
        self.settings.pack(fill="x", pady=(14, 0))

        self._build_footer(outer)

        self.add_stop()
        self.show_mode()
        root.bind("<Escape>", lambda _event: root.focus_set())

    # ----- layout -----

    def _build_header(self, outer: ttk.Frame) -> None:
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, image=self._header_icon).pack(side="left", padx=(0, 14))
        titles = ttk.Frame(header)
        titles.pack(side="left", fill="x", expand=True)
        ttk.Label(titles, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            titles,
            text=(
                "Real-road GPX files for simulator trips. Stops are driven in the order "
                "you enter; nothing is optimized."
            ),
            style="Secondary.TLabel",
            wraplength=560,
        ).pack(anchor="w", pady=(2, 0))
        modes = ttk.Frame(header)
        modes.pack(side="right", anchor="center")
        ttk.Label(modes, text="Trip type", style="Section.TLabel").pack(anchor="w")
        choice = ttk.Frame(modes)
        choice.pack(anchor="w", pady=(4, 0))
        ttk.Radiobutton(
            choice, text="Normal", value="normal", variable=self.mode, command=self.show_mode
        ).pack(side="left")
        ttk.Radiobutton(
            choice, text="Pooled", value="pooled", variable=self.mode, command=self.show_mode
        ).pack(side="left", padx=(12, 0))
        ttk.Separator(outer).pack(fill="x", pady=(14, 0))

    def _build_pooled(self, frame: ttk.LabelFrame) -> None:
        self._add_field(frame, 0, "Pool name", self.pool_name)
        self._add_coordinate_field(frame, 1, "Driver start (latitude, longitude)", self.pool_start)
        ttk.Label(
            frame,
            text=(
                "Stops in driving order. Back-to-back stops with identical coordinates become "
                "one physical stop and one incoming GPX; every passenger is kept. A later "
                "return to the same place is a new stop."
            ),
            style="Secondary.TLabel",
            wraplength=820,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 6))

        holder = ttk.Frame(frame)
        holder.grid(row=4, column=0, columnspan=2, sticky="nsew")
        frame.rowconfigure(4, weight=1)
        frame.columnconfigure(1, weight=1)
        self._canvas = tk.Canvas(holder, highlightthickness=0, height=124, borderwidth=0)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self.stops_frame = ttk.Frame(self._canvas)
        self._window = self._canvas.create_window((0, 0), window=self.stops_frame, anchor="nw")
        self.stops_frame.bind(
            "<Configure>",
            lambda _event: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<Configure>",
            lambda event: self._canvas.itemconfigure(self._window, width=event.width),
        )
        self._canvas.bind_all("<MouseWheel>", self._wheel, add="+")
        for column, text in ((1, "Action"), (2, "Passenger"), (3, "Latitude, longitude")):
            ttk.Label(self.stops_frame, text=text, style="Secondary.TLabel").grid(
                row=0, column=column, sticky="w", padx=(0, 6)
            )
        self.stops_frame.columnconfigure(2, weight=1)
        self.stops_frame.columnconfigure(3, weight=2)

        footer = ttk.Frame(frame)
        footer.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(footer, text="Add Stop", command=self.add_stop).pack(side="left")
        ttk.Label(footer, textvariable=self.preview, style="Secondary.TLabel").pack(
            side="left", padx=(12, 0)
        )

    def _build_settings(self, settings: ttk.LabelFrame) -> None:
        self._add_field(settings, 0, "Speed (mph)", self.speed, width=10, stretch=False)
        self._add_field(settings, 1, "Pause at each stop (seconds)", self.pause, width=10, stretch=False)
        ttk.Label(settings, text="Output folder").grid(row=2, column=0, sticky="w", pady=4, padx=(0, 10))
        out = ttk.Frame(settings)
        out.grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Entry(out, textvariable=self.output).pack(side="left", fill="x", expand=True)
        ttk.Button(out, text="Choose…", command=self.choose_output).pack(side="left", padx=(8, 0))
        ttk.Label(
            settings,
            text="Each run is saved to a new dated folder inside this folder; nothing is overwritten.",
            style="Secondary.TLabel",
        ).grid(row=3, column=1, sticky="w")
        settings.columnconfigure(1, weight=1)

    def _build_footer(self, outer: ttk.Frame) -> None:
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(14, 0))
        self.progress = ttk.Progressbar(actions, mode="indeterminate", length=160)
        self.progress.pack(side="left")
        self.progress.pack_forget()
        self._progress_anchor = ttk.Label(actions, textvariable=self.status, wraplength=480)
        self._progress_anchor.pack(side="left", fill="x", expand=True)
        self.run_button = ttk.Button(
            actions, text="Generate GPX", default="active", command=self.on_generate
        )
        self.run_button.pack(side="right")
        ttk.Button(actions, text="Open Output Folder", command=self.open_output).pack(
            side="right", padx=(0, 8)
        )

        results = ttk.Frame(outer)
        results.pack(fill="both", expand=True, pady=(12, 0))
        self.summary = tk.Text(
            results,
            height=5,
            wrap="word",
            state="disabled",
            font="TkDefaultFont",
            borderwidth=0,
            highlightthickness=1,
            padx=10,
            pady=8,
        )
        scroll = ttk.Scrollbar(results, orient="vertical", command=self.summary.yview)
        self.summary.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.summary.pack(side="left", fill="both", expand=True)

    # ----- mode and stops -----

    def show_mode(self) -> None:
        """Show the selected form. The other form's fields stay intact."""
        self.normal_frame.pack_forget()
        self.pooled_frame.pack_forget()
        target = self.normal_frame if self.mode.get() == "normal" else self.pooled_frame
        target.pack(fill="both", expand=True, pady=(14, 0), before=self.settings)

    def add_stop(
        self,
        kind: str = "pickup",
        name: str = "",
        coordinate: str = "",
    ) -> StopRow:
        row = StopRow(self.stops_frame, self._row_action)
        row.kind.set(kind)
        row.name.set(name)
        row.point.set(coordinate)
        row.point.trace_add("write", lambda *_args: self._refresh_stops())
        row.kind.trace_add("write", lambda *_args: self._refresh_stops())
        row.name.trace_add("write", lambda *_args: self._refresh_stops())
        self.rows.append(row)
        self._repack_rows()
        return row

    def _row_action(self, action: str, row: StopRow) -> None:
        index = self.rows.index(row)
        if action == "remove":
            row.destroy()
            self.rows.remove(row)
            self._repack_rows()
            return
        delta = -1 if action == "up" else 1
        target = index + delta
        if 0 <= target < len(self.rows):
            self.rows[index], self.rows[target] = self.rows[target], self.rows[index]
            self._repack_rows()

    def _repack_rows(self) -> None:
        for row in self.rows:
            row.forget()
        for index, row in enumerate(self.rows):
            row.place(index + 1, index + 1)
            row.up.configure(state="normal" if index else "disabled")
            row.down.configure(state="normal" if index < len(self.rows) - 1 else "disabled")
        self._refresh_stops()

    def _refresh_stops(self) -> None:
        """Per-row coordinate check and a merge preview using the domain rules."""
        parsed = []
        problems = 0
        for row in self.rows:
            text = row.point.get().strip()
            if not text:
                row.check.configure(text="", style="Valid.TLabel")
                problems += 1
                continue
            try:
                point = parse_point(text)
            except ValueError:
                row.check.configure(text="Invalid", style="Error.TLabel")
                problems += 1
                continue
            row.check.configure(text="✓", style="Valid.TLabel")
            parsed.append(point)
        count = len(self.rows)
        if count == 0:
            self.preview.set("Add at least one stop.")
        elif problems:
            self.preview.set(f"{count} stop(s). Enter valid coordinates for every stop.")
        else:
            physical = len(_merge_preview(self.rows, parsed))
            merged = count - physical
            note = f", {merged} merged as shared" if merged else ""
            self.preview.set(f"{count} stop(s) → {physical} physical stop(s){note}.")

    def _wheel(self, event: tk.Event) -> None:
        """Scroll the stops list when the pointer is over it (including its rows)."""
        try:
            under = self.root.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return
        self._scroll_stops_if_inside(under, int(event.delta))

    def _scroll_stops_if_inside(self, widget: tk.Misc | None, delta: int) -> bool:
        if widget is None or not str(widget).startswith(str(self._canvas)):
            return False
        self._canvas.yview_scroll(-1 * delta, "units")
        return True

    # ----- actions -----

    def new_trip(self) -> None:
        """Clear the form for the selected trip type. Settings are kept."""
        if self.mode.get() == "normal":
            for variable in (
                self.normal_name,
                self.normal_start,
                self.normal_pickup,
                self.normal_dropoff,
            ):
                variable.set("")
        else:
            self.pool_name.set("")
            self.pool_start.set("")
            for row in list(self.rows):
                row.destroy()
            self.rows.clear()
            self.add_stop()
        self._set_summary("")
        self.status.set("New trip.")

    def choose_output(self) -> None:
        selected = filedialog.askdirectory(parent=self.root)
        if selected:
            self.output.set(selected)

    def on_generate(self) -> None:
        if self.job.running:
            return
        try:
            trip = self.read_trip()
        except ValueError as exc:
            self._report_input(exc)
            return
        folder = self.output.get().strip()
        if not folder:
            self._report_input(ValueError("Choose an output folder."))
            return
        self.last_result = None
        self.last_error = None
        self._set_busy(True)
        self._set_summary("")
        self.status.set("Generating road routes…")
        self.job.start(trip, Path(folder), self.router_factory())
        self._schedule()

    def read_trip(self) -> Trip:
        if self.mode.get() == "normal":
            return trip_from_normal_fields(
                name=self.normal_name.get(),
                start=self.normal_start.get(),
                pickup=self.normal_pickup.get(),
                dropoff=self.normal_dropoff.get(),
                speed=self.speed.get(),
                pause=self.pause.get(),
            )
        steps = [
            {"kind": row.kind.get(), "name": row.name.get(), "point": row.point.get()}
            for row in self.rows
        ]
        return trip_from_pooled_fields(
            name=self.pool_name.get(),
            start=self.pool_start.get(),
            steps=steps,
            speed=self.speed.get(),
            pause=self.pause.get(),
        )

    def current_trip_dict(self) -> dict:
        return trip_to_dict(self.read_trip())

    def apply_trip_dict(self, data: dict) -> None:
        trip = trip_from_dict(data)
        self._fill_trip(trip)

    def save_path(self, path: Path) -> None:
        payload = self.current_trip_dict()
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def load_path(self, path: Path) -> None:
        self.apply_trip_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_dialog(self) -> None:
        try:
            payload = self.current_trip_dict()
        except ValueError as exc:
            self._report_input(exc)
            return
        selected = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not selected:
            return
        try:
            Path(selected).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            self._report_input(exc)
            return
        self.status.set(f"Saved trip to {selected}")

    def load_dialog(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root, filetypes=[("JSON", "*.json")]
        )
        if not selected:
            return
        try:
            self.load_path(Path(selected))
        except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            self._report_input(exc)
            return
        self.status.set(f"Loaded trip from {selected}")

    def open_output(self) -> None:
        target = self.last_output_dir or Path(self.output.get().strip())
        if not str(target) or not target.exists():
            self._report_input(
                ValueError("No output folder yet. Choose a folder or generate a trip first.")
            )
            return
        try:
            subprocess.run(["open", str(target)], check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            self._report_input(exc)

    def request_close(self) -> None:
        """Stop polling and destroy the window. The worker must not touch Tk after this."""
        if self._closed:
            return
        if self.job.running and self.dialogs:
            leave = messagebox.askyesno(
                "Generation in progress",
                "GPX files are still being generated. Quit anyway? "
                "The unfinished run will not be saved.",
                icon="warning",
                parent=self.root,
            )
            if not leave:
                return
        self._closed = True
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        self.about.close()
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except tk.TclError:
            pass

    # ----- state -----

    def _fill_trip(self, trip: Trip) -> None:
        self.speed.set(_format_number(trip.speed_mph))
        self.pause.set(_format_number(trip.pause_seconds))
        self.mode.set(trip.type)
        if trip.type == "normal":
            self.normal_name.set(trip.name)
            self.normal_start.set(_fmt_point(trip.start))
            self.normal_pickup.set(_fmt_point(trip.steps[0].point))
            self.normal_dropoff.set(_fmt_point(trip.steps[1].point))
        else:
            self.pool_name.set(trip.name)
            self.pool_start.set(_fmt_point(trip.start))
            for row in list(self.rows):
                row.destroy()
            self.rows.clear()
            for step in trip.steps:
                self.add_stop(step.kind, step.name, _fmt_point(step.point))
        self.show_mode()

    def _schedule(self) -> None:
        if self._closed:
            return
        self._after_id = self.root.after(50, self._poll)

    def _poll(self) -> None:
        self._after_id = None
        if self._closed:
            return
        try:
            exists = bool(self.root.winfo_exists())
        except tk.TclError:
            return
        if not exists:
            return
        self._drain()
        if self._closed:
            return
        if self.job.running:
            self._schedule()
            return
        self._drain()

    def _drain(self) -> None:
        for kind, payload in self.job.poll():
            if kind == "progress":
                self.status.set(str(payload))
            elif kind == "done":
                self._set_busy(False)
                self.last_result = payload
                self.last_output_dir = payload.directory  # type: ignore[attr-defined]
                text = payload.summary()  # type: ignore[attr-defined]
                self.status.set(text.split("\n", 1)[0])
                self._set_summary(text)
                if self.dialogs and not self._closed:
                    messagebox.showinfo("GPX ready", text, parent=self.root)
            elif kind == "error":
                self._set_busy(False)
                assert isinstance(payload, BaseException)
                self.last_error = payload
                text = _error_text(payload)
                self.status.set("Generation failed. See details below.")
                self._set_summary(text)
                if self.dialogs and not self._closed:
                    messagebox.showerror("Generation failed", text, parent=self.root)

    def _report_input(self, exc: BaseException) -> None:
        self.last_error = exc
        self.status.set(str(exc))
        if self.dialogs and not self._closed:
            messagebox.showerror("Check the trip details", str(exc), parent=self.root)

    def _set_busy(self, busy: bool) -> None:
        self.run_button.configure(state="disabled" if busy else "normal")
        if busy:
            self.progress.pack(side="left", padx=(0, 10), before=self._progress_anchor)
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()

    def _set_summary(self, text: str) -> None:
        self.summary.configure(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", text)
        self.summary.configure(state="disabled")

    @staticmethod
    def _add_field(
        frame: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
        *,
        width: int | None = None,
        stretch: bool = True,
    ) -> ttk.Entry:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
        entry = ttk.Entry(frame, textvariable=variable)
        if width is not None:
            entry.configure(width=width)
        entry.grid(row=row, column=1, sticky="ew" if stretch else "w", pady=4)
        return entry

    def _add_coordinate_field(
        self, frame: ttk.LabelFrame, row: int, label: str, variable: tk.StringVar
    ) -> None:
        """Entry plus a live hint underneath: format help, ✓ parsed value, or the error."""
        self._add_field(frame, row, label, variable)
        hint = ttk.Label(frame, text=_COORD_HINT, style="Valid.TLabel")
        hint.grid(row=row + 1, column=1, sticky="w", pady=(0, 2))

        def update(*_args: object) -> None:
            text = variable.get().strip()
            if not text:
                hint.configure(text=_COORD_HINT, style="Valid.TLabel")
                return
            try:
                point = parse_point(text)
            except ValueError as exc:
                hint.configure(text=str(exc), style="Error.TLabel")
                return
            hint.configure(text=f"✓ {point[0]:.6f}, {point[1]:.6f}", style="Valid.TLabel")

        variable.trace_add("write", update)


def _merge_preview(rows: list[StopRow], points: list[tuple[float, float]]):
    steps = [
        Step(row.kind.get(), row.name.get().strip() or "?", point)
        for row, point in zip(rows, points)
    ]
    return merge_consecutive(steps)


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _fmt_point(point: tuple[float, float]) -> str:
    return f"{point[0]}, {point[1]}"


def _error_text(exc: BaseException) -> str:
    failed = getattr(exc, "failed_directory", None)
    message = str(exc)
    if failed:
        return (
            f"{message}\n\nA partial run was saved to {failed} and marked as failed. "
            "Generate again to write a new folder. The failed run is left in place."
        )
    return message


def run_app() -> int:
    root = tk.Tk()
    GpxApp(root)
    root.mainloop()
    return 0
