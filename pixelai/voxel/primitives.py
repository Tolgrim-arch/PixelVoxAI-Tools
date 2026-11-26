"""Declarative 3D voxel primitives for AI agents (box, ellipsoid, cylinder, shell, mirror, carve)."""

from __future__ import annotations

from pixelai.voxel.model import Coord3, VoxelLayer


def vox_box(
    layer: VoxelLayer,
    x0: int,
    y0: int,
    z0: int,
    x1: int,
    y1: int,
    z1: int,
    value: int,
) -> None:
    """Fill an axis-aligned 3D box (inclusive bounds) with voxel value."""
    ax, bx = min(x0, x1), max(x0, x1)
    ay, by = min(y0, y1), max(y0, y1)
    az, bz = min(z0, z1), max(z0, z1)
    for z in range(az, bz + 1):
        for y in range(ay, by + 1):
            for x in range(ax, bx + 1):
                layer.set(x, y, z, value)


def vox_ellipsoid(
    layer: VoxelLayer,
    cx: float,
    cy: float,
    cz: float,
    rx: float,
    ry: float,
    rz: float,
    value: int,
) -> None:
    """Fill a 3D ellipsoid centered at (cx, cy, cz) with radii (rx, ry, rz)."""
    if rx <= 0 or ry <= 0 or rz <= 0:
        raise ValueError("Ellipsoid radii must be positive")
    for z in range(int(cz - rz) - 1, int(cz + rz) + 2):
        dz = (z - cz) / rz
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            dy = (y - cy) / ry
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                dx = (x - cx) / rx
                if dx * dx + dy * dy + dz * dz <= 1.0:
                    layer.set(x, y, z, value)


def vox_cylinder(
    layer: VoxelLayer,
    cx: float,
    cy: float,
    z0: int,
    z1: int,
    radius: float,
    value: int,
) -> None:
    """Fill a vertical Z-aligned cylinder."""
    if radius <= 0:
        raise ValueError("Cylinder radius must be positive")
    az, bz = min(z0, z1), max(z0, z1)
    r2 = radius * radius
    for z in range(az, bz + 1):
        for y in range(int(cy - radius) - 1, int(cy + radius) + 2):
            dy = y - cy
            for x in range(int(cx - radius) - 1, int(cx + radius) + 2):
                dx = x - cx
                if dx * dx + dy * dy <= r2:
                    layer.set(x, y, z, value)


def vox_carve(
    layer: VoxelLayer,
    x0: int,
    y0: int,
    z0: int,
    x1: int,
    y1: int,
    z1: int,
) -> None:
    """Erase all voxels inside an axis-aligned 3D box."""
    vox_box(layer, x0, y0, z0, x1, y1, z1, 0)


def vox_mirror_x(layer: VoxelLayer, axis_x: int = 0) -> None:
    """Mirror all voxels in layer across x = axis_x."""
    snapshot = list(layer.voxels.items())
    for (x, y, z), val in snapshot:
        mx = 2 * axis_x - x
        layer.set(mx, y, z, val)


def vox_shell(
    target_layer: VoxelLayer,
    reference_voxels: dict[Coord3, int],
    value: int,
    *,
    z_min: int | None = None,
    z_max: int | None = None,
    thickness: int = 1,
) -> None:
    """Wrap a clothing/armor shell around occupied reference voxels without modifying them."""
    if thickness <= 0:
        raise ValueError("thickness must be positive")
    occupied = set(reference_voxels.keys())
    frontier = set(occupied)
    added: set[Coord3] = set()
    offsets = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))

    for _step in range(thickness):
        next_ring: set[Coord3] = set()
        for x, y, z in frontier:
            if z_min is not None and z < z_min:
                continue
            if z_max is not None and z > z_max:
                continue
            for dx, dy, dz in offsets:
                nb = (x + dx, y + dy, z + dz)
                if nb in occupied or nb in added:
                    continue
                if z_min is not None and nb[2] < z_min:
                    continue
                if z_max is not None and nb[2] > z_max:
                    continue
                next_ring.add(nb)
        added.update(next_ring)
        frontier = next_ring

    for x, y, z in sorted(added, key=lambda c: (c[2], c[1], c[0])):
        target_layer.set(x, y, z, value)
