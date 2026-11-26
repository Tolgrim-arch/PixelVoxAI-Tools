"""Exact CLI Renderer Oracle API, 3D face picking, and game-ready exporter for PixelAI Studio."""

from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from pixelai.canvas import Canvas
from pixelai.exporter import (
    export_gif,
    export_godot_tres,
    export_png,
    export_spritesheet,
    extract_spec_from_png,
)
from pixelai.overrides import apply_bounce, apply_glint, apply_pixel_overrides
from pixelai.palettes import list_palettes
from pixelai.runner import run_spec
from pixelai.voxel import FORMAT_VERSION, VoxelCamera, VoxelModel, ramp_from_color, render_voxel_model


def canvas_to_png_bytes(canvas: Canvas) -> bytes:
    """Encode a Canvas directly to lossless RGBA PNG bytes."""
    img = Image.new("RGBA", (canvas.width, canvas.height))
    img.putdata(canvas.pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def canvas_to_data_url(canvas: Canvas) -> str:
    b64 = base64.b64encode(canvas_to_png_bytes(canvas)).decode("ascii")
    return f"data:image/png;base64,{b64}"


@dataclass(slots=True)
class StudioState:
    """In-memory project state for a local Studio session."""

    file_path: Path | None
    spec: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path | None = None) -> StudioState:
        if path is None:
            return cls(file_path=None, spec=_default_voxel_spec())
        p = Path(path)
        if not p.exists():
            return cls(file_path=p, spec=_default_voxel_spec())
        if p.suffix.lower() == ".png":
            extracted = extract_spec_from_png(str(p))
            if extracted is None:
                raise ValueError(f"PNG {p} does not contain embedded PixelAI-Tools spec metadata")
            return cls(file_path=p, spec=extracted)
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(file_path=p, spec=data)

    def save(self, target: str | Path | None = None) -> Path:
        dest = Path(target) if target is not None else self.file_path
        if dest is None:
            raise ValueError("No target file path specified for save")
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_text(json.dumps(self.spec, indent=2) + "\n", encoding="utf-8")
        tmp.replace(dest)
        self.file_path = dest
        return dest


def _default_voxel_spec() -> dict[str, Any]:
    return {
        "format": FORMAT_VERSION,
        "bounds": {"w": 16, "d": 16, "h": 24},
        "pivot": [0, 0, 0],
        "palette_ref": "cozy24",
        "ramps": [
            {"name": "skin", "colors": ["#8d5524", "#c68642", "#e0ac69", "#f1c27d"], "material": "solid"},
            {"name": "wood", "colors": ["wood_d", "wood", "wood_l"], "material": "solid"},
            {"name": "grass", "colors": ["grass_d", "grass", "grass_l"], "material": "foliage"},
        ],
        "sockets": {"head": [0, 0, 12], "torso": [0, 0, 5]},
        "layers": [
            {
                "id": "body_base",
                "role": "body",
                "priority": 0,
                "visible": True,
                "locked": False,
                "voxels": [
                    [x, y, z, 3]
                    for x in range(-1, 2)
                    for y in range(-1, 2)
                    for z in range(0, 6)
                ],
            }
        ],
    }


def _render_single_frame(payload: dict[str, Any], frame_idx: int, total_frames: int, yaw_override: float | None = None) -> Canvas:
    spec = payload.get("spec", payload)
    yaw = float(yaw_override if yaw_override is not None else payload.get("yaw", 30.0))
    elevation = float(payload.get("elevation", 30.0))
    ppu = int(payload.get("ppu", 2))
    width = int(payload.get("width", spec.get("width", 48)))
    height = int(payload.get("height", spec.get("height", 48)))
    style = str(payload.get("style", spec.get("style", "ext_outline")))
    overrides = payload.get("pixel_overrides") or spec.get("pixel_overrides")
    fx_cfg = payload.get("micro_fx", {})

    if spec.get("format") == FORMAT_VERSION:
        wrapped: dict[str, Any] = {
            "width": width,
            "height": height,
            "palette": spec.get("palette_ref", "cozy24"),
            "style": style,
            "ops": [
                {
                    "op": "voxel_model",
                    **spec,
                    "yaw": yaw,
                    "elevation": elevation,
                    "ppu": ppu,
                }
            ],
        }
        canvas = run_spec(wrapped)
    else:
        canvas = run_spec(spec)

    if overrides:
        canvas = apply_pixel_overrides(canvas, overrides, frame_idx=frame_idx)
    if fx_cfg.get("bounce"):
        canvas = apply_bounce(canvas, frame_idx=frame_idx, total_frames=total_frames, amplitude_px=int(fx_cfg.get("bounce_px", 2)))
    if fx_cfg.get("glint"):
        canvas = apply_glint(canvas, frame_idx=frame_idx, total_frames=total_frames)
    return canvas


def render_studio_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Render a Studio payload via the exact CLI engine."""
    frame_idx = int(payload.get("frame_idx", 0))
    total_frames = int(payload.get("total_frames", 4))
    canvas = _render_single_frame(payload, frame_idx=frame_idx, total_frames=total_frames)
    return {
        "width": canvas.width,
        "height": canvas.height,
        "image": canvas_to_data_url(canvas),
        "png_bytes_len": len(canvas_to_png_bytes(canvas)),
    }


def pick_voxel_at_pixel(payload: dict[str, Any]) -> dict[str, Any]:
    """Return exact 3D voxel coordinate and hit face normal for a 3D viewport click."""
    spec = payload.get("spec", payload)
    px = int(payload["px"])
    py = int(payload["py"])
    width = int(payload.get("width", 48))
    height = int(payload.get("height", 48))
    cam = VoxelCamera(
        yaw=float(payload.get("yaw", 30.0)),
        elevation=float(payload.get("elevation", 30.0)),
        ppu=int(payload.get("ppu", 2)),
    )
    model = VoxelModel.from_dict(spec)
    res = render_voxel_model(model, width=width, height=height, camera=cam)
    if not (0 <= px < width and 0 <= py < height):
        return {"hit": False}
    idx = py * width + px
    coord = res.voxel_map[idx]
    normal = res.normal_map[idx]
    if coord is None or normal is None:
        return {"hit": False}
    return {
        "hit": True,
        "coord": list(coord),
        "normal": list(normal),
        "place": [coord[0] + normal[0], coord[1] + normal[1], coord[2] + normal[2]],
    }


def export_studio_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Export current Studio asset to PNG, GIF, Spritesheet, or Godot 4 .tres."""
    fmt = str(payload.get("format", "png")).lower()
    out_path = Path(str(payload.get("path", f"studio_export.{fmt}")))
    total_frames = int(payload.get("total_frames", 4))
    turntable = bool(payload.get("turntable", False))
    fps = int(payload.get("fps", 8))

    if fmt == "png":
        canvas = _render_single_frame(payload, frame_idx=int(payload.get("frame_idx", 0)), total_frames=total_frames)
        spec_json = json.dumps(payload["spec"]) if "spec" in payload else None
        export_png(canvas, out_path, spec_json=spec_json)
        return {"exported": str(out_path), "format": "png"}

    if turntable:
        turns = int(payload.get("turns", 8))
        frames = [
            _render_single_frame(payload, frame_idx=i, total_frames=turns, yaw_override=i * (360.0 / turns))
            for i in range(turns)
        ]
    else:
        frames = [
            _render_single_frame(payload, frame_idx=i, total_frames=total_frames)
            for i in range(total_frames)
        ]

    if fmt == "gif":
        export_gif(frames, out_path, fps=fps)
        return {"exported": str(out_path), "format": "gif", "frames": len(frames)}
    if fmt == "sheet":
        meta_path = out_path.with_suffix(".json")
        export_spritesheet(frames, out_path, columns=min(4, len(frames)), meta_path=meta_path)
        return {"exported": str(out_path), "meta": str(meta_path), "format": "sheet", "frames": len(frames)}
    if fmt == "godot":
        sheet_path = out_path.with_suffix(".png")
        export_spritesheet(frames, sheet_path, columns=min(4, len(frames)))
        export_godot_tres(sheet_path, out_path, frames, columns=min(4, len(frames)), fps=fps)
        return {"exported": str(out_path), "sheet": str(sheet_path), "format": "godot", "frames": len(frames)}

    raise ValueError(f"Unsupported export format {fmt!r}; expected png|gif|sheet|godot")


def generate_ramp_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Generate a hue-shifted closed-palette ramp from a base hex color."""
    ramp = ramp_from_color(
        base_color=str(payload["color"]),
        steps=int(payload.get("steps", 4)),
        hue_shift=float(payload.get("hue_shift", 0.08)),
        name=str(payload.get("name", "custom")),
        material=str(payload.get("material", "solid")),
        emissive=bool(payload.get("emissive", False)),
    )
    return {"ramp": ramp.to_dict()}


def get_palettes_payload() -> dict[str, Any]:
    return {"palettes": list_palettes()}
