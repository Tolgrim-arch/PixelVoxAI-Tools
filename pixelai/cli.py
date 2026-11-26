"""CLI entry point for pixelai-tools."""

import argparse
import json
import sys
from pathlib import Path

from pixelai import __version__, filters, fx
from pixelai.exporter import (
    export_gif,
    export_godot_tres,
    export_layers,
    export_png,
    export_showcase,
    export_spritesheet,
    extract_spec_from_png,
)
from pixelai.inspect_tool import (
    analyze_image_file,
    load_png_as_canvas,
    render_ascii,
    render_contact_sheet,
    render_diff_sheet,
    render_ruler,
)
from pixelai.palettes import list_palettes
from pixelai.runner import resolve_spec_paths, run_frames, run_layers
from pixelai.quality import assess_artifact, check_catalog_rejection, record_assessment, review_template
from pixelai.schema import build_json_schema, format_op_guide, format_op_list

AGENT_GUIDE = """# pixelai-tools — Agent Reference Guide

## Aesthetic Standard (Mandatory)
- **Default (`"style": "ext_outline"`):** **Lineless Interior + 1px External Outline**. Internal surfaces use pure color planes, specular bevels (`bevel: true`), eave/ground shadows, and recessed openings (`recessed: true`) with ZERO dark internal lines, wrapped in a 1px external silhouette outline.
- **Pure Lineless (`"style": "lineless"` or `--lineless`):** **100% Lineless** (no internal or external outlines).
- **Discarded:** Dark internal outlines (`edge`/`ridge`) are permanently disabled.

## CLI Usage
- New assets: `pixelai validate spec.json --fresh` then `pixelai render spec.json -o out.png --fresh --json`. Top-level `"fresh": true` also rejects external reuse in nested frames, layers, and definitions.
- Never reuse rejected outputs. Use extends/load_png only for an explicitly requested edit of an accepted asset. A fresh spec cannot detect copied JSON geometry: design a new silhouette and inspect it.
- Generate UI directly at final w/h; never stretch a small panel to fill a large container. Generate and inspect down/up/left/right for every top-down creature or human sheet.
- Default (Lineless Interior + External Outline): `pixelai render spec.json -o out.png`
- Pure Lineless (0 outlines): `pixelai render spec.json -o out.png --lineless`
- Animated GIF: `pixelai render spec.json -o anim.gif --fps 8`
- Spritesheet + Metadata + Godot 4 `.tres`:
  `pixelai render spec.json -o sheet.png --sheet --columns 4 --meta sheet.json --godot sheet.tres`
- Apply Reusable FX & Material Recolor to Any Finished PNG or Spec:
  `pixelai fx sprite.png -o enchanted.gif --material gold_specular --effect sheen_sweep --effect sparkle_glint --effect float_bob`
- Terminal Inspection (Metrics + Edge Quality + ASCII + Coordinate Ruler):
  `pixelai inspect out.png --ascii --ruler ruler.png`
- Commercial QA Template: `pixelai qa out.png --template reviews/out.review.json`
- Commercial QA Decision: `pixelai qa out.png --review reviews/out.review.json --catalog reviews/catalog.json --record` (0 approved, 1 rejected, 2 needs review; metrics alone never approve)
- Extract Embedded Spec from PNG: `pixelai extract out.png`

## Drawing Operations (`ops`)
- `{"op": "pixel", "x": 0, "y": 0, "color": "ink"}`
- `{"op": "line", "x0": 0, "y0": 0, "x1": 5, "y1": 5, "color": "ink"}`
- `{"op": "rect", "x": 0, "y": 0, "w": 8, "h": 8, "color": "wood", "filled": true, "bevel": false, "recessed": false}`
- `{"op": "circle", "cx": 8, "cy": 8, "r": 4, "color": "grass", "filled": true}`
- `{"op": "ellipse", "cx": 16, "cy": 28, "rx": 8, "ry": 3, "color": "shadow", "filled": true}`
- `{"op": "bezier", "points": [[2, 20], [16, 4], [30, 20]], "color": "wood", "thickness": 2}`
- `{"op": "particles", "x": 0, "y": 0, "w": 32, "h": 32, "count": 10, "color": "cream", "mode": "smoke|leaves|rain|sparks", "size": 1, "seed": 42}`
- `{"op": "polygon", "points": [[0,0], [8,4], [0,8]], "color": "roof", "filled": true}`
- `{"op": "fill", "x": 4, "y": 4, "color": "water"}`
- `{"op": "grid", "x": 0, "y": 0, "rows": ["..oo..", ".oggo."]}` (`.` and ` ` = transparent)
- `{"op": "dither", "x": 0, "y": 0, "w": 8, "h": 8, "color_a": "grass", "color_b": "grass_d", "mode": "checker|bayer4", "ratio": 0.5}`
- `{"op": "band_gradient", "x": 0, "y": 0, "w": 32, "h": 16, "ramp": ["#263b4d", "#4c7c9e", "#9bd4e8"], "direction": "vertical|horizontal|diagonal|radial", "strip": 0.33}` (Flat color bands with 4x4 Bayer dithering strictly along band edges; also accepts `"hue_ramp": {"n": 5, "hue": 120}`)
- `{"op": "solid", "primitives": [{"type": "capsule", "ax": 16, "ay": 10, "bx": 16, "by": 24, "ra": 5, "rb": 7}, {"type": "ellipse", "x": 16, "y": 8, "rx": 5, "ry": 4}], "ramp": [...], "k": 0.8, "inflate": 0, "dither_strip": 0}` (Smooth-min SDF metaball union with normal-mapped lighting)
- `{"op": "flame", "x": 16, "ground": 30, "height": 22, "width": 7, "embers": 4}` / `{"op": "smoke", "x": 16, "ground": 28, "height": 32, "width": 2.5, "warp": 18}` (Deterministic FBM + warp organic effects; auto-animates across `frame_count`)
- `{"op": "ik_limb", "start": [12, 16], "target": [22, 28], "l1": 8, "l2": 8, "direction": 1, "color": "wood", "radius_a": 2.5, "radius_b": 1.5}` (2-bone analytical IK limb)
- `{"op": "bend", "def": "tail_sprite", "rest": [[4, 16], [16, 16], [28, 16]], "wave": {"amp": 3.0, "wavelength": 16.0, "from": 0.2}}` (Inverse-bilinear spine deformation via explicit `pose` or auto-animated `wave`)
- `{"op": "spine_rig", "facing": "right|left", "action": "walk|run|idle|attack", "body_hue": 270, "horns": true, "tail": true, "scale": 1.0}` (Full-body Spine + 2-bone IK animated biped with guaranteed forward gait, anatomical knee/elbow bends, depth-darkened far limbs, and strict Z-order)
- `{"op": "text", "x": 2, "y": 2, "text": "LV 9", "color": "#ffffff", "scale": 1}` (Crisp 3x5 bitmap pixel font)
- `{"op": "scatter", "x": 0, "y": 0, "w": 32, "h": 32, "color": "grass_l", "target_color": "grass", "pattern": "noise|brick|shingle|cobble|wood|grass|rock|soil|leaves|bark|water|cloth", "density": 0.2, "seed": 42}` (Use material accents clipped to the surface; avoid random noise as a substitute for material planes.)
- `{"op": "material", "kind": "rock|cobble|soil|leaves|bark|grass|water|cloth|wood|roof", "x": 0, "y": 0, "w": 64, "h": 48, "seed": 42, "inside": false}` (Structured native material planes; optional `color` base tint or five-entry `colors` ramp. `trunk` aliases bark, `shingle` aliases roof.)
- `{"op": "building", "x": 12, "y": 14, "w": 104, "h": 98, "roof_style": "gable|pitched|barn", "wall_color": "cream", "roof_color": "roof", "timber_frame": true, "chimney": true, "smoke": true, "shadow_opacity": 0.22}` (Top-down 3/4 architecture; straight projected ground shadow, optional shadow_dx/shadow_dy; PNG preserves partial alpha.)
- `{"op": "stamp", "def": "sub_sprite", "x": 4, "y": 4, "flip_x": false, "flip_y": false, "angle": 45, "pivot": [4, 4], "ramp_shift": 0, "remap": {"wood": "stone"}}`
- `{"op": "load_png", "path": "base.png", "x": 0, "y": 0, "crop": [0, 0, 16, 16]}`
- `{"op": "tilemap", "mode": "ortho|iso", "tile_w": 16, "tile_h": 16, "map": {"G": "grass_tile"}, "rows": ["GGG", "GGG"]}`
- `{"op": "autotile", "x": 0, "y": 0, "tile_size": 16, "inner": "water", "outer": "grass", "lip": "soil_d", "seed": 42}` (Generates 4x4 16-tile Wang bitmask atlas)
- `{"op": "char_rig", "x": 0, "y": 0, "size": 16, "dir": "down|up|left|right|se|sw|ne|nw", "pose": "idle|walk|run|work|jump|fall|attack", "perspective": "topdown|platformer|iso", "shadow": true, "frame": 0, "hat": "wheat", "shirt": "roof", "pants": "water_d"}` (Supports native sizes 16, 32, 64, 128 and direction-coherent work/attack swings)
- `{"op": "portrait_rig", "x": 0, "y": 0, "width": 64, "height": 80, "face_dir": "front|three_quarter_left|three_quarter_right", "gesture": "idle|wave|hip", "hair_style": "layered|spiky", "headband": false, "cheek_marks": 0, "eye_color": "#2b1b2b", "skin": "#f2c38f", "hair": "#6b3f35", "shirt": "#d9e5d2", "garment": "#704b3b"}` (Bust portrait with optional forehead protector and cheek markings, expressive gesture, ears, cheek planes, hair locks, clothing planes, and clean external silhouette)
- `{"op": "portrait_rig", "style": "mistria", "preset": "samurai|farmer", "x": 1, "y": 1, "width": 120, "height": 160, "face_dir": "three_quarter_left|three_quarter_right", "hat": false, "scar": true}` (Fields of Mistria style waist-up portrait engine with 90s-anime facial proportions, cel-shading, and samurai or farmer attire)
- `{"op": "portrait_rig", "preset": "field_farmer", "x": 0, "y": 0, "hat": true, "expression": "smile|neutral", "face_dir": "three_quarter_left|three_quarter_right"}` (Native 116 x 144 field farmer bust, with overridable material colors such as skin, hair, denim and straw.)
- `{"op": "animal_rig", "x": 0, "y": 0, "species": "chicken|cow|pig|sheep|duck|rabbit", "dir": "down|up|left|right|se|sw|ne|nw", "pose": "idle|walk|run|peck|graze|nest|lie|sleep|jump|fall|surprised|happy|sad|angry|sick", "perspective": "topdown|platformer|iso", "shadow": true, "emotes": true, "ground_prop": "auto|grass|seeds|none", "nest_prop": false, "frame": 0}` (Cozy farm creature rig with auto-looping frames, hip-pivot peck, optional props/shadows/emotes)
- `{"op": "item_rig", "x": 0, "y": 0, "kind": "potion|sword|shield|chest|gem|key|coin|apple|axe|pickaxe|carrot|bread|fish|lantern", "orientation": "vertical|diagonal", "size": 24, "fill_level": 0.78, "state": "closed|open", "shine": true, "shadow": false}` (Parametric RPG items, weapons, food and special loot. Lantern supports `flame_color` and four flame frames.)
- `{"op": "nature_rig", "x": 0, "y": 0, "kind": "tree|bush|rock|flower|crop", "variant": "oak|pine|fruit|sakura|boulder|mossy|ore|wheat|berry|carrot", "stage": 3, "sway": false, "shadow": true, "ground_base": "none|grass|soil"}` (Trees, rocks, flowers, and 4-stage crops)
- `{"op": "ui_rig", "x": 0, "y": 0, "kind": "panel|bar|button|heart|slot", "theme": "wood|stone|gold|paper|dark", "state": "normal|hover|pressed|full|half|empty|selected", "fill": 0.75, "w": 48, "h": 12}` (Native pixel UI; panels support frame_width 3..12, theme-specific details and inner_fill:false for a transparent center. Render at final dimensions.)
- `{"op": "emote", "x": 18, "y": 2, "kind": "heart|angry|sweat|zzz|exclamation|sick", "frame": 0, "outline": false}`
- Universal op flags: `"inside": true` (clips shading/markings strictly inside existing opaque silhouette), `"outline": false` (excludes floating particles/emotes/shadows from external outline).
- `{"op": "mirror_x"}` / `{"op": "mirror_y"}`
- Post-processing (`post`): `cleanup` (`tol`, `keep_lone`), `pixel_perfect`, `rim_light` (`ramp`, `dir`, `steps` — runs before `outline`), `outline`, `recolor_material`, `drop_shadow`, `pad`, `shade`, `scale`.
- Top-level `"extends": "sprite.png | spec.json"` inherits palette, defs, and ops from an existing PNG or JSON!
- Top-level `"imports": ["@foliage/leaf_clusters", "@fx/gold_enchant"]` imports reusable defs, material ramps, and FX presets from `library/`.
- Top-level `"style_profile": "cozy_modern|16bit_cluster|crisp_retro|enchanted_hd"` configures directional selout and jaggy cleanup automatically.
- Top-level `"material": "gold_specular|silver_chrome|bronze_aged|emerald_crystal|ruby_enchanted|amethyst_void|frost_ice|obsidian_dark"` recolors a sprite with physical reflectance curves.
- Top-level `"fx": [{"type": "sheen_sweep|sparkle_glint|bounce|float_bob|aura_glow|hit_flash|wind_sway", ...}]` animates any static sprite or rig automatically!
- Showcase Exporter (Itch.io Pack Banner / Contact Sheet): `pixelai showcase <dir_or_files...> -o showcase.png --scale 4`
- Complete Creature Asset Pack (13 GIFs + Spritesheets + Showcase): `pixelai pack chicken -o chicken_pack/ --variant white`

## 2:1 Isometric Operations (`ops`)
- `{"op": "iso_tile", "cx": 32, "cy": 32, "rx": 16, "ry": 8, "color": "grass"}`
- `{"op": "iso_box", "cx": 32, "cy": 32, "rx": 12, "ry": 6, "h": 10, "top": "stone_l", "left": "stone", "right": "stone_d", "bevel": true, "ground_shadow": 2}`
- `{"op": "iso_roof", "cx": 32, "cy": 32, "rx": 12, "ry": 6, "h": 8, "style": "pyramid|gable_left|gable_right", "left": "roof_l", "right": "roof_d", "gable": "wood", "eave_shadow": true, "bevel": true}`
- `{"op": "iso_wall_rect", "face": "left|right", "x": 24, "y": 36, "w": 4, "h": 6, "color": "wood_d", "arch": true, "recessed": true}`
- `{"op": "iso_structure", "origin_x": 32, "origin_y": 30, "bevel": true, "ground_shadow": 2, "items": [{"type": "box|roof", "gx": 0, "gy": 0, "gz": 0, "rx": 8, "h": 10, ...}]}`
"""


def _diagnostics(frames, names):
    messages = []
    for frame, name in zip(frames, names):
        if frame.clipped_pixels:
            messages.append(f"({name}): {frame.clipped_pixels} pixel(s) drawn out of canvas bounds.")
        messages.extend(f"({name}): {warning}" for warning in frame.warnings)
    return list(dict.fromkeys(messages))


def _read_spec(source: str) -> dict:
    if source == "-":
        return resolve_spec_paths(json.loads(sys.stdin.read().lstrip("\ufeff")), Path.cwd())
    path = Path(source).resolve()
    return resolve_spec_paths(json.loads(path.read_text(encoding="utf-8-sig")), path.parent)


def _enforce_fresh_catalog_gate(frames, spec: dict) -> None:
    """In fresh mode, hard-fail if rendered frames match any rejected asset in commercial_catalog.json."""
    if not spec.get("fresh", False):
        return
    repo_catalog = Path(__file__).resolve().parent.parent / "reports" / "commercial_catalog.json"
    cwd_catalog = Path.cwd() / "reports" / "commercial_catalog.json"
    for cat_path in dict.fromkeys((cwd_catalog, repo_catalog)):
        if cat_path.exists():
            catalog = json.loads(cat_path.read_text(encoding="utf-8-sig"))
            rejections = check_catalog_rejection(frames, catalog)
            if rejections:
                raise ValueError("; ".join(rejections))


def _cmd_validate(args: argparse.Namespace) -> int:
    spec = _read_spec(args.spec)
    if args.fresh:
        spec["fresh"] = True
    spec.setdefault("style", "ext_outline")
    frames, names = run_frames(spec)
    _enforce_fresh_catalog_gate(frames, spec)
    layers = run_layers(spec) if spec.get("layers") else []
    warnings = _diagnostics(frames, names) + _diagnostics(
        [frame for _, frame in layers], [name for name, _ in layers]
    )
    print(json.dumps({"valid": True, "frame_count": len(frames), "warnings": warnings}))
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    targets = [Path(value).resolve() for value in (args.output, args.meta, args.manifest, args.godot, args.ruler, args.contact_sheet) if value]
    if len(targets) != len(set(targets)):
        raise ValueError("Render artifact paths must be distinct")
    if args.spec != "-" and Path(args.spec).resolve() in targets:
        raise ValueError("Render output cannot overwrite its source specification")
    spec = _read_spec(args.spec)
    if args.fresh:
        spec["fresh"] = True
    if getattr(args, "style", None):
        spec["style_ref"] = args.style
    if args.lineless:
        spec["style"] = "lineless"
    elif "style_ref" not in spec:
        spec.setdefault("style", "ext_outline")
    frames, names = run_frames(spec)
    _enforce_fresh_catalog_gate(frames, spec)
    layers = run_layers(spec) if args.layers_dir else []
    warnings = _diagnostics(frames, names) + _diagnostics(
        [frame for _, frame in layers], [name for name, _ in layers]
    )
    for message in warnings:
        print(f"[WARN] {message}", file=sys.stderr)

    def report(message: str) -> None:
        if not args.json:
            print(message)

    artifacts = {}
    out_path = Path(args.output)
    is_gif = out_path.suffix.lower() == ".gif"
    fps = args.fps if args.fps is not None else int(spec.get("fps", 8))
    cols = args.columns if args.columns is not None else spec.get("columns")

    if is_gif and (args.sheet or args.meta or args.godot or args.manifest):
        raise ValueError("GIF output cannot be combined with --sheet, --meta, --godot or --manifest")
    if fps <= 0:
        raise ValueError("fps: expected a positive value")
    if cols is not None and (not isinstance(cols, int) or cols <= 0):
        raise ValueError("columns: expected a positive integer")

    from pixelai.animation_contract import durations_ms, clips_by_index, validate_transitions
    timings = durations_ms(len(frames), fps, spec.get("durations_ms"))
    clips = clips_by_index(len(frames), spec.get("clips"))
    from pixelai.animation_score import source_records, validate_scores
    validate_scores(clips, source_records(frames, timings))
    validate_transitions(spec.get("transitions", []), clips)
    manifest = None
    if args.manifest:
        from pixelai.manifest import build_manifest
        manifest = build_manifest(spec, frames, out_path, args.manifest, cols, timings, clips)

    if is_gif:
        out = export_gif(frames, out_path, fps=fps, durations_ms=timings)
        report(f"Rendered GIF ({len(frames)} frames @ {fps}fps, {frames[0].width}x{frames[0].height}) -> {out}")
    elif args.sheet or len(frames) > 1 or args.godot or args.meta:
        out = export_spritesheet(
            frames,
            out_path,
            frame_names=names,
            columns=cols,
            meta_path=args.meta,
            spec_json=json.dumps(spec),
            durations_ms=timings,
            clips=clips,
        )
        report(f"Rendered spritesheet ({len(frames)} frames) -> {out}")
    else:
        out = export_png(frames[0], out_path, spec_json=json.dumps(spec))
        report(f"Rendered {frames[0].width}x{frames[0].height} -> {out}")

    artifacts["image"] = str(out.resolve())
    if manifest is not None:
        import hashlib
        manifest["texture_sha256"] = hashlib.sha256(out.read_bytes()).hexdigest()
        manifest_path = Path(args.manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2))
        artifacts["manifest"] = str(manifest_path.resolve())
    if args.meta:
        artifacts["metadata"] = str(Path(args.meta).resolve())

    if args.godot:
        tres_out = export_godot_tres(
            out_path, args.godot, frames, frame_names=names, columns=cols, fps=fps,
            durations_ms=timings if "durations_ms" in spec else None, clips=clips
        )
        artifacts["godot"] = str(tres_out.resolve())
        report(f"Exported Godot 4 SpriteFrames -> {tres_out}")

    if args.layers_dir:
        paths = export_layers(layers, args.layers_dir)
        artifacts["layers"] = [str(path.resolve()) for path in paths]
        report(f"Exported {len(paths)} layer PNGs -> {args.layers_dir}")

    if args.ruler:
        ruler_canvas = render_ruler(frames[0], scale=args.ruler_scale, step=args.ruler_step)
        ruler_out = export_png(ruler_canvas, args.ruler)
        artifacts["ruler"] = str(ruler_out.resolve())
        report(f"Exported coordinate ruler ({ruler_canvas.width}x{ruler_canvas.height}) -> {ruler_out}")

    if args.contact_sheet:
        cs_canvas = render_contact_sheet(frames, names=names, scale=args.contact_scale, cols=cols)
        cs_out = export_png(cs_canvas, args.contact_sheet)
        artifacts["contact_sheet"] = str(cs_out.resolve())
        report(f"Exported contact sheet ({len(frames)} frames, {cs_canvas.width}x{cs_canvas.height}) -> {cs_out}")

    result = {
        "artifacts": artifacts,
        "width": frames[0].width,
        "height": frames[0].height,
        "frame_count": len(frames),
        "warnings": warnings,
    }
    if any(frame.attachments for frame in frames):
        result["attachments"] = [frame.attachments for frame in frames]
    if args.ascii:
        result["ascii"] = render_ascii(frames[0])
        report(result["ascii"])
    if args.json:
        print(json.dumps(result))

    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    stats, frames = analyze_image_file(args.image)
    if args.ruler:
        ruler_canvas = render_ruler(frames[0], scale=args.ruler_scale, step=args.ruler_step)
        ruler_out = export_png(ruler_canvas, args.ruler)
        stats["ruler"] = str(ruler_out.resolve())
    print(json.dumps(stats, indent=2))
    if args.ascii:
        for idx, f in enumerate(frames if args.all_frames else frames[:1]):
            if len(frames) > 1 and args.all_frames:
                print(f"--- frame_{idx} ---")
            print(render_ascii(f))
    return 0


def _cmd_showcase(args: argparse.Namespace) -> int:
    out = export_showcase(
        args.sources,
        args.output,
        scale=args.scale,
        columns=args.columns,
        fps=args.fps,
    )
    print(f"Exported showcase -> {out}")
    return 0


def _cmd_pack(args: argparse.Namespace) -> int:
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    species = args.species.lower()
    raw_var = args.variant
    if species == "cow" and raw_var == "white":
        raw_var = "holstein"
    elif species == "pig" and raw_var == "white":
        raw_var = "pink"
    variants = [v.strip() for v in raw_var.split(",") if v.strip()]
    is_large = species in ("cow", "pig", "sheep")
    w, h = (32, 32) if is_large else (24, 24)
    jobs = [
        ("walk_down", "down", "walk", 4, 8),
        ("walk_up", "up", "walk", 4, 8),
        ("walk_left", "left", "walk", 4, 8),
        ("walk_right", "right", "walk", 4, 8),
        ("graze_left" if is_large else "peck_left", "left", "graze" if is_large else "peck", 6, 8 if is_large else 10),
        ("graze_right" if is_large else "peck_right", "right", "graze" if is_large else "peck", 6, 8 if is_large else 10),
        ("lie_right" if is_large else "nest_right", "right", "lie" if is_large else "nest", 4, 4),
        ("sleep_right", "right", "sleep", 4, 4),
        ("surprised", "down", "surprised", 4, 8),
        ("sick", "right", "sick", 4, 5),
        ("angry", "right", "angry", 4, 8),
        ("sad", "right", "sad", 4, 5),
        ("happy", "right", "happy", 4, 7),
    ]
    gif_paths: list[Path] = []
    for var in variants:
        prefix = f"{species}_{var}_" if len(variants) > 1 else f"{species}_"
        for suffix, direction, pose, fc, fps in jobs:
            spec = {
                "width": w,
                "height": h,
                "palette": "cozy24",
                "style": "lineless" if args.lineless else "ext_outline",
                "frame_count": fc,
                "ops": [
                    {
                        "op": "animal_rig",
                        "species": species,
                        "variant": var,
                        "dir": direction,
                        "pose": pose,
                    }
                ],
            }
            frames, names = run_frames(spec)
            gif_p = out_dir / f"{prefix}{suffix}.gif"
            export_gif(frames, gif_p, fps=fps)
            gif_paths.append(gif_p)
            if args.sheets:
                sheet_p = out_dir / "sheets" / f"{prefix}{suffix}.png"
                meta_p = out_dir / "sheets" / f"{prefix}{suffix}.json"
                export_spritesheet(frames, sheet_p, frame_names=names, meta_path=meta_p, spec_json=json.dumps(spec))

    sheet_out = export_showcase(gif_paths, out_dir / "itch_showcase_sheet.png", scale=args.scale)
    banner_out = export_showcase(gif_paths, out_dir / "itch_showcase_banner.gif", scale=args.scale, columns=5)
    print(f"Generated {len(gif_paths)} animations + showcase ({sheet_out.name}, {banner_out.name}) -> {out_dir}")
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    spec = extract_spec_from_png(args.image)
    print(json.dumps(spec, indent=2))
    return 0


def _cmd_guide(args: argparse.Namespace) -> int:
    if getattr(args, "style", None):
        from pixelai.style_profile import format_style_guide, load_style_profile
        print(format_style_guide(load_style_profile(args.style)))
        return 0
    if getattr(args, "op", None):
        print(format_op_guide(args.op))
        return 0
    if getattr(args, "list", False):
        print(format_op_list())
        return 0
    print(AGENT_GUIDE)
    print("## Built-in Palettes")
    for name, colors in list_palettes().items():
        keys = ", ".join(colors.keys())
        print(f"- `{name}` ({len(colors)} colors): keys = [{keys}]")
    return 0


def _cmd_schema(_args: argparse.Namespace) -> int:
    print(json.dumps(build_json_schema(), indent=2))
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    before = load_png_as_canvas(args.before)
    after = load_png_as_canvas(args.after)
    stats, sheet = render_diff_sheet(before, after, scale=args.scale)
    if args.output:
        out = export_png(sheet, args.output)
        stats["diff_image"] = str(out.resolve())
    if args.json or not args.output:
        print(json.dumps(stats, indent=2))
    else:
        pct = stats["change_ratio"] * 100.0
        print(
            f"Diff: {stats['changed_pixels']}/{stats['total_pixels']} px changed ({pct:.2f}%) -> {stats['diff_image']}"
        )
    return 0


def _cmd_qa(args: argparse.Namespace) -> int:
    if args.template:
        target = Path(args.template)
        if target.exists():
            raise ValueError("Review template already exists; choose a new path to preserve review evidence")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(review_template(args.image), indent=2) + "\n", encoding="utf-8")
    review = json.loads(Path(args.review).read_text(encoding="utf-8-sig")) if args.review else None
    catalog_path = Path(args.catalog) if args.catalog else None
    catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig")) if catalog_path and catalog_path.exists() else None
    if catalog is not None and not isinstance(catalog, dict):
        raise ValueError("catalog must be a JSON object")
    if args.record and catalog_path is None:
        raise ValueError("--record requires --catalog")
    result = assess_artifact(args.image, review, catalog)
    if getattr(args, "style", None):
        from pixelai.style_profile import compare_canvas_to_style, load_style_profile
        profile = load_style_profile(args.style)
        result["style_fidelity"] = compare_canvas_to_style(load_png_as_canvas(args.image), profile)
    if args.record:
        record_assessment(catalog_path, args.image, result)
    print(json.dumps(result, indent=2))
    return {"approved": 0, "rejected": 1, "needs_review": 2}[result["status"]]


def _cmd_style_ingest(args: argparse.Namespace) -> int:
    from pixelai.style_ingest import ingest_reference_image
    from pixelai.style_study import collect_image_paths

    paths = collect_image_paths(args.inputs)
    if not paths:
        raise ValueError("No supported images (.jpg, .jpeg, .jfif, .png, .webp) found.")

    out_target = Path(args.output)
    multi = len(paths) > 1 or out_target.suffix.lower() != ".png"
    if multi:
        out_target.mkdir(parents=True, exist_ok=True)

    reports = []
    for p in paths:
        res = ingest_reference_image(
            p,
            force_scale=args.scale,
            max_colors=args.max_colors,
            keep_bg=args.keep_bg,
        )
        dst = (out_target / f"{p.stem}_clean.png") if multi else out_target
        saved = export_png(res.canvas, dst)
        reports.append({
            "source": p.name,
            "output": str(saved.resolve()),
            "source_size": list(res.source_size),
            "native_size": [res.grid.grid_w, res.grid.grid_h],
            "cell_size": res.grid.cell_w,
            "confidence": res.grid.confidence,
            "colors": len(res.palette),
            "bg_removed": res.bg_removed,
        })

    if args.json:
        print(json.dumps({"ok": True, "ingested": reports}, indent=2))
    else:
        for r in reports:
            print(
                f"Ingested {r['source']} ({r['source_size'][0]}x{r['source_size'][1]} -> "
                f"{r['native_size'][0]}x{r['native_size'][1]}, cell={r['cell_size']}, "
                f"conf={r['confidence']}, colors={r['colors']}) -> {r['output']}"
            )
    return 0


def _cmd_style_study(args: argparse.Namespace) -> int:
    from pixelai.style_study import study_reference_images

    profile, ingested = study_reference_images(
        args.inputs,
        name=args.name,
        max_colors=args.max_colors,
        force_scale=args.scale,
        keep_bg=args.keep_bg,
    )

    if args.save_clean:
        clean_dir = Path(args.save_clean)
        clean_dir.mkdir(parents=True, exist_ok=True)
        for p, res in ingested:
            export_png(res.canvas, clean_dir / f"{p.stem}_clean.png")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(profile, indent=2))
    else:
        print(
            f"Studied {len(ingested)} reference(s) -> {out_path} "
            f"(palette={len(profile['palette'])}, outline={profile['outline']['mode']}, "
            f"light={profile['lighting']['direction']}, shading={profile['shading']['style']})"
        )
    return 0


def _cmd_style_merge(args: argparse.Namespace) -> int:
    from pixelai.style_profile import load_style_profile
    from pixelai.style_study import merge_style_profiles

    profiles = [load_style_profile(p) for p in args.profiles]
    merged = merge_style_profiles(profiles, name=args.name, max_colors=args.max_colors)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    print(f"Merged {len(profiles)} style profile(s) -> {out_path} (palette={len(merged['palette'])})")
    return 0


def _cmd_style_guide(args: argparse.Namespace) -> int:
    from pixelai.style_profile import format_style_guide, load_style_profile
    print(format_style_guide(load_style_profile(args.profile)))
    return 0


def _cmd_style_compare(args: argparse.Namespace) -> int:
    from pixelai.style_profile import load_style_profile, render_style_comparison

    profile = load_style_profile(args.style) if args.style else None
    report = render_style_comparison(
        args.reference,
        args.generated,
        args.output,
        profile=profile,
        scale=args.scale,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Exported style comparison -> {report['comparison_image']}")
    return 0


def _cmd_fx(args: argparse.Namespace) -> int:
    src_path = Path(args.source)
    if src_path.suffix.lower() == ".json":
        spec = _read_spec(str(src_path))
        spec.setdefault("style", "ext_outline")
        frames, names = run_frames(spec)
    else:
        frames = [load_png_as_canvas(src_path)]
        names = ["frame_0"]

    fx_list: list[dict] = []
    material = args.material
    if args.preset:
        from pixelai.runner import _resolve_import_path
        preset_data = json.loads(_resolve_import_path(args.preset).read_text(encoding="utf-8-sig"))
        if not material and isinstance(preset_data.get("material"), str):
            material = preset_data["material"]
        if isinstance(preset_data.get("fx"), list):
            fx_list.extend(preset_data["fx"])

    if material:
        frames = [filters.recolor_material(f, material) for f in frames]

    for eff_name in args.effect or []:
        eff_spec: dict = {"type": eff_name}
        if eff_name == "sheen_sweep":
            eff_spec["color"] = args.sheen_color
            eff_spec["blend"] = args.sheen_blend
        fx_list.append(eff_spec)

    if fx_list:
        frames = fx.apply_fx_pipeline(frames, fx_list, total_frames=args.frames)
        names = [f"frame_{i}" for i in range(len(frames))]

    if args.scale and args.scale > 1:
        frames = [filters.scale(f, args.scale) for f in frames]

    out_path = Path(args.output)
    if out_path.suffix.lower() == ".gif":
        out = export_gif(frames, out_path, fps=args.fps)
        print(f"Exported FX GIF ({len(frames)} frames @ {args.fps}fps) -> {out}")
    elif len(frames) > 1 or args.sheet or args.meta:
        out = export_spritesheet(frames, out_path, frame_names=names, meta_path=args.meta)
        print(f"Exported FX spritesheet ({len(frames)} frames) -> {out}")
    else:
        out = export_png(frames[0], out_path)
        print(f"Exported FX PNG ({frames[0].width}x{frames[0].height}) -> {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pixelai",
        description="CLI-only deterministic pixel art & animation generator for AI agents.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    render_p = sub.add_parser(
        "render",
        help="Render PNG, spritesheet, or animated GIF from a JSON spec file or stdin ('-').",
        description=(
            "Render a pixel art PNG, spritesheet, or GIF from a declarative JSON spec.\n"
            "Run `pixelai guide` for full JSON DSL documentation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    render_p.add_argument(
        "spec",
        help="Path to JSON spec file, or '-' to read JSON from stdin.",
    )
    render_p.add_argument(
        "-o", "--output",
        required=True,
        help="Output file path (.png or .gif).",
    )
    render_p.add_argument(
        "--style",
        default=None,
        help="Optional learned `.style.json` profile (path or `@styles/<name>`) to guide palette and outline.",
    )
    render_p.add_argument(
        "--fps",
        type=int,
        default=None,
        help="Frames per second when exporting a .gif or Godot .tres (default: 8).",
    )
    render_p.add_argument(
        "--sheet",
        action="store_true",
        help="Force spritesheet export even for single-frame specs.",
    )
    render_p.add_argument(
        "--columns",
        type=int,
        default=None,
        help="Number of columns in exported spritesheet.",
    )
    render_p.add_argument(
        "--meta",
        default=None,
        help="Optional output path for spritesheet JSON metadata.",
    )
    render_p.add_argument("--manifest", help="Export a universal asset manifest; requires spec.asset_id and explicit spec.runtime coordinates.")
    render_p.add_argument(
        "--godot",
        default=None,
        help="Optional output path for Godot 4 SpriteFrames (.tres) resource.",
    )
    render_p.add_argument(
        "--layers-dir",
        default=None,
        help="Optional directory to export individual named layers as separate PNGs.",
    )
    render_p.add_argument(
        "--lineless",
        action="store_true",
        help="Render in Pure Lineless mode (no internal or external outlines).",
    )
    render_p.add_argument(
        "--ascii",
        action="store_true",
        help="Print ASCII luminance preview of the first frame to stdout.",
    )
    render_p.add_argument("--json", action="store_true", help="Return artifact paths, frame dimensions, and warnings as JSON.")
    render_p.add_argument("--ruler", default=None, help="Optional output PNG path for an upscaled coordinate-grid ruler overlay.")
    render_p.add_argument("--ruler-scale", type=int, default=4, help="Upscale factor for --ruler output (default: 4).")
    render_p.add_argument("--ruler-step", type=int, default=8, help="Coordinate grid step in native pixels for --ruler (default: 8).")
    render_p.add_argument("--contact-sheet", default=None, help="Optional output PNG path for a labeled multi-frame checkerboard contact sheet.")
    render_p.add_argument("--contact-scale", type=int, default=4, help="Upscale factor for --contact-sheet (default: 4).")
    render_p.set_defaults(func=_cmd_render)
    render_p.add_argument("--fresh", action="store_true", help="Generate from scratch: reject extends and load_png, including nested definitions and frames.")

    validate_p = sub.add_parser("validate", help="Check a JSON spec in memory without writing output files.")
    validate_p.add_argument("spec", help="JSON spec path or '-' for stdin.")
    validate_p.add_argument("--fresh", action="store_true", help="Reject external asset reuse (extends and load_png) throughout the spec.")
    validate_p.set_defaults(func=_cmd_validate)

    inspect_p = sub.add_parser(
        "inspect",
        help="Inspect a PNG or multi-frame GIF (bounding box, margins, islands, edge quality, color count, ASCII, and ruler).",
    )
    inspect_p.add_argument("image", help="Path to PNG or GIF file to inspect.")
    inspect_p.add_argument(
        "--ascii",
        action="store_true",
        help="Print ASCII luminance preview to stdout.",
    )
    inspect_p.add_argument(
        "--all-frames",
        action="store_true",
        help="Print ASCII preview for every frame of a GIF.",
    )
    inspect_p.add_argument("--ruler", default=None, help="Optional output PNG path for an upscaled coordinate-grid ruler overlay.")
    inspect_p.add_argument("--ruler-scale", type=int, default=4, help="Upscale factor for --ruler output (default: 4).")
    inspect_p.add_argument("--ruler-step", type=int, default=8, help="Coordinate grid step in native pixels for --ruler (default: 8).")
    inspect_p.set_defaults(func=_cmd_inspect)

    qa_p = sub.add_parser("qa", help="Assess commercial readiness against eleven evidenced review criteria; metrics alone never approve art.")
    qa_p.add_argument("image", help="PNG or GIF artifact to assess.")
    review_args = qa_p.add_mutually_exclusive_group()
    review_args.add_argument("--template", help="Write a new unverified review template bound to this artifact; never overwrites a review.")
    review_args.add_argument("--review", help="Review JSON with independent reviewer, native/zoom inspection, delivery contract and all eleven criteria.")
    qa_p.add_argument("--catalog", help="JSON approval/rejection ledger; exact previously rejected pixels cannot be approved.")
    qa_p.add_argument("--record", action="store_true", help="Append this assessment to --catalog. Exit codes: 0 approved, 1 rejected, 2 needs review.")
    qa_p.add_argument("--style", default=None, help="Optional `.style.json` profile to evaluate style fidelity against.")
    qa_p.set_defaults(func=_cmd_qa)

    showcase_p = sub.add_parser(
        "showcase",
        help="Generate an Itch.io showcase contact sheet (.png) or animated pack banner (.gif).",
    )
    showcase_p.add_argument(
        "sources",
        nargs="+",
        help="Directory or list of .png/.gif files to include in the showcase.",
    )
    showcase_p.add_argument(
        "-o", "--output",
        required=True,
        help="Output showcase path (.png for frame contact sheet, .gif for animated pack grid).",
    )
    showcase_p.add_argument(
        "--scale",
        type=int,
        default=4,
        help="Integer upscale factor (default: 4).",
    )
    showcase_p.add_argument(
        "--columns",
        type=int,
        default=4,
        help="Columns when rendering an animated .gif showcase grid (default: 4).",
    )
    showcase_p.add_argument(
        "--fps",
        type=int,
        default=8,
        help="Frames per second for animated .gif showcase (default: 8).",
    )
    showcase_p.set_defaults(func=_cmd_showcase)

    pack_p = sub.add_parser(
        "pack",
        help="Generate a complete Itch.io creature animation pack (13 animations + sheets + showcase) in one call.",
    )
    pack_p.add_argument(
        "species",
        default="chicken",
        nargs="?",
        help="Creature species preset (default: 'chicken').",
    )
    pack_p.add_argument(
        "-o", "--output",
        required=True,
        help="Output directory for the generated asset pack.",
    )
    pack_p.add_argument(
        "--variant",
        default="white",
        help="Breed/color variant or comma-separated list: 'white,brown,golden,dark' (default: 'white').",
    )
    pack_p.add_argument(
        "--sheets",
        action="store_true",
        help="Also export PNG spritesheets + JSON metadata per animation under <output>/sheets/.",
    )
    pack_p.add_argument(
        "--scale",
        type=int,
        default=4,
        help="Upscale factor for showcase sheet and banner (default: 4).",
    )
    pack_p.add_argument(
        "--lineless",
        action="store_true",
        help="Render pack in Pure Lineless mode.",
    )
    pack_p.set_defaults(func=_cmd_pack)

    extract_p = sub.add_parser(
        "extract",
        help="Extract the embedded JSON spec from a PNG generated by pixelai.",
    )
    extract_p.add_argument("image", help="Path to PNG file.")
    extract_p.set_defaults(func=_cmd_extract)

    fx_p = sub.add_parser(
        "fx",
        help="Apply reusable FX (sheen_sweep, bounce, sparkle_glint, float_bob, aura_glow, wind_sway) and material recoloring to any finished PNG or spec.",
    )
    fx_p.add_argument("source", help="Path to input .png or .json spec.")
    fx_p.add_argument("-o", "--output", required=True, help="Output .gif or .png path.")
    fx_p.add_argument(
        "-e", "--effect",
        action="append",
        choices=["sheen_sweep", "sparkle_glint", "bounce", "float_bob", "aura_glow", "hit_flash", "wind_sway"],
        help="Reusable FX to apply (repeatable).",
    )
    fx_p.add_argument(
        "--preset",
        default=None,
        help="Optional library FX/material preset (e.g. '@fx/gold_enchant', '@fx/enchanted_aura').",
    )
    fx_p.add_argument(
        "--material",
        default=None,
        help="Physical material recolor preset (e.g. gold_specular, silver_chrome, emerald_crystal, ruby_enchanted).",
    )
    fx_p.add_argument("--frames", type=int, default=None, help="Override frame count (default: inferred from FX).")
    fx_p.add_argument("--fps", type=int, default=10, help="Frames per second for GIF output (default: 10).")
    fx_p.add_argument("--scale", type=int, default=1, help="Optional integer upscale factor (default: 1).")
    fx_p.add_argument("--sheen-color", default="#fff6b8", help="Hex color for sheen_sweep bar (default: #fff6b8).")
    fx_p.add_argument("--sheen-blend", default="add", choices=["add", "screen", "tint"], help="Blend mode for sheen_sweep.")
    fx_p.add_argument("--sheet", action="store_true", help="Force spritesheet export.")
    fx_p.add_argument("--meta", default=None, help="Optional spritesheet JSON metadata output path.")
    fx_p.set_defaults(func=_cmd_fx)

    guide_p = sub.add_parser(
        "guide",
        help="Print complete LLM agent guide, compact op index (--list), single-op reference (--op <name>), or learned style brief (--style <profile>).",
    )
    guide_p.add_argument("--list", action="store_true", help="Print a compact, token-efficient index of all ops and palettes.")
    guide_p.add_argument("--op", default=None, help="Print focused documentation and JSON example for a single op or post op.")
    guide_p.add_argument("--style", default=None, help="Print an agent-ready style brief from a `.style.json` profile.")
    guide_p.set_defaults(func=_cmd_guide)

    style_p = sub.add_parser(
        "style",
        help="Workflow A: ingest JPG/JFIF/PNG/WEBP references, study their pixel-art Style DNA into `.style.json`, merge packs, and print agent briefs.",
    )
    style_sub = style_p.add_subparsers(dest="style_command", required=True)

    st_ingest = style_sub.add_parser(
        "ingest",
        help="Recover clean 1:1 native pixel art PNG(s) from upscaled/compressed JPG, JFIF, PNG, or WEBP references.",
    )
    st_ingest.add_argument("inputs", nargs="+", help="Reference image file(s) or directory.")
    st_ingest.add_argument("-o", "--output", required=True, help="Output .png file (single input) or directory (multiple inputs).")
    st_ingest.add_argument("--scale", type=float, default=None, help="Optional manual logical pixel size (auto-detected if omitted).")
    st_ingest.add_argument("--max-colors", type=int, default=32, help="Maximum palette colors after OKLAB quantization (default: 32).")
    st_ingest.add_argument("--keep-bg", action="store_true", help="Keep original background instead of flood-fill removing solid borders.")
    st_ingest.add_argument("--json", action="store_true", help="Print ingestion metrics as JSON.")
    st_ingest.set_defaults(func=_cmd_style_ingest)

    st_study = style_sub.add_parser(
        "study",
        help="Ingest one or more references and extract a reusable `.style.json` profile (ramps, hue-shifting, outline, lighting, shading).",
    )
    st_study.add_argument("inputs", nargs="+", help="Reference image file(s) or directory.")
    st_study.add_argument("-o", "--output", required=True, help="Output `.style.json` path (e.g. library/styles/my_style.style.json).")
    st_study.add_argument("--name", default="learned_style", help="Human-readable style name (default: learned_style).")
    st_study.add_argument("--max-colors", type=int, default=24, help="Maximum colors in learned palette (default: 24).")
    st_study.add_argument("--scale", type=float, default=None, help="Optional manual logical pixel size.")
    st_study.add_argument("--keep-bg", action="store_true", help="Keep original background during ingestion.")
    st_study.add_argument("--save-clean", default=None, help="Optional directory to also save cleaned 1:1 native PNGs.")
    st_study.add_argument("--json", action="store_true", help="Print the full `.style.json` profile to stdout.")
    st_study.set_defaults(func=_cmd_style_study)

    st_merge = style_sub.add_parser(
        "merge",
        help="Consolidate multiple `.style.json` profiles into one consensus style pack.",
    )
    st_merge.add_argument("profiles", nargs="+", help="Input `.style.json` profile paths or `@styles/<name>`.")
    st_merge.add_argument("-o", "--output", required=True, help="Output merged `.style.json` path.")
    st_merge.add_argument("--name", default="merged_style", help="Name for the merged style pack.")
    st_merge.add_argument("--max-colors", type=int, default=32, help="Maximum colors in merged palette (default: 32).")
    st_merge.set_defaults(func=_cmd_style_merge)

    st_guide = style_sub.add_parser(
        "guide",
        help="Print a concise, AI-agent-ready style brief from a `.style.json` profile.",
    )
    st_guide.add_argument("profile", help="Path to `.style.json` or `@styles/<name>`.")
    st_guide.set_defaults(func=_cmd_style_guide)

    st_compare = style_sub.add_parser(
        "compare",
        help="Export a side-by-side visual comparison sheet (Reference | Ingest 1:1 | Generated).",
    )
    st_compare.add_argument("reference", help="Original reference image (JPG/JFIF/PNG/WEBP).")
    st_compare.add_argument("generated", help="Generated sprite PNG to compare.")
    st_compare.add_argument("-o", "--output", required=True, help="Output comparison PNG path.")
    st_compare.add_argument("--style", default=None, help="Optional `.style.json` profile to include fidelity score.")
    st_compare.add_argument("--scale", type=int, default=6, help="Nearest-neighbor zoom factor (default: 6).")
    st_compare.add_argument("--json", action="store_true", help="Print comparison report as JSON.")
    st_compare.set_defaults(func=_cmd_style_compare)

    schema_p = sub.add_parser(
        "schema",
        help="Print the JSON Schema (draft-07) for PixelAI-Tools declarative specs.",
    )
    schema_p.set_defaults(func=_cmd_schema)

    diff_p = sub.add_parser(
        "diff",
        help="Compare two PNG/GIF sprites pixel-by-pixel and export a BEFORE | AFTER | DIFF sheet.",
    )
    diff_p.add_argument("before", help="Path to the baseline PNG/GIF image.")
    diff_p.add_argument("after", help="Path to the modified PNG/GIF image.")
    diff_p.add_argument("-o", "--output", default=None, help="Optional output PNG path for BEFORE | AFTER | DIFF sheet.")
    diff_p.add_argument("--scale", type=int, default=4, help="Integer upscale factor for diff sheet (default: 4).")
    diff_p.add_argument("--json", action="store_true", help="Print diff metrics as JSON.")
    diff_p.set_defaults(func=_cmd_diff)

    structure_p = sub.add_parser("structure", help="Inspect growth/anatomy/architecture/fracture graphs independently of colors and labels.")
    structure_p.add_argument("spec")
    structure_p.add_argument("--compare", help="Optional second source specification.")
    structure_p.add_argument("--frame", type=int, default=0)
    structure_p.add_argument("--full", action="store_true", help="Include complete rendered graph records.")
    structure_p.add_argument("--motion", action="store_true", help="Trace body/limb movement across named clips; requires one consistent anatomy graph per frame.")
    structure_p.add_argument("--json", action="store_true")

    def report_structure(args):
        from pixelai.structure import analyze_structures
        print(json.dumps(analyze_structures(_read_spec(args.spec), _read_spec(args.compare) if args.compare else None, args.frame, args.full, args.motion)))
        return 0

    structure_p.set_defaults(func=report_structure)
    from pixelai.workflow import register
    register(sub)
    from pixelai.manifest import register as register_manifest
    register_manifest(sub)
    from pixelai.diversity import register as register_diversity
    register_diversity(sub)
    from pixelai.runtime import register as register_runtime
    register_runtime(sub)
    from pixelai.nine_slice import register as register_ui
    register_ui(sub)
    from pixelai.tileqa import register as register_tileqa
    register_tileqa(sub)

    studio_p = sub.add_parser(
        "studio",
        help="Launch the optional offline local browser Studio (127.0.0.1) for voxel sculpting, 2D frame patching, and live FX.",
    )
    studio_p.add_argument("file", nargs="?", default=None, help="Optional .vox.json, .json, or .png file to open.")
    studio_p.add_argument("--port", type=int, default=5190, help="Localhost port (default: 5190).")
    studio_p.add_argument("--no-browser", action="store_true", help="Do not automatically open the system browser.")

    def _run_studio(args: argparse.Namespace) -> int:
        from pixelai.studio import run_studio_server
        run_studio_server(args.file, port=args.port, open_browser=not args.no_browser)
        return 0

    studio_p.set_defaults(func=_run_studio)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, OverflowError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "command": args.command, "error": str(exc)}), file=sys.stderr)
        else:
            print(f"pixelai {args.command}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
