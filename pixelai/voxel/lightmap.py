"""Pre-baked 3D voxel lightmap for O(1) lighting queries across frames and world views."""

from __future__ import annotations

from dataclasses import dataclass, field

from pixelai.voxel.daycycle import DayCycleState, evaluate_day_cycle
from pixelai.voxel.lighting import (
    PointLight,
    compute_point_light_energy,
    extract_emissive_lights,
    is_in_sun_shadow,
)
from pixelai.voxel.model import Coord3, VoxelModel


@dataclass(slots=True)
class BakedLightmap:
    """Pre-computed per-voxel light intensity map."""

    values: dict[Coord3, float] = field(default_factory=dict)
    lights_count: int = 0
    hour: float = 12.0

    def sample(self, coord: Coord3, default: float = 0.0) -> float:
        """Return pre-baked light intensity at `coord` in O(1)."""
        return self.values.get(coord, default)

    def shade_shift(self, coord: Coord3, ambient_dark: bool = False) -> int:
        """Convert pre-baked light intensity into a closed-palette shade shift (-1, 0, +1)."""
        val = self.values.get(coord, 0.0)
        if ambient_dark:
            if val >= 0.75:
                return 1
            if val >= 0.3:
                return 0
            return -1
        if val >= 0.85:
            return 1
        if val <= 0.2:
            return -1
        return 0


def bake_lightmap(
    model: VoxelModel,
    *,
    extra_lights: list[PointLight] | None = None,
    hour: float = 12.0,
    include_emissive: bool = True,
    sun_shadow: bool = True,
) -> BakedLightmap:
    """Pre-compute light intensity for every occupied voxel in `model`."""
    flat = model.flatten()
    day: DayCycleState = evaluate_day_cycle(hour)
    sun_step = (
        int(round(day.sun_dir[0] * 2)) or -1,
        int(round(day.sun_dir[1] * 2)) or 1,
        max(1, int(round(day.sun_dir[2] * 2))),
    )

    lights: list[PointLight] = list(extra_lights or [])
    if include_emissive:
        lights.extend(extract_emissive_lights(model))

    values: dict[Coord3, float] = {}
    for coord in flat:
        level = day.ambient_level * 0.5
        if day.sun_intensity > 0.0:
            if not (sun_shadow and is_in_sun_shadow(coord, flat, model, sun_dir=sun_step)):
                level += day.sun_intensity * 0.6
        if lights:
            level += compute_point_light_energy(coord, lights, flat, model)
        values[coord] = max(0.0, min(2.0, level))

    return BakedLightmap(values=values, lights_count=len(lights), hour=day.hour)
