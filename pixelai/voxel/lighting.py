"""Deterministic 3D point lighting and integer sun-shadow raycasting ported from VoxPix (MIT).

All light accumulation translates strictly into integer palette-ramp shade shifts,
preserving closed-palette pixel art determinism.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pixelai.voxel.model import Coord3, VoxelModel


@dataclass(frozen=True, slots=True)
class PointLight:
    """A 3D point light source (e.g., torch, lantern, brazier, neon)."""

    position: Coord3
    radius: float = 10.0
    intensity: float = 1.0
    kind: str = "torch"


def _cell_shadow_threshold(x: int, y: int, z: int) -> int:
    """Deterministic position-hashed shadow threshold in [4, 16] for mottled canopy shadows."""
    h = (x * 73856093) ^ (y * 19349663) ^ (z * 83492791)
    return 4 + (abs(h) % 13)


def _material_ray_cost(light_transmission: float) -> int:
    """Integer ray cost per voxel: opaque=16, foliage(0.5)=4, glass(0.85)=1."""
    if light_transmission <= 0.0:
        return 16
    if light_transmission >= 1.0:
        return 0
    return max(1, round(-math.log2(light_transmission) * 4.0))


def is_in_sun_shadow(
    coord: Coord3,
    flat: dict[Coord3, int],
    model: VoxelModel,
    sun_dir: tuple[int, int, int] = (-1, 1, 2),
    max_steps: int = 32,
) -> bool:
    """Deterministic integer raycast toward sun_dir; supports mottled foliage shadows."""
    x, y, z = coord
    dx, dy, dz = sun_dir
    threshold = _cell_shadow_threshold(x, y, z)
    cost = 0
    for step in range(1, max_steps + 1):
        cx = x + dx * step
        cy = y + dy * step
        cz = z + dz * step
        val = flat.get((cx, cy, cz), 0)
        if val == 0:
            continue
        mat = model.palette.resolve_material(val)
        cost += _material_ray_cost(mat.light)
        if cost >= threshold:
            return True
    return False


def compute_point_light_energy(
    coord: Coord3,
    lights: list[PointLight],
    flat: dict[Coord3, int],
    model: VoxelModel,
) -> float:
    """Compute occluded point-light energy at coord in [0.0, 2.0]."""
    if not lights:
        return 0.0
    x, y, z = coord
    total = 0.0
    for light in lights:
        lx, ly, lz = light.position
        dx = lx - x
        dy = ly - y
        dz = lz - z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist > light.radius:
            continue
        if dist < 1e-6:
            total += light.intensity
            continue
        # Step along ray from voxel center to light center checking transmission
        steps = max(1, int(math.ceil(dist)))
        trans = 1.0
        for s in range(1, steps):
            t = s / steps
            sx = math.floor(x + 0.5 + dx * t)
            sy = math.floor(y + 0.5 + dy * t)
            sz = math.floor(z + 0.5 + dz * t)
            if (sx, sy, sz) == coord or (sx, sy, sz) == light.position:
                continue
            val = flat.get((sx, sy, sz), 0)
            if val != 0:
                mat = model.palette.resolve_material(val)
                trans *= mat.light
                if trans <= 0.01:
                    trans = 0.0
                    break
        falloff = max(0.0, 1.0 - dist / light.radius)
        total += light.intensity * falloff * trans
    return min(2.0, total)


def compute_lighting_shade_shift(
    coord: Coord3,
    flat: dict[Coord3, int],
    model: VoxelModel,
    *,
    lights: list[PointLight] | None = None,
    sun_shadow: bool = True,
    ambient_dark: bool = False,
) -> int:
    """Return integer ramp shade shift (-2..+2) from sun shadow and point lights."""
    shift = -1 if ambient_dark else 0
    if sun_shadow and is_in_sun_shadow(coord, flat, model):
        shift -= 1
    if lights:
        energy = compute_point_light_energy(coord, lights, flat, model)
        if energy >= 0.65:
            shift += 2
        elif energy >= 0.25:
            shift += 1
    return max(-2, min(2, shift))
