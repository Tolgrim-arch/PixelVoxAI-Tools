"""Procedural multi-floor building generator with interior rooms, doors, windows, and stairs."""
from __future__ import annotations

import random

from .model import VoxelLayer, VoxelModel, VoxelPalette


def _box(layer, p0: tuple[int, int, int], p1: tuple[int, int, int], color_idx: int) -> None:
    x0, y0, z0 = min(p0[0], p1[0]), min(p0[1], p1[1]), min(p0[2], p1[2])
    x1, y1, z1 = max(p0[0], p1[0]), max(p0[1], p1[1]), max(p0[2], p1[2])
    for z in range(z0, z1 + 1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                layer.set(x, y, z, color_idx)


_BUILDING_THEMES: dict[str, dict[str, str]] = {
    "medieval": {
        "wall": "#8d8a82",
        "floor": "#6e5038",
        "roof": "#7a3b32",
        "trim": "#4b382a",
        "stair": "#9c744c",
        "window": "#8ecae6",
    },
    "garden": {
        "wall": "#e0d8c8",
        "floor": "#8f6d4c",
        "roof": "#4f7d4a",
        "trim": "#5c4a38",
        "stair": "#a3815b",
        "window": "#a8dadc",
    },
    "neon": {
        "wall": "#2b2d42",
        "floor": "#1d1e2c",
        "roof": "#3a0ca3",
        "trim": "#7209b7",
        "stair": "#4cc9f0",
        "window": "#f72585",
    },
    "toxic": {
        "wall": "#38423b",
        "floor": "#28302a",
        "roof": "#4f6d2c",
        "trim": "#212622",
        "stair": "#709438",
        "window": "#aacc00",
    },
}


def generate_building(
    width: int = 16,
    depth: int = 16,
    floors: int = 2,
    floor_height: int = 5,
    theme: str = "medieval",
    seed: int = 42,
    roof: str = "gable",
) -> VoxelModel:
    """Generate a multi-floor voxel building with interior rooms, doors, windows, and stairs."""
    rng = random.Random(seed)
    w = max(8, int(width))
    d = max(8, int(depth))
    n_floors = max(1, int(floors))
    fh = max(4, int(floor_height))
    colors = _BUILDING_THEMES.get(theme, _BUILDING_THEMES["medieval"])

    roof_h = (min(w, d) // 2 + 1) if roof == "gable" else 2
    total_h = n_floors * fh + roof_h + 1

    from .ramps import VoxelRamp

    def _rgba(h: str) -> tuple[int, int, int, int]:
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)

    palette = VoxelPalette(
        ramps=[
            VoxelRamp(name="w", colors=[_rgba(colors["wall"])]),
            VoxelRamp(name="f", colors=[_rgba(colors["floor"])]),
            VoxelRamp(name="r", colors=[_rgba(colors["roof"])]),
            VoxelRamp(name="t", colors=[_rgba(colors["trim"])]),
            VoxelRamp(name="s", colors=[_rgba(colors["stair"])]),
            VoxelRamp(name="g", colors=[_rgba(colors["window"])]),
        ]
    )
    wall_c, floor_c, roof_c, trim_c, stair_c, win_c = 1, 2, 3, 4, 5, 6

    layer = VoxelLayer(id="main")
    model = VoxelModel(bounds=(w, d, total_h), palette=palette, layers=[layer])

    for f in range(n_floors):
        z0 = f * fh
        z_top = z0 + fh - 1

        # Floor slab
        _box(layer, (0, 0, z0), (w - 1, d - 1, z0), floor_c)

        # Exterior walls
        _box(layer, (0, 0, z0 + 1), (w - 1, 0, z_top), wall_c)
        _box(layer, (0, d - 1, z0 + 1), (w - 1, d - 1, z_top), wall_c)
        _box(layer, (0, 0, z0 + 1), (0, d - 1, z_top), wall_c)
        _box(layer, (w - 1, 0, z0 + 1), (w - 1, d - 1, z_top), wall_c)

        # Corner trim pillars
        for cx, cy in ((0, 0), (w - 1, 0), (0, d - 1), (w - 1, d - 1)):
            _box(layer, (cx, cy, z0 + 1), (cx, cy, z_top), trim_c)

        # Windows on exterior walls
        win_z = z0 + 2
        if win_z < z_top:
            for wx in range(3, w - 3, 4):
                layer.set(wx, 0, win_z, win_c)
                layer.set(wx, d - 1, win_z, win_c)
            for wy in range(3, d - 3, 4):
                layer.set(0, wy, win_z, win_c)
                layer.set(w - 1, wy, win_z, win_c)

        # Ground floor entrance door
        if f == 0:
            door_x = w // 2
            for dz in range(1, min(4, fh)):
                layer.set(door_x, 0, z0 + dz, 0)
                if door_x + 1 < w - 1:
                    layer.set(door_x + 1, 0, z0 + dz, 0)

        # Interior room divider wall + doorway
        split_x = rng.randint(max(3, w // 3), min(w - 4, (2 * w) // 3))
        _box(layer, (split_x, 1, z0 + 1), (split_x, d - 2, z_top), wall_c)
        door_y = d // 2
        for dz in range(1, min(4, fh)):
            layer.set(split_x, door_y, z0 + dz, 0)

        # Interior stairs to next floor
        if f < n_floors - 1:
            sx = 2 if split_x > 4 else w - 3
            for step in range(fh):
                sy = 2 + step
                if sy < d - 2:
                    layer.set(sx, sy, z0 + 1 + step, stair_c)
                    # Clear ceiling above stair
                    layer.set(sx, sy, z0 + fh, 0)

    # Roof
    roof_z = n_floors * fh
    if roof == "gable":
        steps = min(w, d) // 2 + 1
        for i in range(steps):
            if i <= w - 1 - i and i <= d - 1 - i and roof_z + i < total_h:
                _box(layer, (i, i, roof_z + i), (w - 1 - i, d - 1 - i, roof_z + i), roof_c)
    else:
        _box(layer, (0, 0, roof_z), (w - 1, d - 1, roof_z), roof_c)

    return model
