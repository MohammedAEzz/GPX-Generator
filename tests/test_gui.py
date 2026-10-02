"""Window behavior that does not need a modal dialog."""

import threading
import time
import tkinter as tk
from pathlib import Path

import pytest

from naveera_gpx.domain.routing import Route
from naveera_gpx.presentation.gui import GpxApp
from tests.fakes import road


@pytest.fixture
def app():
    root = tk.Tk()
    root.withdraw()
    window = GpxApp(root, dialogs=False)
    yield window
    if not window._closed:
        window.request_close()


def _fill_normal(window: GpxApp) -> None:
    window.normal_name.set("Passenger A")
    window.normal_start.set("39.69, -105.08")
    window.normal_pickup.set("39.69801, -105.070418")
    window.normal_dropoff.set("39.710486, -105.064513")


def test_switching_mode_keeps_both_forms(app: GpxApp):
    _fill_normal(app)
    app.mode.set("pooled")
    app.show_mode()
    app.pool_name.set("Pool A")
    app.rows[0].name.set("Ada")
    app.rows[0].point.set("39.1, -105.1")
    app.mode.set("normal")
    app.show_mode()
    assert app.normal_name.get() == "Passenger A"
    assert app.normal_pickup.get() == "39.69801, -105.070418"
    app.mode.set("pooled")
    app.show_mode()
    assert app.pool_name.get() == "Pool A"
    assert app.rows[0].name.get() == "Ada"
    assert app.rows[0].point.get() == "39.1, -105.1"


def test_normal_form_has_no_kind_or_reorder_controls(app: GpxApp):
    classes = [child.winfo_class() for child in app.normal_frame.winfo_children()]
    assert "TCombobox" not in classes
    labels = [
        child.cget("text")
        for child in app.normal_frame.winfo_children()
        if child.winfo_class() == "TLabel"
    ]
    assert "Pickup (latitude, longitude)" in labels
    assert "Drop-off (latitude, longitude)" in labels


def test_pooled_rows_have_reorder_and_remove_buttons(app: GpxApp):
    app.add_stop("dropoff", "Bea", "39.2, -105.2")
    app.rows[0].name.set("Ada")
    texts = []
    for row in app.rows:
        texts.append(row.up.cget("text"))
        texts.append(row.down.cget("text"))
        texts.append(row.remove.cget("text"))
    assert texts.count("Up") == 2
    assert texts.count("Remove") == 2
    app._row_action("down", app.rows[0])
    assert app.rows[0].name.get() == "Bea"
    assert app.rows[1].name.get() == "Ada"
    app._row_action("remove", app.rows[0])
    assert [row.name.get() for row in app.rows] == ["Ada"]


def test_invalid_start_is_reported_without_generating(app: GpxApp):
    _fill_normal(app)
    app.normal_start.set("not-a-point")
    app.on_generate()
    assert app.last_error is not None
    assert "Driver start" in str(app.last_error)
    assert not app.job.running


def test_generation_events_are_applied_on_the_main_thread(app: GpxApp, tmp_path: Path):
    _fill_normal(app)
    app.output.set(str(tmp_path))
    idents: list[int] = []

    class Router:
        def route(self, start, end) -> Route:
            idents.append(threading.get_ident())
            return road(start, end)

    app.router_factory = lambda: Router()
    app.on_generate()
    deadline = time.time() + 5
    while time.time() < deadline and app.last_result is None and app.last_error is None:
        app.root.update()
        time.sleep(0.02)
    assert app.last_error is None
    assert app.last_result is not None
    assert idents and idents[0] != threading.get_ident()
    assert "Snapped" in app.summary.get("1.0", "end")
    app.job.join(2)
    assert app.job.uncaught is None


def test_closing_the_window_during_generation_does_not_raise(app: GpxApp, tmp_path: Path):
    _fill_normal(app)
    app.output.set(str(tmp_path))
    started = threading.Event()
    release = threading.Event()

    class Slow:
        def route(self, start, end) -> Route:
            started.set()
            assert release.wait(5)
            return road(start, end)

    app.router_factory = lambda: Slow()
    app.on_generate()
    assert started.wait(5)
    app.request_close()
    release.set()
    app.job.join(5)
    assert app.job.uncaught is None
    assert not app.job.running
    events = app.job.poll()
    assert not any(isinstance(payload, tk.TclError) for _kind, payload in events)


def test_save_and_load_json_round_trip(app: GpxApp, tmp_path: Path):
    _fill_normal(app)
    app.speed.set("18")
    app.pause.set("4")
    path = tmp_path / "trip.json"
    app.save_path(path)
    app.normal_name.set("")
    app.normal_pickup.set("")
    app.load_path(path)
    assert app.normal_name.get() == "Passenger A"
    assert app.normal_pickup.get() == "39.69801, -105.070418"
    assert app.speed.get() == "18"
    assert app.pause.get() == "4"
    assert app.mode.get() == "normal"


def _hint_for(window: GpxApp, frame, label_text: str) -> str:
    labels = [c for c in frame.winfo_children() if c.winfo_class() == "TLabel"]
    entry_label = next(c for c in labels if c.cget("text") == label_text)
    row = int(entry_label.grid_info()["row"])
    hint = next(
        c for c in labels
        if c.grid_info().get("row") == row + 1 and int(c.grid_info()["column"]) == 1
    )
    return str(hint.cget("text"))


def test_coordinate_hint_shows_parsed_value(app: GpxApp):
    app.normal_pickup.set("39.69801, -105.070418")
    assert _hint_for(app, app.normal_frame, "Pickup (latitude, longitude)") == "✓ 39.698010, -105.070418"


def test_coordinate_hint_shows_validation_error(app: GpxApp):
    app.normal_pickup.set("95, -105")
    assert "Latitude must be between -90 and 90" in _hint_for(
        app, app.normal_frame, "Pickup (latitude, longitude)"
    )


def test_merge_preview_counts_consecutive_shared_stops(app: GpxApp):
    app.rows[0].point.set("39.1, -105.1")
    app.add_stop("pickup", "Bea", "39.1, -105.1")
    app.add_stop("dropoff", "Ada", "39.2, -105.2")
    app.add_stop("dropoff", "Bea", "39.1, -105.1")
    assert app.preview.get() == "4 stop(s) → 3 physical stop(s), 1 merged as shared."


def test_merge_preview_flags_invalid_stop(app: GpxApp):
    app.rows[0].point.set("nope")
    assert "Enter valid coordinates" in app.preview.get()
    assert app.rows[0].check.cget("text") == "Invalid"


def test_new_trip_clears_only_the_active_form(app: GpxApp):
    _fill_normal(app)
    app.pool_name.set("Pool A")
    app.speed.set("30")
    app.new_trip()
    assert app.normal_name.get() == ""
    assert app.normal_pickup.get() == ""
    assert app.pool_name.get() == "Pool A"
    assert app.speed.get() == "30"


def test_about_window_opens_once_and_closes(app: GpxApp):
    app.about.show()
    first = app.about.window
    app.about.show()
    assert app.about.window is first
    texts = [c.cget("text") for c in first.winfo_children()[0].winfo_children() if c.winfo_class() == "TLabel"]
    assert "Naveera GPX" in texts
    app.about.close()
    assert app.about.window is None


def test_icon_assets_are_bundled_pngs():
    from naveera_gpx.presentation.branding import ASSETS

    for size in (64, 128, 1024):
        data = (ASSETS / f"app_icon_{size}.png").read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"


def test_packaged_gui_self_test_generates_through_the_window():
    from naveera_gpx.smoke import run_gui_self_test

    assert run_gui_self_test(live=False) == 0


def test_mouse_wheel_over_a_stop_row_scrolls_the_list(app: GpxApp):
    app.root.deiconify()
    app.mode.set("pooled")
    app.show_mode()
    for index in range(12):
        app.add_stop("pickup", f"P{index}", "39.1, -105.1")
    app.root.update()
    before = app._canvas.yview()[0]
    assert app._scroll_stops_if_inside(app.rows[1].name_entry, -3)
    assert app._canvas.yview()[0] > before


def test_mouse_wheel_outside_the_stop_list_is_ignored(app: GpxApp):
    assert not app._scroll_stops_if_inside(app.summary, -3)
