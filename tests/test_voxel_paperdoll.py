"""Phase V2 tests: Paper-doll layering, socket attachment, outfit shell wrapping, and base immutability."""

from __future__ import annotations

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


def _make_base_human(head_z: int = 12) -> VoxelModel:
    skin = ramp_from_color("#e0ac69", steps=4, name="skin")
    pal = VoxelPalette(ramps=[skin])
    body = VoxelLayer(id="body_base", role="body", priority=0)
    vox_box(body, -2, -1, 0, 2, 1, head_z - 2, encode_voxel_value(0, 2))  # torso/legs
    vox_box(body, -2, -2, head_z - 1, 2, 2, head_z + 3, encode_voxel_value(0, 2))  # head
    body.locked = True
    return VoxelModel(
        palette=pal,
        layers=[body],
        bounds=(24, 24, 32),
        pivot=(0, 0, 0),
        sockets={"head": (0, 0, head_z + 4), "torso": (0, 0, 5)},
    )


def test_paperdoll_composes_farmer_outfit_without_mutating_base() -> None:
    base = _make_base_human(head_z=12)
    base_snapshot = base.to_dict()

    composed = compose_paperdoll(
        base,
        extra_ramps=[
            {"name": "straw", "colors": ["#9a613b", "#d69b4b", "#ffe680"], "material": "solid"},
            {"name": "overalls", "colors": ["#29366f", "#3b5dc9", "#41a6f6"], "material": "solid"},
        ],
        overlays=[
            {
                "id": "farmer_overalls",
                "role": "outfit",
                "priority": 10,
                "ops": [
                    {"op": "vox_shell", "around": "body_base", "ramp": "overalls", "shade": 1, "z_min": 1, "z_max": 8}
                ],
            },
            {
                "id": "straw_hat",
                "role": "hat",
                "priority": 20,
                "attach_socket": "head",
                "ops": [
                    {"op": "vox_cylinder", "cx": 0, "cy": 0, "z0": 0, "z1": 0, "radius": 4.2, "ramp": "straw", "shade": 2},
                    {"op": "vox_cylinder", "cx": 0, "cy": 0, "z0": 1, "z1": 2, "radius": 2.2, "ramp": "straw", "shade": 1},
                ],
            },
        ],
    )

    # Base model must be strictly untouched
    assert base.to_dict() == base_snapshot
    assert len(composed.layers) == 3
    assert len(composed.get_layer("farmer_overalls").voxels) > 20
    assert (0, 0, 16) in composed.get_layer("straw_hat").voxels  # attached at head_z + 4 = 16

    # Renders cleanly across 8 angles
    frames = render_voxel_turntable(composed, turns=8, width=48, height=48, ppu=2)
    assert len(frames) == 8
    assert all(any(px[3] > 0 for px in f.pixels) for f in frames)


def test_socket_attachment_tracks_body_height_changes() -> None:
    tall_base = _make_base_human(head_z=18)
    composed = compose_paperdoll(
        tall_base,
        extra_ramps=[{"name": "helmet", "colors": ["#596070", "#828c9e", "#b5bfd1"], "material": "metal"}],
        overlays=[
            {
                "id": "samurai_helmet",
                "role": "hat",
                "attach_socket": "head",
                "ops": [{"op": "vox_box", "x0": -1, "y0": -1, "z0": 0, "x1": 1, "y1": 1, "z1": 1, "ramp": "helmet", "shade": 1}],
            }
        ],
    )
    # head socket is at z = 18 + 4 = 22
    assert (0, 0, 22) in composed.get_layer("samurai_helmet").voxels
    assert (0, 0, 16) not in composed.get_layer("samurai_helmet").voxels
