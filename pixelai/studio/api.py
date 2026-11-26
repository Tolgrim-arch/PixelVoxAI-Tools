"""Exact CLI Renderer Oracle API for PixelAI Studio.

Guarantees 1:1 pixel parity between what the user sees in the browser Studio
and what `pixelai render` exports on the command line.
"""

from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from pixelai.canvas import Canvas
from pixelai.exporter import extract_spec_from_png
from pixelai.overrides import apply_bounce, apply_glint, apply_pixel_overrides
from pixelai.palettes import list_palettes
from pixelai.runner import run_spec
from pixelai.voxel import FORMAT_VERSION, VoxelCamera, VoxelModel, render_voxel_model


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


def render_studio_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Render a Studio payload (either .vox.json or standard PixelAI spec) via the CLI engine."""
    spec = payload.get("spec", payload)
    yaw = float(payload.get("yaw", 30.0))
    elevation = float(payload.get("elevation", 30.0))
    ppu = int(payload.get("ppu", 2))
    width = int(payload.get("width", spec.get("width", 48)))
    height = int(payload.get("height", spec.get("height", 48)))
    style = str(payload.get("style", spec.get("style", "ext_outline")))
    overrides = payload.get("pixel_overrides") or spec.get("pixel_overrides")
    frame_idx = int(payload.get("frame_idx", 0))
    total_frames = int(payload.get("total_frames", 4))
    fx_cfg = payload.get("micro_fx", {})

    if spec.get("format") == FORMAT_VERSION:
        # Wrap standalone .vox.json into a standard spec so CLI filters (ext_outline/lineless) run identically
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

    return {
        "width": canvas.width,
        "height": canvas.height,
        "image": canvas_to_data_url(canvas),
        "png_bytes_len": len(canvas_to_png_bytes(canvas)),
    }


def get_palettes_payload() -> dict[str, Any]:
    return {"palettes": list_palettes()}
