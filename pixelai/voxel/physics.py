"""Falling block gravity and crush physics for 2.5D voxel worlds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from pixelai.voxel.model import Coord3, VoxelModel


@dataclass(frozen=True, slots=True)
class CrushEvent:
    """Event emitted when a falling voxel impacts an entity."""

    coord: Coord3
    entity_index: int


def step_falling_blocks(
    model: VoxelModel,
    *,
    anchored_colors: set[int] | None = None,
    ground_z: int = 0,
) -> list[Coord3]:
    """Advance unsupported voxels downward by 1 Z-level deterministically.

    Returns the list of new coordinates where blocks landed/moved this tick.
    """
    moved: list[Coord3] = []
    occupied = model.flatten()
    for layer in model.layers:
        if not layer.visible or not layer.voxels:
            continue
        # Process bottom-up so stacked unsupported blocks fall together cleanly.
        coords_sorted = sorted(layer.voxels.keys(), key=lambda c: (c[2], c[0], c[1]))
        for x, y, z in coords_sorted:
            if z <= ground_z:
                continue
            color_idx = layer.voxels[(x, y, z)]
            if anchored_colors and color_idx in anchored_colors:
                continue
            below = (x, y, z - 1)
            if below not in occupied:
                del layer.voxels[(x, y, z)]
                layer.voxels[below] = color_idx
                occupied.pop((x, y, z), None)
                occupied[below] = color_idx
                moved.append(below)
    return moved


def detect_crush(
    falling_coords: Iterable[Coord3],
    entity_coords: Iterable[Coord3],
) -> list[CrushEvent]:
    """Detect collisions between falling blocks and entity positions."""
    falling_set = set(falling_coords)
    events: list[CrushEvent] = []
    for idx, ecoord in enumerate(entity_coords):
        if ecoord in falling_set:
            events.append(CrushEvent(coord=ecoord, entity_index=idx))
    return events
