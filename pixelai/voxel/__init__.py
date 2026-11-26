"""Deterministic voxel engine package for PixelAI-Tools (inspired by VoxPix MIT)."""

from pixelai.voxel.camera import VoxelCamera
from pixelai.voxel.daycycle import DayCycleState, evaluate_day_cycle
from pixelai.voxel.fluid import ShallowWaterSim, fill_basin, fill_to_level, pour_fluid, tap_fluid
from pixelai.voxel.lightmap import BakedLightmap, bake_lightmap
from pixelai.voxel.materials import MATERIALS, VoxelMaterial, resolve_material
from pixelai.voxel.model import FORMAT_VERSION, MAX_COORD, MIN_COORD, VoxelLayer, VoxelModel, validate_coord
from pixelai.voxel.palettes_io import (
    COMMUNITY_PRESETS,
    load_palette_any,
    load_palette_preset,
    parse_gpl_palette,
    parse_hex_palette,
    verify_palette_colors,
)
from pixelai.voxel.pxl_bridge import export_pxl, export_pxl_file, import_pxl, import_pxl_file
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
from pixelai.voxel.samples import SAMPLE_NAMES, get_sample_model
from pixelai.voxel.weather import WEATHER_MODES, apply_weather_overlay
from pixelai.voxel.world import Door, Floater, Particle, VoxelWorld
from pixelai.voxel.worldgen import WORLD_GENERATORS, WORLD_THEMES, WorldRecipe, generate_world_model

__all__ = [
    "BakedLightmap",
    "COMMUNITY_PRESETS",
    "DayCycleState",
    "Door",
    "FORMAT_VERSION",
    "Floater",
    "MATERIALS",
    "MAX_COORD",
    "MAX_RAMPS",
    "MAX_SHADES",
    "MIN_COORD",
    "Particle",
    "SAMPLE_NAMES",
    "ShallowWaterSim",
    "VoxelCamera",
    "VoxelLayer",
    "VoxelMaterial",
    "VoxelModel",
    "VoxelPalette",
    "VoxelRamp",
    "VoxelRenderResult",
    "VoxelWorld",
    "WEATHER_MODES",
    "WORLD_GENERATORS",
    "WORLD_THEMES",
    "WorldRecipe",
    "apply_weather_overlay",
    "bake_lightmap",
    "decode_voxel_value",
    "encode_voxel_value",
    "evaluate_day_cycle",
    "export_pxl",
    "export_pxl_file",
    "fill_basin",
    "fill_to_level",
    "generate_world_model",
    "get_sample_model",
    "import_pxl",
    "import_pxl_file",
    "load_palette_any",
    "load_palette_preset",
    "parse_gpl_palette",
    "parse_hex_palette",
    "pour_fluid",
    "ramp_from_color",
    "render_voxel_model",
    "render_voxel_turntable",
    "resolve_material",
    "tap_fluid",
    "validate_coord",
    "verify_palette_colors",
]
