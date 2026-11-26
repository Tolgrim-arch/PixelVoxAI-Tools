"""End-to-end tests for VoxPix parity features: CLI, pxl bridge, fluids, daycycle, lightmap, weather, and world."""

from __future__ import annotations

import json
from pathlib import Path

from pixelai.canvas import Canvas
from pixelai.cli import main as cli_main
from pixelai.voxel import (
    ShallowWaterSim,
    VoxelLayer,
    VoxelModel,
    VoxelWorld,
    WorldRecipe,
    apply_weather_overlay,
    bake_lightmap,
    encode_voxel_value,
    evaluate_day_cycle,
    export_pxl,
    get_sample_model,
    import_pxl,
    load_palette_preset,
    pour_fluid,
    tap_fluid,
)
from pixelai.voxel.primitives import vox_box


def test_pxl_stack_roundtrip() -> None:
    model = get_sample_model("torch")
    pxl_text = export_pxl(model, stack_prefix="torch")
    assert "// voxpix: outline" in pxl_text
    assert "// voxpix: emissive" in pxl_text
    rebuilt = import_pxl(pxl_text, stack_prefix="torch")
    assert len(rebuilt.flatten()) == len(model.flatten())


def test_pxl_turn_and_single_plane_and_palette_only() -> None:
    model = get_sample_model("torch")
    pxl_turn = export_pxl(model, name="torch", turn=4, width=24, height=24)
    assert "torch_a00" in pxl_turn and "torch_a03" in pxl_turn

    pal_only = import_pxl(pxl_turn, sprite_name="-")
    assert len(pal_only.flatten()) == 0
    assert len(pal_only.palette.ramps) >= 1

    front = import_pxl(pxl_turn, sprite_name="torch_a00", plane="front", z=0)
    assert len(front.flatten()) > 0


def test_fluid_pour_tap_and_shallow_water() -> None:
    pal = load_palette_preset("medieval", steps=4)
    model = VoxelModel(palette=pal, bounds=(12, 12, 10))
    bed = VoxelLayer(id="bed", priority=0)
    water = VoxelLayer(id="water", priority=1)
    model.add_layer(bed)
    model.add_layer(water)

    stone = encode_voxel_value(2, 2)
    fluid = encode_voxel_value(5, 2)
    vox_box(bed, -3, -3, 0, 3, 3, 0, stone)
    placed = pour_fluid(model, water, (0, 0, 4), fluid, volume=10)
    assert placed == 10
    added = tap_fluid(model, water, (0, 0, 4), fluid, ticks=3, rate=2)
    assert added == 6

    sim = ShallowWaterSim(width=8, height=8)
    sim.disturb(4, 4, 1.0)
    sim.step(3)
    assert sim.water_surface_shade(4, 4) in (-1, 0, 1)


def test_daycycle_lightmap_and_weather() -> None:
    noon = evaluate_day_cycle(12.0)
    night = evaluate_day_cycle(23.0)
    assert noon.phase == "day" and not noon.ambient_dark
    assert night.phase == "night" and night.ambient_dark

    model = get_sample_model("torch")
    lm = bake_lightmap(model, hour=22.0)
    assert lm.lights_count >= 1
    assert len(lm.values) == len(model.flatten())

    c = Canvas(32, 32)
    apply_weather_overlay(c, "rain", tick=2)
    apply_weather_overlay(c, "snow", tick=4)
    apply_weather_overlay(c, "fog", tick=1)


def test_world_generation_simulation_section_and_bake() -> None:
    recipe = WorldRecipe.from_theme("neon", seed=99, width=20, depth=20)
    world = VoxelWorld.from_recipe(recipe)
    world.step(5)
    lm = world.bake()
    assert lm.lights_count >= 1
    info = world.info()
    assert info["theme"] == "neon"
    assert info["tick"] == 5
    cut = world.section_cut(max_z=1)
    assert all(z <= 1 for (_x, _y, z) in cut.flatten())
    canvas = world.render(width=64, height=48, whole=True)
    assert canvas.width == 64 and canvas.height == 48


def test_cli_voxel_and_world_commands(tmp_path: Path) -> None:
    png_out = tmp_path / "sample.png"
    assert cli_main(["voxel", "render", "torch", str(png_out), "--size", "32x32", "--verify-palette"]) == 0
    assert png_out.exists()

    strip_out = tmp_path / "strip.png"
    assert cli_main(["voxel", "render", "torch", str(strip_out), "--turn", "4", "--size", "24x24"]) == 0
    assert strip_out.exists()

    gif_out = tmp_path / "turn.gif"
    assert cli_main(["voxel", "turntable", "torch", str(gif_out), "--frames", "4", "--size", "24x24", "--scale", "1"]) == 0
    assert gif_out.exists()

    pal_out = tmp_path / "pico8.json"
    assert cli_main(["voxel", "palette", "pico8", "-o", str(pal_out)]) == 0
    assert pal_out.exists()

    pxl_out = tmp_path / "torch.px.js"
    model_out = tmp_path / "torch_rebuilt.json"
    assert cli_main(["voxel", "export-pxl", "torch", str(pxl_out), "--stack", "t"]) == 0
    assert cli_main(["voxel", "import-pxl", str(pxl_out), "-", str(model_out), "--stack", "t"]) == 0
    assert model_out.exists()

    world_png = tmp_path / "world.png"
    world_info = tmp_path / "world_info.json"
    assert cli_main([
        "world", "medieval", str(world_png),
        "--size", "64x48", "--ticks", "3", "--whole", "--bake", "--info", str(world_info),
    ]) == 0
    assert world_png.exists()
    data = json.loads(world_info.read_text(encoding="utf-8"))
    assert data["theme"] == "medieval"
    assert data["tick"] == 3
