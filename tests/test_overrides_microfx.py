"""Phase V4 tests: Non-destructive 2D pixel_overrides and bounce/glint micro-FX."""

from __future__ import annotations

from pixelai.canvas import Canvas
from pixelai.color import TRANSPARENT
from pixelai.overrides import apply_bounce, apply_glint, apply_pixel_overrides


def test_pixel_overrides_set_and_erase_non_destructive() -> None:
    base = Canvas(8, 8)
    base.set_pixel(2, 2, (100, 120, 140, 255))
    base.set_pixel(3, 2, (100, 120, 140, 255))

    overrides = {
        "frame_0": {
            "set": [[4, 4, "#ff004d"]],
            "erase": [[2, 2]],
        }
    }
    patched = apply_pixel_overrides(base, overrides, frame_idx=0)
    # Original canvas untouched
    assert base.get_pixel(2, 2) == (100, 120, 140, 255)
    assert base.get_pixel(4, 4) == TRANSPARENT
    # Patched canvas has exact edits
    assert patched.get_pixel(2, 2) == TRANSPARENT
    assert patched.get_pixel(4, 4) == (255, 0, 77, 255)
    assert patched.get_pixel(3, 2) == (100, 120, 140, 255)


def test_bounce_and_glint_micro_fx() -> None:
    base = Canvas(16, 16)
    for y in range(6, 12):
        for x in range(5, 11):
            base.set_pixel(x, y, (80, 140, 200, 255))

    # Bounce mid-cycle shifts pixels up by amplitude_px
    bounced = apply_bounce(base, frame_idx=2, total_frames=4, amplitude_px=2)
    assert bounced.get_pixel(6, 4) == (80, 140, 200, 255)
    assert bounced.get_pixel(6, 11) == TRANSPARENT

    # Glint highlights opaque pixels without leaking into transparent background
    shine = (255, 250, 224, 255)
    glinted = apply_glint(base, frame_idx=2, total_frames=6, color=shine, width_px=2, slope=0.0)
    assert glinted.get_pixel(0, 0) == TRANSPARENT
    assert any(px == shine for px in glinted.pixels)
