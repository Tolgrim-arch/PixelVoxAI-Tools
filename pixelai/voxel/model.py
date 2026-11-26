"""Sparse 3D voxel model with named semantic layers and anchor sockets.

Coordinate system (matching VoxPix):
    X = East (+right)
    Y = North (+away from camera in front view)
    Z = Up (+height)
    Pivot = (0, 0, 0) at the model's feet/ground anchor.
    Valid integer coordinate range: [-1023, 1023] on each axis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from pixelai.voxel.ramps import VoxelPalette, decode_voxel_value

MIN_COORD = -1023
MAX_COORD = 1023
FORMAT_VERSION = "pixelai.voxel.v1"

Coord3 = tuple[int, int, int]


def validate_coord(x: int, y: int, z: int) -> Coord3:
    """Validate integer voxel coordinates within [-1023, 1023]."""
    if not (isinstance(x, int) and isinstance(y, int) and isinstance(z, int)):
        raise TypeError(f"Voxel coordinates must be integers, got ({x!r}, {y!r}, {z!r})")
    if isinstance(x, bool) or isinstance(y, bool) or isinstance(z, bool):
        raise TypeError(f"Voxel coordinates must not be booleans, got ({x!r}, {y!r}, {z!r})")
    if not (MIN_COORD <= x <= MAX_COORD and MIN_COORD <= y <= MAX_COORD and MIN_COORD <= z <= MAX_COORD):
        raise ValueError(
            f"Voxel coordinate ({x}, {y}, {z}) out of bounds [{MIN_COORD}, {MAX_COORD}]"
        )
    return (x, y, z)


@dataclass(slots=True)
class VoxelLayer:
    """A named semantic layer of sparse voxels (e.g., body, outfit, hat, face)."""

    id: str
    role: str = "body"
    priority: int = 0
    visible: bool = True
    locked: bool = False
    voxels: dict[Coord3, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("VoxelLayer id must be non-empty")

    def set(self, x: int, y: int, z: int, value: int) -> None:
        """Set or erase (value=0) a voxel in this layer."""
        if self.locked:
            raise PermissionError(f"VoxelLayer {self.id!r} is locked and cannot be mutated")
        coord = validate_coord(x, y, z)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Voxel value must be a non-negative int, got {value!r}")
        if value == 0:
            self.voxels.pop(coord, None)
        else:
            decode_voxel_value(value)  # validates range
            self.voxels[coord] = value

    def get(self, x: int, y: int, z: int) -> int:
        """Return voxel value at (x, y, z), or 0 if empty."""
        return self.voxels.get((x, y, z), 0)

    def to_dict(self) -> dict[str, Any]:
        sorted_voxels = [
            [x, y, z, val]
            for (x, y, z), val in sorted(self.voxels.items(), key=lambda item: (item[0][2], item[0][1], item[0][0]))
        ]
        return {
            "id": self.id,
            "role": self.role,
            "priority": self.priority,
            "visible": self.visible,
            "locked": self.locked,
            "voxels": sorted_voxels,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoxelLayer:
        layer = cls(
            id=str(data["id"]),
            role=str(data.get("role", "body")),
            priority=int(data.get("priority", 0)),
            visible=bool(data.get("visible", True)),
            locked=False,
        )
        for entry in data.get("voxels", []):
            if not isinstance(entry, (list, tuple)) or len(entry) != 4:
                raise ValueError(f"Invalid voxel entry {entry!r}; expected [x, y, z, value]")
            x, y, z, val = entry
            layer.set(x, y, z, val)
        layer.locked = bool(data.get("locked", False))
        return layer


@dataclass(slots=True)
class VoxelModel:
    """Sparse 3D voxel model with semantic layers, sockets, and closed palette."""

    palette: VoxelPalette = field(default_factory=VoxelPalette)
    layers: list[VoxelLayer] = field(default_factory=list)
    bounds: tuple[int, int, int] = (32, 32, 32)
    pivot: Coord3 = (0, 0, 0)
    sockets: dict[str, Coord3] = field(default_factory=dict)

    def __post_init__(self) -> None:
        w, d, h = self.bounds
        if w <= 0 or d <= 0 or h <= 0:
            raise ValueError(f"VoxelModel bounds must be positive, got {self.bounds}")
        self.pivot = validate_coord(*self.pivot)
        self.sockets = {k: validate_coord(*v) for k, v in self.sockets.items()}

    def get_layer(self, layer_id: str) -> VoxelLayer:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        raise KeyError(f"Unknown voxel layer {layer_id!r}")

    def add_layer(self, layer: VoxelLayer) -> None:
        if any(existing.id == layer.id for existing in self.layers):
            raise ValueError(f"Duplicate voxel layer id {layer.id!r}")
        self.layers.append(layer)

    def flatten(self) -> dict[Coord3, int]:
        """Composite all visible layers in ascending priority order (higher wins)."""
        ordered = sorted(
            (layer for layer in self.layers if layer.visible),
            key=lambda l: l.priority,
        )
        merged: dict[Coord3, int] = {}
        for layer in ordered:
            merged.update(layer.voxels)
        return merged

    def iter_voxels(self) -> Iterator[tuple[Coord3, int]]:
        """Yield flattened (coord, value) pairs in deterministic Z, Y, X order."""
        merged = self.flatten()
        for coord in sorted(merged.keys(), key=lambda c: (c[2], c[1], c[0])):
            yield coord, merged[coord]

    def bounding_box(self) -> tuple[Coord3, Coord3] | None:
        """Return ((min_x, min_y, min_z), (max_x, max_y, max_z)) or None if empty."""
        merged = self.flatten()
        if not merged:
            return None
        xs = [c[0] for c in merged]
        ys = [c[1] for c in merged]
        zs = [c[2] for c in merged]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def to_dict(self) -> dict[str, Any]:
        w, d, h = self.bounds
        pal_dict = self.palette.to_dict()
        out: dict[str, Any] = {
            "format": FORMAT_VERSION,
            "bounds": {"w": w, "d": d, "h": h},
            "pivot": list(self.pivot),
            "ramps": pal_dict["ramps"],
            "outline": pal_dict["outline"],
            "sockets": {k: list(v) for k, v in sorted(self.sockets.items())},
            "layers": [l.to_dict() for l in self.layers],
        }
        if "palette_ref" in pal_dict:
            out["palette_ref"] = pal_dict["palette_ref"]
        return out

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json() + "\n", encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoxelModel:
        fmt = data.get("format", FORMAT_VERSION)
        if fmt != FORMAT_VERSION:
            raise ValueError(f"Unsupported voxel format {fmt!r}; expected {FORMAT_VERSION!r}")
        raw_bounds = data.get("bounds", {"w": 32, "d": 32, "h": 32})
        bounds = (int(raw_bounds["w"]), int(raw_bounds["d"]), int(raw_bounds["h"]))
        raw_pivot = data.get("pivot", [0, 0, 0])
        pivot = validate_coord(int(raw_pivot[0]), int(raw_pivot[1]), int(raw_pivot[2]))
        palette = VoxelPalette.from_dict(data)
        raw_sockets = data.get("sockets", {})
        sockets = {
            str(k): validate_coord(int(v[0]), int(v[1]), int(v[2]))
            for k, v in raw_sockets.items()
        }
        layers = [VoxelLayer.from_dict(l) for l in data.get("layers", [])]
        model = cls(palette=palette, layers=layers, bounds=bounds, pivot=pivot, sockets=sockets)
        # Validate all voxel ramp references against palette
        for _coord, val in model.iter_voxels():
            palette.resolve_color(val)
        return model

    @classmethod
    def load(cls, path: str | Path) -> VoxelModel:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)
