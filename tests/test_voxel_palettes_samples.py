"""Tests for external voxel palette importers (.hex/.gpl), presets, and sample models."""

from __future__ import annotations

from pathlib import Path

import pytest

from pixelai.voxel.palettes_io import (
    COMMUNITY_PRESETS,
    load_palette_any,
    load_palette_preset,
    parse_gpl_palette,
    parse_hex_palette,
    verify_palette_colors,
)
from pixelai.voxel.camera import VoxelCamera
from pixelai.voxel.render import render_voxel_model
from pixelai.voxel.samples import SAMPLE_NAMES, get_sample_model


def test_parse_hex_palette() -> None:
    text = """
    # comment line
    1d2b53
    #ff004d
    00e436
    """
    pal = parse_hex_palette(text, steps=4)
    assert len(pal.ramps) == 3
    assert all(len(r.colors) == 4 for r in pal.ramps)


def test_parse_gpl_palette() -> None:
    text = """GIMP Palette
Name: Mini
Columns: 2
#
  29  43  83 Navy
 255   0  77 Crimson
"""
    pal = parse_gpl_palette(text, steps=4)
    assert len(pal.ramps) == 2
    assert pal.ramps[0].name == "navy"
    assert pal.ramps[1].name == "crimson"


def test_load_palette_presets_and_files(tmp_path: Path) -> None:
    for name in COMMUNITY_PRESETS:
        pal = load_palette_preset(name)
        assert len(pal.ramps) >= 8

    hex_file = tmp_path / "custom.hex"
    hex_file.write_text("ff004d\n29adff\n", encoding="utf-8")
    pal = load_palette_any(hex_file)
    assert len(pal.ramps) == 2

    gpl_file = tmp_path / "custom.gpl"
    gpl_file.write_text("GIMP Palette\n10 20 30 Slate\n200 180 40 Gold\n", encoding="utf-8")
    pal2 = load_palette_any(gpl_file)
    assert len(pal2.ramps) == 2


def test_sample_models_render_strictly_within_palette() -> None:
    for name in SAMPLE_NAMES:
        model = get_sample_model(name)
        assert len(model.flatten()) > 0
        res = render_voxel_model(
            model,
            width=64,
            height=64,
            camera=VoxelCamera(yaw=35.0, elevation=30.0),
        )
        ok, stray = verify_palette_colors(res.canvas, model.palette)
        assert ok, f"Sample {name} produced stray colors: {stray}"
