"""Declarative JSON spec and multi-frame runner for pixelai-tools."""

from pathlib import Path
import json
from typing import Any
from pixelai.canvas import Canvas
from pixelai.color import RGBA, TRANSPARENT, brighten, darken, hue_ramp, parse_color
from pixelai.exporter import extract_spec_from_png
from pixelai.inspect_tool import load_png_as_canvas
from pixelai.palettes import resolve_palette
from pixelai.schema import lint_op_fields, lint_post_fields
from pixelai import autotile, building, creatures, deform, filters, fx, iso, items, materials, nature, organic, rig, ui, voxel


_GENERATOR_OPS = frozenset({
    "assembly",
    "animal_rig", "char_rig", "nature_rig", "item_rig",
    "building", "portrait_rig", "ui_rig", "autotile",
    "tilemap", "iso_structure", "material", "spine_rig",
    "voxel_model",
})


def _execute_ops(
    canvas: Canvas,
    ops: list[dict[str, Any]],
    palette: dict[str, RGBA],
    defs: dict[str, Canvas],
    frame_idx: int = 0,
    total_frames: int = 1,
) -> None:
    """Execute a sequence of drawing operations on a Canvas."""
    for index, op in enumerate(ops):
        try:
            _execute_ops_unchecked(canvas, [op], palette, defs, frame_idx, total_frames)
        except KeyError as exc:
            raise ValueError(f"ops[{index}] ({op.get('op')}): missing or unknown field/key {exc}") from exc
        except (ValueError, TypeError, IndexError, OSError) as exc:
            kind = op.get("op") if isinstance(op, dict) else None
            raise ValueError(f"ops[{index}] ({kind}): {exc}") from exc


def _execute_ops_unchecked(canvas, ops, palette, defs, frame_idx, total_frames):
    for op in ops:
        kind = op["op"]
        for warn in lint_op_fields(op):
            canvas.warnings.append(warn)
        if "z" in op:
            canvas.current_z = float(op["z"])
        else:
            canvas.current_z = None

        is_shadow_op = (
            kind not in _GENERATOR_OPS
            and (
                bool(op.get("shadow", False))
                or (kind in ("ellipse", "rect") and str(op.get("color", "")) == "shadow" and op.get("outline") is not True)
            )
        )
        canvas.mark_shadow = is_shadow_op
        if "outline" in op:
            canvas.mark_no_outline = not bool(op["outline"])
        elif kind == "particles":
            canvas.mark_no_outline = True
        else:
            canvas.mark_no_outline = is_shadow_op

        canvas.clip_to_opaque = bool(op.get("inside", op.get("clip", False)))

        if kind == "assembly":
            from pixelai.assembly import resolve_parts
            for part, (px, py) in resolve_parts(op["parts"]):
                local = Canvas(part["width"], part["height"])
                _execute_ops(local, part["ops"], palette, defs, frame_idx, total_frames)
                ox, oy = int(op.get("x", 0)) + px, int(op.get("y", 0)) + py
                canvas.blit(local, ox, oy)
                canvas.clipped_pixels += local.clipped_pixels
                canvas.warnings.extend(f"part[{part['id']}]: {warning}" for warning in local.warnings)
                for field in ("shadow_pixels", "no_outline"):
                    destination = getattr(canvas, field)
                    for index in getattr(local, field):
                        x, y = ox + index % local.width, oy + index // local.width
                        if canvas.in_bounds(x, y):
                            destination.add(y * canvas.width + x)
                canvas.attachments.append({"type": "part", "name": part["id"], "parent": part.get("parent"),
                                           "origin": [ox, oy], "material": part.get("material")})
        elif kind == "pixel":
            canvas.set_pixel(op["x"], op["y"], parse_color(op["color"], palette))
        elif kind == "line":
            canvas.draw_line(
                op["x0"], op["y0"], op["x1"], op["y1"],
                parse_color(op["color"], palette),
            )
        elif kind == "rect":
            canvas.draw_rect(
                op["x"], op["y"], op["w"], op["h"],
                parse_color(op["color"], palette),
                filled=op.get("filled", True),
                bevel=bool(op.get("bevel", False)),
                recessed=bool(op.get("recessed", False)),
            )
        elif kind == "circle":
            canvas.draw_circle(
                op["cx"], op["cy"], op["r"],
                parse_color(op["color"], palette),
                filled=op.get("filled", False),
            )
        elif kind == "ellipse":
            canvas.draw_ellipse(
                int(op["cx"]),
                int(op["cy"]),
                int(op["rx"]),
                int(op["ry"]),
                parse_color(op["color"], palette),
                filled=bool(op.get("filled", True)),
            )
        elif kind == "bezier":
            pts = [(int(p[0]), int(p[1])) for p in op["points"]]
            canvas.draw_bezier(
                pts,
                parse_color(op["color"], palette),
                thickness=int(op.get("thickness", 1)),
            )
        elif kind == "particles":
            pw = int(op.get("w", canvas.width))
            ph = int(op.get("h", canvas.height))
            mode = op.get("mode", "smoke")
            px = int(op.get("x", 0))
            py = int(op.get("y", 0))
            if mode == "smoke" and canvas.last_chimney is not None and op.get("attach_chimney", True):
                ccx, ccy = canvas.last_chimney
                if "x" not in op or abs((px + pw // 2) - ccx) > 3 or (py + ph) > ccy + 2:
                    px = ccx - pw // 2
                    py = max(0, ccy - ph)
            canvas.draw_particles(
                px,
                py,
                pw,
                ph,
                int(op.get("count", 8)),
                parse_color(op["color"], palette),
                frame=int(op.get("frame", frame_idx)),
                total_frames=int(op.get("total_frames", max(1, total_frames))),
                mode=mode,
                size=int(op.get("size", 1)),
                seed=int(op.get("seed", 42)),
            )
        elif kind == "polygon":
            pts = [(int(p[0]), int(p[1])) for p in op["points"]]
            canvas.draw_polygon(
                pts,
                parse_color(op["color"], palette),
                filled=op.get("filled", True),
            )
        elif kind == "fill":
            canvas.flood_fill(op["x"], op["y"], parse_color(op["color"], palette))
        elif kind == "mirror_x":
            canvas.mirror_x()
        elif kind == "mirror_y":
            canvas.mirror_y()
        elif kind == "grid":
            cmap = dict(palette)
            if "colors" in op:
                cmap.update({k: parse_color(v, palette) for k, v in op["colors"].items()})
            canvas.draw_grid(op.get("x", 0), op.get("y", 0), op["rows"], cmap)
        elif kind == "dither":
            canvas.draw_dither_rect(
                op["x"], op["y"], op["w"], op["h"],
                parse_color(op["color_a"], palette),
                parse_color(op["color_b"], palette),
                mode=str(op.get("mode", "checker")),
                ratio=float(op.get("ratio", 0.5)),
            )
        elif kind == "scatter":
            tgt = (
                parse_color(op["target_color"], palette)
                if "target_color" in op
                else None
            )
            canvas.scatter(
                op.get("x", 0),
                op.get("y", 0),
                op.get("w", canvas.width),
                op.get("h", canvas.height),
                parse_color(op["color"], palette),
                density=float(op.get("density", 0.15)),
                seed=int(op.get("seed", 42)),
                target_color=tgt,
                pattern=op.get("pattern", "noise"),
            )
        elif kind == "stamp":
            def_name = op["def"]
            if def_name not in defs:
                raise ValueError(f"Unknown stamp def: {def_name!r}")
            remap = None
            if "remap" in op:
                remap = {
                    parse_color(k, palette): parse_color(v, palette)
                    for k, v in op["remap"].items()
                }
            src_def = defs[def_name]
            ramp_shift = float(op.get("ramp_shift", 0.0))
            if ramp_shift != 0.0:
                src_def = src_def.copy()
                for i, px in enumerate(src_def.pixels):
                    if px[3] > 0:
                        if ramp_shift > 0:
                            src_def.pixels[i] = brighten(px, 1.0 + 0.16 * ramp_shift)
                        else:
                            src_def.pixels[i] = darken(px, max(0.35, 1.0 + 0.22 * ramp_shift))
            pivot = (
                (float(op["pivot"][0]), float(op["pivot"][1]))
                if "pivot" in op
                else None
            )
            canvas.blit(
                src_def,
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                flip_x=bool(op.get("flip_x", False)),
                flip_y=bool(op.get("flip_y", False)),
                remap=remap,
                angle=float(op.get("angle", 0.0)),
                pivot=pivot,
            )
        elif kind == "load_png":
            src = load_png_as_canvas(op["path"])
            if "crop" in op:
                cx, cy, cw, ch = (int(v) for v in op["crop"])
                cropped = Canvas(cw, ch)
                cropped.blit(src, -cx, -cy)
                src = cropped
            canvas.blit(
                src,
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                flip_x=bool(op.get("flip_x", False)),
                flip_y=bool(op.get("flip_y", False)),
            )
        elif kind == "tilemap":
            tw = int(op.get("tile_w", 16))
            th = int(op.get("tile_h", 16))
            ox = int(op.get("x", 0))
            oy = int(op.get("y", 0))
            mode = op.get("mode", "ortho").lower()
            mapping: dict[str, str] = op.get("map", {})
            cells: list[tuple[int, int, str]] = []
            for ry_idx, row in enumerate(op["rows"]):
                tokens = row.split() if " " in row else list(row)
                for rx_idx, tok in enumerate(tokens):
                    if tok == ".":
                        continue
                    def_key = mapping.get(tok, tok)
                    if def_key not in defs:
                        raise ValueError(f"Tilemap token {tok!r} -> {def_key!r} not in defs")
                    cells.append((rx_idx, ry_idx, def_key))
            if mode == "iso":
                step_x = int(op.get("step_x", tw // 2))
                step_y = int(op.get("step_y", th // 4))
                cells.sort(key=lambda c: c[0] + c[1])
                for rx_idx, ry_idx, def_key in cells:
                    px = ox + (rx_idx - ry_idx) * step_x
                    py = oy + (rx_idx + ry_idx) * step_y
                    canvas.blit(defs[def_key], px, py)
            else:
                for rx_idx, ry_idx, def_key in cells:
                    canvas.blit(defs[def_key], ox + rx_idx * tw, oy + ry_idx * th)
        elif kind == "autotile":
            lip = parse_color(op["lip"], palette) if "lip" in op else None
            autotile.draw_autotile_atlas(
                canvas,
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                int(op.get("tile_size", 16)),
                parse_color(op["inner"], palette),
                parse_color(op["outer"], palette),
                lip_color=lip,
                seed=int(op.get("seed", 42)),
            )
        elif kind == "char_rig":
            rig.draw_char_rig(
                canvas,
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                palette,
                op,
                frame_idx=frame_idx,
                total_frames=total_frames,
            )
        elif kind == "portrait_rig":
            rig.draw_portrait_rig(
                canvas,
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                palette,
                op,
            )
        elif kind == "animal_rig":
            creatures.draw_animal_rig(
                canvas,
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                palette,
                op,
                frame_idx=frame_idx,
                total_frames=total_frames,
            )
        elif kind == "emote":
            creatures.draw_emote(
                canvas,
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                op.get("kind", "heart"),
                frame=int(op.get("frame", frame_idx)),
                palette=palette,
                outline=bool(op.get("outline", False)),
            )
        elif kind == "building":
            building.draw_building(
                canvas,
                palette,
                op,
                frame_idx=frame_idx,
                total_frames=total_frames,
            )
        elif kind == "item_rig":
            items.draw_item_rig(
                canvas,
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                palette,
                op,
                frame_idx=frame_idx,
                total_frames=total_frames,
            )
        elif kind == "nature_rig":
            nature.draw_nature_rig(
                canvas,
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                palette,
                op,
                frame_idx=frame_idx,
                total_frames=total_frames,
            )
        elif kind == "material":
            materials.draw_material(canvas, int(op.get("x", 0)), int(op.get("y", 0)), palette, op)
        elif kind == "ui_rig":
            ui.draw_ui_rig(
                canvas,
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                palette,
                op,
            )
        elif kind == "iso_tile":
            rx = int(op["rx"])
            ry = int(op.get("ry", max(1, rx // 2)))
            border = parse_color(op["border"], palette) if "border" in op else None
            iso.draw_iso_tile(
                canvas,
                int(op["cx"]),
                int(op["cy"]),
                rx,
                ry,
                parse_color(op["color"], palette),
                border=border,
            )
        elif kind == "iso_box":
            rx = int(op["rx"])
            ry = int(op.get("ry", max(1, rx // 2)))
            wins = op.get("windows") or ([op["window"]] if "window" in op else None)
            iso.draw_iso_box(
                canvas,
                int(op["cx"]),
                int(op["cy"]),
                rx,
                ry,
                int(op["h"]),
                parse_color(op["top"], palette),
                parse_color(op["left"], palette),
                parse_color(op["right"], palette),
                bevel=bool(op.get("bevel", True)),
                ground_shadow=int(op.get("ground_shadow", 0)),
                door=op.get("door"),
                windows=wins,
                roof=op.get("roof"),
                palette=palette,
            )
        elif kind == "iso_roof":
            rx = int(op["rx"]) if "rx" in op else None
            ry = int(op["ry"]) if "ry" in op else (max(1, rx // 2) if rx is not None else None)
            gable = parse_color(op["gable"], palette) if "gable" in op else None
            iso.draw_iso_roof(
                canvas,
                int(op["cx"]) if "cx" in op else None,
                int(op["cy"]) if "cy" in op else None,
                rx,
                ry,
                int(op.get("h", 8)),
                parse_color(op.get("left", "roof_l"), palette),
                parse_color(op.get("right", "roof_d"), palette),
                style=op.get("style", "pyramid"),
                gable_color=gable,
                eave_shadow=bool(op.get("eave_shadow", True)),
                bevel=bool(op.get("bevel", True)),
                chimney=op.get("chimney", False),
                palette=palette,
            )
        elif kind == "iso_wall_rect":
            iso.draw_iso_wall_rect(
                canvas,
                op.get("face", "left"),
                int(op["x"]) if "x" in op else None,
                int(op["y"]) if "y" in op else None,
                int(op.get("w", 4)),
                int(op.get("h", 6)),
                parse_color(op.get("color", "wood_d"), palette),
                arch=bool(op.get("arch", False)),
                recessed=bool(op.get("recessed", True)),
                role=op.get("role"),
            )
        elif kind == "iso_structure":
            iso.draw_iso_structure(
                canvas,
                int(op.get("origin_x", canvas.width // 2)),
                int(op.get("origin_y", canvas.height // 2)),
                op["items"],
                palette,
                step_x=int(op["step_x"]) if "step_x" in op else None,
                step_y=int(op["step_y"]) if "step_y" in op else None,
                default_bevel=bool(op.get("bevel", True)),
                default_ground_shadow=int(op.get("ground_shadow", 2)),
            )
        elif kind == "voxel_model":
            if "source" in op:
                vmodel = voxel.VoxelModel.load(op["source"])
            else:
                vmodel = voxel.VoxelModel.from_dict(op)
            raw_oblique = op.get("oblique")
            oblique_tuple = (
                (float(raw_oblique["y"]), float(raw_oblique["z"]))
                if isinstance(raw_oblique, dict)
                else (tuple(float(v) for v in raw_oblique) if isinstance(raw_oblique, (list, tuple)) else None)
            )
            cam = voxel.VoxelCamera(
                yaw=float(op.get("yaw", 0.0)),
                elevation=float(op.get("elevation", 30.0)),
                ppu=int(op.get("ppu", 1)),
                oblique=oblique_tuple,
                origin_x=int(op["origin_x"]) if "origin_x" in op else None,
                origin_y=int(op["origin_y"]) if "origin_y" in op else None,
            )
            raw_thresh = op.get("thresholds", (-0.18, 0.28))
            voxel.render_voxel_model(
                vmodel,
                canvas=canvas,
                camera=cam,
                smooth=float(op.get("smooth", 0.5)),
                ao=float(op.get("ao", 0.35)),
                thresholds=(float(raw_thresh[0]), float(raw_thresh[1])),
            )
        elif kind == "band_gradient":
            if "ramp" in op:
                ramp = [parse_color(c, palette) for c in op["ramp"]]
            elif "hue_ramp" in op:
                hr = op["hue_ramp"]
                ramp = hue_ramp(
                    int(hr.get("n", 5)),
                    hue=float(hr.get("hue", 110.0)),
                    shift=float(hr.get("shift", 60.0)),
                    sat=float(hr.get("sat", 0.55)),
                    sat_drop=float(hr.get("sat_drop", 0.35)),
                    light=tuple(hr.get("light", (0.12, 0.62))),
                )
            else:
                base_col = parse_color(op["color"], palette)
                ramp = [darken(base_col, 0.68), base_col, brighten(base_col, 1.18)]
            canvas.draw_band_gradient(
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                int(op.get("w", canvas.width)),
                int(op.get("h", canvas.height)),
                ramp,
                direction=str(op.get("direction", "vertical")),
                strip=float(op.get("strip", 1.0 / 3.0)),
            )
        elif kind == "text":
            canvas.draw_bitmap_text(
                int(op.get("x", 0)),
                int(op.get("y", 0)),
                str(op["text"]),
                parse_color(op.get("color", "#ffffff"), palette),
                scale=int(op.get("scale", 1)),
            )
        elif kind == "solid":
            if "ramp" in op:
                ramp = [parse_color(c, palette) for c in op["ramp"]]
            elif "hue_ramp" in op:
                hr = op["hue_ramp"]
                ramp = hue_ramp(
                    int(hr.get("n", 5)),
                    hue=float(hr.get("hue", 110.0)),
                    shift=float(hr.get("shift", 60.0)),
                    sat=float(hr.get("sat", 0.55)),
                    sat_drop=float(hr.get("sat_drop", 0.35)),
                    light=tuple(hr.get("light", (0.12, 0.62))),
                )
            else:
                base_col = parse_color(op["color"], palette)
                ramp = [darken(base_col, 0.62), darken(base_col, 0.82), base_col, brighten(base_col, 1.16)]
            light_raw = op.get("light", (-0.55, -0.65, 0.52))
            organic.draw_solid(
                canvas,
                op["primitives"],
                ramp,
                light=(float(light_raw[0]), float(light_raw[1]), float(light_raw[2])),
                k=float(op.get("k", 0.8)),
                ambient=float(op.get("ambient", 0.24)),
                dark=float(op.get("dark", 1.0)),
                gloss=float(op.get("gloss", 0.0)),
                shine=float(op.get("shine", 10.0)),
                cut=float(op.get("cut", 0.12)),
                inflate=float(op.get("inflate", 0.0)),
                inflate_mix=float(op.get("inflate_mix", 0.75)),
                dither_strip=float(op.get("dither_strip", 0.0)),
            )
        elif kind == "flame":
            ramp = [parse_color(c, palette) for c in op["ramp"]] if "ramp" in op else None
            t_val = float(op["t"]) if "t" in op else (frame_idx / max(1, total_frames))
            organic.draw_flame(
                canvas,
                float(op.get("x", canvas.width * 0.5)),
                float(op.get("ground", op.get("y", canvas.height - 2))),
                t=t_val,
                height=float(op.get("height", 28.0)),
                width=float(op.get("width", 9.0)),
                ramp=ramp,
                speed=float(op.get("speed", 3.4)),
                rough=float(op.get("rough", 1.45)),
                sway_amp=float(op.get("sway_amp", 5.0)),
                dither_strip=float(op.get("dither_strip", 0.4)),
                seed=int(op.get("seed", 9)),
                embers=int(op.get("embers", 4)),
            )
        elif kind == "smoke":
            ramp = [parse_color(c, palette) for c in op["ramp"]] if "ramp" in op else None
            t_val = float(op["t"]) if "t" in op else (frame_idx / max(1, total_frames))
            organic.draw_smoke(
                canvas,
                float(op.get("x", canvas.width * 0.5)),
                float(op.get("ground", op.get("y", canvas.height - 2))),
                t=t_val,
                height=float(op.get("height", 40.0)),
                width=float(op.get("width", 2.5)),
                ramp=ramp,
                speed=float(op.get("speed", 1.5)),
                rough=float(op.get("rough", 1.3)),
                sway_amp=float(op.get("sway_amp", 5.0)),
                warp=float(op.get("warp", 22.0)),
                dither_strip=float(op.get("dither_strip", 0.5)),
                seed=int(op.get("seed", 13)),
            )
        elif kind == "ik_limb":
            ramp = [parse_color(c, palette) for c in op["ramp"]] if "ramp" in op else None
            deform.draw_ik_limb(
                canvas,
                op["start"],
                op["target"],
                float(op["l1"]),
                float(op["l2"]),
                parse_color(op.get("color", "#c0a080"), palette),
                direction=int(op.get("direction", op.get("dir", 1))),
                radius_a=float(op.get("radius_a", op.get("radius", 2.0))),
                radius_b=float(op.get("radius_b", op.get("radius", 1.5))),
                radius_c=float(op["radius_c"]) if "radius_c" in op else None,
                ramp=ramp,
            )
        elif kind == "bend":
            def_name = op["def"]
            if def_name not in defs:
                raise ValueError(f"Unknown bend def: {def_name!r}")
            rest = op["rest"]
            if "pose" in op:
                pose = op["pose"]
            elif "wave" in op:
                wv = op["wave"]
                t_val = float(wv["t"]) if "t" in wv else (frame_idx / max(1, total_frames))
                pose = deform.wave_polyline(
                    rest,
                    t=t_val,
                    amp=float(wv.get("amp", 3.0)),
                    wavelength=float(wv.get("wavelength", 16.0)),
                    anchor_from=float(wv.get("from", 0.0)),
                )
            else:
                raise ValueError("bend op requires 'pose' or 'wave'")
            deform.bend_canvas(
                defs[def_name],
                rest=rest,
                pose=pose,
                reach=float(op["reach"]) if "reach" in op else None,
                target=canvas,
                offset_x=int(op.get("x", 0)),
                offset_y=int(op.get("y", 0)),
            )
        elif kind == "spine_rig":
            eye_col = parse_color(op.get("eye_color", "#ff3b6b"), palette)
            deform.draw_biped_spine_rig(
                canvas,
                cx=float(op["cx"]) if "cx" in op else None,
                ground_y=float(op["ground_y"]) if "ground_y" in op else None,
                facing=op.get("facing", op.get("dir", "right")),
                action=str(op.get("action", op.get("pose", "walk"))),
                frame=int(op.get("frame", frame_idx)),
                total_frames=int(op.get("total_frames", max(1, total_frames))),
                body_hue=float(op.get("body_hue", op.get("hue", 270.0))),
                body_sat=float(op.get("body_sat", op.get("sat", 0.65))),
                eye_color=eye_col,
                horns=bool(op.get("horns", True)),
                tail=bool(op.get("tail", True)),
                scale=float(op.get("scale", 1.0)),
                shadow=bool(op.get("shadow", True)),
            )
        else:
            raise ValueError(f"Unknown op: {kind!r}")
        canvas.mark_no_outline = False
        canvas.mark_shadow = False
        canvas.clip_to_opaque = False


_STYLE_PROFILES: dict[str, dict[str, Any]] = {
    "cozy_modern": {
        "selout": True,
        "directional_selout": True,
        "selout_amount": 0.55,
        "clean_jaggies": True,
    },
    "16bit_cluster": {
        "selout": True,
        "directional_selout": True,
        "selout_amount": 0.72,
        "clean_jaggies": True,
    },
    "crisp_retro": {
        "selout": False,
        "directional_selout": False,
        "clean_jaggies": True,
    },
    "enchanted_hd": {
        "selout": True,
        "directional_selout": True,
        "selout_amount": 0.48,
        "clean_jaggies": True,
    },
}


def _resolve_post_ops(
    spec: dict[str, Any], palette: dict[str, RGBA]
) -> list[dict[str, Any]]:
    """Enforce 'ext_outline' / 'lineless', style_profile presets, and top-level material recoloring."""
    style = spec.get("style")
    profile_name = spec.get("style_profile")
    profile_cfg: dict[str, Any] = {}
    if profile_name:
        key = str(profile_name).strip().lower()
        if key not in _STYLE_PROFILES:
            avail = ", ".join(sorted(_STYLE_PROFILES))
            raise ValueError(f"Unknown style_profile {profile_name!r}. Available: {avail}")
        profile_cfg = _STYLE_PROFILES[key]

    raw_post = list(spec.get("post", []))

    if style == "lineless":
        out_ops = [p for p in raw_post if p.get("op") != "outline"]
    elif style == "ext_outline" and not any(p.get("op") == "outline" for p in raw_post):
        fallback_col: Any = "#21181b"
        if "ink" in palette:
            fallback_col = "ink"
        elif "0" in palette:
            c0 = palette["0"]
            lum = c0[0] * 0.299 + c0[1] * 0.587 + c0[2] * 0.114
            if lum < 65:
                fallback_col = "0"
        default_col = spec.get("outline_color", fallback_col)
        outline_op: dict[str, Any] = {"op": "outline", "color": default_col, **profile_cfg}
        if spec.get("auto_pad"):
            outline_op["auto_pad"] = True
        # Insert before 'scale' so the outline stays 1px in art resolution
        out_ops = []
        inserted = False
        for p in raw_post:
            if p.get("op") == "scale" and not inserted:
                out_ops.append(outline_op)
                inserted = True
            out_ops.append(p)
        if not inserted:
            out_ops.append(outline_op)
    else:
        out_ops = []
        for p in raw_post:
            if p.get("op") == "outline" and profile_cfg:
                merged_p = {**profile_cfg, **p}
                out_ops.append(merged_p)
            else:
                out_ops.append(p)

    # Top-level material recolor shortcut (e.g. "material": "gold_specular")
    if "material" in spec and not any(p.get("op") == "recolor_material" for p in out_ops):
        mat_op: dict[str, Any] = {"op": "recolor_material", "material": spec["material"]}
        final_ops: list[dict[str, Any]] = []
        inserted_mat = False
        for p in out_ops:
            if p.get("op") == "scale" and not inserted_mat:
                final_ops.append(mat_op)
                inserted_mat = True
            final_ops.append(p)
        if not inserted_mat:
            final_ops.append(mat_op)
        return final_ops

    return out_ops


def _apply_post(
    canvas: Canvas, post_ops: list[dict[str, Any]], palette: dict[str, RGBA]
) -> Canvas:
    for post in post_ops:
        kind = post["op"]
        for warn in lint_post_fields(post):
            canvas.warnings.append(warn)
        if kind == "outline":
            canvas = filters.outline(
                canvas,
                parse_color(post["color"], palette),
                selout=bool(post.get("selout", False)),
                selout_amount=float(post.get("selout_amount", 0.55)),
                auto_pad=bool(post.get("auto_pad", False)),
                directional_selout=bool(post.get("directional_selout", False)),
                clean_jaggies=bool(post.get("clean_jaggies", False)),
            )
        elif kind == "recolor_material":
            targets = (
                [parse_color(c, palette) for c in post["target_colors"]]
                if "target_colors" in post
                else None
            )
            canvas = filters.recolor_material(
                canvas,
                post["material"],
                target_colors=targets,
                reflectance=post.get("reflectance"),
                recolor_outline=bool(post.get("recolor_outline", True)),
            )
        elif kind == "drop_shadow":
            col = (
                parse_color(post["color"], palette)
                if "color" in post
                else (33, 24, 27, 96)
            )
            canvas = filters.drop_shadow(
                canvas,
                dx=int(post.get("dx", 1)),
                dy=int(post.get("dy", 2)),
                color=col,
            )
        elif kind == "pad":
            canvas = filters.pad(canvas, int(post.get("size", 1)))
        elif kind == "shade":
            canvas = filters.shade(
                canvas,
                float(post.get("amount", 0.25)),
                hue_shift=bool(post.get("hue_shift", False)),
            )
        elif kind == "cleanup":
            canvas = filters.cleanup(
                canvas,
                tol=float(post.get("tol", 60.0)),
                keep_lone=bool(post.get("keep_lone", False)),
            )
        elif kind == "pixel_perfect":
            canvas = filters.pixel_perfect(canvas)
        elif kind == "rim_light":
            ramp = [parse_color(c, palette) for c in post["ramp"]] if "ramp" in post else None
            raw_dir = post.get("dir", post.get("direction", (-1, -1)))
            canvas = filters.rim_light(
                canvas,
                ramp=ramp,
                direction=(int(raw_dir[0]), int(raw_dir[1])),
                steps=int(post.get("steps", 1)),
            )
        elif kind == "scale":
            canvas = filters.scale(canvas, int(post["factor"]))
        else:
            raise ValueError(f"Unknown post-processing op: {kind!r}")
    return canvas


def resolve_spec_paths(spec: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """Anchor declared input paths to the directory containing the spec."""
    if not isinstance(spec, dict):
        raise ValueError("spec: expected a JSON object")
    spec = dict(spec)
    if "extends" in spec:
        spec["extends"] = str((base_dir / spec["extends"]).resolve())
    for key in ("ops", "layers", "frames", "keyframes"):
        if key not in spec:
            continue
        if not isinstance(spec[key], list):
            raise ValueError(f"{key}: expected an array")
        entries = []
        for index, entry in enumerate(spec[key]):
            if not isinstance(entry, dict):
                raise ValueError(f"{key}[{index}]: expected an object")
            if key != "ops":
                entry = resolve_spec_paths(entry, base_dir)
            elif entry.get("op") == "load_png" and "path" in entry:
                if not isinstance(entry["path"], str):
                    raise ValueError(f"ops[{index}] (load_png): path must be a string")
                entry = {**entry, "path": str((base_dir / entry["path"]).resolve())}
            entries.append(entry)
        spec[key] = entries
    if "defs" in spec:
        if not isinstance(spec["defs"], dict):
            raise ValueError("defs: expected an object")
        spec["defs"] = {
            name: resolve_spec_paths(definition, base_dir)
            for name, definition in spec["defs"].items()
        }
    return spec


def _check_fresh(spec: dict[str, Any]) -> None:
    """Reject external asset reuse throughout a fresh generation spec."""
    if "fresh" in spec and not isinstance(spec["fresh"], bool):
        raise ValueError("fresh must be a boolean")
    def visit(value, path):
        if isinstance(value, dict):
            if "extends" in value or value.get("op") == "load_png":
                raise ValueError(f"{path}: fresh generation forbids extends and load_png; draw a new asset")
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
    if spec.get("fresh", False):
        visit(spec, "spec")


from pixelai.resources import library_root

_LIBRARY_ROOT = library_root()


def _resolve_import_path(ref: str) -> Path:
    """Resolve '@namespace/name' against the built-in library or a relative file path."""
    if ref.startswith("@"):
        rel = ref[1:].strip("/")
        if not rel.endswith(".json"):
            rel += ".json"
        candidate = _LIBRARY_ROOT / rel
        if not candidate.resolve().is_relative_to(_LIBRARY_ROOT.resolve()):
            raise ValueError("Library imports must remain inside the built-in library")
        if not candidate.exists():
            raise ValueError(f"Unknown library import {ref!r} (expected {candidate})")
        return candidate
    candidate = Path(ref)
    if not candidate.exists():
        raise ValueError(f"Import file not found: {ref!r}")
    return candidate


def _resolve_imports(spec: dict[str, Any]) -> dict[str, Any]:
    """Merge reusable defs, palette_ext, material, and fx from 'imports'."""
    imports = spec.get("imports")
    if not imports:
        return spec
    if not isinstance(imports, list):
        raise ValueError("imports: expected an array of '@namespace/name' or file paths")

    merged = dict(spec)
    combined_defs: dict[str, Any] = {}
    combined_pal_ext: dict[str, Any] = {}
    imported_fx: list[dict[str, Any]] = []
    imported_material: str | None = None

    for ref in imports:
        if not isinstance(ref, str):
            raise ValueError(f"imports entry must be a string, got {type(ref).__name__}")
        path = _resolve_import_path(ref)
        lib_data = resolve_spec_paths(json.loads(path.read_text(encoding="utf-8-sig")), path.parent)
        if isinstance(lib_data.get("defs"), dict):
            combined_defs.update(lib_data["defs"])
        if isinstance(lib_data.get("palette_ext"), dict):
            combined_pal_ext.update(lib_data["palette_ext"])
        if isinstance(lib_data.get("fx"), list):
            imported_fx.extend(lib_data["fx"])
        if "material" in lib_data and isinstance(lib_data["material"], str):
            imported_material = lib_data["material"]
        if "palette" in lib_data and "palette" not in merged:
            merged["palette"] = lib_data["palette"]

    if combined_defs:
        own_defs = merged.get("defs", {})
        combined_defs.update(own_defs)
        merged["defs"] = combined_defs
    if combined_pal_ext:
        own_ext = merged.get("palette_ext", {})
        combined_pal_ext.update(own_ext)
        merged["palette_ext"] = combined_pal_ext
    if imported_fx and "fx" not in merged:
        merged["fx"] = imported_fx
    if imported_material and "material" not in merged:
        merged["material"] = imported_material
    return merged


def _resolve_extends(spec: dict[str, Any]) -> dict[str, Any]:
    """Merge parent spec from 'extends' (.png with embedded spec or .json file) and 'imports'."""
    _check_fresh(spec)
    if "extends" not in spec:
        resolved = _resolve_imports(spec)
        _check_fresh(resolved)
        return resolved
    parent_path = Path(spec["extends"])
    if parent_path.suffix.lower() == ".png":
        parent = extract_spec_from_png(parent_path)
    else:
        parent = json.loads(parent_path.read_text(encoding="utf-8-sig"))

    merged = resolve_spec_paths(parent, parent_path.resolve().parent)
    for k, v in spec.items():
        if k == "extends":
            continue
        if k in ("defs", "palette_ext") and isinstance(merged.get(k), dict) and isinstance(v, dict):
            combined = dict(merged[k])
            combined.update(v)
            merged[k] = combined
        elif k == "ops" and spec.get("inherit_ops", False):
            merged["ops"] = list(merged.get("ops", [])) + list(v)
        else:
            merged[k] = v
    _check_fresh(merged)
    resolved = _resolve_imports(merged)
    _check_fresh(resolved)
    return resolved


_TWEEN_KEYS = ("x", "y", "cx", "cy", "rx", "ry", "r", "w", "h", "angle", "x0", "y0", "x1", "y1")


def _expand_keyframes(keyframes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Interpolate numeric op properties across consecutive keyframes."""
    if not keyframes:
        return []
    expanded: list[dict[str, Any]] = []
    for k_idx, kf in enumerate(keyframes):
        steps = max(1, int(kf.get("steps", 1)))
        base_name = kf.get("name", f"kf_{k_idx}")
        ops_a = kf.get("ops", [])
        if k_idx + 1 >= len(keyframes) or steps == 1:
            expanded.append({"name": base_name, "ops": ops_a, "inherit_base": kf.get("inherit_base", True)})
            continue
        ops_b = keyframes[k_idx + 1].get("ops", [])
        for s in range(steps):
            t = s / steps
            interp_ops: list[dict[str, Any]] = []
            for idx, op_a in enumerate(ops_a):
                if idx < len(ops_b) and ops_b[idx].get("op") == op_a.get("op"):
                    op_b = ops_b[idx]
                    new_op = dict(op_a)
                    for tk in _TWEEN_KEYS:
                        if tk in op_a and tk in op_b:
                            val = float(op_a[tk]) * (1.0 - t) + float(op_b[tk]) * t
                            new_op[tk] = val if tk == "angle" else int(round(val))
                    interp_ops.append(new_op)
                else:
                    interp_ops.append(dict(op_a))
            expanded.append({
                "name": f"{base_name}_{s}",
                "ops": interp_ops,
                "inherit_base": kf.get("inherit_base", True),
            })
    return expanded


def _resolve_style_ref(spec: dict[str, Any]) -> dict[str, Any]:
    """If top-level `style_ref` is present, apply the learned `.style.json` profile."""
    ref = spec.get("style_ref")
    if not ref:
        return spec
    from pixelai.style_profile import apply_style_to_spec, load_style_profile
    profile = load_style_profile(ref)
    return apply_style_to_spec(spec, profile)


def _ordered_layers(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Return visible layers sorted back-to-front by explicit `z` (lower=behind, higher=front)."""
    raw = spec.get("layers", [])
    visible = [(idx, lspec) for idx, lspec in enumerate(raw) if lspec.get("visible", True)]
    visible.sort(key=lambda pair: (int(pair[1].get("z", 0)), pair[0]))
    return [lspec for _, lspec in visible]


def run_layers(spec: dict[str, Any]) -> list[tuple[str, Canvas]]:
    """Render each visible named layer in `spec['layers']` (sorted back-to-front by `z`) into its own Canvas."""
    spec = _resolve_style_ref(_resolve_extends(spec))
    width = int(spec["width"])
    height = int(spec["height"])
    palette = resolve_palette(spec.get("palette"), spec.get("palette_ext"))

    defs: dict[str, Canvas] = {}
    for name, dspec in spec.get("defs", {}).items():
        dw = int(dspec.get("width", width))
        dh = int(dspec.get("height", height))
        dc = Canvas(dw, dh, fill=TRANSPARENT)
        _execute_ops(dc, dspec.get("ops", []), palette, defs)
        if "post" in dspec:
            dc = _apply_post(dc, dspec["post"], palette)
        defs[name] = dc

    result: list[tuple[str, Canvas]] = []
    for idx, lspec in enumerate(_ordered_layers(spec)):
        lname = lspec.get("name", f"layer_{idx}")
        lc = Canvas(width, height, fill=TRANSPARENT)
        _execute_ops(lc, lspec.get("ops", []), palette, defs)
        if "post" in lspec:
            lc = _apply_post(lc, lspec["post"], palette)
        result.append((lname, lc))
    return result


def _merge_frame_ops_into_base(
    base_ops: list[dict[str, Any]], frame_ops: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge frame/keyframe ops into base_ops without burying foreground structures under shadows."""
    if not base_ops:
        return list(frame_ops)
    if not frame_ops:
        return list(base_ops)
    merged = [dict(op) for op in base_ops]
    appended: list[dict[str, Any]] = []
    for fop in frame_ops:
        # If frame op matches a background/shadow op already in base_ops, update it in-place
        replaced = False
        for idx, bop in enumerate(merged):
            if (
                bop.get("op") == fop.get("op")
                and bop.get("color") == fop.get("color")
                and fop.get("op") in ("ellipse", "particles")
            ):
                merged[idx] = dict(fop)
                replaced = True
                break
        if not replaced:
            if fop.get("op") == "ellipse" and str(fop.get("color", "")).startswith("shadow"):
                merged.insert(0, dict(fop))
            else:
                appended.append(dict(fop))
    return merged + appended


def run_frames(spec: dict[str, Any]) -> tuple[list[Canvas], list[str]]:
    """Execute a spec into one or more post-processed frames and their names."""
    spec = _resolve_style_ref(_resolve_extends(spec))
    from pixelai.runtime_contract import attach_runtime
    width = int(spec["width"])
    height = int(spec["height"])
    palette = resolve_palette(spec.get("palette"), spec.get("palette_ext"))
    bg = parse_color(spec["background"], palette) if "background" in spec else TRANSPARENT

    defs: dict[str, Canvas] = {}
    for name, dspec in spec.get("defs", {}).items():
        dw = int(dspec.get("width", width))
        dh = int(dspec.get("height", height))
        dc = Canvas(dw, dh, fill=TRANSPARENT)
        _execute_ops(dc, dspec.get("ops", []), palette, defs)
        if "post" in dspec:
            dc = _apply_post(dc, dspec["post"], palette)
        defs[name] = dc

    base_ops = list(spec.get("ops", []))
    for lspec in _ordered_layers(spec):
        base_ops.extend(lspec.get("ops", []))

    post_ops = _resolve_post_ops(spec, palette)
    raw_frames = spec.get("frames")
    if not raw_frames and "keyframes" in spec:
        raw_frames = _expand_keyframes(spec["keyframes"])
    if not raw_frames and (
        "frame_count" in spec
        or any(op.get("op") in ("particles", "animal_rig", "emote") for op in base_ops)
        or any(op.get("op") == "nature_rig" and op.get("sway") for op in base_ops)
    ):
        default_fc = 6 if any(op.get("pose") == "peck" for op in base_ops) else (
            4 if (
                any(op.get("op") in ("particles", "animal_rig", "emote") for op in base_ops)
                or any(op.get("op") == "nature_rig" and op.get("sway") for op in base_ops)
            ) else 1
        )
        fc = int(spec.get("frame_count", default_fc))
        if fc > 1:
            raw_frames = [{"name": f"frame_{i}", "ops": []} for i in range(fc)]

    fx_list = spec.get("fx", [])
    if not isinstance(fx_list, list):
        raise ValueError("fx: expected an array of FX objects")

    if not raw_frames:
        canvas = Canvas(width, height, fill=bg)
        _execute_ops(canvas, _merge_frame_ops_into_base([], base_ops), palette, defs, frame_idx=0, total_frames=1)
        attach_runtime(canvas, spec, 0, 1)
        base_frame = _apply_post(canvas, post_ops, palette)
        if fx_list:
            fx_frames = fx.apply_fx_pipeline(
                [base_frame],
                fx_list,
                palette=palette,
                total_frames=spec.get("frame_count"),
            )
            return fx_frames, [f"frame_{i}" for i in range(len(fx_frames))]
        return [base_frame], ["frame_0"]

    total = len(raw_frames)
    frames: list[Canvas] = []
    names: list[str] = []
    for idx, fspec in enumerate(raw_frames):
        canvas = Canvas(width, height, fill=bg)
        effective_ops = (
            _merge_frame_ops_into_base(base_ops, fspec.get("ops", []))
            if fspec.get("inherit_base", True)
            else list(fspec.get("ops", []))
        )
        _execute_ops(canvas, effective_ops, palette, defs, frame_idx=idx, total_frames=total)
        attach_runtime(canvas, spec, idx, total)
        frames.append(_apply_post(canvas, post_ops, palette))
        names.append(fspec.get("name", f"frame_{idx}"))
    if fx_list:
        frames = fx.apply_fx_pipeline(frames, fx_list, palette=palette)
    return frames, names


def run_spec(spec: dict[str, Any]) -> Canvas:
    """Execute a declarative pixel art specification and return the first Canvas."""
    frames, _ = run_frames(spec)
    return frames[0]
