"""Deterministic CPU voxel-to-pixel-art renderer using exact 3D DDA ray-marching.

Ported in spirit from VoxPix (MIT):
- Exact Amanatides & Woo 3D DDA per pixel -> ZERO diagonal pinholes at any yaw/elevation.
- Strict closed-palette output (shading + 3D lighting shift indices inside each ramp).
- Supports orthographic and 3/4 oblique cameras, point lights, sun shadows, and fluids.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pixelai.canvas import Canvas
from pixelai.voxel.camera import VoxelCamera
from pixelai.voxel.lighting import PointLight, compute_lighting_shade_shift
from pixelai.voxel.model import Coord3, VoxelModel

# Fixed screen-space top-left directional light: (-X left, +Y up, +Z toward camera)
_SCREEN_LIGHT = (-0.52, 0.58, 0.63)

_NEIGHBORS_6: tuple[Coord3, ...] = (
    (1, 0, 0), (-1, 0, 0),
    (0, 1, 0), (0, -1, 0),
    (0, 0, 1), (0, 0, -1),
)

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
    normal_map: list[Coord3 | None]


def _estimate_normal(
    coord: Coord3,
    face_normal: Coord3,
    occupied: set[Coord3],
    smooth: float,
) -> tuple[float, float, float]:
    """Blend exact hit face normal with air-neighbor smoothing."""
    if smooth <= 0.0:
        return (float(face_normal[0]), float(face_normal[1]), float(face_normal[2]))
    x, y, z = coord
    nx, ny, nz = float(face_normal[0]), float(face_normal[1]), float(face_normal[2])
    w6 = smooth * 0.45
    for dx, dy, dz in _NEIGHBORS_6:
        if (x + dx, y + dy, z + dz) not in occupied:
            nx += dx * w6
            ny += dy * w6
            nz += dz * w6
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-6:
        return (0.0, 0.0, 1.0)
    return (nx / length, ny / length, nz / length)


def _compute_ao(coord: Coord3, occupied: set[Coord3]) -> float:
    x, y, z = coord
    blocked = 0
    for dx, dy, dz in _AO_OFFSETS:
        if (x + dx, y + dy, z + dz) in occupied:
            blocked += 1
    return blocked / len(_AO_OFFSETS)


def _intersect_aabb(
    ox: float, oy: float, oz: float,
    dx: float, dy: float, dz: float,
    bmin: tuple[float, float, float],
    bmax: tuple[float, float, float],
) -> tuple[float, float] | None:
    """Slab intersection returning (t_enter, t_exit) or None."""
    tmin = -1e18
    tmax = 1e18
    for o, d, mn, mx in ((ox, dx, bmin[0], bmax[0]), (oy, dy, bmin[1], bmax[1]), (oz, dz, bmin[2], bmax[2])):
        if abs(d) < 1e-12:
            if o < mn or o > mx:
                return None
        else:
            inv = 1.0 / d
            t1 = (mn - o) * inv
            t2 = (mx - o) * inv
            if t1 > t2:
                t1, t2 = t2, t1
            if t1 > tmin:
                tmin = t1
            if t2 < tmax:
                tmax = t2
            if tmin > tmax:
                return None
    return tmin, tmax


def _dda_raycast(
    ox: float, oy: float, oz: float,
    dx: float, dy: float, dz: float,
    flat: dict[Coord3, int],
    bmin: tuple[float, float, float],
    bmax: tuple[float, float, float],
) -> tuple[Coord3, int, Coord3, float] | None:
    """Exact 3D Amanatides & Woo DDA raymarch returning (coord, value, face_normal, t_hit)."""
    hit = _intersect_aabb(ox, oy, oz, dx, dy, dz, bmin, bmax)
    if hit is None:
        return None
    t_enter, t_exit = hit
    # Start slightly inside the AABB
    t = t_enter + 1e-5
    if t > t_exit:
        return None

    px = ox + dx * t
    py = oy + dy * t
    pz = oz + dz * t

    ix = math.floor(px)
    iy = math.floor(py)
    iz = math.floor(pz)

    # Determine entry face normal
    eps = 1e-3
    if abs(px - bmin[0]) < eps:
        last_n: Coord3 = (-1, 0, 0)
    elif abs(px - bmax[0]) < eps:
        last_n = (1, 0, 0)
    elif abs(py - bmin[1]) < eps:
        last_n = (0, -1, 0)
    elif abs(py - bmax[1]) < eps:
        last_n = (0, 1, 0)
    elif abs(pz - bmin[2]) < eps:
        last_n = (0, 0, -1)
    else:
        last_n = (0, 0, 1)

    step_x = 1 if dx > 0 else (-1 if dx < 0 else 0)
    step_y = 1 if dy > 0 else (-1 if dy < 0 else 0)
    step_z = 1 if dz > 0 else (-1 if dz < 0 else 0)

    t_delta_x = abs(1.0 / dx) if abs(dx) > 1e-12 else 1e18
    t_delta_y = abs(1.0 / dy) if abs(dy) > 1e-12 else 1e18
    t_delta_z = abs(1.0 / dz) if abs(dz) > 1e-12 else 1e18

    t_max_x = ((ix + (1 if dx > 0 else 0)) - px) / dx + t if step_x != 0 else 1e18
    t_max_y = ((iy + (1 if dy > 0 else 0)) - py) / dy + t if step_y != 0 else 1e18
    t_max_z = ((iz + (1 if dz > 0 else 0)) - pz) / dz + t if step_z != 0 else 1e18

    max_iters = int(bmax[0] - bmin[0] + bmax[1] - bmin[1] + bmax[2] - bmin[2]) + 8
    for _ in range(max_iters):
        val = flat.get((ix, iy, iz), 0)
        if val != 0:
            return (ix, iy, iz), val, last_n, t

        if t_max_x <= t_max_y and t_max_x <= t_max_z:
            t = t_max_x
            t_max_x += t_delta_x
            ix += step_x
            last_n = (-step_x, 0, 0)
        elif t_max_y <= t_max_z:
            t = t_max_y
            t_max_y += t_delta_y
            iy += step_y
            last_n = (0, -step_y, 0)
        else:
            t = t_max_z
            t_max_z += t_delta_z
            iz += step_z
            last_n = (0, 0, -step_z)

        if t > t_exit + 1e-5:
            break
    return None


def render_voxel_model(
    model: VoxelModel,
    canvas: Canvas | None = None,
    *,
    width: int = 64,
    height: int = 64,
    camera: VoxelCamera | None = None,
    smooth: float = 0.4,
    ao: float = 0.35,
    thresholds: tuple[float, float] = (-0.18, 0.28),
    lights: list[PointLight] | None = None,
    sun_shadow: bool = False,
    ambient_dark: bool = False,
) -> VoxelRenderResult:
    """Render a VoxelModel onto a Canvas via exact 3D DDA ray-marching (zero pinholes)."""
    cam = camera or VoxelCamera()
    target = canvas if canvas is not None else Canvas(width, height)
    w, h = target.width, target.height
    depth_map = [float("-inf")] * (w * h)
    voxel_map: list[Coord3 | None] = [None] * (w * h)
    normal_map: list[Coord3 | None] = [None] * (w * h)

    flat = model.flatten()
    if not flat:
        return VoxelRenderResult(canvas=target, depth_map=depth_map, voxel_map=voxel_map, normal_map=normal_map)

    bbox = model.bounding_box()
    assert bbox is not None
    (min_x, min_y, min_z), (max_x, max_y, max_z) = bbox
    # Each voxel (x, y, z) occupies [x, x+1) x [y, y+1) x [z, z+1)
    bmin = (float(min_x), float(min_y), float(min_z))
    bmax = (float(max_x + 1), float(max_y + 1), float(max_z + 1))

    # Compute tight 2D screen bounding box from the 8 AABB corners to keep CPU raycasting fast
    px_off_x, px_off_y, px_off_z = model.pivot
    sx_vals: list[float] = []
    sy_vals: list[float] = []
    for cx in (bmin[0], bmax[0]):
        for cy in (bmin[1], bmax[1]):
            for cz in (bmin[2], bmax[2]):
                sx, sy, _ = cam.project(cx - px_off_x, cy - px_off_y, cz - px_off_z, w, h)
                sx_vals.append(sx)
                sy_vals.append(sy)

    min_px = max(0, math.floor(min(sx_vals)) - 1)
    max_px = min(w - 1, math.ceil(max(sx_vals)) + 1)
    min_py = max(0, math.floor(min(sy_vals)) - 1)
    max_py = min(h - 1, math.ceil(max(sy_vals)) + 1)

    ox_scr, oy_scr = cam.resolve_origin(w, h)
    rad_yaw = math.radians(cam.yaw)
    cy_w = math.cos(rad_yaw)
    sy_w = math.sin(rad_yaw)

    if cam.oblique is not None:
        oy_step, oz_step = cam.oblique
        # Oblique ray direction: moving +1 in +Y shifts screen up by oy_step, so to stay on same screen pixel, dz = -oy_step/oz_step
        dry = 1.0
        dz = -oy_step / max(oz_step, 1e-6)
        rlen = math.sqrt(dry * dry + dz * dz)
        dry /= rlen
        dz /= rlen
        dx_w = dry * sy_w
        dy_w = dry * cy_w
        dz_w = dz
    else:
        rad_elev = math.radians(cam.elevation)
        ce = math.cos(rad_elev)
        se = math.sin(rad_elev)
        dx_w = ce * sy_w
        dy_w = ce * cy_w
        dz_w = -se

    occupied = set(flat.keys())
    low_t, high_t = thresholds
    lx, ly, lz = _SCREEN_LIGHT
    ppu = cam.ppu
    use_lighting = bool(lights) or sun_shadow or ambient_dark

    for py in range(min_py, max_py + 1):
        u_up = (oy_scr - (py + 0.5)) / ppu
        if cam.oblique is not None:
            ry0 = 0.0
            z0 = u_up / max(cam.oblique[1], 1e-6)
        else:
            ry0 = u_up * se
            z0 = u_up * ce
        row_off = py * w
        for px in range(min_px, max_px + 1):
            rx0 = ((px + 0.5) - ox_scr) / ppu
            x0 = rx0 * cy_w + ry0 * sy_w + px_off_x
            y0 = -rx0 * sy_w + ry0 * cy_w + px_off_y
            z_start = z0 + px_off_z

            hit = _dda_raycast(x0, y0, z_start, dx_w, dy_w, dz_w, flat, bmin, bmax)
            if hit is None:
                continue
            coord, val, face_n, t_hit = hit
            depth = -t_hit
            idx = row_off + px
            if depth < depth_map[idx]:
                continue

            nx, ny, nz = _estimate_normal(coord, face_n, occupied, smooth)
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

            if use_lighting:
                shift += compute_lighting_shade_shift(
                    coord,
                    flat,
                    model,
                    lights=lights,
                    sun_shadow=sun_shadow,
                    ambient_dark=ambient_dark,
                )

            rgba = model.palette.resolve_color(val, shade_shift=shift)
            depth_map[idx] = depth
            voxel_map[idx] = coord
            normal_map[idx] = face_n
            target.set_pixel(px, py, rgba)

    return VoxelRenderResult(
        canvas=target,
        depth_map=depth_map,
        voxel_map=voxel_map,
        normal_map=normal_map,
    )


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
    smooth: float = 0.4,
    ao: float = 0.35,
    lights: list[PointLight] | None = None,
    sun_shadow: bool = False,
    ambient_dark: bool = False,
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
            lights=lights,
            sun_shadow=sun_shadow,
            ambient_dark=ambient_dark,
        )
        frames.append(res.canvas)
    return frames
