"""Standalone procedural terrain generator producing a VoxelModel."""

from __future__ import annotations

from pixelai.voxel.model import VoxelModel
from pixelai.voxel.worldgen import WorldRecipe, generate_world_model


def generate_terrain_model(
    width: int = 32,
    depth: int = 32,
    height: int = 16,
    seed: int = 42,
    theme: str = "medieval",
    trees: bool = True,
) -> VoxelModel:
    """Generate a standalone procedural terrain VoxelModel."""
    recipe = WorldRecipe(
        generator="terrain",
        seed=seed,
        width=width,
        depth=depth,
        height=height,
        theme=theme,
        vegetation=trees,
    )
    model, _ = generate_world_model(recipe)
    return model
