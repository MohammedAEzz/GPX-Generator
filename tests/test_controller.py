"""Headless generation job: events arrive on the queue, not via Tk."""

import threading
import time
from pathlib import Path

from naveera_gpx.domain.routing import Route
from naveera_gpx.domain.trip import trip_from_normal_fields
from naveera_gpx.presentation.controller import GenerationJob
from tests.fakes import DROPOFF, PICKUP, START, road


def _trip():
    return trip_from_normal_fields(
        name="Passenger A",
        start=START,
        pickup=PICKUP,
        dropoff=DROPOFF,
        speed=20,
        pause=0,
    )


def test_background_generation_completes_via_the_queue(tmp_path: Path):
    job = GenerationJob()
    seen: list[int] = []

    class Router:
        def route(self, start, end) -> Route:
            seen.append(threading.get_ident())
            return road(start, end)

    job.start(_trip(), tmp_path, Router())
    deadline = time.time() + 5
    events: list[tuple[str, object]] = []
    while time.time() < deadline:
        events.extend(job.poll())
        if any(kind == "done" for kind, _payload in events):
            break
        time.sleep(0.01)
    job.join(2)
    assert job.uncaught is None
    assert seen and seen[0] != threading.get_ident()
    kinds = [kind for kind, _payload in events]
    assert "progress" in kinds
    assert kinds[-1] == "done"
    result = events[-1][1]
    assert result.directory.is_dir()  # type: ignore[attr-defined]


def test_closing_during_generation_does_not_raise(tmp_path: Path):
    """The worker only queues events, so abandoning the job cannot raise TclError."""
    job = GenerationJob()
    started = threading.Event()
    release = threading.Event()

    class Slow:
        def route(self, start, end) -> Route:
            started.set()
            assert release.wait(5)
            return road(start, end)

    job.start(_trip(), tmp_path, Slow())
    assert started.wait(5)
    # Stand-in for the window going away: nobody drains Tk, and the worker is released.
    release.set()
    job.join(5)
    assert job.uncaught is None
    assert not job.running
    kinds = [kind for kind, _payload in job.poll()]
    assert "done" in kinds
    assert "error" not in kinds
