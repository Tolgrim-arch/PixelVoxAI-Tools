"""Phase V3 tests: 3D point lighting, integer sun-shadow raycasting, and deterministic voxel fluids."""

from __future__ import annotations

from pixelai.voxel import (
    VoxelLayer,
    VoxelModel,
    VoxelPalette,
    VoxelRamp,
    encode_voxel_value,
    ramp_from_color,
    resolve_material,
)
from pixelai.voxel.fluid import fill_basin
from pixelai.voxel.lighting import PointLight, compute_lighting_shade_shift, compute_point_light_energy, is_in_sun_shadow
from pixelai.voxel.primitives import vox_box


def test_sun_shadow_and_point_light_occlusion() -> None:
    stone = ramp_from_color("#828c9e", 4, name="stone")
    pal = VoxelPalette(ramps=[stone])
    layer = VoxelLayer(id="scene", role="terrain", priority=0)
    val = encode_voxel_value(0, 2)
    # Floor at z=0
    vox_box(layer, -4, -4, 0, 4, 4, 0, val)
    # Tall wall blocking sun_dir (-1, 1, 2) from (0, 0, 0) -> (-1, 1, 2)
    vox_box(layer, -2, 0, 1, 0, 2, 4, val)

    model = VoxelModel(palette=pal, layers=[layer], bounds=(16, 16, 16))
    flat = model.flatten()

    assert is_in_sun_shadow((0, 0, 0), flat, model, sun_dir=(-1, 1, 2)) is True
    assert is_in_sun_shadow((3, -3, 0), flat, model, sun_dir=(-1, 1, 2)) is False

    # Point light on same side vs occluded behind wall
    torch = PointLight(position=(2, -2, 1), radius=8.0, intensity=1.0)
    near_e = compute_point_light_energy((1, -2, 0), [torch], flat, model)
    occluded_e = compute_point_light_energy((-3, 2, 0), [torch], flat, model)
    assert near_e > 0.5
    assert occluded_e == 0.0

    shift = compute_lighting_shade_shift((1, -2, 0), flat, model, lights=[torch], sun_shadow=False, ambient_dark=True)
    assert -2 <= shift <= 2


def test_fluid_basin_containment() -> None:
    stone = ramp_from_color("#828c9e", 3, name="stone")
    water = VoxelRamp(
        name="water",
        colors=((50, 100, 150, 255), (79, 164, 196, 255)),
        material=resolve_material("emissive"),
    )
    pal = VoxelPalette(ramps=[stone, water])
    basin = VoxelLayer(id="basin", role="terrain", priority=0)
    v_stone = encode_voxel_value(0, 1)
    # Floor + 4 walls enclosing interior x in [-1, 1], y in [-1, 1], z in [1, 2]
    vox_box(basin, -2, -2, 0, 2, 2, 0, v_stone)
    vox_box(basin, -2, -2, 1, -2, 2, 2, v_stone)
    vox_box(basin, 2, -2, 1, 2, 2, 2, v_stone)
    vox_box(basin, -2, -2, 1, 2, -2, 2, v_stone)
    vox_box(basin, -2, 2, 1, 2, 2, 2, v_stone)

    fluid_layer = VoxelLayer(id="water_fill", role="fluid", priority=5)
    model = VoxelModel(palette=pal, layers=[basin, fluid_layer], bounds=(16, 16, 16))
    filled = fill_basin(model, fluid_layer, start=(0, 0, 1), water_level_z=2, fluid_value=encode_voxel_value(1, 0))
    # Interior is 3 x 3 x 2 = 18 cells
    assert filled == 18
    assert (3, 0, 1) not in fluid_layer.voxels
