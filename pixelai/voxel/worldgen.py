"""Procedural 2.5D voxel world generator from JSON recipes and themes (inspired by VoxPix MIT)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from pixelai.color import parse_color
from pixelai.voxel.model import Coord3, VoxelLayer, VoxelModel
from pixelai.voxel.primitives import vox_box, vox_ellipsoid
from pixelai.voxel.ramps import VoxelPalette, encode_voxel_value, ramp_from_color

WORLD_THEMES: dict[str, dict[str, Any]] = {
    "medieval": {
        "generator": "courtyard",
        "outline": "#1a1724",
        "hour": 14.0,
        "weather": "none",
        "colors": {
            "floor": ("#4f8f3b", "solid", False),
            "wall": ("#7c8496", "solid", False),
            "wood": ("#8f563b", "solid", False),
            "liquid": ("#2e7fb8", "glass", False),
            "foliage": ("#397336", "foliage", False),
            "accent": ("#a83d3b", "solid", False),
            "light": ("#ffcf4a", "emissive", True),
        },
    },
    "garden": {
        "generator": "terrain",
        "outline": "#1c241b",
        "hour": 11.0,
        "weather": "none",
        "colors": {
            "floor": ("#63a84a", "solid", False),
            "wall": ("#9a9488", "solid", False),
            "wood": ("#8a5a3a", "solid", False),
            "liquid": ("#38a4d4", "glass", False),
            "foliage": ("#3d8c40", "foliage", False),
            "accent": ("#e86f8c", "solid", False),
            "light": ("#ffe680", "emissive", True),
        },
    },
    "neon": {
        "generator": "rooms",
        "outline": "#0c0a18",
        "hour": 22.0,
        "weather": "rain",
        "colors": {
            "floor": ("#2a2d44", "solid", False),
            "wall": ("#43496b", "metal", False),
            "wood": ("#5c4a72", "solid", False),
            "liquid": ("#00e5ff", "emissive", True),
            "foliage": ("#ff3ea5", "emissive", True),
            "accent": ("#ff3ea5", "emissive", True),
            "light": ("#00f5d4", "emissive", True),
        },
    },
    "toxic": {
        "generator": "labyrinth",
        "outline": "#101812",
        "hour": 20.0,
        "weather": "fog",
        "colors": {
            "floor": ("#3b4238", "solid", False),
            "wall": ("#586352", "solid", False),
            "wood": ("#6e5a3b", "solid", False),
            "liquid": ("#7cff2e", "emissive", True),
            "foliage": ("#4e7a34", "foliage", False),
            "accent": ("#d4a72c", "solid", False),
            "light": ("#aaff44", "emissive", True),
        },
    },
    "office": {
        "generator": "rooms",
        "outline": "#1c1f2b",
        "hour": 13.0,
        "weather": "none",
        "colors": {
            "floor": ("#9aa4b2", "solid", False),
            "wall": ("#d4d8e0", "solid", False),
            "wood": ("#9c6b43", "solid", False),
            "liquid": ("#4692c8", "glass", False),
            "foliage": ("#498c4d", "foliage", False),
            "accent": ("#3b6ec4", "solid", False),
            "light": ("#fff4c2", "emissive", True),
        },
    },
}

WORLD_GENERATORS = ("terrain", "rooms", "courtyard", "labyrinth")


@dataclass(slots=True)
class WorldRecipe:
    """Declarative JSON recipe for procedural 2.5D voxel world generation."""

    generator: str = "courtyard"
    seed: int = 1337
    width: int = 32
    depth: int = 32
    height: int = 16
    theme: str = "medieval"
    hour: float | None = None
    weather: str | None = None
    columns: int = 4
    vegetation: int = 6
    lights: int = 4
    colors: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_theme(cls, theme: str, *, seed: int = 1337, width: int = 32, depth: int = 32) -> WorldRecipe:
        key = theme.strip().lower()
        if key not in WORLD_THEMES:
            raise ValueError(f"Unknown world theme {theme!r}. Available: {', '.join(sorted(WORLD_THEMES))}")
        t = WORLD_THEMES[key]
        return cls(
            generator=t["generator"],
            seed=seed,
            width=width,
            depth=depth,
            theme=key,
            hour=t["hour"],
            weather=t["weather"],
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldRecipe:
        theme = str(data.get("theme", "medieval")).strip().lower()
        base = WORLD_THEMES.get(theme, WORLD_THEMES["medieval"])
        size = data.get("size")
        width = int(data.get("width", size[0] if isinstance(size, (list, tuple)) and len(size) >= 2 else 32))
        depth = int(data.get("depth", size[1] if isinstance(size, (list, tuple)) and len(size) >= 2 else 32))
        height = int(data.get("height", size[2] if isinstance(size, (list, tuple)) and len(size) >= 3 else 16))
        return cls(
            generator=str(data.get("generator", base["generator"])).strip().lower(),
            seed=int(data.get("seed", 1337)),
            width=max(12, min(96, width)),
            depth=max(12, min(96, depth)),
            height=max(8, min(48, height)),
            theme=theme if theme in WORLD_THEMES else "medieval",
            hour=float(data["hour"]) if "hour" in data and data["hour"] is not None else float(base["hour"]),
            weather=str(data.get("weather", base["weather"])).strip().lower(),
            columns=int(data.get("columns", 4)),
            vegetation=int(data.get("vegetation", 6)),
            lights=int(data.get("lights", 4)),
            colors=dict(data.get("colors", {})),
        )


def _value_noise(x: float, y: float, seed: int) -> float:
    """Deterministic 2D value noise in [0.0, 1.0]."""
    ix = math.floor(x)
    iy = math.floor(y)
    fx = x - ix
    fy = y - iy

    def _h(a: int, b: int) -> float:
        n = (a * 374761393 + b * 668265263 + seed * 1442695041) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0

    u = fx * fx * (3.0 - 2.0 * fx)
    v = fy * fy * (3.0 - 2.0 * fy)
    a = _h(ix, iy)
    b = _h(ix + 1, iy)
    c = _h(ix, iy + 1)
    d = _h(ix + 1, iy + 1)
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v


def _build_theme_palette(recipe: WorldRecipe) -> VoxelPalette:
    theme_spec = WORLD_THEMES.get(recipe.theme, WORLD_THEMES["medieval"])
    ramps = []
    for key in ("floor", "wall", "wood", "liquid", "foliage", "accent", "light"):
        hex_col, mat, is_emissive = theme_spec["colors"][key]
        if key in recipe.colors:
            hex_col = recipe.colors[key]
        ramps.append(
            ramp_from_color(
                hex_col,
                steps=4,
                name=key,
                material=mat,
                emissive=is_emissive,
            )
        )
    return VoxelPalette(ramps=ramps, outline=parse_color(theme_spec["outline"]))


def generate_world_model(recipe: WorldRecipe) -> tuple[VoxelModel, dict[str, Any]]:
    """Generate a procedural 2.5D VoxelModel and world metadata from `recipe`."""
    if recipe.generator not in WORLD_GENERATORS:
        raise ValueError(
            f"Unknown world generator {recipe.generator!r}. Available: {', '.join(WORLD_GENERATORS)}"
        )

    rng = random.Random(recipe.seed)
    palette = _build_theme_palette(recipe)
    model = VoxelModel(palette=palette, bounds=(recipe.width, recipe.depth, recipe.height), pivot=(0, 0, 0))

    terrain = VoxelLayer(id="terrain", role="terrain", priority=0)
    arch = VoxelLayer(id="architecture", role="architecture", priority=1)
    water_layer = VoxelLayer(id="water", role="water", priority=2)
    veg = VoxelLayer(id="vegetation", role="foliage", priority=3)
    lights_layer = VoxelLayer(id="lights", role="emissive", priority=4)
    for lyr in (terrain, arch, water_layer, veg, lights_layer):
        model.add_layer(lyr)

    v_floor = encode_voxel_value(0, 2)
    v_wall = encode_voxel_value(1, 2)
    v_wood = encode_voxel_value(2, 2)
    v_liquid = encode_voxel_value(3, 2)
    v_foliage = encode_voxel_value(4, 2)
    v_accent = encode_voxel_value(5, 2)
    v_light = encode_voxel_value(6, 3)

    hx = recipe.width // 2
    hy = recipe.depth // 2
    x0, x1 = -hx, hx - 1
    y0, y1 = -hy, hy - 1

    columns_placed: list[Coord3] = []
    furniture_placed: list[Coord3] = []
    lights_placed: list[Coord3] = []
    doors_placed: list[Coord3] = []
    veg_placed: list[Coord3] = []
    water_coords: list[Coord3] = []

    if recipe.generator == "terrain":
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                n = _value_noise(x * 0.14, y * 0.14, recipe.seed)
                h = 1 + int(n * 3.5)
                if n < 0.28:
                    terrain.set(x, y, 0, v_wall)
                    water_layer.set(x, y, 1, v_liquid)
                    water_coords.append((x, y, 1))
                else:
                    for z in range(h):
                        terrain.set(x, y, z, v_floor if z == h - 1 else v_wall)
    elif recipe.generator == "rooms":
        vox_box(terrain, x0, y0, 0, x1, y1, 0, v_floor)
        # Perimeter walls
        vox_box(arch, x0, y0, 1, x1, y0, 4, v_wall)
        vox_box(arch, x0, y1, 1, x1, y1, 4, v_wall)
        vox_box(arch, x0, y0, 1, x0, y1, 4, v_wall)
        vox_box(arch, x1, y0, 1, x1, y1, 4, v_wall)
        # Interior dividing wall with doorway
        vox_box(arch, 0, y0 + 1, 1, 0, y1 - 1, 4, v_wall)
        vox_box(arch, 0, -1, 1, 0, 1, 3, 0)
        doors_placed.append((0, 0, 1))
        # Central liquid channel
        for x in range(x0 + 2, x1 - 1):
            if x != 0:
                water_layer.set(x, 0, 0, v_liquid)
                water_coords.append((x, 0, 0))
    elif recipe.generator == "labyrinth":
        vox_box(terrain, x0, y0, 0, x1, y1, 0, v_floor)
        for y in range(y0, y1 + 1, 4):
            for x in range(x0, x1 + 1, 4):
                if rng.random() < 0.55 and (abs(x) > 2 or abs(y) > 2):
                    vox_box(arch, x, y, 1, min(x + 2, x1), min(y + 1, y1), 3, v_wall)
                elif rng.random() < 0.25:
                    water_layer.set(x, y, 0, v_liquid)
                    water_coords.append((x, y, 0))
    else:  # courtyard
        vox_box(terrain, x0, y0, 0, x1, y1, 0, v_floor)
        # Perimeter low wall
        vox_box(arch, x0, y0, 1, x1, y0, 2, v_wall)
        vox_box(arch, x0, y1, 1, x1, y1, 2, v_wall)
        vox_box(arch, x0, y0, 1, x0, y1, 2, v_wall)
        vox_box(arch, x1, y0, 1, x1, y1, 2, v_wall)
        # Central fountain/pond
        vox_box(water_layer, -2, -2, 0, 2, 2, 0, v_liquid)
        for wy in range(-2, 3):
            for wx in range(-2, 3):
                water_coords.append((wx, wy, 0))
        arch.set(0, 0, 1, v_accent)
        arch.set(0, 0, 2, v_accent)

    # Columns
    for _ in range(max(0, recipe.columns)):
        cx = rng.randint(x0 + 3, x1 - 3)
        cy = rng.randint(y0 + 3, y1 - 3)
        if abs(cx) <= 2 and abs(cy) <= 2:
            continue
        vox_box(arch, cx, cy, 1, cx, cy, 5, v_wall)
        columns_placed.append((cx, cy, 1))

    # Furniture / crates
    for _ in range(3):
        fx = rng.randint(x0 + 3, x1 - 3)
        fy = rng.randint(y0 + 3, y1 - 3)
        if abs(fx) <= 2 and abs(fy) <= 2:
            continue
        vox_box(arch, fx, fy, 1, fx + 1, fy, 1, v_wood)
        furniture_placed.append((fx, fy, 1))

    # Vegetation
    for _ in range(max(0, recipe.vegetation)):
        tx = rng.randint(x0 + 3, x1 - 3)
        ty = rng.randint(y0 + 3, y1 - 3)
        if abs(tx) <= 3 and abs(ty) <= 3:
            continue
        vox_box(veg, tx, ty, 1, tx, ty, 3, v_wood)
        vox_ellipsoid(veg, tx, ty, 5, 1.8, 1.8, 1.6, v_foliage)
        veg_placed.append((tx, ty, 1))

    # Emissive lights
    for _ in range(max(0, recipe.lights)):
        lx = rng.randint(x0 + 2, x1 - 2)
        ly = rng.randint(y0 + 2, y1 - 2)
        arch.set(lx, ly, 1, v_wood)
        lights_layer.set(lx, ly, 2, v_light)
        lights_placed.append((lx, ly, 2))

    meta: dict[str, Any] = {
        "spawn": (0, 0, 1),
        "columns": columns_placed,
        "furniture": furniture_placed,
        "lights": lights_placed,
        "doors": doors_placed,
        "vegetation": veg_placed,
        "water_coords": water_coords,
    }
    return model, meta
