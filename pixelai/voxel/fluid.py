"""Deterministic cellular voxel fluid solver ported from VoxPix (MIT).

Supports basin filling (`fill_basin`) and pouring (`pour_fluid`) respecting
material `bed` flags, and bakes directly into a VoxelLayer.
"""

from __future__ import annotations

from collections import deque

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
