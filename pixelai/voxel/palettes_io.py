"""External palette importers (.hex Lospec, .gpl GIMP), community presets, and palette verification."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pixelai.canvas import Canvas
from pixelai.color import RGBA, parse_color
from pixelai.voxel.ramps import MAX_RAMPS, VoxelPalette, VoxelRamp, ramp_from_color, rgba_to_hex

COMMUNITY_PRESETS: dict[str, dict[str, Any]] = {
    "pico8": {
        "outline": "#1d2b53",
        "colors": [
            ("navy", "#1d2b53"),
            ("plum", "#7e2553"),
            ("pine", "#008751"),
            ("brown", "#ab5236"),
            ("slate", "#5f574f"),
            ("silver", "#c2c3c7"),
            ("white", "#fff1e8"),
            ("red", "#ff004d"),
            ("orange", "#ffa300"),
            ("yellow", "#ffec27"),
            ("green", "#00e436"),
            ("blue", "#29adff"),
            ("indigo", "#83769c"),
            ("pink", "#ff77a8"),
            ("peach", "#ffccaa"),
        ],
    },
    "endesga32": {
        "outline": "#181425",
        "colors": [
            ("wood_dark", "#743f39"),
            ("wood_mid", "#b86f50"),
            ("sand", "#e4a672"),
            ("gold", "#feae34"),
            ("sun", "#fee761"),
            ("leaf_mid", "#63c74d"),
            ("leaf_dark", "#3e8948"),
            ("pine", "#265c42"),
            ("water_deep", "#124e89"),
            ("water_mid", "#0099db"),
            ("sky", "#2ce8f5"),
            ("stone_dark", "#3a4466"),
            ("stone_mid", "#5a6988"),
            ("stone_light", "#8b9bb4"),
            ("cream", "#ffffff"),
            ("crimson", "#e43b44"),
            ("brick", "#9e2835"),
            ("violet", "#68386c"),
        ],
    },
    "aap64": {
        "outline": "#060608",
        "colors": [
            ("charcoal", "#141013"),
            ("iron", "#3b1725"),
            ("bark", "#73172d"),
            ("rust", "#b4202a"),
            ("flame", "#df3e23"),
            ("amber", "#fa6a0a"),
            ("gold", "#f9a31b"),
            ("lemon", "#ffd541"),
            ("cream", "#fffc40"),
            ("moss", "#59c135"),
            ("forest", "#14a02e"),
            ("emerald", "#1a7a3e"),
            ("teal", "#249fde"),
            ("cobalt", "#285cc4"),
            ("stone", "#6d758d"),
            ("mist", "#b3b9d1"),
        ],
    },
    "medieval": {
        "outline": "#1a1724",
        "colors": [
            ("grass", "#4f8f3b"),
            ("dirt", "#8a5a3a"),
            ("stone", "#7c8496"),
            ("wood", "#8f563b"),
            ("roof", "#a83d3b"),
            ("water", "#2e7fb8"),
            ("foliage", "#397336"),
            ("torch", "#ffcf4a"),
        ],
        "materials": {
            "water": ("glass", False),
            "foliage": ("foliage", False),
            "torch": ("emissive", True),
        },
    },
}

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def parse_hex_palette(text: str, steps: int = 4, hue_shift: float = 0.08) -> VoxelPalette:
    """Parse a Lospec .hex file (one RRGGBB per line) into a hue-shifted VoxelPalette."""
    ramps: list[VoxelRamp] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") and not _HEX_RE.match(raw):
            continue
        m = _HEX_RE.match(raw)
        if not m:
            continue
        if len(ramps) >= MAX_RAMPS:
            break
        hex_code = f"#{m.group(1).lower()}"
        ramps.append(
            ramp_from_color(
                hex_code,
                steps=steps,
                hue_shift=hue_shift,
                name=f"c{len(ramps):02d}",
            )
        )
    if not ramps:
        raise ValueError("No valid hex colors found in .hex palette")
    return VoxelPalette(ramps=ramps)


def parse_gpl_palette(text: str, steps: int = 4, hue_shift: float = 0.08) -> VoxelPalette:
    """Parse a GIMP .gpl palette file into a hue-shifted VoxelPalette."""
    ramps: list[VoxelRamp] = []
    seen_names: set[str] = set()
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith(("GIMP Palette", "Name:", "Columns:")):
            continue
        parts = raw.split(None, 3)
        if len(parts) < 3:
            continue
        try:
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
            continue
        if len(ramps) >= MAX_RAMPS:
            break
        base_name = parts[3].strip().lower().replace(" ", "_") if len(parts) == 4 else f"c{len(ramps):02d}"
        if not base_name or base_name in seen_names:
            base_name = f"c{len(ramps):02d}"
        seen_names.add(base_name)
        ramps.append(
            ramp_from_color(
                (r, g, b, 255),
                steps=steps,
                hue_shift=hue_shift,
                name=base_name,
            )
        )
    if not ramps:
        raise ValueError("No valid RGB entries found in .gpl palette")
    return VoxelPalette(ramps=ramps)


def load_palette_preset(name: str, steps: int = 4, hue_shift: float = 0.08) -> VoxelPalette:
    """Load a built-in community palette preset by name."""
    key = name.strip().lower()
    if key not in COMMUNITY_PRESETS:
        raise ValueError(
            f"Unknown palette preset {name!r}. Available: {', '.join(sorted(COMMUNITY_PRESETS))}"
        )
    spec = COMMUNITY_PRESETS[key]
    materials = spec.get("materials", {})
    ramps: list[VoxelRamp] = []
    for rname, hex_color in spec["colors"]:
        mat_name, is_emissive = materials.get(rname, ("solid", False))
        ramps.append(
            ramp_from_color(
                hex_color,
                steps=steps,
                hue_shift=hue_shift,
                name=rname,
                material=mat_name,
                emissive=is_emissive,
            )
        )
    return VoxelPalette(ramps=ramps, outline=parse_color(spec["outline"]))


def load_palette_any(source: str | Path, steps: int = 4, hue_shift: float = 0.08) -> VoxelPalette:
    """Load a VoxelPalette from a preset name, .hex, .gpl, or .json file."""
    s = str(source).strip()
    if s.lower() in COMMUNITY_PRESETS:
        return load_palette_preset(s, steps=steps, hue_shift=hue_shift)
    path = Path(s)
    if not path.exists():
        raise FileNotFoundError(f"Palette file or preset not found: {source}")
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".hex":
        return parse_hex_palette(text, steps=steps, hue_shift=hue_shift)
    if suffix == ".gpl":
        return parse_gpl_palette(text, steps=steps, hue_shift=hue_shift)
    if suffix == ".json":
        data = json.loads(text)
        if "palette" in data and isinstance(data["palette"], dict):
            return VoxelPalette.from_dict(data["palette"])
        return VoxelPalette.from_dict(data)
    raise ValueError(f"Unsupported palette format {suffix!r}; expected .hex, .gpl, .json, or preset name")


def verify_palette_colors(
    canvas: Canvas,
    palette: VoxelPalette,
    bg: RGBA | None = None,
) -> tuple[bool, list[str]]:
    """Verify that every non-transparent pixel on canvas belongs to palette (or bg)."""
    allowed: set[tuple[int, int, int]] = set()
    for ramp in palette.ramps:
        for r, g, b, _a in ramp.colors:
            allowed.add((r, g, b))
    oc = palette.outline
    allowed.add((oc[0], oc[1], oc[2]))
    if bg is not None:
        allowed.add((bg[0], bg[1], bg[2]))

    stray: set[str] = set()
    for y in range(canvas.height):
        for x in range(canvas.width):
            r, g, b, a = canvas.get_pixel(x, y)
            if a == 0:
                continue
            if (r, g, b) not in allowed:
                stray.add(rgba_to_hex((r, g, b, a)))
    return (len(stray) == 0, sorted(stray))
