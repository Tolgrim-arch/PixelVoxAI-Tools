"""Procedural voxel character animation (walk & idle cycles) for spritesheets and GIFs."""

from __future__ import annotations

import math
from pathlib import Path

from pixelai.canvas import Canvas
from pixelai.color import RGBA
from pixelai.exporter import export_gif, export_png
from pixelai.filters import scale as scale_nearest
from pixelai.voxel.camera import VoxelCamera
from pixelai.voxel.model import VoxelLayer, VoxelModel
from pixelai.voxel.render import render_voxel_model


def _clone_model_empty_layers(model: VoxelModel) -> VoxelModel:
    return VoxelModel(
        palette=model.palette,
        layers=[
            VoxelLayer(
                id=layer.id,
                role=layer.role,
                priority=layer.priority,
                visible=layer.visible,
                locked=layer.locked,
                voxels={},
            )
            for layer in model.layers
        ],
        bounds=model.bounds,
        pivot=model.pivot,
        sockets=dict(model.sockets),
    )


def generate_walk_frames(
    model: VoxelModel,
    frames: int = 4,
    stride: int = 1,
    bob: int = 1,
) -> list[VoxelModel]:
    """Generate procedural walk-cycle VoxelModel frames."""
    if frames < 2:
        raise ValueError("frames must be >= 2")
    bbox = model.bounding_box()
    if bbox is None:
        return [VoxelModel.from_dict(model.to_dict()) for _ in range(frames)]
    (_, _, z0), (_, _, z1) = bbox
    leg_cutoff = z0 + max(1, (z1 - z0) // 3)

    result: list[VoxelModel] = []
    for i in range(frames):
        phase = 2.0 * math.pi * i / frames
        dz_bob = round(bob * max(0.0, math.sin(phase * 2.0)))
        swing = round(stride * math.sin(phase))
        frame_model = _clone_model_empty_layers(model)
        for src_layer, dst_layer in zip(model.layers, frame_model.layers):
            for (x, y, z), val in src_layer.voxels.items():
                ny = y
                nz = z + dz_bob
                if z <= leg_cutoff:
                    if x < 0:
                        ny += swing
                    elif x > 0:
                        ny -= swing
                elif abs(x) >= 2:
                    if x < 0:
                        ny -= swing // 2
                    else:
                        ny += swing // 2
                dst_layer.set(x, ny, nz, val)
        result.append(frame_model)
    return result


def generate_idle_frames(
    model: VoxelModel,
    frames: int = 4,
    bob: int = 1,
) -> list[VoxelModel]:
    """Generate procedural idle/breathing VoxelModel frames."""
    if frames < 2:
        raise ValueError("frames must be >= 2")
    bbox = model.bounding_box()
    if bbox is None:
        return [VoxelModel.from_dict(model.to_dict()) for _ in range(frames)]
    (_, _, z0), (_, _, z1) = bbox
    torso_cutoff = z0 + max(1, (z1 - z0) // 3)

    result: list[VoxelModel] = []
    for i in range(frames):
        phase = 2.0 * math.pi * i / frames
        dz = round(bob * max(0.0, math.sin(phase)))
        frame_model = _clone_model_empty_layers(model)
        for src_layer, dst_layer in zip(model.layers, frame_model.layers):
            for (x, y, z), val in src_layer.voxels.items():
                nz = z + dz if z > torso_cutoff else z
                dst_layer.set(x, y, nz, val)
        result.append(frame_model)
    return result


def render_animation_frames(
    models: list[VoxelModel],
    yaw: float = 0.0,
    elev: float = 30.0,
    scale: int = 4,
    size: tuple[int, int] = (64, 48),
    outline: str = "outer",
    bg: RGBA | None = None,
) -> list[Canvas]:
    """Render a list of VoxelModel frames to scaled Canvases."""
    cam = VoxelCamera(yaw=yaw, elevation=elev)
    canvases: list[Canvas] = []
    for m in models:
        c = render_voxel_model(m, width=size[0], height=size[1], camera=cam).canvas
        if scale > 1:
            c = scale_nearest(c, scale)
        if bg is not None:
            for py in range(c.height):
                for px in range(c.width):
                    if c.get_pixel(px, py)[3] == 0:
                        c.set_pixel(px, py, bg)
        canvases.append(c)
    return canvases


def export_animation_sheet(frames: list[Canvas], output_path: str | Path) -> None:
    """Stitch rendered frames horizontally into a single PNG spritesheet."""
    if not frames:
        raise ValueError("frames must be non-empty")
    fw, fh = frames[0].width, frames[0].height
    sheet = Canvas(fw * len(frames), fh)
    for idx, frame in enumerate(frames):
        ox = idx * fw
        for py in range(fh):
            for px in range(fw):
                rgba = frame.get_pixel(px, py)
                if rgba[3] > 0:
                    sheet.set_pixel(ox + px, py, rgba)
    export_png(sheet, str(output_path))


def export_animation_gif(frames: list[Canvas], output_path: str | Path, ms: int = 120) -> None:
    """Export rendered frames as an animated GIF."""
    if not frames:
        raise ValueError("frames must be non-empty")
    export_gif(frames, str(output_path), ms)
