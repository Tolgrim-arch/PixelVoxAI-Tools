"""Deterministic orthographic and 3/4 oblique camera projections for voxels.

The pivot (0, 0, 0) always projects to the exact integer pixel (origin_x, origin_y),
guaranteeing zero jitter across multi-angle turntables and animation frames.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VoxelCamera:
    """Camera configuration for projecting 3D voxels to 2D pixel art."""

    yaw: float = 0.0                          # Degrees around vertical Z axis
    elevation: float = 30.0                   # Degrees tilted down toward north (+Y)
    ppu: int = 1                              # Integer pixels per voxel unit
    oblique: tuple[float, float] | None = None  # Optional (y_step, z_step) 3/4 oblique mode
    origin_x: int | None = None               # Pivot screen X (defaults to canvas.width // 2)
    origin_y: int | None = None               # Pivot screen Y (defaults to int(canvas.height * 0.75))

    def __post_init__(self) -> None:
        if not isinstance(self.ppu, int) or self.ppu <= 0:
            raise ValueError(f"ppu must be a positive integer, got {self.ppu!r}")

    def resolve_origin(self, width: int, height: int) -> tuple[int, int]:
        ox = self.origin_x if self.origin_x is not None else width // 2
        oy = self.origin_y if self.origin_y is not None else int(height * 0.75)
        return ox, oy

    def project(
        self,
        x: float,
        y: float,
        z: float,
        width: int,
        height: int,
    ) -> tuple[float, float, float]:
        """Project world (x, y, z) relative to pivot into (screen_x, screen_y, depth).

        Higher `depth` means closer to the camera (painter's order draws smaller depth first).
        """
        ox, oy = self.resolve_origin(width, height)
        rad_yaw = math.radians(self.yaw)
        cy = math.cos(rad_yaw)
        sy = math.sin(rad_yaw)

        # Rotate around Z axis
        rx = x * cy - y * sy
        ry = x * sy + y * cy

        if self.oblique is not None:
            oy_step, oz_step = self.oblique
            sx = ox + rx * self.ppu
            sy_pos = oy - (ry * oy_step + z * oz_step) * self.ppu
            # Closer to camera = smaller ry (south) and higher z
            depth = -ry + z * 0.01
            return sx, sy_pos, depth

        rad_elev = math.radians(self.elevation)
        ce = math.cos(rad_elev)
        se = math.sin(rad_elev)

        sx = ox + rx * self.ppu
        # +Y goes north (up on screen by sin(elev)), +Z goes up on screen by cos(elev)
        sy_pos = oy - (ry * se + z * ce) * self.ppu
        # Depth toward camera: -ry * cos(elev) + z * sin(elev)
        depth = -ry * ce + z * se
        return sx, sy_pos, depth

    def rotate_normal_to_screen(self, nx: float, ny: float, nz: float) -> tuple[float, float, float]:
        """Rotate a world-space normal into camera screen space for fixed top-left lighting."""
        rad_yaw = math.radians(self.yaw)
        cy = math.cos(rad_yaw)
        sy = math.sin(rad_yaw)
        rx = nx * cy - ny * sy
        ry = nx * sy + ny * cy
        if self.oblique is not None:
            return (rx, ry, nz)
        rad_elev = math.radians(self.elevation)
        ce = math.cos(rad_elev)
        se = math.sin(rad_elev)
        # Screen-space up and toward-camera components
        sy_n = ry * se + nz * ce
        sz_n = -ry * ce + nz * se
        return (rx, sy_n, sz_n)
