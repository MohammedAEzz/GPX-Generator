"""Background generation. The worker never calls Tk."""

from __future__ import annotations

import queue
import threading
from pathlib import Path

from naveera_gpx.domain.generate import RunResult, generate_run
from naveera_gpx.domain.routing import Router
from naveera_gpx.domain.trip import Trip


class GenerationJob:
    """Runs ``generate_run`` on a daemon thread and publishes events on a queue.

    Events are ``(\"progress\", str)``, ``(\"done\", RunResult)``, or ``(\"error\", Exception)``.
    The GUI drains the queue on the main thread.
    """

    def __init__(self) -> None:
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self.uncaught: BaseException | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, trip: Trip, output_dir: Path, router: Router) -> None:
        if self.running:
            raise RuntimeError("Generation is already running.")
        self.uncaught = None

        def worker() -> None:
            try:
                result = generate_run(
                    trip,
                    output_dir,
                    router,
                    on_progress=lambda message: self.events.put(("progress", message)),
                )
                self.events.put(("done", result))
            except Exception as exc:
                self.events.put(("error", exc))
            except BaseException as exc:  # pragma: no cover - crash path
                self.uncaught = exc
                raise

        self._thread = threading.Thread(target=worker, name="gpx-generate", daemon=True)
        self._thread.start()

    def poll(self) -> list[tuple[str, object]]:
        items: list[tuple[str, object]] = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except queue.Empty:
                return items

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)
