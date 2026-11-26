"""Articulated 3D voxel character rig and keyframe animation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pixelai.voxel.model import Coord3, VoxelLayer, VoxelModel
from pixelai.voxel.ramps import VoxelPalette, ramp_from_color


@dataclass(slots=True)
class RigPart:
    """A single articulated voxel part with a local pivot and offset."""

    name: str
    voxels: dict[Coord3, int] = field(default_factory=dict)
    pivot: tuple[float, float, float] = (0.0, 0.0, 0.0)
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(slots=True)
class VoxelRig:
    """Articulated 3D voxel character rig."""

    parts: list[RigPart]
    palette: VoxelPalette
    name: str = "rig"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "palette": self.palette.to_dict(),
            "parts": [
                {
                    "name": p.name,
                    "pivot": list(p.pivot),
                    "offset": list(p.offset),
                    "voxels": [[x, y, z, c] for (x, y, z), c in p.voxels.items()],
                }
                for p in self.parts
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoxelRig:
        palette = VoxelPalette.from_dict(data["palette"])
        parts: list[RigPart] = []
        for pd in data.get("parts", []):
            vox = {(int(v[0]), int(v[1]), int(v[2])): int(v[3]) for v in pd.get("voxels", [])}
            parts.append(
                RigPart(
                    name=str(pd["name"]),
                    voxels=vox,
                    pivot=tuple(float(x) for x in pd.get("pivot", (0.0, 0.0, 0.0))),  # type: ignore[arg-type]
                    offset=tuple(float(x) for x in pd.get("offset", (0.0, 0.0, 0.0))),  # type: ignore[arg-type]
                )
            )
        return cls(parts=parts, palette=palette, name=str(data.get("name", "rig")))

    @classmethod
    def load(cls, path: str | Path) -> VoxelRig:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _rotate_xz(x: float, y: float, z: float, angle_deg: float) -> tuple[float, float, float]:
    rad = math.radians(angle_deg)
    c = math.cos(rad)
    s = math.sin(rad)
    return (x * c - z * s, y, x * s + z * c)


def pose_rig(
    rig: VoxelRig,
    angles: dict[str, float] | None = None,
    *,
    root_bob_z: int = 0,
) -> VoxelModel:
    """Compose a VoxelModel by rotating each rig part around its pivot."""
    angles = angles or {}
    merged: dict[Coord3, int] = {}
    for part in rig.parts:
        ang = angles.get(part.name, 0.0)
        px, py, pz = part.pivot
        ox, oy, oz = part.offset
        for (vx, vy, vz), color_idx in part.voxels.items():
            rx, ry, rz = _rotate_xz(vx - px, vy - py, vz - pz, ang)
            wx = round(rx + px + ox)
            wy = round(ry + py + oy)
            wz = round(rz + pz + oz) + root_bob_z
            merged[(wx, wy, wz)] = color_idx
    return VoxelModel(palette=rig.palette, layers=[VoxelLayer(id=rig.name, voxels=merged)])


def generate_rig_walk_frames(rig: VoxelRig, *, frames: int = 4, swing_deg: float = 28.0) -> list[VoxelModel]:
    """Generate articulated walk-cycle frames for a VoxelRig."""
    out: list[VoxelModel] = []
    for i in range(max(1, frames)):
        phase = (2.0 * math.pi * i) / max(1, frames)
        leg_ang = math.sin(phase) * swing_deg
        arm_ang = -math.sin(phase) * (swing_deg * 0.8)
        bob = 1 if abs(math.sin(phase)) > 0.7 else 0
        angles = {
            "leg_l": leg_ang,
            "leg_r": -leg_ang,
            "arm_l": arm_ang,
            "arm_r": -arm_ang,
            "item_r": -arm_ang,
        }
        out.append(pose_rig(rig, angles, root_bob_z=bob))
    return out


def generate_rig_idle_frames(rig: VoxelRig, *, frames: int = 4) -> list[VoxelModel]:
    """Generate subtle breathing idle frames for a VoxelRig."""
    out: list[VoxelModel] = []
    for i in range(max(1, frames)):
        phase = (2.0 * math.pi * i) / max(1, frames)
        bob = 1 if math.sin(phase) > 0.5 else 0
        arm_ang = math.sin(phase) * 6.0
        out.append(pose_rig(rig, {"arm_l": arm_ang, "arm_r": -arm_ang}, root_bob_z=bob))
    return out


def default_humanoid_rig() -> VoxelRig:
    """Create a ready-to-use articulated humanoid voxel rig."""
    palette = VoxelPalette(
        ramps=[
            ramp_from_color((26, 28, 44, 255), name="outline"),
            ramp_from_color((244, 204, 161, 255), name="skin"),
            ramp_from_color((65, 114, 178, 255), name="tunic"),
            ramp_from_color((58, 68, 102, 255), name="pants"),
            ramp_from_color((115, 62, 57, 255), name="hair"),
        ]
    )
    leg_l = RigPart(
        name="leg_l",
        pivot=(0.0, -1.0, 4.0),
        voxels={(x, -1, z): 3 for x in range(-1, 1) for z in range(0, 4)},
    )
    leg_r = RigPart(
        name="leg_r",
        pivot=(0.0, 1.0, 4.0),
        voxels={(x, 1, z): 3 for x in range(-1, 1) for z in range(0, 4)},
    )
    torso = RigPart(
        name="torso",
        pivot=(0.0, 0.0, 6.0),
        voxels={(x, y, z): 2 for x in range(-1, 2) for y in range(-1, 2) for z in range(4, 9)},
    )
    arm_l = RigPart(
        name="arm_l",
        pivot=(0.0, -2.0, 8.0),
        voxels={(0, -2, z): 1 if z < 6 else 2 for z in range(5, 9)},
    )
    arm_r = RigPart(
        name="arm_r",
        pivot=(0.0, 2.0, 8.0),
        voxels={(0, 2, z): 1 if z < 6 else 2 for z in range(5, 9)},
    )
    head = RigPart(
        name="head",
        pivot=(0.0, 0.0, 9.0),
        voxels={
            (x, y, z): (4 if z == 12 or x == -1 else 1)
            for x in range(-1, 2)
            for y in range(-1, 2)
            for z in range(9, 13)
        },
    )
    return VoxelRig(parts=[leg_l, leg_r, torso, arm_l, arm_r, head], palette=palette, name="humanoid")
