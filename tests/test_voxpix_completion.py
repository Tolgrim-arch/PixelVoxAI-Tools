"""Tests for VoxPix CLI completion blocks (2.5D pathfinding, world GIF/follow, buildings)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pixelai.voxel.buildings import generate_building
from pixelai.voxel.model import VoxelLayer, VoxelModel, VoxelPalette
from pixelai.voxel.paths import find_path_25d
from pixelai.voxel.sim import WorldAgent
from pixelai.voxel.world import VoxelWorld, WorldRecipe


class TestVoxPixCompletion(unittest.TestCase):
    def test_find_path_25d_flat_and_ramp(self) -> None:
        pal = VoxelPalette(ramps={"x": ["#808080"]})
        c = 1
        layer = VoxelLayer(id="main")
        m = VoxelModel(bounds=(8, 8, 6), palette=pal, layers=[layer])
        for x in range(8):
            for y in range(8):
                layer.set(x, y, 0, c)
        # Step up at x >= 4
        for x in range(4, 8):
            for y in range(8):
                layer.set(x, y, 1, c)
        path = find_path_25d(m, (0, 2, 1), (6, 2, 2))
        self.assertTrue(len(path) >= 7)
        self.assertEqual(path[0], (0, 2, 1))
        self.assertEqual((path[-1][0], path[-1][1]), (6, 2))

    def test_agent_navigate_to(self) -> None:
        recipe = WorldRecipe(theme="medieval", generator="terrain", seed=7, width=16, depth=16)
        world = VoxelWorld.from_recipe(recipe)
        ag = WorldAgent(x=2, y=2, z=1)
        # Ensure flat walkable strip
        c = 1
        layer = world.model.layers[0]
        for x in range(2, 7):
            layer.set(x, 2, 0, c)
            for z in range(1, 5):
                layer.set(x, 2, z, 0)
        ok = ag.navigate_to(world, (6, 2, 1))
        self.assertTrue(ok)
        self.assertTrue(len(ag.path) > 0)

    def test_generate_building(self) -> None:
        b = generate_building(width=14, depth=14, floors=2, theme="medieval", seed=42, roof="gable")
        self.assertEqual(b.bounds[0], 14)
        self.assertEqual(b.bounds[1], 14)
        self.assertGreater(len(b.flatten()), 100)

    def test_cli_building_and_world_gif(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            b_out = tmp_path / "tower.vox.json"
            res = subprocess.run(
                [sys.executable, "-m", "pixelai", "voxel", "building", str(b_out), "--floors", "2", "--theme", "neon"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(b_out.exists())

            gif_out = tmp_path / "world.gif"
            res2 = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pixelai",
                    "world",
                    "medieval",
                    str(gif_out),
                    "--size",
                    "64x48",
                    "--frames",
                    "3",
                    "--ms",
                    "80",
                    "--follow",
                    "0",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res2.returncode, 0, res2.stderr)
            self.assertTrue(gif_out.exists())
            self.assertGreater(gif_out.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main()
