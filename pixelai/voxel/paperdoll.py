"""Paper-doll 3D layer composition, socket attachment, and outfit wrapping.

Enables the Human <-> AI hybrid workflow:
- Human sculpts a locked `body_base` in `.vox.json` with anchor sockets (`head`, `torso`, `hand_r`).
- AI agent generates swappable outfit/hat/face/item overlay specs via CLI.
- `compose_paperdoll()` produces a new VoxelModel without mutating the base body.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pixelai.voxel.model import Coord3, VoxelLayer, VoxelModel
from pixelai.voxel.primitives import vox_box, vox_carve, vox_cylinder, vox_ellipsoid, vox_mirror_x, vox_shell
from pixelai.voxel.ramps import VoxelPalette, VoxelRamp, encode_voxel_value


def _resolve_op_value(op: dict[str, Any], palette: VoxelPalette) -> int:
    if "value" in op:
        return int(op["value"])
    ramp_name = str(op["ramp"])
    shade = int(op.get("shade", 1))
    r_idx = palette.ramp_index(ramp_name)
    return encode_voxel_value(r_idx, shade)


def compose_paperdoll(
    base_model: VoxelModel,
    overlays: list[dict[str, Any]],
    *,
    extra_ramps: list[dict[str, Any]] | None = None,
) -> VoxelModel:
    """Compose swappable overlay layers onto a base VoxelModel without mutating base_model."""
    # Deep-copy palette and layers so base_model is strictly immutable
    new_ramps = list(base_model.palette.ramps)
    if extra_ramps:
        for r_dict in extra_ramps:
            new_ramps.append(VoxelRamp.from_dict(r_dict))
    new_palette = VoxelPalette(
        ramps=new_ramps,
        outline=base_model.palette.outline,
        palette_ref=base_model.palette.palette_ref,
    )

    new_layers = [
        VoxelLayer(
            id=l.id,
            role=l.role,
            priority=l.priority,
            visible=l.visible,
            locked=l.locked,
            voxels=dict(l.voxels),
        )
        for l in base_model.layers
    ]
    composed = VoxelModel(
        palette=new_palette,
        layers=new_layers,
        bounds=base_model.bounds,
        pivot=base_model.pivot,
        sockets=deepcopy(base_model.sockets),
    )

    for ov in overlays:
        layer_id = str(ov["id"])
        role = str(ov.get("role", "outfit"))
        priority = int(ov.get("priority", 10))
        attach_socket = ov.get("attach_socket")
        ox = oy = oz = 0
        if attach_socket:
            if attach_socket not in composed.sockets:
                raise KeyError(f"Overlay {layer_id!r} references unknown socket {attach_socket!r}")
            ox, oy, oz = composed.sockets[attach_socket]

        # Optional masking/culling of lower layers (e.g., helmet hides hair)
        for mask_id in ov.get("hide_layers", []):
            for existing in composed.layers:
                if existing.id == mask_id:
                    existing.visible = False

        layer = VoxelLayer(id=layer_id, role=role, priority=priority, visible=True, locked=False)

        # Raw voxels (shifted by socket if attached)
        for entry in ov.get("voxels", []):
            x, y, z, val = entry
            layer.set(x + ox, y + oy, z + oz, int(val))

        # Declarative ops
        for op in ov.get("ops", []):
            kind = str(op["op"])
            if kind == "vox_box":
                val = _resolve_op_value(op, new_palette)
                vox_box(
                    layer,
                    int(op["x0"]) + ox, int(op["y0"]) + oy, int(op["z0"]) + oz,
                    int(op["x1"]) + ox, int(op["y1"]) + oy, int(op["z1"]) + oz,
                    val,
                )
            elif kind == "vox_ellipsoid":
                val = _resolve_op_value(op, new_palette)
                vox_ellipsoid(
                    layer,
                    float(op["cx"]) + ox, float(op["cy"]) + oy, float(op["cz"]) + oz,
                    float(op["rx"]), float(op["ry"]), float(op["rz"]),
                    val,
                )
            elif kind == "vox_cylinder":
                val = _resolve_op_value(op, new_palette)
                vox_cylinder(
                    layer,
                    float(op["cx"]) + ox, float(op["cy"]) + oy,
                    int(op["z0"]) + oz, int(op["z1"]) + oz,
                    float(op["radius"]),
                    val,
                )
            elif kind == "vox_carve":
                vox_carve(
                    layer,
                    int(op["x0"]) + ox, int(op["y0"]) + oy, int(op["z0"]) + oz,
                    int(op["x1"]) + ox, int(op["y1"]) + oy, int(op["z1"]) + oz,
                )
            elif kind == "vox_mirror_x":
                vox_mirror_x(layer, axis_x=int(op.get("axis_x", 0)) + ox)
            elif kind == "vox_shell":
                ref_id = str(op.get("around", "body_base"))
                ref_layer = composed.get_layer(ref_id)
                val = _resolve_op_value(op, new_palette)
                vox_shell(
                    layer,
                    ref_layer.voxels,
                    val,
                    z_min=int(op["z_min"]) + oz if "z_min" in op else None,
                    z_max=int(op["z_max"]) + oz if "z_max" in op else None,
                    thickness=int(op.get("thickness", 1)),
                )
            else:
                raise ValueError(f"Unknown voxel overlay op {kind!r}")

        composed.add_layer(layer)

    return composed
