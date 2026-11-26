"""Procedural foliage and modular architectural piece generators."""

from __future__ import annotations

import random

from pixelai.voxel.model import Coord3, VoxelLayer, VoxelModel
from pixelai.voxel.ramps import VoxelPalette, ramp_from_color

FOLIAGE_KINDS = ("oak", "pine", "bush", "flower_patch")
PIECE_KINDS = ("wall", "pillar", "arch", "stairs", "bridge")


def _foliage_palette() -> VoxelPalette:
    return VoxelPalette(
        ramps=[
            ramp_from_color((26, 28, 44, 255), name="outline"),
            ramp_from_color((115, 62, 57, 255), name="trunk"),
            ramp_from_color((37, 113, 121, 255), name="leaf_dark"),
            ramp_from_color((56, 183, 100, 255), name="leaf_bright"),
            ramp_from_color((228, 59, 68, 255), name="flower_a"),
            ramp_from_color((254, 231, 97, 255), name="flower_b"),
        ]
    )


def generate_foliage(
    kind: str = "oak",
    *,
    seed: int = 42,
    scale: int = 1,
) -> VoxelModel:
    """Generate a standalone foliage VoxelModel ('oak', 'pine', 'bush', 'flower_patch')."""
    if kind not in FOLIAGE_KINDS:
        raise ValueError(f"Unknown foliage kind '{kind}'; expected one of {FOLIAGE_KINDS}")
    rng = random.Random(seed)
    s = max(1, scale)
    voxels: dict[Coord3, int] = {}

    if kind == "oak":
        trunk_h = 5 * s
        for z in range(trunk_h):
            voxels[(0, 0, z)] = 1
        r = 3 * s
        cz = trunk_h + s
        for x in range(-r, r + 1):
            for y in range(-r, r + 1):
                for z in range(cz - r, cz + r + 1):
                    d2 = x * x + y * y + (z - cz) * (z - cz)
                    if d2 <= r * r + rng.randint(0, s):
                        voxels[(x, y, z)] = 3 if z >= cz else 2
    elif kind == "pine":
        trunk_h = 3 * s
        for z in range(trunk_h):
            voxels[(0, 0, z)] = 1
        layers = 5 * s
        for dz in range(layers):
            rad = max(0, (layers - dz) // 2 + 1)
            z = trunk_h + dz
            for x in range(-rad, rad + 1):
                for y in range(-rad, rad + 1):
                    if abs(x) + abs(y) <= rad + 1:
                        voxels[(x, y, z)] = 3 if dz % 2 == 0 else 2
    elif kind == "bush":
        r = 2 * s
        for x in range(-r, r + 1):
            for y in range(-r, r + 1):
                for z in range(0, r + 1):
                    if x * x + y * y + z * z <= r * r + rng.randint(0, 1):
                        voxels[(x, y, z)] = 3 if z >= r // 2 else 2
    elif kind == "flower_patch":
        r = 3 * s
        for x in range(-r, r + 1):
            for y in range(-r, r + 1):
                if x * x + y * y <= r * r:
                    voxels[(x, y, 0)] = 2
                    if rng.random() < 0.28:
                        voxels[(x, y, 1)] = 4 if rng.random() < 0.5 else 5

    return VoxelModel(palette=_foliage_palette(), layers=[VoxelLayer(id=kind, voxels=voxels)])


def _piece_palette(theme: str = "medieval") -> VoxelPalette:
    if theme == "neon":
        stone = (44, 52, 78, 255)
        trim = (65, 220, 240, 255)
        wood = (90, 60, 140, 255)
    elif theme == "toxic":
        stone = (58, 70, 56, 255)
        trim = (140, 220, 60, 255)
        wood = (80, 64, 48, 255)
    else:
        stone = (139, 155, 180, 255)
        trim = (90, 105, 136, 255)
        wood = (138, 86, 54, 255)
    return VoxelPalette(
        ramps=[
            ramp_from_color((26, 28, 44, 255), name="outline"),
            ramp_from_color(stone, name="stone"),
            ramp_from_color(trim, name="trim"),
            ramp_from_color(wood, name="wood"),
        ]
    )


def generate_piece(
    kind: str = "wall",
    *,
    width: int = 8,
    depth: int = 4,
    height: int = 8,
    theme: str = "medieval",
) -> VoxelModel:
    """Generate a modular architectural piece ('wall', 'pillar', 'arch', 'stairs', 'bridge')."""
    if kind not in PIECE_KINDS:
        raise ValueError(f"Unknown piece kind '{kind}'; expected one of {PIECE_KINDS}")
    w = max(2, width)
    d = max(2, depth)
    h = max(2, height)
    voxels: dict[Coord3, int] = {}

    if kind == "wall":
        for x in range(w):
            for y in range(min(2, d)):
                for z in range(h):
                    if z == h - 1 and x % 2 == 1:
                        continue  # crenellations
                    voxels[(x, y, z)] = 2 if z in (0, h - 1) else 1
    elif kind == "pillar":
        for x in range(min(3, w)):
            for y in range(min(3, d)):
                for z in range(h):
                    is_cap = z == 0 or z == h - 1
                    if not is_cap and (x in (0, 2) and y in (0, 2)):
                        continue
                    voxels[(x, y, z)] = 2 if is_cap else 1
    elif kind == "arch":
        for x in range(w):
            for y in range(min(2, d)):
                for z in range(h):
                    in_opening = (1 <= x <= w - 2) and (z < h - 2)
                    if not in_opening:
                        voxels[(x, y, z)] = 2 if z >= h - 2 else 1
    elif kind == "stairs":
        steps = min(w, h)
        for s in range(steps):
            for y in range(d):
                for z in range(s + 1):
                    voxels[(s, y, z)] = 2 if z == s else 1
    elif kind == "bridge":
        for x in range(w):
            for y in range(d):
                voxels[(x, y, 1)] = 3
                if y in (0, d - 1) and x % 2 == 0:
                    voxels[(x, y, 2)] = 2

    return VoxelModel(palette=_piece_palette(theme), layers=[VoxelLayer(id=kind, voxels=voxels)])
