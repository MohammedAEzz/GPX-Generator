"""Layer boundaries."""

from pathlib import Path


def test_domain_does_not_import_tk_or_the_network():
    root = Path(__file__).resolve().parents[1] / "naveera_gpx" / "domain"
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "tkinter" not in text
        assert "urllib" not in text
        assert "subprocess" not in text
        assert "certifi" not in text
