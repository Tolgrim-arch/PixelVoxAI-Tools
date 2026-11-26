"""Tests for pixelai.voxel.editor (VoxelEditor and apply_operations)."""

from __future__ import annotations

from pixelai.voxel.editor import VoxelEditor, apply_operations
from pixelai.voxel.model import VoxelModel
from pixelai.voxel.ramps import VoxelPalette, encode_voxel_value, ramp_from_color


def _make_model() -> VoxelModel:
    pal = VoxelPalette(ramps=[
        ramp_from_color("#808080", name="stone"),
        ramp_from_color("#3366cc", name="water"),
        ramp_from_color("#ffcc33", name="gold"),
    ])
    return VoxelModel(palette=pal)


def test_editor_paint_erase_repaint_undo_redo() -> None:
    model = _make_model()
    ed = VoxelEditor(model)
    val1 = encode_voxel_value(1, 2)
    val2 = encode_voxel_value(2, 2)

    ed.paint(0, 0, 0, val1)
    assert ed.eyedropper(0, 0, 0) == val1

    assert ed.repaint(0, 0, 0, val2) is True
    assert ed.eyedropper(0, 0, 0) == val2
    assert ed.repaint(5, 5, 5, val2) is False

    assert ed.undo() is True
    assert ed.eyedropper(0, 0, 0) == val1
    assert ed.redo() is True
    assert ed.eyedropper(0, 0, 0) == val2

    ed.erase(0, 0, 0)
    assert ed.eyedropper(0, 0, 0) == 0


def test_editor_box_mirror_flood_fill_resize() -> None:
    model = _make_model()
    ed = VoxelEditor(model)
    stone = encode_voxel_value(1, 2)
    gold = encode_voxel_value(3, 2)

    count = ed.box(1, 0, 0, 2, 1, 1, stone)
    assert count == 8
    ed.mirror(axis="x", center=0)
    assert ed.eyedropper(-1, 0, 0) == stone
    assert ed.eyedropper(-2, 1, 1) == stone

    filled = ed.flood_fill(1, 0, 0, gold)
    assert filled == 8
    assert ed.eyedropper(2, 1, 1) == gold

    ed.add_light(0, 0, 3, color="#ffaa44", radius=6.0)
    assert "light:0,0,3" in ed.model.sockets

    removed = ed.resize(2, 2, 1)
    assert removed > 0
    assert ed.eyedropper(2, 1, 1) == 0


def test_apply_operations_batch() -> None:
    model = _make_model()
    stone = encode_voxel_value(1, 2)
    ops = [
        {"type": "box", "x0": -1, "y0": -1, "z0": 0, "x1": 1, "y1": 1, "z1": 0, "value": stone},
        {"type": "erase", "x": 0, "y": 0, "z": 0},
        {"type": "add_light", "x": 0, "y": 0, "z": 2, "color": "#ffdd88"},
    ]
    out = apply_operations(model, ops)
    assert out.layers[0].get(0, 0, 0) == 0
    assert out.layers[0].get(1, 1, 0) == stone
    assert "light:0,0,2" in out.sockets
