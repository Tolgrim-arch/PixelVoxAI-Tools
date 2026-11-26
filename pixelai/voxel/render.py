"""Deterministic CPU voxel-to-pixel-art renderer ported from VoxPix (MIT).

Guarantees:
- Identical bytes for identical model + camera + shading options.
- Strict closed-palette output (shading shifts indices inside each ramp).
- Compatible with PixelAI-Tools post-processing (ext_outline, lineless, rim_light, cleanup).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pixelai.canvas import Canvas
from pixelai.voxel.camera import VoxelCamera
from pixelai.voxel.model import Coord3, VoxelModel

# Fixed screen-space top-left directional light: (-X left, +Y up, +Z toward camera)
_SCREEN_LIGHT = (-0.52, 0.58, 0.63)

# 6-connected neighbor offsets for normal estimation and occlusion
_NEIGHBORS_6: tuple[Coord3, ...] = (
    (1, 0, 0), (-1, 0, 0),
    (0, 1, 0), (0, -1, 0),
    (0, 0, 1), (0, 0, -1),
)

# 12 diagonal upper/side neighbors for corner ambient occlusion
_AO_OFFSETS: tuple[Coord3, ...] = (
    (1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
    (1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0),
    (1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1),
)


@dataclass(slots=True)
class VoxelRenderResult:
    """Output of a deterministic CPU voxel render."""

    canvas: Canvas
    depth_map: list[float]
    voxel_map: list[Coord3 | None]


def _estimate_normal(coord: Coord3, occupied: set[Coord3], smooth: float) -> tuple[float, float, float]:
    """Estimate surface normal pointing toward empty air neighbors."""
    x, y, z = coord
    nx = ny = nz = 0.0
    for dx, dy, dz in _NEIGHBORS_6:
        if (x + dx, y + dy, z + dz) not in occupied:
            nx += dx
            ny += dy
            nz += dz
    if smooth > 0.0:
        w = smooth * 0.35
        for dx, dy, dz in _AO_OFFSETS:
            if (x + dx, y + dy, z + dz) not in occupied:
                nx += dx * w
                ny += dy * w
                nz += dz * w
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-6:
        return (0.0, 0.0, 1.0)
    return (nx / length, ny / length, nz / length)


def _compute_ao(coord: Coord3, occupied: set[Coord3]) -> float:
    """Return ambient occlusion factor in [0.0, 1.0] based on solid corner neighbors."""
    x, y, z = coord
    blocked = 0
    for dx, dy, dz in _AO_OFFSETS:
        if (x + dx, y + dy, z + dz) in occupied:
            blocked += 1
    return blocked / len(_AO_OFFSETS)


def render_voxel_model(
    model: VoxelModel,
    canvas: Canvas | None = None,
    *,
    width: int = 64,
    height: int = 64,
    camera: VoxelCamera | None = None,
    smooth: float = 0.5,
    ao: float = 0.35,
    thresholds: tuple[float, float] = (-0.18, 0.28),
) -> VoxelRenderResult:
    """Render a VoxelModel onto a Canvas with deterministic closed-palette shading."""
    cam = camera or VoxelCamera()
    target = canvas if canvas is not None else Canvas(width, height)
    w, h = target.width, target.height
    depth_map = [float("-inf")] * (w * h)
    voxel_map: list[Coord3 | None] = [None] * (w * h)

    flat = model.flatten()
    if not flat:
        return VoxelRenderResult(canvas=target, depth_map=depth_map, voxel_map=voxel_map)

    occupied = set(flat.keys())
    px_offset_x, px_offset_y, px_offset_z = model.pivot
    low_t, high_t = thresholds
    lx, ly, lz = _SCREEN_LIGHT

    # Project all surface voxels (skip completely enclosed interior voxels)
    projected: list[tuple[float, int, int, Coord3, int]] = []
    for coord, val in sorted(flat.items(), key=lambda item: (item[0][2], item[0][1], item[0][0])):
        x, y, z = coord
        if all((x + dx, y + dy, z + dz) in occupied for dx, dy, dz in _NEIGHBORS_6):
            continue
        sx, sy, depth = cam.project(
            x - px_offset_x,
            y - px_offset_y,
            z - px_offset_z,
            w,
            h,
        )
        # Deterministic half-up rounding
        ix = math.floor(sx + 0.5)
        iy = math.floor(sy + 0.5)
        projected.append((depth, ix, iy, coord, val))

    # Painter's order: far to near (ascending depth, deterministic tie-break by coord)
    projected.sort(key=lambda item: (item[0], item[3][2], item[3][1], item[3][0]))

    ppu = cam.ppu
    for depth, ix, iy, coord, val in projected:
        nx, ny, nz = _estimate_normal(coord, occupied, smooth)
        snx, sny, snz = cam.rotate_normal_to_screen(nx, ny, nz)
        ndotl = snx * lx + sny * ly + snz * lz
        ao_pen = _compute_ao(coord, occupied) * ao
        score = ndotl - ao_pen

        if score >= high_t:
            shift = 1
        elif score <= low_t:
            shift = -1
        else:
            shift = 0

        rgba = model.palette.resolve_color(val, shade_shift=shift)

        # Splat ppu x ppu block
        for dy in range(ppu):
            py = iy - dy
            if not (0 <= py < h):
                continue
            row_off = py * w
            for dx in range(ppu):
                px = ix + dx
                if not (0 <= px < w):
                    continue
                idx = row_off + px
                if depth >= depth_map[idx]:
                    depth_map[idx] = depth
                    voxel_map[idx] = coord
                    target.set_pixel(px, py, rgba)

    return VoxelRenderResult(canvas=target, depth_map=depth_map, voxel_map=voxel_map)


def render_voxel_turntable(
    model: VoxelModel,
    *,
    turns: int = 8,
    width: int = 64,
    height: int = 64,
    elevation: float = 30.0,
    ppu: int = 1,
    oblique: tuple[float, float] | None = None,
    origin_x: int | None = None,
    origin_y: int | None = None,
    smooth: float = 0.5,
    ao: float = 0.35,
) -> list[Canvas]:
    """Render a deterministic multi-angle turntable (e.g., 4 or 8 directions)."""
    if turns <= 0:
        raise ValueError(f"turns must be positive, got {turns}")
    frames: list[Canvas] = []
    step = 360.0 / turns
    for i in range(turns):
        cam = VoxelCamera(
            yaw=i * step,
            elevation=elevation,
            ppu=ppu,
            oblique=oblique,
            origin_x=origin_x,
            origin_y=origin_y,
        )
        res = render_voxel_model(
            model,
            width=width,
            height=height,
            camera=cam,
            smooth=smooth,
            ao=ao,
        )
        frames.append(res.canvas)
    return frames
