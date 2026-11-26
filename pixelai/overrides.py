"""Non-destructive 2D per-frame pixel_overrides and quick micro-FX (bounce, glint).

Allows humans to patch individual pixels on specific frames or add instant
micro-animations (bounce, vertical shine sweep) without consuming AI tokens
and without losing deterministic CLI reproducibility.
"""

from __future__ import annotations

import math
from typing import Any

from pixelai.canvas import Canvas
from pixelai.color import RGBA, TRANSPARENT, parse_color


def apply_pixel_overrides(
    canvas: Canvas,
    overrides: dict[str, Any] | None,
    frame_idx: int = 0,
    palette: dict[str, RGBA] | None = None,
) -> Canvas:
    """Apply non-destructive per-frame `set` and `erase` pixel patches onto a copy of canvas."""
    if not overrides:
        return canvas
    frame_key = f"frame_{frame_idx}"
    patch = overrides.get(frame_key)
    if not isinstance(patch, dict):
        return canvas

    out = canvas.copy()
    for entry in patch.get("erase", []):
        x, y = int(entry[0]), int(entry[1])
        if out.in_bounds(x, y):
            out.set_pixel(x, y, TRANSPARENT)
    for entry in patch.get("set", []):
        x, y, raw_color = int(entry[0]), int(entry[1]), entry[2]
        if out.in_bounds(x, y):
            out.set_pixel(x, y, parse_color(raw_color, palette))
    return out


def apply_bounce(
    canvas: Canvas,
    frame_idx: int,
    total_frames: int,
    *,
    amplitude_px: int = 2,
) -> Canvas:
    """Shift opaque sprite pixels vertically along a deterministic integer hop curve."""
    if amplitude_px == 0 or total_frames <= 1:
        return canvas.copy()
    phase = (frame_idx % total_frames) / total_frames
    dy = -round(abs(math.sin(phase * math.pi)) * amplitude_px)
    if dy == 0:
        return canvas.copy()

    out = Canvas(canvas.width, canvas.height)
    for y in range(canvas.height):
        ny = y + dy
        if not (0 <= ny < canvas.height):
            continue
        for x in range(canvas.width):
            px = canvas.get_pixel(x, y)
            if px[3] > 0:
                out.set_pixel(x, ny, px)
    return out


def apply_glint(
    canvas: Canvas,
    frame_idx: int,
    total_frames: int,
    *,
    color: RGBA = (255, 250, 224, 255),
    width_px: int = 2,
    slope: float = 0.5,
) -> Canvas:
    """Sweep a crisp 1..N px vertical/diagonal specular shine strictly across opaque pixels."""
    out = canvas.copy()
    span = canvas.width + int(abs(slope) * canvas.height) + width_px * 2
    t = (frame_idx % max(1, total_frames)) / max(1, total_frames)
    sweep_x = -width_px + t * span

    for y in range(canvas.height):
        band_center = sweep_x - y * slope
        for x in range(canvas.width):
            px = canvas.get_pixel(x, y)
            if px[3] > 0 and abs(x - band_center) < (width_px / 2.0):
                out.set_pixel(x, y, color)
    return out
