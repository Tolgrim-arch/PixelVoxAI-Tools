"""Deterministic pixel-art weather overlays (rain, snow, fog) for voxel renders."""

from __future__ import annotations

from pixelai.canvas import Canvas
from pixelai.color import RGBA

WEATHER_MODES = ("none", "rain", "snow", "fog")


def _hash2(x: int, y: int, seed: int) -> int:
    n = (x * 374761393 + y * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n ^ (n >> 16)) & 0xFFFFFFFF


def apply_weather_overlay(
    canvas: Canvas,
    weather: str = "none",
    *,
    tick: int = 0,
    intensity: float = 0.5,
    seed: int = 42,
) -> Canvas:
    """Apply deterministic rain, snow, or fog overlay directly onto `canvas` and return it."""
    mode = weather.strip().lower()
    if mode not in WEATHER_MODES:
        raise ValueError(f"Unknown weather mode {weather!r}. Available: {', '.join(WEATHER_MODES)}")
    if mode == "none" or intensity <= 0.0:
        return canvas

    w, h = canvas.width, canvas.height
    strength = max(0.0, min(1.0, float(intensity)))

    if mode == "rain":
        rain_color: RGBA = (176, 212, 242, 255)
        drops = max(4, int((w * h) * 0.008 * strength))
        for i in range(drops):
            hx = _hash2(i, 1, seed)
            hy = _hash2(i, 2, seed)
            x0 = (hx - tick * 2) % max(1, w)
            y0 = (hy + tick * 5) % max(1, h)
            for step in range(3):
                px = x0 - step // 2
                py = y0 + step
                if 0 <= px < w and 0 <= py < h:
                    canvas.set_pixel(px, py, rain_color)
    elif mode == "snow":
        snow_color: RGBA = (238, 244, 252, 255)
        flakes = max(4, int((w * h) * 0.01 * strength))
        for i in range(flakes):
            hx = _hash2(i, 3, seed)
            hy = _hash2(i, 4, seed)
            drift = ((tick + i) % 3) - 1
            px = (hx + drift) % max(1, w)
            py = (hy + tick * 2) % max(1, h)
            if 0 <= px < w and 0 <= py < h:
                canvas.set_pixel(px, py, snow_color)
    elif mode == "fog":
        fog_color: RGBA = (196, 206, 220, 255)
        # Ordered Bayer-like checkerboard dither concentrated toward the top/distance
        for py in range(h):
            depth_factor = 1.0 - (py / max(1, h))
            if depth_factor * strength < 0.25:
                continue
            for px in range(w):
                if ((px + py + (tick // 4)) & 3) == 0:
                    r, g, b, a = canvas.get_pixel(px, py)
                    if a == 0:
                        continue
                    nr = round(r * 0.65 + fog_color[0] * 0.35)
                    ng = round(g * 0.65 + fog_color[1] * 0.35)
                    nb = round(b * 0.65 + fog_color[2] * 0.35)
                    canvas.set_pixel(px, py, (nr, ng, nb, a))

    return canvas
