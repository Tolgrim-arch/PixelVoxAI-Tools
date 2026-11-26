"""Deterministic cellular voxel fluid solver and shallow-water wave simulation (inspired by VoxPix MIT).

Supports:
- `fill_basin` / `fill_to_level`: flood-fill a connected basin up to `water_level_z` respecting material `bed` flags.
- `pour_fluid`: gravity-first cellular pouring with lateral spread.
- `tap_fluid`: continuous tap emission over N simulation ticks.
- `ShallowWaterSim`: 2D shallow-water ripple/wave simulation for animated water surface shading.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from pixelai.voxel.model import Coord3, VoxelLayer, VoxelModel


def _is_bed(coord: Coord3, flat: dict[Coord3, int], model: VoxelModel) -> bool:
    val = flat.get(coord, 0)
    if val == 0:
        return False
    return model.palette.resolve_material(val).bed


def fill_basin(
    model: VoxelModel,
    fluid_layer: VoxelLayer,
    start: Coord3,
    water_level_z: int,
    fluid_value: int,
    *,
    max_cells: int = 4096,
) -> int:
    """Flood-fill a connected basin up to `water_level_z` (inclusive) without leaking through bed walls."""
    flat = model.flatten()
    sx, sy, sz = start
    if sz > water_level_z or _is_bed(start, flat, model):
        return 0

    w, d, _h = model.bounds
    min_x, max_x = -(w // 2), w // 2
    min_y, max_y = -(d // 2), d // 2

    visited: set[Coord3] = {start}
    queue: deque[Coord3] = deque([start])
    filled = 0

    while queue and filled < max_cells:
        x, y, z = queue.popleft()
        fluid_layer.set(x, y, z, fluid_value)
        filled += 1
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            nx, ny, nz = x + dx, y + dy, z + dz
            if nz > water_level_z or nz < 0:
                continue
            if not (min_x <= nx <= max_x and min_y <= ny <= max_y):
                continue
            nb = (nx, ny, nz)
            if nb in visited or _is_bed(nb, flat, model):
                continue
            visited.add(nb)
            queue.append(nb)

    return filled


def fill_to_level(
    model: VoxelModel,
    fluid_layer: VoxelLayer,
    start: Coord3,
    water_level_z: int,
    fluid_value: int,
    *,
    max_cells: int = 4096,
) -> int:
    """Alias for `fill_basin` matching VoxPix's fill-to-level tool."""
    return fill_basin(model, fluid_layer, start, water_level_z, fluid_value, max_cells=max_cells)


def pour_fluid(
    model: VoxelModel,
    fluid_layer: VoxelLayer,
    start: Coord3,
    fluid_value: int,
    *,
    volume: int = 64,
    min_z: int = 0,
) -> int:
    """Pour a fixed `volume` of fluid voxels from `start`, falling by gravity first then spreading laterally."""
    if volume <= 0:
        return 0
    flat = model.flatten()
    w, d, _h = model.bounds
    min_x, max_x = -(w // 2), w // 2
    min_y, max_y = -(d // 2), d // 2

    def _free(c: Coord3) -> bool:
        x, y, z = c
        if z < min_z or not (min_x <= x <= max_x and min_y <= y <= max_y):
            return False
        if c in fluid_layer.voxels:
            return False
        return not _is_bed(c, flat, model)

    placed = 0
    for _ in range(volume):
        cx, cy, cz = start
        if not _free((cx, cy, cz)):
            # Try immediate lateral neighbors if source is already full
            found = False
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if _free((cx + dx, cy + dy, cz)):
                    cx, cy = cx + dx, cy + dy
                    found = True
                    break
            if not found:
                break

        # Drop under gravity until supported, then spread laterally
        for _step in range(256):
            if _free((cx, cy, cz - 1)):
                cz -= 1
                continue
            # Spread laterally toward the first free neighbor (deterministic order)
            moved = False
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if _free((nx, ny, cz)) and _free((nx, ny, cz - 1)):
                    cx, cy = nx, ny
                    moved = True
                    break
            if moved:
                continue
            break

        fluid_layer.set(cx, cy, cz, fluid_value)
        placed += 1
    return placed


def tap_fluid(
    model: VoxelModel,
    fluid_layer: VoxelLayer,
    start: Coord3,
    fluid_value: int,
    *,
    ticks: int = 16,
    rate: int = 4,
    min_z: int = 0,
) -> int:
    """Simulate a continuous fluid tap emitting `rate` voxels per tick for `ticks` ticks."""
    total = 0
    for _ in range(max(0, ticks)):
        added = pour_fluid(model, fluid_layer, start, fluid_value, volume=rate, min_z=min_z)
        total += added
        if added == 0:
            break
    return total


@dataclass(slots=True)
class ShallowWaterSim:
    """Deterministic 2D shallow-water wave heightfield for animated water surfaces."""

    width: int
    height: int
    damping: float = 0.94
    _curr: list[list[float]] = field(init=False)
    _prev: list[list[float]] = field(init=False)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ShallowWaterSim dimensions must be positive")
        self._curr = [[0.0] * self.width for _ in range(self.height)]
        self._prev = [[0.0] * self.width for _ in range(self.height)]

    def disturb(self, x: int, y: int, amount: float = 1.0) -> None:
        """Inject a wave impulse at (x, y)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._curr[y][x] += amount

    def step(self, steps: int = 1) -> None:
        """Advance the 2D wave equation deterministically by `steps` ticks."""
        for _ in range(max(0, steps)):
            nxt = [[0.0] * self.width for _ in range(self.height)]
            for y in range(self.height):
                for x in range(self.width):
                    acc = 0.0
                    cnt = 0
                    if x > 0:
                        acc += self._curr[y][x - 1]
                        cnt += 1
                    if x + 1 < self.width:
                        acc += self._curr[y][x + 1]
                        cnt += 1
                    if y > 0:
                        acc += self._curr[y - 1][x]
                        cnt += 1
                    if y + 1 < self.height:
                        acc += self._curr[y + 1][x]
                        cnt += 1
                    avg = (acc / cnt) if cnt else 0.0
                    val = (2.0 * avg - self._prev[y][x]) * self.damping
                    nxt[y][x] = max(-2.0, min(2.0, val))
            self._prev = self._curr
            self._curr = nxt

    def height_at(self, x: int, y: int) -> float:
        """Return current wave height at (x, y), or 0.0 if out of bounds."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self._curr[y][x]
        return 0.0

    def water_surface_shade(self, x: int, y: int, threshold: float = 0.12) -> int:
        """Return discrete palette shade shift (-1 trough, 0 flat, +1 crest/foam)."""
        h = self.height_at(x, y)
        if h >= threshold:
            return 1
        if h <= -threshold:
            return -1
        return 0
