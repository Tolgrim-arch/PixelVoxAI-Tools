"""Closed-palette ramp encoding and hue-shifted ramp generation for voxels.

Voxel values are encoded as integers:
    0 = empty
    value = ramp_index * 16 + shade_index + 1
where ramp_index in [0, 63] and shade_index in [0, 15].

Shading shifts shade_index within the ramp rather than multiplying RGB,
preserving strict closed-palette pixel art determinism.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass, field
from typing import Any

from pixelai.color import RGBA, parse_color
from pixelai.palettes import get_palette
from pixelai.voxel.materials import VoxelMaterial, resolve_material

MAX_RAMPS = 64
MAX_SHADES = 16


def encode_voxel_value(ramp_index: int, shade_index: int) -> int:
    """Encode (ramp_index, shade_index) into a non-zero voxel integer."""
    if not (0 <= ramp_index < MAX_RAMPS):
        raise ValueError(f"ramp_index must be in [0, {MAX_RAMPS - 1}], got {ramp_index}")
    if not (0 <= shade_index < MAX_SHADES):
        raise ValueError(f"shade_index must be in [0, {MAX_SHADES - 1}], got {shade_index}")
    return ramp_index * MAX_SHADES + shade_index + 1


def decode_voxel_value(value: int) -> tuple[int, int]:
    """Decode a positive voxel integer into (ramp_index, shade_index)."""
    if value <= 0:
        raise ValueError(f"Cannot decode empty/negative voxel value: {value}")
    zero_based = value - 1
    ramp_index = zero_based // MAX_SHADES
    shade_index = zero_based % MAX_SHADES
    if ramp_index >= MAX_RAMPS:
        raise ValueError(f"Voxel value {value} exceeds MAX_RAMPS ({MAX_RAMPS})")
    return ramp_index, shade_index


def rgba_to_hex(rgba: RGBA) -> str:
    """Convert an RGBA tuple to lowercase #rrggbb hex string."""
    r, g, b, _a = rgba
    return f"#{r:02x}{g:02x}{b:02x}"


def ramp_from_color(
    base_color: str | RGBA,
    steps: int = 4,
    hue_shift: float = 0.08,
    name: str = "custom",
    material: str = "solid",
    emissive: bool = False,
) -> VoxelRamp:
    """Generate a pixel-art hue-shifted ramp (cool shadows, warm highlights)."""
    if not (1 <= steps <= MAX_SHADES):
        raise ValueError(f"steps must be in [1, {MAX_SHADES}], got {steps}")
    rgba = parse_color(base_color) if isinstance(base_color, str) else base_color
    r, g, b, a = rgba
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    if steps == 1:
        return VoxelRamp(
            name=name,
            colors=(rgba,),
            material=resolve_material(material, emissive=emissive),
        )
    mid = (steps - 1) / 2.0
    colors: list[RGBA] = []
    for i in range(steps):
        t = (i - mid) / max(mid, 1.0)  # -1.0 (darkest) .. +1.0 (lightest)
        # Shadows shift cooler (toward blue ~0.66), highlights shift warmer (toward yellow ~0.14)
        new_h = (h - t * hue_shift) % 1.0
        new_l = max(0.06, min(0.96, l + t * 0.24))
        new_s = max(0.05, min(1.0, s + (0.06 if t < 0 else -0.04) * abs(t)))
        nr, ng, nb = colorsys.hls_to_rgb(new_h, new_l, new_s)
        colors.append((round(nr * 255), round(ng * 255), round(nb * 255), a))
    return VoxelRamp(
        name=name,
        colors=tuple(colors),
        material=resolve_material(material, emissive=emissive),
    )


@dataclass(frozen=True, slots=True)
class VoxelRamp:
    """A single material ramp ordered from darkest shade (0) to lightest shade (N-1)."""

    name: str
    colors: tuple[RGBA, ...]
    material: VoxelMaterial = field(default_factory=lambda: resolve_material("solid"))

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("VoxelRamp name must be non-empty")
        if not (1 <= len(self.colors) <= MAX_SHADES):
            raise ValueError(
                f"VoxelRamp {self.name!r} must have 1..{MAX_SHADES} colors, got {len(self.colors)}"
            )

    def color_at(self, shade_index: int, shift: int = 0) -> RGBA:
        """Return clamped RGBA at (shade_index + shift) within this ramp."""
        idx = max(0, min(len(self.colors) - 1, shade_index + shift))
        return self.colors[idx]

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "colors": [rgba_to_hex(c) for c in self.colors],
            "material": self.material.name,
        }
        if self.material.emissive and self.material.name != "emissive":
            out["emissive"] = True
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any], palette_lookup: dict[str, RGBA] | None = None) -> VoxelRamp:
        raw_colors = data.get("colors", [])
        if not isinstance(raw_colors, list) or not raw_colors:
            raise ValueError(f"VoxelRamp {data.get('name')!r} requires a non-empty 'colors' list")
        parsed = tuple(parse_color(c, palette_lookup) for c in raw_colors)
        mat = resolve_material(
            name=data.get("material", "solid"),
            props=data.get("props"),
            emissive=bool(data.get("emissive", False)),
        )
        return cls(name=str(data["name"]), colors=parsed, material=mat)


@dataclass(slots=True)
class VoxelPalette:
    """Closed palette of up to 64 ramps plus optional outline color."""

    ramps: list[VoxelRamp] = field(default_factory=list)
    outline: RGBA = (13, 12, 18, 255)
    palette_ref: str | None = None

    def __post_init__(self) -> None:
        if len(self.ramps) > MAX_RAMPS:
            raise ValueError(f"VoxelPalette supports at most {MAX_RAMPS} ramps, got {len(self.ramps)}")

    def ramp_index(self, name: str) -> int:
        """Find ramp index by name."""
        for idx, ramp in enumerate(self.ramps):
            if ramp.name == name:
                return idx
        available = ", ".join(r.name for r in self.ramps)
        raise KeyError(f"Unknown ramp {name!r}. Available: {available}")

    def resolve_color(self, voxel_value: int, shade_shift: int = 0) -> RGBA:
        """Resolve a positive voxel value with optional lighting shade shift."""
        r_idx, s_idx = decode_voxel_value(voxel_value)
        if r_idx >= len(self.ramps):
            raise IndexError(f"Voxel value {voxel_value} references missing ramp index {r_idx}")
        ramp = self.ramps[r_idx]
        if ramp.material.emissive:
            shade_shift = 0
        return ramp.color_at(s_idx, shade_shift)

    def resolve_material(self, voxel_value: int) -> VoxelMaterial:
        """Return the material for a positive voxel value."""
        r_idx, _ = decode_voxel_value(voxel_value)
        if r_idx >= len(self.ramps):
            raise IndexError(f"Voxel value {voxel_value} references missing ramp index {r_idx}")
        return self.ramps[r_idx].material

    def all_colors(self) -> frozenset[RGBA]:
        """Return the exact closed set of allowed RGBA colors in this palette."""
        colors: set[RGBA] = {self.outline}
        for ramp in self.ramps:
            colors.update(ramp.colors)
        return frozenset(colors)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ramps": [r.to_dict() for r in self.ramps],
            "outline": rgba_to_hex(self.outline),
        }
        if self.palette_ref:
            out["palette_ref"] = self.palette_ref
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoxelPalette:
        palette_ref = data.get("palette_ref")
        lookup = get_palette(palette_ref) if isinstance(palette_ref, str) and palette_ref else None
        raw_ramps = data.get("ramps", [])
        ramps = [VoxelRamp.from_dict(r, lookup) for r in raw_ramps]
        raw_outline = data.get("outline")
        if raw_outline is not None:
            outline = parse_color(raw_outline, lookup)
        elif lookup and "ink" in lookup:
            outline = lookup["ink"]
        else:
            outline = (13, 12, 18, 255)
        return cls(ramps=ramps, outline=outline, palette_ref=palette_ref)
