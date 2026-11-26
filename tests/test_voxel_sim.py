"""Tests for pixelai.voxel.sim (mine_block, find_path, WorldAgent)."""

from __future__ import annotations

from pixelai.voxel.sim import WorldAgent, find_path, mine_block
from pixelai.voxel.world import VoxelWorld
from pixelai.voxel.worldgen import WorldRecipe


def test_mine_block_and_pathfinding() -> None:
    recipe = WorldRecipe(generator="terrain", seed=7, theme="medieval")
    world = VoxelWorld.from_recipe(recipe)

    path = find_path(world, (2, 2), (6, 6), max_step_up=2)
    assert len(path) >= 2
    assert path[0] == (2, 2)
    assert path[-1] == (6, 6)

    agent = WorldAgent(x=2, y=2, path=list(path[1:]))
    assert agent.step(world) is True

    # Find a solid voxel and mine it
    solid = next(iter(world.model.layers[0].voxels.keys()))
    before_particles = len(world.particles)
    assert mine_block(world, *solid) is True
    assert world.model.layers[0].get(*solid) == 0
    assert len(world.particles) > before_particles
