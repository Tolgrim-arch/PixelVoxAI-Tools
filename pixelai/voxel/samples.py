"""Built-in voxel sample models (matching VoxPix's `sample` CLI target)."""

from __future__ import annotations

from pixelai.voxel.model import VoxelLayer, VoxelModel
from pixelai.voxel.palettes_io import load_palette_preset
from pixelai.voxel.primitives import vox_box, vox_ellipsoid
from pixelai.voxel.ramps import encode_voxel_value

SAMPLE_NAMES = ("sample", "medieval", "torch", "tree", "house")


def _new_layer(model: VoxelModel, layer_id: str, role: str, priority: int) -> VoxelLayer:
    layer = VoxelLayer(id=layer_id, role=role, priority=priority)
    model.add_layer(layer)
    return layer


def build_sample_medieval() -> VoxelModel:
    """Build a compact 24x24x18 medieval diorama: tower, cottage, river, bridge, trees, lanterns."""
    palette = load_palette_preset("medieval", steps=4)
    model = VoxelModel(palette=palette, bounds=(24, 24, 18), pivot=(0, 0, 0))
    terrain = _new_layer(model, "terrain", "terrain", 0)
    structures = _new_layer(model, "structures", "architecture", 1)
    water_layer = _new_layer(model, "water", "water", 2)
    vegetation = _new_layer(model, "vegetation", "foliage", 3)
    lights = _new_layer(model, "lights", "emissive", 4)

    grass = encode_voxel_value(0, 2)
    dirt = encode_voxel_value(1, 1)
    stone = encode_voxel_value(2, 2)
    stone_dark = encode_voxel_value(2, 1)
    wood = encode_voxel_value(3, 2)
    roof = encode_voxel_value(4, 2)
    water = encode_voxel_value(5, 2)
    foliage = encode_voxel_value(6, 2)
    torch = encode_voxel_value(7, 3)

    # Base ground: dirt under grass, with a river carved along x in [-2..2]
    vox_box(terrain, -11, -11, 0, 11, 11, 0, dirt)
    vox_box(terrain, -11, -11, 1, 11, 11, 1, grass)
    for y in range(-11, 12):
        for x in range(-2, 3):
            terrain.set(x, y, 1, 0)
            water_layer.set(x, y, 1, water)

    # Wooden bridge across the river at y in [-1..1]
    vox_box(structures, -3, -1, 2, 3, 1, 2, wood)

    # Stone watchtower on the west bank (-9..-4, -8..-3)
    vox_box(structures, -9, -8, 2, -4, -3, 10, stone)
    vox_box(structures, -8, -7, 3, -5, -4, 9, 0)
    for bx in (-9, -7, -4):
        structures.set(bx, -8, 11, stone_dark)
        structures.set(bx, -3, 11, stone_dark)
    lights.set(-6, -5, 11, torch)

    # Small cottage on the east bank (4..9, -7..-2)
    vox_box(structures, 4, -7, 2, 9, -2, 6, wood)
    vox_box(structures, 5, -6, 3, 8, -3, 5, 0)
    vox_box(structures, 3, -8, 7, 10, -1, 7, roof)
    vox_box(structures, 4, -7, 8, 9, -2, 8, roof)
    vox_box(structures, 5, -6, 9, 8, -3, 9, roof)
    lights.set(4, -1, 4, torch)

    # Two trees
    for tx, ty in ((-7, 6), (7, 6)):
        vox_box(vegetation, tx, ty, 2, tx, ty, 5, wood)
        vox_ellipsoid(vegetation, tx, ty, 7, 2.6, 2.6, 2.4, foliage)

    # Bridge lantern
    lights.set(-3, -2, 3, torch)
    return model


def build_sample_torch() -> VoxelModel:
    """Build a small standing torch sample with emissive flame."""
    palette = load_palette_preset("medieval", steps=4)
    model = VoxelModel(palette=palette, bounds=(8, 8, 12), pivot=(0, 0, 0))
    body = _new_layer(model, "body", "prop", 0)
    flame = _new_layer(model, "flame", "emissive", 1)
    wood = encode_voxel_value(3, 2)
    stone = encode_voxel_value(2, 1)
    torch = encode_voxel_value(7, 3)
    vox_box(body, -1, -1, 0, 1, 1, 0, stone)
    vox_box(body, 0, 0, 1, 0, 0, 6, wood)
    vox_box(flame, 0, 0, 7, 0, 0, 8, torch)
    return model


def build_sample_tree() -> VoxelModel:
    """Build a standalone voxel oak tree sample."""
    palette = load_palette_preset("medieval", steps=4)
    model = VoxelModel(palette=palette, bounds=(14, 14, 16), pivot=(0, 0, 0))
    trunk = _new_layer(model, "trunk", "wood", 0)
    canopy = _new_layer(model, "canopy", "foliage", 1)
    wood = encode_voxel_value(3, 2)
    foliage = encode_voxel_value(6, 2)
    vox_box(trunk, -1, -1, 0, 1, 1, 5, wood)
    vox_ellipsoid(canopy, 0, 0, 8, 4.2, 4.2, 3.6, foliage)
    return model


def build_sample_house() -> VoxelModel:
    """Build a standalone medieval cottage sample."""
    palette = load_palette_preset("medieval", steps=4)
    model = VoxelModel(palette=palette, bounds=(14, 14, 14), pivot=(0, 0, 0))
    base = _new_layer(model, "base", "architecture", 0)
    lights = _new_layer(model, "lights", "emissive", 1)
    stone = encode_voxel_value(2, 2)
    wood = encode_voxel_value(3, 2)
    roof = encode_voxel_value(4, 2)
    torch = encode_voxel_value(7, 3)
    vox_box(base, -4, -4, 0, 4, 4, 0, stone)
    vox_box(base, -3, -3, 1, 3, 3, 5, wood)
    vox_box(base, -4, -4, 6, 4, 4, 6, roof)
    vox_box(base, -3, -3, 7, 3, 3, 7, roof)
    vox_box(base, -2, -2, 8, 2, 2, 8, roof)
    lights.set(0, -4, 3, torch)
    return model


def get_sample_model(name: str = "sample") -> VoxelModel:
    """Return a built-in sample VoxelModel by name."""
    key = name.strip().lower()
    if key in ("sample", "medieval"):
        return build_sample_medieval()
    if key == "torch":
        return build_sample_torch()
    if key == "tree":
        return build_sample_tree()
    if key == "house":
        return build_sample_house()
    raise ValueError(f"Unknown sample model {name!r}. Available: {', '.join(SAMPLE_NAMES)}")
