"""CLI entry point with a mocked router."""

import json
from pathlib import Path

import generator
from tests.fakes import road


def test_cli_writes_a_run_folder(tmp_path: Path, monkeypatch):
    payload = {
        "type": "normal",
        "name": "Passenger A",
        "start": [39.69, -105.08],
        "pickup": [39.69801, -105.070418],
        "dropoff": [39.710486, -105.064513],
    }
    source = tmp_path / "trip.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    def fake_route(self, start, end):
        return road(start, end)

    monkeypatch.setattr(generator.OsrmRouter, "route", fake_route)
    code = generator.main(["--input", str(source), "--output", str(tmp_path / "out")])
    assert code == 0
    written = list((tmp_path / "out").glob("*/*.gpx"))
    assert len(written) == 2


def test_cli_reports_a_routing_error(tmp_path: Path, monkeypatch, capsys):
    payload = {
        "type": "normal",
        "name": "Passenger A",
        "start": [39.69, -105.08],
        "pickup": [39.69801, -105.070418],
        "dropoff": [39.710486, -105.064513],
    }
    source = tmp_path / "trip.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    def fake_route(self, start, end):
        from naveera_gpx.domain.routing import NoRouteError

        raise NoRouteError(start, end)

    monkeypatch.setattr(generator.OsrmRouter, "route", fake_route)
    code = generator.main(["--input", str(source), "--output", str(tmp_path / "out")])
    assert code == 1
    captured = capsys.readouterr()
    assert "No driving route" in captured.err
    assert list((tmp_path / "out").rglob("*.gpx")) == []
