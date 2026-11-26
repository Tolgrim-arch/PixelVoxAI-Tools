"""Programmatic voxel model editor with undo/redo and batch operations (VoxPix agent API parity)."""

from __future__ import annotations

from collections import deque
from typing import Any

from pixelai.voxel.fluid import fill_to_level, pour_fluid, tap_fluid
from pixelai.voxel.model import Coord3, VoxelLayer, VoxelModel


class VoxelEditor:
    """Stateful editor for VoxelModel with deterministic undo/redo snapshots."""

    def __init__(self, model: VoxelModel, layer_id: str | None = None, max_history: int = 64) -> None:
        self.model = model
        if layer_id is None:
            layer_id = model.layers[0].id if model.layers else "main"
        self.layer_id = layer_id
        self.max_history = max_history
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []

    def _push_snapshot(self) -> None:
        self._undo_stack.append(self.model.to_dict())
        if len(self._undo_stack) > self.max_history:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> bool:
        """Revert to the previous model snapshot. Returns True if undone."""
        if not self._undo_stack:
            return False
        self._redo_stack.append(self.model.to_dict())
        prev = self._undo_stack.pop()
        self.model = VoxelModel.from_dict(prev)
        return True

    def redo(self) -> bool:
        """Reapply a previously undone snapshot. Returns True if redone."""
        if not self._redo_stack:
            return False
        self._undo_stack.append(self.model.to_dict())
        nxt = self._redo_stack.pop()
        self.model = VoxelModel.from_dict(nxt)
        return True

    def _layer(self) -> VoxelLayer:
        for layer in self.model.layers:
            if layer.id == self.layer_id:
                return layer
        layer = VoxelLayer(id=self.layer_id)
        self.model.layers.append(layer)
        return layer

    def eyedropper(self, x: int, y: int, z: int) -> int:
        """Return the voxel value at (x, y, z) in the active layer, or 0 if empty."""
        return self._layer().get(x, y, z)

    def paint(self, x: int, y: int, z: int, value: int) -> None:
        """Paint a single voxel at (x, y, z)."""
        self._push_snapshot()
        self._layer().set(x, y, z, value)

    def erase(self, x: int, y: int, z: int) -> None:
        """Erase a single voxel at (x, y, z)."""
        self._push_snapshot()
        self._layer().set(x, y, z, 0)

    def repaint(self, x: int, y: int, z: int, value: int) -> bool:
        """Paint (x, y, z) only if it is currently non-empty. Returns True if painted."""
        if self._layer().get(x, y, z) == 0:
            return False
        self._push_snapshot()
        self._layer().set(x, y, z, value)
        return True

    def box(
        self,
        x0: int,
        y0: int,
        z0: int,
        x1: int,
        y1: int,
        z1: int,
        value: int,
        hollow: bool = False,
    ) -> int:
        """Fill an axis-aligned 3D box with `value`. Returns count of modified voxels."""
        self._push_snapshot()
        layer = self._layer()
        lx0, lx1 = min(x0, x1), max(x0, x1)
        ly0, ly1 = min(y0, y1), max(y0, y1)
        lz0, lz1 = min(z0, z1), max(z0, z1)
        count = 0
        for z in range(lz0, lz1 + 1):
            for y in range(ly0, ly1 + 1):
                for x in range(lx0, lx1 + 1):
                    if hollow and (lx0 < x < lx1) and (ly0 < y < ly1) and (lz0 < z < lz1):
                        continue
                    layer.set(x, y, z, value)
                    count += 1
        return count

    def flood_fill(self, x: int, y: int, z: int, value: int, max_voxels: int = 4096) -> int:
        """3D 6-connected flood fill starting at (x, y, z). Returns count of filled voxels."""
        layer = self._layer()
        target = layer.get(x, y, z)
        if target == value:
            return 0
        self._push_snapshot()
        layer = self._layer()
        queue: deque[Coord3] = deque([(x, y, z)])
        visited: set[Coord3] = {(x, y, z)}
        count = 0
        while queue and count < max_voxels:
            cx, cy, cz = queue.popleft()
            if layer.get(cx, cy, cz) != target:
                continue
            layer.set(cx, cy, cz, value)
            count += 1
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                nb = (cx + dx, cy + dy, cz + dz)
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        return count

    def mirror(self, axis: str = "x", center: int = 0) -> int:
        """Mirror all voxels in the active layer across `axis` ('x', 'y', or 'z')."""
        axis = axis.lower()
        if axis not in ("x", "y", "z"):
            raise ValueError(f"Invalid mirror axis {axis!r}; expected 'x', 'y', or 'z'")
        self._push_snapshot()
        layer = self._layer()
        items = list(layer.voxels.items())
        count = 0
        for (x, y, z), val in items:
            if axis == "x":
                nx, ny, nz = 2 * center - x, y, z
            elif axis == "y":
                nx, ny, nz = x, 2 * center - y, z
            else:
                nx, ny, nz = x, y, 2 * center - z
            layer.set(nx, ny, nz, val)
            count += 1
        return count

    def add_light(
        self,
        x: int,
        y: int,
        z: int,
        color: str = "#ffaa44",
        radius: float = 8.0,
        intensity: float = 1.0,
    ) -> None:
        """Attach a point light socket to the model."""
        self._push_snapshot()
        key = f"light:{int(x)},{int(y)},{int(z)}"
        self.model.sockets[key] = (int(x), int(y), int(z))

    def resize(self, width: int, depth: int, height: int) -> int:
        """Clip voxels to fit within (width, depth, height) centered on X/Y and Z>=0."""
        if width <= 0 or depth <= 0 or height <= 0:
            raise ValueError("Dimensions must be positive integers")
        self._push_snapshot()
        half_x = width // 2
        half_y = depth // 2
        removed = 0
        for layer in self.model.layers:
            to_del = [
                coord
                for coord in layer.voxels
                if not (-half_x <= coord[0] <= half_x and -half_y <= coord[1] <= half_y and 0 <= coord[2] < height)
            ]
            for coord in to_del:
                del layer.voxels[coord]
                removed += 1
        return removed

    def pour(self, x: int, y: int, z: int, value: int, steps: int = 64) -> int:
        """Pour fluid from (x, y, z) into the active layer."""
        self._push_snapshot()
        return pour_fluid(self.model, (x, y, z), value, steps=steps, layer_id=self.layer_id)

    def tap(self, x: int, y: int, z: int, value: int, ticks: int = 16) -> int:
        """Simulate a continuous fluid tap at (x, y, z)."""
        self._push_snapshot()
        return tap_fluid(self.model, (x, y, z), value, ticks=ticks, layer_id=self.layer_id)

    def fill_level(self, x: int, y: int, z: int, value: int, level_z: int) -> int:
        """Fill a basin starting at (x, y, z) up to `level_z`."""
        self._push_snapshot()
        return fill_to_level(self.model, (x, y, z), value, water_level_z=level_z, layer_id=self.layer_id)


def apply_operations(model: VoxelModel, ops: list[dict[str, Any]]) -> VoxelModel:
    """Execute a sequence of JSON-serializable edit operations on a VoxelModel."""
    editor = VoxelEditor(model)
    for op in ops:
        kind = str(op.get("type", "")).lower()
        if "layer" in op and op["layer"]:
            editor.layer_id = str(op["layer"])
        if kind == "paint":
            editor.paint(int(op["x"]), int(op["y"]), int(op["z"]), int(op["value"]))
        elif kind == "erase":
            editor.erase(int(op["x"]), int(op["y"]), int(op["z"]))
        elif kind == "repaint":
            editor.repaint(int(op["x"]), int(op["y"]), int(op["z"]), int(op["value"]))
        elif kind == "box":
            editor.box(
                int(op["x0"]),
                int(op["y0"]),
                int(op["z0"]),
                int(op["x1"]),
                int(op["y1"]),
                int(op["z1"]),
                int(op["value"]),
                hollow=bool(op.get("hollow", False)),
            )
        elif kind == "flood_fill":
            editor.flood_fill(
                int(op["x"]),
                int(op["y"]),
                int(op["z"]),
                int(op["value"]),
                max_voxels=int(op.get("max_voxels", 4096)),
            )
        elif kind == "mirror":
            editor.mirror(axis=str(op.get("axis", "x")), center=int(op.get("center", 0)))
        elif kind == "add_light":
            editor.add_light(
                int(op["x"]),
                int(op["y"]),
                int(op["z"]),
                color=str(op.get("color", "#ffaa44")),
                radius=float(op.get("radius", 8.0)),
                intensity=float(op.get("intensity", 1.0)),
            )
        elif kind == "resize":
            editor.resize(int(op["width"]), int(op["depth"]), int(op["height"]))
        elif kind == "pour":
            editor.pour(int(op["x"]), int(op["y"]), int(op["z"]), int(op["value"]), steps=int(op.get("steps", 64)))
        elif kind == "tap":
            editor.tap(int(op["x"]), int(op["y"]), int(op["z"]), int(op["value"]), ticks=int(op.get("ticks", 16)))
        elif kind == "fill_level":
            editor.fill_level(int(op["x"]), int(op["y"]), int(op["z"]), int(op["value"]), level_z=int(op["level_z"]))
        elif kind == "undo":
            editor.undo()
        elif kind == "redo":
            editor.redo()
        else:
            raise ValueError(f"Unknown edit operation type: {kind!r}")
    return editor.model
