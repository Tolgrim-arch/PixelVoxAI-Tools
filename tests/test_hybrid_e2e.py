"""Phase V7 End-to-End Hybrid Benchmark: Human Base Body -> AI Paper-Doll Outfit -> Studio Patch & FX -> CLI Parity."""

from __future__ import annotations

import base64
from pathlib import Path

from pixelai.overrides import apply_bounce, apply_glint, apply_pixel_overrides
from pixelai.runner import run_spec
from pixelai.studio.api import StudioState, canvas_to_png_bytes, render_studio_payload
from pixelai.voxel import (
    VoxelLayer,
    VoxelModel,
    VoxelPalette,
    encode_voxel_value,
    ramp_from_color,
    render_voxel_turntable,
)
from pixelai.voxel.paperdoll import compose_paperdoll
from pixelai.voxel.primitives import vox_box


def test_hybrid_human_to_ai_to_studio_e2e(tmp_path: Path) -> None:
    # 1. Human sculpts locked base body in Studio and saves base_human.vox.json
    skin = ramp_from_color("#e0ac69", 4, name="skin")
    body = VoxelLayer(id="body_base", role="body", priority=0)
    vox_box(body, -2, -1, 0, 2, 1, 9, encode_voxel_value(0, 2))
    vox_box(body, -2, -2, 10, 2, 2, 14, encode_voxel_value(0, 2))
    body.locked = True
    base_model = VoxelModel(
        palette=VoxelPalette(ramps=[skin]),
        layers=[body],
        bounds=(24, 24, 32),
        sockets={"head": (0, 0, 15)},
    )
    base_path = tmp_path / "base_human.vox.json"
    base_model.save(base_path)

    # 2. AI Agent loads base body and composes farmer outfit + straw hat via CLI
    reloaded = VoxelModel.load(base_path)
    dressed = compose_paperdoll(
        reloaded,
        extra_ramps=[
            {"name": "straw", "colors": ["#9a613b", "#d69b4b", "#ffe680"], "material": "solid"},
            {"name": "cloth", "colors": ["#29366f", "#3b5dc9", "#41a6f6"], "material": "solid"},
        ],
        overlays=[
            {
                "id": "overalls",
                "role": "outfit",
                "priority": 10,
                "ops": [{"op": "vox_shell", "around": "body_base", "ramp": "cloth", "shade": 1, "z_min": 1, "z_max": 7}],
            },
            {
                "id": "hat",
                "role": "hat",
                "priority": 20,
                "attach_socket": "head",
                "ops": [{"op": "vox_cylinder", "cx": 0, "cy": 0, "z0": 0, "z1": 1, "radius": 3.5, "ramp": "straw", "shade": 2}],
            },
        ],
    )
    turntable = render_voxel_turntable(dressed, turns=8, width=48, height=48, ppu=2)
    assert len(turntable) == 8

    # 3. Human opens composed model in Studio, applies 1-pixel patch + bounce + glint
    overrides = {"frame_1": {"set": [[24, 24, "#fff099"]]}}
    studio_out = render_studio_payload({
        "spec": dressed.to_dict(),
        "yaw": 45.0,
        "elevation": 30.0,
        "ppu": 2,
        "width": 48,
        "height": 48,
        "style": "ext_outline",
        "pixel_overrides": overrides,
        "frame_idx": 1,
        "total_frames": 4,
        "micro_fx": {"bounce": True, "glint": True},
    })
    studio_png = base64.b64decode(studio_out["image"].split(",", 1)[1])

    # 4. Exact CLI re-render with same overrides + micro-FX must match byte-for-byte
    cli_canvas = run_spec({
        "width": 48,
        "height": 48,
        "palette": "cozy24",
        "style": "ext_outline",
        "ops": [{"op": "voxel_model", **dressed.to_dict(), "yaw": 45.0, "elevation": 30.0, "ppu": 2}],
    })
    cli_canvas = apply_pixel_overrides(cli_canvas, overrides, frame_idx=1)
    cli_canvas = apply_bounce(cli_canvas, frame_idx=1, total_frames=4, amplitude_px=2)
    cli_canvas = apply_glint(cli_canvas, frame_idx=1, total_frames=4)
    assert studio_png == canvas_to_png_bytes(cli_canvas)
