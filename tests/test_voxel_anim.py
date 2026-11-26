"""Tests for pixelai.voxel.anim (walk/idle cycles, spritesheet and GIF export)."""

from __future__ import annotations

from pathlib import Path

from pixelai.voxel.anim import (
    export_animation_gif,
    export_animation_sheet,
    generate_idle_frames,
    generate_walk_frames,
    render_animation_frames,
)
from pixelai.voxel.samples import get_sample_model


def test_walk_and_idle_frames_generation(tmp_path: Path) -> None:
    model = get_sample_model("torch")
    walk = generate_walk_frames(model, frames=4, stride=1, bob=1)
    assert len(walk) == 4
    idle = generate_idle_frames(model, frames=4, bob=1)
    assert len(idle) == 4

    canvases = render_animation_frames(walk, scale=2, size=(32, 32))
    assert len(canvases) == 4
    assert canvases[0].width == 64

    sheet_path = tmp_path / "walk_sheet.png"
    export_animation_sheet(canvases, sheet_path)
    assert sheet_path.exists() and sheet_path.stat().st_size > 0

    gif_path = tmp_path / "walk.gif"
    export_animation_gif(canvases, gif_path, ms=100)
    assert gif_path.exists() and gif_path.stat().st_size > 0
