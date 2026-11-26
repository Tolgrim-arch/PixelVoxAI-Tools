"""Deterministic voxel engine package for PixelAI-Tools (inspired by VoxPix MIT)."""

from pixelai.voxel.camera import VoxelCamera
from pixelai.voxel.materials import MATERIALS, VoxelMaterial, resolve_material
from pixelai.voxel.model import FORMAT_VERSION, MAX_COORD, MIN_COORD, VoxelLayer, VoxelModel, validate_coord
from pixelai.voxel.ramps import (
    MAX_RAMPS,
    MAX_SHADES,
    VoxelPalette,
    VoxelRamp,
    decode_voxel_value,
    encode_voxel_value,
    ramp_from_color,
)
from pixelai.voxel.render import VoxelRenderResult, render_voxel_model, render_voxel_turntable

__all__ = [
    "FORMAT_VERSION",
    "MATERIALS",
    "MAX_COORD",
    "MAX_RAMPS",
    "MAX_SHADES",
    "MIN_COORD",
    "VoxelCamera",
    "VoxelLayer",
    "VoxelMaterial",
    "VoxelModel",
    "VoxelPalette",
    "VoxelRamp",
    "VoxelRenderResult",
    "decode_voxel_value",
    "encode_voxel_value",
    "ramp_from_color",
    "render_voxel_model",
    "render_voxel_turntable",
    "resolve_material",
    "validate_coord",
]
