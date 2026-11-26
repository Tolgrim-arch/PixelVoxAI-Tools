"""Deterministic day/night cycle lighting evaluator (inspired by VoxPix MIT)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from pixelai.color import RGBA


@dataclass(frozen=True, slots=True)
class DayCycleState:
    """Evaluated sun and ambient parameters for a given hour of day [0.0, 24.0)."""

    hour: float
    sun_dir: tuple[float, float, float]
    sun_intensity: float
    ambient_level: float
    ambient_dark: bool
    phase: str
    sky_color: RGBA


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_rgba(c0: RGBA, c1: RGBA, t: float) -> RGBA:
    return (
        round(_lerp(c0[0], c1[0], t)),
        round(_lerp(c0[1], c1[1], t)),
        round(_lerp(c0[2], c1[2], t)),
        255,
    )


def evaluate_day_cycle(hour: float = 12.0) -> DayCycleState:
    """Evaluate sun direction, ambient darkness, phase, and sky color for `hour` in [0, 24)."""
    h = float(hour) % 24.0
    # Sun rises at 6:00, peaks at 12:00, sets at 18:00
    angle = ((h - 6.0) / 12.0) * math.pi  # 0 at 6:00, pi/2 at 12:00, pi at 18:00
    sun_z = math.sin(angle)
    sun_x = -math.cos(angle)
    sun_y = 0.35
    length = math.sqrt(sun_x * sun_x + sun_y * sun_y + sun_z * sun_z) or 1.0
    sun_dir = (sun_x / length, sun_y / length, sun_z / length)

    sun_intensity = max(0.0, sun_z)
    ambient_level = 0.25 + 0.75 * sun_intensity
    ambient_dark = sun_intensity < 0.25

    night_sky: RGBA = (18, 22, 42, 255)
    dawn_sky: RGBA = (214, 134, 96, 255)
    day_sky: RGBA = (128, 178, 224, 255)
    dusk_sky: RGBA = (176, 92, 108, 255)

    if 5.0 <= h < 8.0:
        phase = "dawn"
        t = (h - 5.0) / 3.0
        sky = _lerp_rgba(night_sky, dawn_sky, t * 2.0) if t < 0.5 else _lerp_rgba(dawn_sky, day_sky, (t - 0.5) * 2.0)
    elif 8.0 <= h < 17.0:
        phase = "day"
        sky = day_sky
    elif 17.0 <= h < 20.0:
        phase = "dusk"
        t = (h - 17.0) / 3.0
        sky = _lerp_rgba(day_sky, dusk_sky, t * 2.0) if t < 0.5 else _lerp_rgba(dusk_sky, night_sky, (t - 0.5) * 2.0)
    else:
        phase = "night"
        sky = night_sky

    return DayCycleState(
        hour=h,
        sun_dir=sun_dir,
        sun_intensity=sun_intensity,
        ambient_level=ambient_level,
        ambient_dark=ambient_dark,
        phase=phase,
        sky_color=sky,
    )
