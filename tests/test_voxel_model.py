"""Phase V0 tests: Sparse VoxelModel, semantic layers, anchor sockets, and closed-palette ramps."""

from __future__ import annotations

from pathlib import Path
import pytest

from pixelai.schema import OP_SPECS, lint_op_fields
from pixelai.voxel import (
    FORMAT_VERSION,
    MATERIALS,
    MAX_COORD,
    MIN_COORD,
    VoxelLayer,
    VoxelModel,
    VoxelPalette,
    VoxelRamp,
    decode_voxel_value,
    encode_voxel_value,
    ramp_from_color,
    resolve_material,
)


def test_encode_decode_voxel_value_roundtrip() -> None:
    for r_idx in (0, 1, 15, 63):
        for s_idx in (0, 3, 15):
            val = encode_voxel_value(r_idx, s_idx)
            assert val > 0
            assert decode_voxel_value(val) == (r_idx, s_idx)


def test_encode_decode_rejects_invalid_ranges() -> None:
    with pytest.raises(ValueError):
        encode_voxel_value(-1, 0)
    with pytest.raises(ValueError):
        encode_voxel_value(64, 0)
    with pytest.raises(ValueError):
        encode_voxel_value(0, 16)
    with pytest.raises(ValueError):
        decode_voxel_value(0)
    with pytest.raises(ValueError):
        decode_voxel_value(-5)


def test_materials_and_overrides() -> None:
    solid = resolve_material("solid")
    assert solid.light == 0.0 and solid.bed is True and solid.blocks is True
    foliage = resolve_material("follaje")  # VoxPix alias
    assert foliage.name == "foliage" and foliage.light == 0.5 and foliage.backlit == 0.25
    custom_glass = resolve_material("glass", props={"light": 0.6})
    assert custom_glass.light == 0.6 and custom_glass.bed is True
    emissive_stone = resolve_material("solid", emissive=True)
    assert emissive_stone.emissive is True
    with pytest.raises(ValueError):
        resolve_material("unknown_mat")
    with pytest.raises(ValueError):
        resolve_material("glass", props={"light": 1.5})


def test_ramp_from_color_and_closed_palette() -> None:
    skin = ramp_from_color("#e0ac69", steps=4, name="skin")
    glow = VoxelRamp(
        name="glow",
        colors=((255, 170, 51, 255), (255, 240, 153, 255)),
        material=resolve_material("emissive"),
    )
    pal = VoxelPalette(ramps=[skin, glow])
    allowed = pal.all_colors()

    v_skin = encode_voxel_value(0, 1)
    assert pal.resolve_color(v_skin, shade_shift=-10) == skin.colors[0]
    assert pal.resolve_color(v_skin, shade_shift=+10) == skin.colors[-1]
    assert pal.resolve_color(v_skin, shade_shift=1) in allowed

    # Emissive ignores shade shift
    v_glow = encode_voxel_value(1, 0)
    assert pal.resolve_color(v_glow, shade_shift=-3) == glow.colors[0]
    assert pal.resolve_color(v_glow, shade_shift=+3) == glow.colors[0]


def test_layer_priority_locking_and_bounds() -> None:
    body = VoxelLayer(id="body_base", role="body", priority=0)
    body.set(0, 0, 0, encode_voxel_value(0, 1))
    body.set(0, 0, 1, encode_voxel_value(0, 2))
    body.locked = True

    with pytest.raises(PermissionError):
        body.set(0, 0, 0, encode_voxel_value(0, 3))

    outfit = VoxelLayer(id="shirt", role="outfit", priority=10)
    outfit.set(0, 0, 1, encode_voxel_value(1, 1))

    with pytest.raises(ValueError):
        outfit.set(MAX_COORD + 1, 0, 0, 1)
    with pytest.raises(ValueError):
        outfit.set(0, MIN_COORD - 1, 0, 1)
    with pytest.raises(TypeError):
        outfit.set(True, 0, 0, 1)  # type: ignore[arg-type]

    pal = VoxelPalette(ramps=[ramp_from_color("#c68642", 4, name="skin"), ramp_from_color("#3b5dc9", 4, name="cloth")])
    model = VoxelModel(palette=pal, layers=[outfit, body], sockets={"head": (0, 0, 26)})
    flat = model.flatten()
    assert flat[(0, 0, 0)] == encode_voxel_value(0, 1)
    assert flat[(0, 0, 1)] == encode_voxel_value(1, 1)  # higher priority outfit wins

    outfit.visible = False
    assert model.flatten()[(0, 0, 1)] == encode_voxel_value(0, 2)


def test_voxel_model_json_roundtrip_and_palette_ref(tmp_path: Path) -> None:
    raw = {
        "format": FORMAT_VERSION,
        "bounds": {"w": 32, "d": 32, "h": 48},
        "pivot": [0, 0, 0],
        "palette_ref": "cozy24",
        "ramps": [
            {"name": "wood", "colors": ["wood_d", "wood", "wood_l"], "material": "solid"},
            {"name": "leaf", "colors": ["grass_d", "grass", "grass_l"], "material": "foliage"},
        ],
        "sockets": {"head": [0, 0, 26], "hand_r": [7, 0, 14]},
        "layers": [
            {"id": "body_base", "role": "body", "priority": 0, "locked": True, "voxels": [[0, 0, 0, 2], [0, 0, 1, 18]]}
        ],
    }
    model = VoxelModel.from_dict(raw)
    out_file = tmp_path / "base_human.vox.json"
    model.save(out_file)
    reloaded = VoxelModel.load(out_file)

    assert reloaded.to_dict() == model.to_dict()
    assert reloaded.sockets["head"] == (0, 0, 26)
    assert reloaded.get_layer("body_base").locked is True
    assert reloaded.palette.resolve_material(18).name == "foliage"


def test_schema_registration_for_voxel_model() -> None:
    assert "voxel_model" in OP_SPECS
    warnings = lint_op_fields({"op": "voxel_model", "yaw": 45, "elevation": 30, "layers": []})
    assert warnings == []
    bad_warnings = lint_op_fields({"op": "voxel_model", "ywa": 45})
    assert len(bad_warnings) == 1 and "yaw" in bad_warnings[0]
