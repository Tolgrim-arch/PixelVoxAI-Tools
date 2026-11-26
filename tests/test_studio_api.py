"""Phase V5 tests: Studio Oracle API parity with CLI renderer and atomic save."""

from __future__ import annotations

import base64
from pathlib import Path

from pixelai.cli import build_parser
from pixelai.runner import run_spec
from pixelai.studio.api import StudioState, canvas_to_png_bytes, render_studio_payload


def test_studio_oracle_pixel_parity_with_cli() -> None:
    state = StudioState.load(None)
    studio_res = render_studio_payload({
        "spec": state.spec,
        "yaw": 30.0,
        "elevation": 30.0,
        "ppu": 2,
        "width": 48,
        "height": 48,
        "style": "ext_outline",
    })
    prefix = "data:image/png;base64,"
    assert studio_res["image"].startswith(prefix)
    studio_png = base64.b64decode(studio_res["image"][len(prefix):])

    # Render directly via CLI runner
    cli_canvas = run_spec({
        "width": 48,
        "height": 48,
        "palette": "cozy24",
        "style": "ext_outline",
        "ops": [{"op": "voxel_model", **state.spec, "yaw": 30.0, "elevation": 30.0, "ppu": 2}],
    })
    assert studio_png == canvas_to_png_bytes(cli_canvas)


def test_studio_atomic_save_and_reload(tmp_path: Path) -> None:
    target = tmp_path / "sculpted.vox.json"
    state = StudioState.load(None)
    saved = state.save(target)
    assert saved == target and target.is_file()
    reloaded = StudioState.load(target)
    assert reloaded.spec == state.spec


def test_studio_cli_subcommand_registered() -> None:
    parser = build_parser()
    args = parser.parse_args(["studio", "model.vox.json", "--port", "5199", "--no-browser"])
    assert args.command == "studio"
    assert args.file == "model.vox.json"
    assert args.port == 5199
    assert args.no_browser is True


def test_studio_3d_pick_ramp_and_exports(tmp_path: Path) -> None:
    from pixelai.studio.api import export_studio_payload, generate_ramp_payload, pick_voxel_at_pixel

    state = StudioState.load(None)
    # 3D face picking near center pivot (24, 34)
    pick = pick_voxel_at_pixel({"spec": state.spec, "px": 24, "py": 34, "yaw": 30.0, "elevation": 30.0, "ppu": 2, "width": 48, "height": 48})
    assert pick["hit"] is True
    assert len(pick["coord"]) == 3 and len(pick["normal"]) == 3 and len(pick["place"]) == 3

    # Hue-shifted ramp generator
    ramp_res = generate_ramp_payload({"color": "#3b5dc9", "steps": 4, "name": "cobalt"})
    assert ramp_res["ramp"]["name"] == "cobalt" and len(ramp_res["ramp"]["colors"]) == 4

    # Export PNG, GIF, Spritesheet, and Godot 4 .tres
    for fmt, ext in (("png", "png"), ("gif", "gif"), ("sheet", "png"), ("godot", "tres")):
        out = tmp_path / f"out_{fmt}.{ext}"
        res = export_studio_payload({"spec": state.spec, "format": fmt, "path": str(out), "total_frames": 4, "micro_fx": {"bounce": True}})
        assert Path(res["exported"]).is_file()

