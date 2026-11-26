"""CLI subcommands for voxel rendering, turntables, palettes, pxl bridge, and 2.5D worlds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pixelai.canvas import Canvas
from pixelai.color import RGBA, parse_color
from pixelai.exporter import export_gif, export_png
from pixelai.filters import scale as scale_nearest
from pixelai.voxel.camera import VoxelCamera
from pixelai.voxel.anim import (
    export_animation_gif,
    export_animation_sheet,
    generate_idle_frames,
    generate_walk_frames,
    render_animation_frames,
)
from pixelai.voxel.bench import BenchmarkReport, measure_step
from pixelai.voxel.daycycle import evaluate_day_cycle
from pixelai.voxel.editor import apply_operations
from pixelai.voxel.lighting import extract_emissive_lights
from pixelai.voxel.model import VoxelModel
from pixelai.voxel.palettes_io import COMMUNITY_PRESETS, load_palette_any, verify_palette_colors
from pixelai.voxel.pxl_bridge import export_pxl_file, import_pxl_file
from pixelai.voxel.render import render_voxel_model, render_voxel_turntable
from pixelai.voxel.samples import SAMPLE_NAMES, get_sample_model
from pixelai.voxel.terrain import generate_terrain_model
from pixelai.voxel.weather import WEATHER_MODES, apply_weather_overlay
from pixelai.voxel.world import VoxelWorld
from pixelai.voxel.worldgen import WORLD_THEMES, WorldRecipe


def _parse_size(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    parts = raw.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid --size {raw!r}; expected WxH (e.g. 64x48)")
    return (int(parts[0]), int(parts[1]))


def _parse_xy(raw: str | None) -> tuple[int, int] | None:
    if not raw:
        return None
    parts = raw.split(",")
    if len(parts) != 2:
        raise ValueError(f"Invalid coordinate {raw!r}; expected x,y")
    return (int(parts[0]), int(parts[1]))


def _load_model_source(source: str) -> VoxelModel:
    if source.strip().lower() in SAMPLE_NAMES:
        return get_sample_model(source)
    return VoxelModel.from_dict(json.loads(Path(source).read_text(encoding="utf-8")))


def _auto_canvas_size(model: VoxelModel) -> tuple[int, int]:
    bbox = model.bounding_box()
    if bbox is None:
        return (64, 48)
    (x0, y0, z0), (x1, y1, z1) = bbox
    span_xy = max(x1 - x0 + 1, y1 - y0 + 1)
    span_z = z1 - z0 + 1
    w = max(64, int(span_xy * 3.0) + 16)
    h = max(48, int((span_xy * 0.7 + span_z) * 2.5) + 16)
    return (w, h)


def _apply_bg(canvas: Canvas, bg_rgba: RGBA | None) -> Canvas:
    if bg_rgba is None:
        return canvas
    for py in range(canvas.height):
        for px in range(canvas.width):
            if canvas.get_pixel(px, py)[3] == 0:
                canvas.set_pixel(px, py, bg_rgba)
    return canvas


def _cmd_voxel_edit(args: argparse.Namespace) -> int:
    model = _load_model_source(args.model)
    ops: list[dict] = []
    if args.ops:
        loaded = json.loads(Path(args.ops).read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError("--ops JSON file must contain a list of operation objects")
        ops.extend(loaded)
    for raw_op in args.op:
        ops.append(json.loads(raw_op))
    edited = apply_operations(model, ops)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(edited.to_dict(), indent=2), encoding="utf-8")
    return 0


def _cmd_voxel_animate(args: argparse.Namespace) -> int:
    model = _load_model_source(args.model)
    if args.cycle == "walk":
        frames_models = generate_walk_frames(model, frames=args.frames, stride=args.stride, bob=args.bob)
    else:
        frames_models = generate_idle_frames(model, frames=args.frames, bob=args.bob)
    w, h = _parse_size(args.size) or _auto_canvas_size(model)
    bg_rgba = parse_color(args.bg) if args.bg else None
    canvases = render_animation_frames(
        frames_models,
        yaw=args.yaw,
        elev=args.elev,
        scale=args.scale,
        size=(w, h),
        outline=args.outline,
        bg=bg_rgba,
    )
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == ".gif":
        export_animation_gif(canvases, out_path, ms=args.ms)
    else:
        export_animation_sheet(canvases, out_path)
    return 0


def _cmd_voxel_terrain(args: argparse.Namespace) -> int:
    parts = [int(p) for p in args.size.lower().split("x")]
    if len(parts) != 3:
        raise ValueError(f"Invalid --size {args.size!r}; expected WxDxH (e.g. 32x32x16)")
    model = generate_terrain_model(
        width=parts[0],
        depth=parts[1],
        height=parts[2],
        seed=args.seed,
        theme=args.theme,
        trees=not args.no_trees,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(model.to_dict(), indent=2), encoding="utf-8")
    return 0


def _cmd_voxel_render(args: argparse.Namespace) -> int:
    model = _load_model_source(args.model)
    if args.palette:
        model.palette = load_palette_any(args.palette)

    w, h = _parse_size(args.size) or _auto_canvas_size(model)
    origin = _parse_xy(args.origin)
    bg_rgba = parse_color(args.bg) if args.bg else None
    outline_mode = "none" if args.outline == "none" else "outer"

    lights = extract_emissive_lights(model) if args.lights else None
    ambient_dark = args.ambient < 0.5 if args.lights else False

    if args.turn and args.turn > 1:
        results = render_voxel_turntable(
            model,
            turns=args.turn,
            width=w,
            height=h,
            elevation=args.elev,
            lights=lights,
            sun_shadow=args.lights,
            ambient_dark=ambient_dark,
        )
        strip = Canvas(w * len(results), h)
        for i, res in enumerate(results):
            frame = _apply_bg(res, bg_rgba)
            strip.blit(frame, i * w, 0)
        out_canvas = strip
    else:
        cam = VoxelCamera(
            yaw=args.yaw,
            elevation=args.elev,
            origin_x=float(origin[0]) if origin else None,
            origin_y=float(origin[1]) if origin else None,
        )
        res = render_voxel_model(
            model,
            width=w,
            height=h,
            camera=cam,
            lights=lights,
            sun_shadow=args.lights,
            ambient_dark=ambient_dark,
        )
        out_canvas = _apply_bg(res.canvas, bg_rgba)

    if args.verify_palette:
        ok, stray = verify_palette_colors(out_canvas, model.palette, bg=bg_rgba)
        if not ok:
            raise ValueError(f"Palette verification failed; stray colors found: {', '.join(stray[:8])}")

    if args.scale > 1:
        out_canvas = scale_nearest(out_canvas, args.scale)

    export_png(out_canvas, args.output)
    print(f"Rendered {args.model} -> {args.output} ({out_canvas.width}x{out_canvas.height})")
    return 0


def _cmd_voxel_turntable(args: argparse.Namespace) -> int:
    model = _load_model_source(args.model)
    if args.palette:
        model.palette = load_palette_any(args.palette)

    w, h = _parse_size(args.size) or _auto_canvas_size(model)
    bg_rgba = parse_color(args.bg) if args.bg else None
    outline_mode = "none" if args.outline == "none" else "outer"
    lights = extract_emissive_lights(model) if args.lights else None
    ambient_dark = args.ambient < 0.5 if args.lights else False

    n = max(2, args.frames)
    results = render_voxel_turntable(
        model,
        turns=n,
        width=w,
        height=h,
        elevation=args.elev,
        lights=lights,
        sun_shadow=args.lights,
        ambient_dark=ambient_dark,
    )
    frames: list[Canvas] = []
    for res in results:
        c = _apply_bg(res, bg_rgba)
        if args.scale > 1:
            c = scale_nearest(c, args.scale)
        frames.append(c)

    export_gif(frames, args.output, fps=max(1, round(1000 / max(1, args.ms))))
    print(f"Turntable ({len(frames)} frames) -> {args.output} ({frames[0].width}x{frames[0].height})")
    return 0


def _cmd_voxel_palette(args: argparse.Namespace) -> int:
    if args.list or not args.source:
        print("Built-in voxel palette presets:")
        for name in sorted(COMMUNITY_PRESETS):
            print(f"  - {name} ({len(COMMUNITY_PRESETS[name]['colors'])} ramps)")
        return 0
    pal = load_palette_any(args.source, steps=args.steps)
    payload = json.dumps(pal.to_dict(), indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
        print(f"Saved palette ({len(pal.ramps)} ramps) -> {args.output}")
    else:
        print(payload)
    return 0


def _cmd_voxel_export_pxl(args: argparse.Namespace) -> int:
    model = _load_model_source(args.model)
    w, h = _parse_size(args.size) or (64, 48)
    out = export_pxl_file(
        model,
        args.output,
        name=args.name,
        stack_prefix=args.stack,
        turn=args.turn,
        elevation=args.elev,
        width=w,
        height=h,
    )
    mode = f"stack:{args.stack}" if args.stack else f"turn:{args.turn}"
    print(f"Exported .px.js ({mode}) -> {out}")
    return 0


def _cmd_voxel_import_pxl(args: argparse.Namespace) -> int:
    model = import_pxl_file(
        args.input,
        stack_prefix=args.stack,
        sprite_name=None if args.stack else args.sprite,
        plane=args.plane,
        z=args.z,
        outline=args.outline,
    )
    Path(args.output).write_text(json.dumps(model.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(f"Imported {args.input} -> {args.output} ({len(model.flatten())} voxels, {len(model.palette.ramps)} ramps)")
    return 0


def _cmd_world(args: argparse.Namespace) -> int:
    src = args.recipe.strip()
    if src.lower() in WORLD_THEMES:
        recipe = WorldRecipe.from_theme(src.lower(), seed=args.seed)
    else:
        data = json.loads(Path(src).read_text(encoding="utf-8"))
        recipe = WorldRecipe.from_dict(data)
        if args.seed is not None:
            recipe.seed = args.seed

    world = VoxelWorld.from_recipe(recipe)
    if args.ticks > 0:
        world.step(args.ticks)
    if args.bake:
        world.bake()

    info_data = world.info()
    if args.info:
        Path(args.info).write_text(json.dumps(info_data, indent=2) + "\n", encoding="utf-8")

    if args.output == "-":
        print(json.dumps(info_data, indent=2))
        return 0

    w, h = _parse_size(args.size) or (192, 128)
    at = _parse_xy(args.at)
    use_lights = args.lights.lower() not in ("no", "false", "0", "off")
    canvas = world.render(
        width=w,
        height=h,
        at=at,
        whole=args.whole,
        yaw=args.yaw,
        elevation=args.elev,
        use_lights=use_lights,
        hour=args.hour,
        weather=args.weather,
        section_z=args.section_z,
        bg=args.bg,
    )
    if args.scale > 1:
        canvas = scale_nearest(canvas, args.scale)
    export_png(canvas, args.output)
    print(f"World ({recipe.theme}/{recipe.generator}, seed={recipe.seed}) -> {args.output} ({canvas.width}x{canvas.height})")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register `pixelai voxel` and `pixelai world` CLI subcommands."""
    vox_p = subparsers.add_parser(
        "voxel",
        help="Direct voxel CLI: render models/samples, 360° turntables, .hex/.gpl palettes, and .px.js bridge.",
    )
    vox_sub = vox_p.add_subparsers(dest="voxel_cmd", required=True)

    # pixelai voxel render
    vr = vox_sub.add_parser("render", help="Render a .vox.json model or built-in sample to PNG or angle strip.")
    vr.add_argument("model", help=f"Path to voxel model JSON or built-in sample ({', '.join(SAMPLE_NAMES)}).")
    vr.add_argument("output", help="Output PNG path.")
    vr.add_argument("--yaw", type=float, default=35.0, help="Camera yaw in degrees (default: 35).")
    vr.add_argument("--elev", type=float, default=30.0, help="Camera elevation in degrees (default: 30).")
    vr.add_argument("--turn", type=int, default=1, help="Render a horizontal strip of N angles (default: 1).")
    vr.add_argument("--scale", type=int, default=1, help="Nearest-neighbor output scale factor (default: 1).")
    vr.add_argument("--size", default=None, help="Canvas size WxH (auto-framed if omitted).")
    vr.add_argument("--origin", default=None, help="Screen origin x,y.")
    vr.add_argument("--outline", choices=("outer", "none"), default="outer", help="External silhouette outline or lineless.")
    vr.add_argument("--bg", default=None, help="Optional background color #rrggbb.")
    vr.add_argument("--lights", action="store_true", help="Enable emissive point lights and sun shadows.")
    vr.add_argument("--ambient", type=float, default=0.8, help="Ambient brightness 0..1 when --lights is set.")
    vr.add_argument("--palette", default=None, help="Override palette (.hex, .gpl, .json, or preset name).")
    vr.add_argument("--verify-palette", action="store_true", help="Fail if any rendered pixel is outside the active palette.")
    vr.set_defaults(func=_cmd_voxel_render)

    # pixelai voxel turntable
    vt = vox_sub.add_parser("turntable", help="Render a 360° rotating GIF turntable of a voxel model or sample.")
    vt.add_argument("model", help=f"Path to voxel model JSON or built-in sample ({', '.join(SAMPLE_NAMES)}).")
    vt.add_argument("output", help="Output GIF path.")
    vt.add_argument("--frames", type=int, default=16, help="Number of rotation frames (default: 16).")
    vt.add_argument("--scale", type=int, default=2, help="Nearest-neighbor output scale (default: 2).")
    vt.add_argument("--elev", type=float, default=32.0, help="Camera elevation in degrees (default: 32).")
    vt.add_argument("--ms", type=int, default=80, help="Frame duration in milliseconds (default: 80).")
    vt.add_argument("--size", default=None, help="Frame size WxH (auto-framed if omitted).")
    vt.add_argument("--outline", choices=("outer", "none"), default="outer", help="External silhouette outline or lineless.")
    vt.add_argument("--bg", default=None, help="Optional background color #rrggbb.")
    vt.add_argument("--lights", action="store_true", help="Enable emissive point lights and sun shadows.")
    vt.add_argument("--ambient", type=float, default=0.8, help="Ambient brightness 0..1 when --lights is set.")
    vt.add_argument("--palette", default=None, help="Override palette (.hex, .gpl, .json, or preset name).")
    vt.set_defaults(func=_cmd_voxel_turntable)

    # pixelai voxel palette
    vp = vox_sub.add_parser("palette", help="List built-in community palettes or import .hex/.gpl to VoxelPalette JSON.")
    vp.add_argument("source", nargs="?", default=None, help="Preset name or path to .hex/.gpl/.json palette.")
    vp.add_argument("--list", action="store_true", help="List available built-in palette presets.")
    vp.add_argument("--steps", type=int, default=4, help="Shades per generated ramp (default: 4).")
    vp.add_argument("-o", "--output", default=None, help="Optional output JSON path (prints to stdout if omitted).")
    vp.set_defaults(func=_cmd_voxel_palette)

    # pixelai voxel export-pxl
    ve = vox_sub.add_parser("export-pxl", help="Export a voxel model or sample to .px.js (angles or --stack layers).")
    ve.add_argument("model", help=f"Path to voxel model JSON or built-in sample ({', '.join(SAMPLE_NAMES)}).")
    ve.add_argument("output", help="Output .px.js file path.")
    ve.add_argument("--turn", type=int, default=8, help="Number of angles to export (default: 8).")
    ve.add_argument("--stack", default=None, help="Export Z height layers as <prefix>_zNN instead of angles.")
    ve.add_argument("--name", default="model", help="Sprite base name (default: model).")
    ve.add_argument("--elev", type=float, default=30.0, help="Camera elevation for angle export (default: 30).")
    ve.add_argument("--size", default=None, help="Frame size WxH for angle export (default: 64x48).")
    ve.set_defaults(func=_cmd_voxel_export_pxl)

    # pixelai voxel import-pxl
    vi = vox_sub.add_parser("import-pxl", help="Import a .px.js file into a VoxelModel JSON (--stack, sprite plane, or '-').")
    vi.add_argument("input", help="Input .px.js file path.")
    vi.add_argument("sprite", nargs="?", default="-", help="Sprite name, or '-' to import palette only.")
    vi.add_argument("output", help="Output voxel model JSON path.")
    vi.add_argument("--stack", default=None, help="Build 3D model from <prefix>_zNN height layers.")
    vi.add_argument("--plane", choices=("front", "top"), default="front", help="Plane orientation for single sprite.")
    vi.add_argument("--z", type=int, default=0, help="Z (or Y) slice offset for single sprite import.")
    vi.add_argument("--outline", default=None, help="Override outline hex color #rrggbb.")
    vi.set_defaults(func=_cmd_voxel_import_pxl)

    # pixelai voxel edit
    ved = vox_sub.add_parser("edit", help="Apply programmatic edit operations (paint, box, mirror, fluid, etc.) to a model.")
    ved.add_argument("model", help=f"Path to voxel model JSON or built-in sample ({', '.join(SAMPLE_NAMES)}).")
    ved.add_argument("output", help="Output voxel model JSON path.")
    ved.add_argument("--ops", default=None, help="Path to JSON file containing a list of edit operations.")
    ved.add_argument("--op", action="append", default=[], help="Inline JSON operation object (repeatable).")
    ved.set_defaults(func=_cmd_voxel_edit)

    # pixelai voxel animate
    va = vox_sub.add_parser("animate", help="Generate procedural walk or idle animation (PNG sheet or GIF).")
    va.add_argument("model", help=f"Path to voxel model JSON or built-in sample ({', '.join(SAMPLE_NAMES)}).")
    va.add_argument("output", help="Output .png (spritesheet) or .gif path.")
    va.add_argument("--cycle", choices=("walk", "idle"), default="walk", help="Animation cycle (default: walk).")
    va.add_argument("--frames", type=int, default=4, help="Number of animation frames (default: 4).")
    va.add_argument("--stride", type=int, default=1, help="Leg stride in voxels for walk cycle (default: 1).")
    va.add_argument("--bob", type=int, default=1, help="Vertical bob in voxels (default: 1).")
    va.add_argument("--yaw", type=float, default=0.0, help="Camera yaw in degrees (default: 0).")
    va.add_argument("--elev", type=float, default=30.0, help="Camera elevation in degrees (default: 30).")
    va.add_argument("--scale", type=int, default=4, help="Nearest-neighbor scale factor (default: 4).")
    va.add_argument("--ms", type=int, default=120, help="Frame duration in ms for GIF output (default: 120).")
    va.add_argument("--size", default=None, help="Frame size WxH (auto-framed if omitted).")
    va.add_argument("--outline", choices=("outer", "none"), default="outer", help="External silhouette outline or lineless.")
    va.add_argument("--bg", default=None, help="Optional background color #rrggbb.")
    va.set_defaults(func=_cmd_voxel_animate)

    # pixelai voxel terrain
    vter = vox_sub.add_parser("terrain", help="Generate a standalone procedural terrain VoxelModel JSON.")
    vter.add_argument("output", help="Output voxel model JSON path.")
    vter.add_argument("--size", default="32x32x16", help="Terrain dimensions WxDxH (default: 32x32x16).")
    vter.add_argument("--seed", type=int, default=42, help="Procedural seed (default: 42).")
    vter.add_argument("--theme", choices=sorted(WORLD_THEMES), default="medieval", help="Terrain theme (default: medieval).")
    vter.add_argument("--no-trees", action="store_true", help="Disable procedural trees/vegetation.")
    vter.set_defaults(func=_cmd_voxel_terrain)

    # pixelai world
    wp = subparsers.add_parser(
        "world",
        help="Generate, simulate, and render a procedural 2.5D voxel world from a JSON recipe or theme.",
    )
    wp.add_argument("recipe", help=f"Path to world recipe JSON or built-in theme ({', '.join(sorted(WORLD_THEMES))}).")
    wp.add_argument("output", help="Output PNG path, or '-' to print world info JSON only.")
    wp.add_argument("--seed", type=int, default=1337, help="Procedural generation seed (default: 1337).")
    wp.add_argument("--at", default=None, help="Focus camera at world coordinate x,y.")
    wp.add_argument("--size", default="192x128", help="Output size WxH (default: 192x128).")
    wp.add_argument("--ticks", type=int, default=0, help="Simulation ticks to advance before rendering.")
    wp.add_argument("--scale", type=int, default=1, help="Nearest-neighbor output scale factor (default: 1).")
    wp.add_argument("--whole", action="store_true", help="Zoom out to frame the whole world.")
    wp.add_argument("--yaw", type=float, default=35.0, help="Camera yaw in degrees (default: 35).")
    wp.add_argument("--elev", type=float, default=32.0, help="Camera elevation in degrees (default: 32).")
    wp.add_argument("--lights", default="yes", help="Enable lighting ('yes' or 'no', default: yes).")
    wp.add_argument("--hour", type=float, default=None, help="Override time of day 0..24.")
    wp.add_argument("--weather", choices=WEATHER_MODES, default=None, help="Override weather overlay.")
    wp.add_argument("--section-z", type=int, default=None, help="Cutaway section clip at max Z height.")
    wp.add_argument("--bg", default=None, help="Override background color #rrggbb.")
    wp.add_argument("--bake", action="store_true", help="Pre-bake 3D lightmap before rendering.")
    wp.add_argument("--info", default=None, help="Optional path to write world info JSON.")
    wp.set_defaults(func=_cmd_world)
