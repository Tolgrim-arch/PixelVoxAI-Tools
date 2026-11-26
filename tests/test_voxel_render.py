"""Phase V1 tests: Deterministic CPU voxel-to-pixel renderer and multi-angle turntables."""

from __future__ import annotations

from pixelai.color import TRANSPARENT
from pixelai.runner import run_spec
from pixelai.voxel import (
    VoxelCamera,
    VoxelLayer,
    VoxelModel,
    VoxelPalette,
    encode_voxel_value,
    ramp_from_color,
    render_voxel_model,
    render_voxel_turntable,
)


def _make_cube_model() -> VoxelModel:
    stone = ramp_from_color("#828c9e", steps=4, name="stone")
    pal = VoxelPalette(ramps=[stone])
    layer = VoxelLayer(id="cube", role="body", priority=0)
    val = encode_voxel_value(0, 2)
    for x in range(-3, 4):
        for y in range(-3, 4):
            for z in range(0, 7):
                layer.set(x, y, z, val)
    return VoxelModel(palette=pal, layers=[layer], bounds=(16, 16, 16), pivot=(0, 0, 0))


def test_voxel_render_determinism_and_closed_palette() -> None:
    model = _make_cube_model()
    cam = VoxelCamera(yaw=35.0, elevation=30.0, ppu=2)
    res1 = render_voxel_model(model, width=48, height=48, camera=cam)
    res2 = render_voxel_model(model, width=48, height=48, camera=cam)

    assert res1.canvas.pixels == res2.canvas.pixels
    assert res1.depth_map == res2.depth_map

    allowed = model.palette.all_colors() | {TRANSPARENT}
    opaque_count = 0
    for px in res1.canvas.pixels:
        assert px in allowed
        if px[3] > 0:
            opaque_count += 1
    assert opaque_count > 50


def test_voxel_turntable_8_angles_pivot_stability() -> None:
    model = _make_cube_model()
    frames = render_voxel_turntable(model, turns=8, width=48, height=48, ppu=2, origin_x=24, origin_y=36)
    assert len(frames) == 8
    # Every angle must render non-empty art and pivot pixel (24, 36) stays covered
    for frame in frames:
        assert any(px[3] > 0 for px in frame.pixels)
        assert frame.get_pixel(24, 36)[3] > 0
    # 0 deg and 45 deg should differ visually (diagonal silhouette wider than front)
    assert frames[0].pixels != frames[1].pixels


def test_voxel_oblique_camera() -> None:
    model = _make_cube_model()
    cam = VoxelCamera(yaw=0.0, oblique=(0.5, 1.0), ppu=2)
    res = render_voxel_model(model, width=48, height=48, camera=cam)
    assert any(px[3] > 0 for px in res.canvas.pixels)


def test_voxel_model_via_runner_with_ext_outline() -> None:
    spec = {
        "width": 32,
        "height": 32,
        "palette": "cozy24",
        "style": "ext_outline",
        "ops": [
            {
                "op": "voxel_model",
                "bounds": {"w": 16, "d": 16, "h": 16},
                "palette_ref": "cozy24",
                "ramps": [
                    {"name": "stone", "colors": ["stone_d", "stone", "stone_l"], "material": "solid"}
                ],
                "layers": [
                    {
                        "id": "pillar",
                        "role": "body",
                        "priority": 0,
                        "voxels": [
                            [x, y, z, 2]
                            for x in range(-2, 3)
                            for y in range(-2, 3)
                            for z in range(0, 6)
                        ],
                    }
                ],
                "yaw": 30,
                "elevation": 30,
                "ppu": 2,
            }
        ],
    }
    canvas = run_spec(spec)
    opaque = sum(1 for px in canvas.pixels if px[3] > 0)
    assert opaque > 40
