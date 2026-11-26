"""Phase V6 tests: Studio static frontend offline guarantee & 100% SVG icon compliance."""

from __future__ import annotations

from pathlib import Path
import re

STATIC_DIR = Path(__file__).resolve().parent.parent / "pixelai" / "studio" / "static"


def test_studio_static_files_are_100_percent_offline() -> None:
    assert (STATIC_DIR / "index.html").is_file()
    assert (STATIC_DIR / "styles.css").is_file()
    assert (STATIC_DIR / "icons.js").is_file()
    assert (STATIC_DIR / "app.js").is_file()

    for path in STATIC_DIR.iterdir():
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            assert "http://" not in content and "https://" not in content, (
                f"External URL found in {path.name}; Studio must be 100% offline."
            )


def test_studio_uses_svg_icons_only() -> None:
    # Per AGENTS.md: all GUI icons must be SVG, zero raster PNG/JPG icon assets
    for path in STATIC_DIR.iterdir():
        assert path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".ico"}
    icons_js = (STATIC_DIR / "icons.js").read_text(encoding="utf-8")
    svg_matches = re.findall(r"<svg\b", icons_js)
    assert len(svg_matches) >= 6
