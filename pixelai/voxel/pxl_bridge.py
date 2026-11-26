"""Bidirectional bridge between VoxelModel and pxl (.px.js) code-as-pixel-art format."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pixelai.color import parse_color
from pixelai.voxel.camera import VoxelCamera
from pixelai.voxel.model import VoxelLayer, VoxelModel
from pixelai.voxel.ramps import VoxelPalette, decode_voxel_value, encode_voxel_value, ramp_from_color, rgba_to_hex
from pixelai.voxel.render import render_voxel_model

_GLYPHS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-+=[]{}:;<>?"
_OUTLINE_DIRECTIVE_RE = re.compile(r"//\s*voxpix:\s*outline\s+(#[0-9a-fA-F]{6})", re.IGNORECASE)
_EMISSIVE_DIRECTIVE_RE = re.compile(r"//\s*voxpix:\s*emissive\s+(.+)", re.IGNORECASE)


def export_pxl(
    model: VoxelModel,
    *,
    name: str = "model",
    stack_prefix: str | None = None,
    turn: int = 8,
    elevation: float = 30.0,
    width: int = 64,
    height: int = 48,
) -> str:
    """Export a VoxelModel to a .px.js string (either --stack height layers or --turn angles)."""
    palette_map: dict[str, str] = {}
    emissive_keys: list[str] = []
    ramp_to_key: dict[int, str] = {}

    for idx, ramp in enumerate(model.palette.ramps):
        if idx >= len(_GLYPHS):
            break
        key = _GLYPHS[idx]
        ramp_to_key[idx] = key
        # Representative mid-shade color for the ramp
        mid_color = ramp.colors[len(ramp.colors) // 2]
        palette_map[key] = rgba_to_hex(mid_color)
        if ramp.material.emissive:
            emissive_keys.append(key)

    lines: list[str] = [
        f"// Exported by PixelVoxAI-Tools ({name})",
        f"// voxpix: outline {rgba_to_hex(model.palette.outline)}",
    ]
    if emissive_keys:
        lines.append(f"// voxpix: emissive {' '.join(emissive_keys)}")
    lines.append("")
    lines.append(f"export const palette = {json.dumps(palette_map, indent=2)};")
    lines.append("")

    sprites: dict[str, list[str]] = {}
    if stack_prefix is not None:
        flat = model.flatten()
        bbox = model.bounding_box()
        if bbox is None:
            sprites[f"{stack_prefix}_z00"] = ["."]
        else:
            (min_x, min_y, min_z), (max_x, max_y, max_z) = bbox
            for z in range(min_z, max_z + 1):
                rows: list[str] = []
                # Top-down, north (+Y) at top
                for y in range(max_y, min_y - 1, -1):
                    row_chars: list[str] = []
                    for x in range(min_x, max_x + 1):
                        val = flat.get((x, y, z), 0)
                        if val == 0:
                            row_chars.append(".")
                        else:
                            r_idx, _s_idx = decode_voxel_value(val)
                            row_chars.append(ramp_to_key.get(r_idx, "."))
                    rows.append("".join(row_chars))
                if any(ch != "." for row in rows for ch in row):
                    sprites[f"{stack_prefix}_z{z - min_z:02d}"] = rows
    else:
        # Render N turntable angles and quantize each pixel to nearest palette key
        color_to_key: dict[tuple[int, int, int], str] = {}
        for idx, ramp in enumerate(model.palette.ramps):
            key = ramp_to_key.get(idx)
            if key is None:
                continue
            for r, g, b, _a in ramp.colors:
                color_to_key[(r, g, b)] = key
        oc = model.palette.outline
        outline_key = "O"
        if outline_key in palette_map:
            outline_key = "~"
        palette_map[outline_key] = rgba_to_hex(oc)
        color_to_key[(oc[0], oc[1], oc[2])] = outline_key

        n_angles = max(1, turn)
        for i in range(n_angles):
            yaw = (360.0 * i) / n_angles
            res = render_voxel_model(
                model,
                width=width,
                height=height,
                camera=VoxelCamera(yaw=yaw, elevation=elevation),
            )
            rows = []
            for py in range(res.canvas.height):
                row_chars = []
                for px in range(res.canvas.width):
                    r, g, b, a = res.canvas.get_pixel(px, py)
                    if a == 0:
                        row_chars.append(".")
                    else:
                        row_chars.append(color_to_key.get((r, g, b), outline_key))
                rows.append("".join(row_chars))
            sprites[f"{name}_a{i:02d}"] = rows

        # Re-emit palette with outline key included
        lines[lines.index(next(l for l in lines if l.startswith("export const palette")))] = (
            f"export const palette = {json.dumps(palette_map, indent=2)};"
        )

    lines.append(f"export const sprites = {json.dumps(sprites, indent=2)};")
    lines.append("")
    return "\n".join(lines)


def _extract_js_object(text: str, var_name: str) -> dict:
    """Extract a JSON-compatible object literal assigned to `var_name = { ... }`."""
    pattern = re.compile(rf"(?:export\s+)?(?:const|let|var)\s+{re.escape(var_name)}\s*=\s*(\{{)", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        return {}
    start = m.start(1)
    depth = 0
    in_str: str | None = None
    escaped = False
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if in_str is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        raise ValueError(f"Unclosed object literal for {var_name!r} in .px.js")
    raw = text[start:end]
    # Normalize single quotes and trailing commas for lenient JS object parsing
    raw = re.sub(r"//[^\n]*", "", raw)
    raw = re.sub(r",(\s*[}\]])", r"\1", raw)
    raw = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', raw)
    raw = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_-]*)(\s*:)', r'\1"\2"\3', raw)
    return json.loads(raw)


def import_pxl(
    source_text: str,
    *,
    stack_prefix: str | None = None,
    sprite_name: str | None = None,
    plane: str = "front",
    z: int = 0,
    outline: str | None = None,
    steps: int = 4,
) -> VoxelModel:
    """Import a .px.js file into a VoxelModel (via --stack, single sprite plane, or palette-only '-')."""
    outline_hex = outline
    if outline_hex is None:
        om = _OUTLINE_DIRECTIVE_RE.search(source_text)
        if om:
            outline_hex = om.group(1)

    emissive_keys: set[str] = set()
    for em in _EMISSIVE_DIRECTIVE_RE.finditer(source_text):
        for tok in em.group(1).strip().split():
            emissive_keys.add(tok)

    raw_palette = _extract_js_object(source_text, "palette")
    if not raw_palette:
        raise ValueError("No `palette` object found in .px.js source")

    ramps = []
    key_to_ramp: dict[str, int] = {}
    for key, hex_color in raw_palette.items():
        if not isinstance(hex_color, str):
            continue
        is_emissive = key in emissive_keys
        key_to_ramp[key] = len(ramps)
        ramps.append(
            ramp_from_color(
                hex_color,
                steps=steps,
                name=f"pxl_{key}",
                material="emissive" if is_emissive else "solid",
                emissive=is_emissive,
            )
        )

    pal_outline = parse_color(outline_hex) if outline_hex else (13, 12, 18, 255)
    palette = VoxelPalette(ramps=ramps, outline=pal_outline)
    model = VoxelModel(palette=palette, bounds=(64, 64, 64), pivot=(0, 0, 0))
    layer = VoxelLayer(id="imported", role="body", priority=0)
    model.add_layer(layer)

    mid_shade = max(0, steps // 2)
    _apply_voxmap_calls(source_text, layer, key_to_ramp, mid_shade)

    if sprite_name == "-":
        return model

    sprites = _extract_js_object(source_text, "sprites")
    mid_shade = max(0, steps // 2)

    if stack_prefix is not None:
        prefix_re = re.compile(rf"^{re.escape(stack_prefix)}_z(\d+)$")
        matched: list[tuple[int, list[str]]] = []
        for sname, rows in sprites.items():
            m = prefix_re.match(sname)
            if m and isinstance(rows, list):
                matched.append((int(m.group(1)), rows))
        if not matched:
            raise ValueError(f"No stack sprites matching '{stack_prefix}_zNN' found in .px.js")
        matched.sort(key=lambda item: item[0])
        for z_idx, rows in matched:
            h = len(rows)
            w = max((len(r) for r in rows), default=0)
            cx = w // 2
            cy = h // 2
            for row_i, row in enumerate(rows):
                y_coord = (h - 1 - row_i) - cy
                for col_i, ch in enumerate(row):
                    if ch in (".", " "):
                        continue
                    r_idx = key_to_ramp.get(ch)
                    if r_idx is not None:
                        layer.set(col_i - cx, y_coord, z_idx, encode_voxel_value(r_idx, mid_shade))
        return model

    _apply_voxmap_calls(source_text, layer, key_to_ramp, mid_shade)

    if sprite_name == "-":
        return model

    if sprite_name is None:
        if not sprites:
            return model
        sprite_name = next(iter(sprites.keys()))

    if sprite_name not in sprites:
        raise KeyError(f"Sprite {sprite_name!r} not found in .px.js. Available: {', '.join(sprites)}")
    rows = sprites[sprite_name]
    h = len(rows)
    w = max((len(r) for r in rows), default=0)
    cx = w // 2
    for row_i, row in enumerate(rows):
        for col_i, ch in enumerate(row):
            if ch in (".", " "):
                continue
            r_idx = key_to_ramp.get(ch)
            if r_idx is None:
                continue
            val = encode_voxel_value(r_idx, mid_shade)
            if plane == "top":
                layer.set(col_i - cx, (h - 1 - row_i) - (h // 2), z, val)
            else:
                # front plane: X horizontal, Z vertical, Y = z
                layer.set(col_i - cx, z, h - 1 - row_i, val)
    return model


def export_pxl_file(model: VoxelModel, out_path: str | Path, **kwargs) -> Path:
    """Export a VoxelModel to a .px.js file on disk."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(export_pxl(model, **kwargs), encoding="utf-8")
    return p


def import_pxl_file(in_path: str | Path, **kwargs) -> VoxelModel:
    """Import a .px.js file from disk into a VoxelModel."""
    text = Path(in_path).read_text(encoding="utf-8")
    return import_pxl(text, **kwargs)


def _apply_voxmap_calls(
    source_text: str,
    layer: VoxelLayer,
    key_to_ramp: dict[str, int],
    mid_shade: int,
) -> int:
    """Parse `vox.set(x,y,z,key)`, `vox.box(x0,y0,z0,x1,y1,z1,key)`, `vox.fill(...)`, `vox.cylinder(cx,cy,z0,r,h,key)`."""
    count = 0
    for m in re.finditer(r"\bvox\.set\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*['\"]([^'\"]+)['\"]\s*\)", source_text):
        x, y, z, key = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        r_idx = key_to_ramp.get(key)
        if r_idx is not None:
            layer.set(x, y, z, encode_voxel_value(r_idx, mid_shade))
            count += 1

    for m in re.finditer(
        r"\bvox\.(?:box|fill)\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
        source_text,
    ):
        x0, y0, z0, x1, y1, z1 = (int(m.group(i)) for i in range(1, 7))
        r_idx = key_to_ramp.get(m.group(7))
        if r_idx is None:
            continue
        val = encode_voxel_value(r_idx, mid_shade)
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    layer.set(x, y, z, val)
                    count += 1

    for m in re.finditer(
        r"\bvox\.cylinder\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
        source_text,
    ):
        cx, cy, z0, r, h = (int(m.group(i)) for i in range(1, 6))
        r_idx = key_to_ramp.get(m.group(6))
        if r_idx is None:
            continue
        val = encode_voxel_value(r_idx, mid_shade)
        for x in range(cx - r, cx + r + 1):
            for y in range(cy - r, cy + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    for z in range(z0, z0 + h):
                        layer.set(x, y, z, val)
                        count += 1
    return count

