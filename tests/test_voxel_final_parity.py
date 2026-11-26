"""Tests for final VoxPix parity blocks (world flags, save/load, regions, physics, rig, foliage/pieces, voxmap)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pixelai.voxel.foliage import generate_foliage, generate_piece
from pixelai.voxel.model import VoxelLayer, VoxelModel
from pixelai.voxel.physics import detect_crush, step_falling_blocks
from pixelai.voxel.pxl_bridge import import_pxl
from pixelai.voxel.ramps import VoxelPalette, ramp_from_color
from pixelai.voxel.regions import RegionManager, autotile_mask, water_tile_edges
from pixelai.voxel.rig import default_humanoid_rig, generate_rig_idle_frames, generate_rig_walk_frames, pose_rig
from pixelai.voxel.world import VoxelWorld
from pixelai.voxel.worldgen import WorldRecipe


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pixelai", *args],
        capture_output=True,
        text=True,
        check=True,
    )


def test_world_save_load_and_cli_flags(tmp_path: Path) -> None:
    save_path = tmp_path / "world_state.json"
    out_png = tmp_path / "world.png"
    res = _run_cli(
        "world",
        "medieval",
        str(out_png),
        "--seed",
        "77",
        "--ticks",
        "2",
        "--mine",
        "0,0,1",
        "--gravity",
        "--save",
        str(save_path),
        "--bench",
    )
    assert out_png.exists()
    assert save_path.exists()
    assert "Benchmark" in res.stdout or "render_world" in res.stdout

    # Load saved world and advance 1 more tick
    out_png2 = tmp_path / "world2.png"
    _run_cli("world", "medieval", str(out_png2), "--load", str(save_path), "--ticks", "1")
    assert out_png2.exists()

    loaded = VoxelWorld.load(save_path)
    assert loaded.tick == 2
    assert loaded.recipe.seed == 77


def test_regions_and_autotile(tmp_path: Path) -> None:
    grid = {(0, 0), (1, 0), (0, 1)}
    mask = autotile_mask(0, 0, lambda x, y: (x, y) in grid)
    assert mask == (2 | 4)  # E + S
    edges = water_tile_edges(0, 0, lambda x, y: (x, y) in grid)
    assert edges == (1 | 8)  # N + W are shore

    mgr = RegionManager(seed=10, chunk_size=8, theme="medieval")
    model = mgr.build_window_model(cx=0, cy=0, radius=1)
    assert len(model.flatten()) > 0

    out_json = tmp_path / "region.json"
    _run_cli("voxel", "region", str(out_json), "--center", "4,4", "--radius", "1", "--chunk-size", "8")
    assert out_json.exists()


def test_physics_falling_and_crush() -> None:
    pal = VoxelPalette(ramps=[ramp_from_color((26, 28, 44, 255), name="outline"), ramp_from_color((220, 200, 120, 255), name="sand")])
    layer = VoxelLayer(id="main", voxels={(0, 0, 2): 1, (1, 0, 0): 1})
    model = VoxelModel(palette=pal, layers=[layer])

    moved = step_falling_blocks(model)
    assert (0, 0, 1) in moved
    flat = model.flatten()
    assert flat.get((0, 0, 2)) is None
    assert flat.get((0, 0, 1)) == 1
    assert flat.get((1, 0, 0)) == 1

    events = detect_crush(moved, [(0, 0, 1), (5, 5, 0)])
    assert len(events) == 1
    assert events[0].entity_index == 0


def test_rig_animation_and_cli(tmp_path: Path) -> None:
    rig = default_humanoid_rig()
    posed = pose_rig(rig, {"leg_l": 20.0})
    assert len(posed.flatten()) > 0
    walk = generate_rig_walk_frames(rig, frames=4)
    idle = generate_rig_idle_frames(rig, frames=4)
    assert len(walk) == 4
    assert len(idle) == 4

    out_sheet = tmp_path / "rig_walk.png"
    _run_cli("voxel", "rig", "humanoid", str(out_sheet), "--cycle", "walk", "--frames", "4", "--scale", "2")
    assert out_sheet.exists()


def test_foliage_and_pieces_and_cli(tmp_path: Path) -> None:
    for kind in ("oak", "pine", "bush", "flower_patch"):
        m = generate_foliage(kind, seed=12)
        assert len(m.flatten()) > 0
    for kind in ("wall", "pillar", "arch", "stairs", "bridge"):
        m = generate_piece(kind, width=6, depth=4, height=6)
        assert len(m.flatten()) > 0

    fol_json = tmp_path / "oak.json"
    pce_json = tmp_path / "arch.json"
    _run_cli("voxel", "foliage", "oak", str(fol_json))
    _run_cli("voxel", "piece", "arch", str(pce_json), "--size", "8x4x8")
    assert fol_json.exists()
    assert pce_json.exists()


def test_pxl_voxmap_import() -> None:
    src = """
// voxpix: outline #1a1c2c
const palette = {
  s: '#8b9bb4',
};
vox.box(0, 0, 0, 1, 1, 1, 's');
vox.set(2, 0, 0, 's');
"""
    model = import_pxl(src, sprite_name="-")
    voxels = model.flatten()
    assert len(voxels) == 9
    assert (2, 0, 0) in voxels
