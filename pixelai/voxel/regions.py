"""Chunked region streaming, 4/8-neighbor autotiling, and water tile edge detection."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Callable

from pixelai.voxel.model import VoxelLayer, VoxelModel
from pixelai.voxel.ramps import VoxelPalette, ramp_from_color
from pixelai.voxel.worldgen import WORLD_THEMES


def autotile_mask(
    x: int,
    y: int,
    predicate: Callable[[int, int], bool],
    *,
    eight_way: bool = False,
) -> int:
    """Compute a bitmask of matching neighbors around (x, y).

    4-way bits: 1=N (y-1), 2=E (x+1), 4=S (y+1), 8=W (x-1).
    8-way adds: 16=NE, 32=SE, 64=SW, 128=NW.
    """
    mask = 0
    if predicate(x, y - 1):
        mask |= 1
    if predicate(x + 1, y):
        mask |= 2
    if predicate(x, y + 1):
        mask |= 4
    if predicate(x - 1, y):
        mask |= 8
    if eight_way:
        if predicate(x + 1, y - 1):
            mask |= 16
        if predicate(x + 1, y + 1):
            mask |= 32
        if predicate(x - 1, y + 1):
            mask |= 64
        if predicate(x - 1, y - 1):
            mask |= 128
    return mask


def water_tile_edges(x: int, y: int, is_water: Callable[[int, int], bool]) -> int:
    """Return 4-bit mask of non-water (shoreline) edges around a water tile."""
    if not is_water(x, y):
        return 0
    return autotile_mask(x, y, lambda nx, ny: not is_water(nx, ny), eight_way=False)


def _chunk_seed(base_seed: int, rx: int, ry: int) -> int:
    raw = f"{base_seed}:{rx}:{ry}".encode("utf-8")
    return int.from_bytes(hashlib.blake2b(raw, digest_size=4).digest(), "little")


@dataclass(slots=True)
class RegionChunk:
    rx: int
    ry: int
    size: int
    voxels: dict[tuple[int, int, int], int] = field(default_factory=dict)


class RegionManager:
    """Deterministic on-demand chunked region generator."""

    def __init__(self, *, seed: int = 42, chunk_size: int = 16, theme: str = "medieval") -> None:
        if theme not in WORLD_THEMES:
            raise ValueError(f"Unknown theme '{theme}'; expected one of {sorted(WORLD_THEMES)}")
        self.seed = seed
        self.chunk_size = max(4, chunk_size)
        self.theme = theme
        self.palette = VoxelPalette(
            ramps=[
                ramp_from_color((26, 28, 44, 255), name="outline"),
                ramp_from_color((110, 120, 140, 255), name="stone"),
                ramp_from_color((56, 183, 100, 255) if theme != "toxic" else (120, 190, 60, 255), name="grass"),
                ramp_from_color((65, 166, 246, 255) if theme != "toxic" else (140, 220, 60, 255), name="water"),
            ]
        )
        self._chunks: dict[tuple[int, int], RegionChunk] = {}

    def get_or_generate_region(self, rx: int, ry: int) -> RegionChunk:
        """Return cached chunk (rx, ry) or generate it deterministically."""
        key = (rx, ry)
        if key in self._chunks:
            return self._chunks[key]

        cseed = _chunk_seed(self.seed, rx, ry)
        voxels: dict[tuple[int, int, int], int] = {}
        ox = rx * self.chunk_size
        oy = ry * self.chunk_size

        for lx in range(self.chunk_size):
            for ly in range(self.chunk_size):
                wx = ox + lx
                wy = oy + ly
                h = 2 + int(2.0 * (0.5 + 0.5 * math.sin(wx * 0.18 + self.seed * 0.1) * math.cos(wy * 0.18)))
                for z in range(h):
                    color = 1 if z < h - 1 else 2
                    voxels[(wx, wy, z)] = color
                # Deterministic water basin
                if math.sin(wx * 0.12 - wy * 0.11 + (cseed & 0xFF) * 0.01) > 0.72 and h <= 2:
                    voxels[(wx, wy, h - 1)] = 3

        chunk = RegionChunk(rx=rx, ry=ry, size=self.chunk_size, voxels=voxels)
        self._chunks[key] = chunk
        return chunk

    def build_window_model(self, cx: int = 0, cy: int = 0, radius: int = 1) -> VoxelModel:
        """Assemble a VoxelModel from chunks within `radius` around world (cx, cy)."""
        crx = cx // self.chunk_size
        cry = cy // self.chunk_size
        merged: dict[tuple[int, int, int], int] = {}
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                chunk = self.get_or_generate_region(crx + dx, cry + dy)
                merged.update(chunk.voxels)

        layer = VoxelLayer(id="regions", voxels=merged)
        return VoxelModel(palette=self.palette, layers=[layer])
