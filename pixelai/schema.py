"""JSON Schema, modular per-op documentation, and fuzzy field linting for AI agents."""

from __future__ import annotations

import difflib
from typing import Any

from pixelai.palettes import list_palettes

UNIVERSAL_OP_FIELDS: frozenset[str] = frozenset({"op", "z", "inside", "clip", "outline", "shadow"})

OP_SPECS: dict[str, dict[str, Any]] = {
    "assembly": {
        "summary": "Render named parented native-pixel parts with stable ids, offsets and draw order.",
        "required": ["parts"], "optional": ["x", "y"],
        "example": {"op": "assembly", "parts": [{"id": "body", "width": 8, "height": 8, "offset": [4, 4], "ops": [{"op": "rect", "x": 0, "y": 0, "w": 8, "h": 8, "color": "#448855"}]}]},
    },
    "pixel": {
        "summary": "Set a single pixel at (x, y).",
        "required": ["x", "y", "color"],
        "optional": [],
        "example": {"op": "pixel", "x": 4, "y": 4, "color": "ink"},
    },
    "line": {
        "summary": "Draw a 1px Bresenham line from (x0, y0) to (x1, y1).",
        "required": ["x0", "y0", "x1", "y1", "color"],
        "optional": [],
        "example": {"op": "line", "x0": 2, "y0": 2, "x1": 14, "y1": 10, "color": "wood"},
    },
    "rect": {
        "summary": "Draw a filled or outlined rectangle with optional bevel or recessed lip.",
        "required": ["x", "y", "w", "h", "color"],
        "optional": ["filled", "bevel", "recessed"],
        "example": {"op": "rect", "x": 4, "y": 4, "w": 16, "h": 12, "color": "wood", "bevel": True},
    },
    "circle": {
        "summary": "Draw a midpoint pixel-art circle centered at (cx, cy) with radius r.",
        "required": ["cx", "cy", "r", "color"],
        "optional": ["filled"],
        "example": {"op": "circle", "cx": 16, "cy": 16, "r": 8, "color": "grass", "filled": True},
    },
    "ellipse": {
        "summary": "Draw a filled or outlined ellipse centered at (cx, cy) with radii (rx, ry).",
        "required": ["cx", "cy", "rx", "ry", "color"],
        "optional": ["filled"],
        "example": {"op": "ellipse", "cx": 16, "cy": 24, "rx": 10, "ry": 4, "color": "shadow"},
    },
    "bezier": {
        "summary": "Draw a quadratic or N-degree Bezier curve through control points.",
        "required": ["points", "color"],
        "optional": ["thickness"],
        "example": {"op": "bezier", "points": [[2, 20], [16, 4], [30, 20]], "color": "wood", "thickness": 2},
    },
    "polygon": {
        "summary": "Draw a filled or outlined polygon from [x, y] vertices.",
        "required": ["points", "color"],
        "optional": ["filled"],
        "example": {"op": "polygon", "points": [[4, 16], [16, 4], [28, 16]], "color": "roof", "filled": True},
    },
    "fill": {
        "summary": "4-way flood fill starting at (x, y).",
        "required": ["x", "y", "color"],
        "optional": [],
        "example": {"op": "fill", "x": 8, "y": 8, "color": "water"},
    },
    "grid": {
        "summary": "Draw pixels from an ASCII art row grid ('.' and ' ' are transparent).",
        "required": ["rows"],
        "optional": ["x", "y", "colors"],
        "example": {"op": "grid", "x": 0, "y": 0, "rows": ["..oo..", ".oggo."]},
    },
    "dither": {
        "summary": "Fill a rectangle with checkerboard or Bayer 4x4 ordered dithering.",
        "required": ["x", "y", "w", "h", "color_a", "color_b"],
        "optional": ["mode", "ratio"],
        "example": {"op": "dither", "x": 0, "y": 0, "w": 16, "h": 16, "color_a": "grass", "color_b": "grass_d", "mode": "bayer4", "ratio": 0.5},
    },
    "band_gradient": {
        "summary": "Flat color bands with Bayer 4x4 dithering strictly along band edges.",
        "required": [],
        "optional": ["x", "y", "w", "h", "ramp", "hue_ramp", "color", "direction", "strip"],
        "example": {"op": "band_gradient", "x": 0, "y": 0, "w": 32, "h": 16, "hue_ramp": {"n": 5, "hue": 210}, "direction": "vertical", "strip": 0.33},
    },
    "solid": {
        "summary": "Smooth-min SDF metaball union of capsules/ellipsoids with normal-mapped lighting.",
        "required": ["primitives"],
        "optional": ["ramp", "hue_ramp", "color", "light", "k", "ambient", "dark", "gloss", "shine", "cut", "inflate", "inflate_mix", "dither_strip"],
        "example": {"op": "solid", "primitives": [{"type": "capsule", "ax": 16, "ay": 10, "bx": 16, "by": 24, "ra": 5, "rb": 7}], "hue_ramp": {"n": 5, "hue": 140}, "inflate": 3},
    },
    "flame": {
        "summary": "Deterministic FBM-driven animated pixel-art flame with rising embers.",
        "required": [],
        "optional": ["x", "y", "ground", "t", "height", "width", "ramp", "speed", "rough", "sway_amp", "dither_strip", "seed", "embers"],
        "example": {"op": "flame", "x": 16, "ground": 30, "height": 22, "width": 7, "embers": 4},
    },
    "smoke": {
        "summary": "Deterministic FBM-warped translucent pixel-art smoke plume.",
        "required": [],
        "optional": ["x", "y", "ground", "t", "height", "width", "ramp", "speed", "rough", "sway_amp", "warp", "dither_strip", "seed"],
        "example": {"op": "smoke", "x": 16, "ground": 28, "height": 32, "width": 2.5, "warp": 18},
    },
    "ik_limb": {
        "summary": "2-bone analytical inverse kinematics limb rendered with smooth SDF shading.",
        "required": ["start", "target", "l1", "l2"],
        "optional": ["color", "direction", "dir", "radius", "radius_a", "radius_b", "radius_c", "ramp"],
        "example": {"op": "ik_limb", "start": [10, 16], "target": [22, 26], "l1": 9, "l2": 9, "direction": 1, "color": "wood"},
    },
    "bend": {
        "summary": "Inverse-bilinear spine deformation of a named `def` via `pose` or auto-animated `wave`.",
        "required": ["def", "rest"],
        "optional": ["pose", "wave", "reach", "x", "y"],
        "example": {"op": "bend", "def": "tail", "rest": [[4, 16], [16, 16], [28, 16]], "wave": {"amp": 3.0, "wavelength": 16.0, "from": 0.1}},
    },
    "spine_rig": {
        "summary": "Full-body Spine + 2-bone IK animated biped creature with guaranteed forward gait, anatomical knee/elbow bends, depth-darkened far limbs, and strict back-to-front Z-order.",
        "required": [],
        "optional": ["cx", "ground_y", "facing", "dir", "action", "pose", "frame", "total_frames", "body_hue", "hue", "body_sat", "sat", "eye_color", "horns", "tail", "scale", "shadow"],
        "example": {"op": "spine_rig", "facing": "right", "action": "walk", "body_hue": 270, "horns": True, "tail": True},
    },
    "text": {
        "summary": "Render crisp 3x5 bitmap pixel text.",
        "required": ["text"],
        "optional": ["x", "y", "color", "scale"],
        "example": {"op": "text", "x": 2, "y": 2, "text": "LV 9", "color": "#ffffff", "scale": 1},
    },
    "particles": {
        "summary": "Looping procedural particles (smoke, leaves, rain, sparks).",
        "required": ["color"],
        "optional": ["x", "y", "w", "h", "count", "frame", "total_frames", "mode", "size", "seed", "attach_chimney"],
        "example": {"op": "particles", "x": 0, "y": 0, "w": 32, "h": 32, "count": 10, "color": "cream", "mode": "sparks"},
    },
    "scatter": {
        "summary": "Procedural surface texture accents clipped to target_color.",
        "required": ["color"],
        "optional": ["x", "y", "w", "h", "density", "seed", "target_color", "pattern"],
        "example": {"op": "scatter", "x": 0, "y": 0, "w": 32, "h": 32, "color": "grass_l", "target_color": "grass", "pattern": "grass"},
    },
    "stamp": {
        "summary": "Blit a reusable `def` canvas with optional flip, rotation, ramp_shift, and color remap.",
        "required": ["def"],
        "optional": ["x", "y", "flip_x", "flip_y", "remap", "angle", "pivot", "ramp_shift"],
        "example": {"op": "stamp", "def": "leaf", "x": 8, "y": 8, "angle": 45},
    },
    "load_png": {
        "summary": "Blit an external PNG file (forbidden in `--fresh` mode).",
        "required": ["path"],
        "optional": ["x", "y", "crop", "flip_x", "flip_y"],
        "example": {"op": "load_png", "path": "base.png", "x": 0, "y": 0},
    },
    "mirror_x": {"summary": "Mirror left half of canvas onto right half.", "required": [], "optional": [], "example": {"op": "mirror_x"}},
    "mirror_y": {"summary": "Mirror top half of canvas onto bottom half.", "required": [], "optional": [], "example": {"op": "mirror_y"}},
    "material": {"summary": "Structured native material plane (rock, cobble, soil, leaves, bark, grass, water, cloth, wood, roof).", "required": ["kind"], "optional": ["x", "y", "w", "h", "seed", "color", "colors"], "flexible": True, "example": {"op": "material", "kind": "rock", "x": 0, "y": 0, "w": 32, "h": 32}},
    "building": {"summary": "Top-down 3/4 cozy building generator.", "required": [], "optional": ["x", "y", "w", "h", "roof_style", "wall_color", "roof_color", "timber_frame", "chimney", "smoke", "shadow_opacity"], "flexible": True, "example": {"op": "building", "x": 8, "y": 10, "w": 64, "h": 64}},
    "tilemap": {"summary": "Ortho or 2:1 isometric tilemap composer.", "required": ["map", "rows"], "optional": ["mode", "tile_w", "tile_h", "x", "y"], "flexible": True, "example": {"op": "tilemap", "mode": "ortho", "tile_w": 16, "tile_h": 16, "map": {"G": "grass"}, "rows": ["GG", "GG"]}},
    "autotile": {"summary": "16-tile Wang bitmask autotile atlas.", "required": [], "optional": ["x", "y", "tile_size", "inner", "outer", "lip", "seed"], "flexible": True, "example": {"op": "autotile", "tile_size": 16, "inner": "water", "outer": "grass"}},
    "char_rig": {"summary": "4/8-direction humanoid character rig (16/32/64/128px).", "required": [], "optional": ["x", "y", "size", "dir", "pose", "perspective", "frame", "hat", "shirt", "pants"], "flexible": True, "example": {"op": "char_rig", "size": 32, "dir": "down", "pose": "idle"}},
    "portrait_rig": {"summary": "Bust / Fields-of-Mistria style character portrait generator.", "required": [], "optional": ["x", "y", "width", "height", "style", "preset", "face_dir"], "flexible": True, "example": {"op": "portrait_rig", "width": 64, "height": 80, "face_dir": "front"}},
    "animal_rig": {"summary": "Cozy farm animal rig (chicken, cow, pig, sheep, duck, rabbit).", "required": [], "optional": ["x", "y", "species", "variant", "dir", "pose", "perspective", "frame", "emotes"], "flexible": True, "example": {"op": "animal_rig", "species": "chicken", "dir": "right", "pose": "walk"}},
    "item_rig": {"summary": "Parametric RPG item generator (potion, sword, shield, gem, lantern, etc.).", "required": [], "optional": ["x", "y", "kind", "size", "orientation", "state", "shine"], "flexible": True, "example": {"op": "item_rig", "kind": "potion", "size": 24}},
    "nature_rig": {"summary": "Trees, bushes, rocks, flowers, and 4-stage crops.", "required": [], "optional": ["x", "y", "kind", "variant", "stage", "sway", "ground_base"], "flexible": True, "example": {"op": "nature_rig", "kind": "tree", "variant": "oak"}},
    "ui_rig": {"summary": "Native-dimension pixel UI (panel, bar, button, heart, slot).", "required": [], "optional": ["x", "y", "kind", "theme", "state", "fill", "w", "h"], "flexible": True, "example": {"op": "ui_rig", "kind": "panel", "theme": "wood", "w": 64, "h": 32}},
    "emote": {"summary": "Floating pixel emote bubble (heart, angry, sweat, zzz, exclamation, sick).", "required": [], "optional": ["x", "y", "kind", "frame"], "flexible": True, "example": {"op": "emote", "x": 16, "y": 2, "kind": "heart"}},
    "iso_tile": {"summary": "2:1 isometric diamond ground tile.", "required": ["cx", "cy", "rx", "ry", "color"], "optional": [], "flexible": True, "example": {"op": "iso_tile", "cx": 32, "cy": 32, "rx": 16, "ry": 8, "color": "grass"}},
    "iso_box": {"summary": "2:1 isometric extruded box with bevel and ground shadow.", "required": ["cx", "cy", "rx", "ry", "h"], "optional": ["top", "left", "right", "bevel", "ground_shadow"], "flexible": True, "example": {"op": "iso_box", "cx": 32, "cy": 32, "rx": 12, "ry": 6, "h": 10}},
    "iso_roof": {"summary": "2:1 isometric pyramid or gabled roof.", "required": ["cx", "cy", "rx", "ry", "h"], "optional": ["style", "left", "right", "gable", "eave_shadow", "bevel"], "flexible": True, "example": {"op": "iso_roof", "cx": 32, "cy": 32, "rx": 12, "ry": 6, "h": 8, "style": "pyramid"}},
    "iso_wall_rect": {"summary": "2:1 isometric wall opening (door/window) on left or right face.", "required": ["face", "x", "y"], "optional": ["w", "h", "color", "arch", "recessed", "role"], "flexible": True, "example": {"op": "iso_wall_rect", "face": "left", "x": 24, "y": 36, "w": 4, "h": 6}},
    "iso_structure": {"summary": "Depth-sorted multi-part 2:1 isometric structure with per-pixel Z-buffer.", "required": ["items"], "optional": ["origin_x", "origin_y", "step_x", "step_y", "bevel", "ground_shadow"], "flexible": True, "example": {"op": "iso_structure", "origin_x": 32, "origin_y": 30, "items": []}},
}

# Generator fields are explicit so ignored agent inventions cannot masquerade
# as supported anatomy/material controls. This registry also drives help/lint.
_GENERATOR_FIELDS = {
    "material": "x y w h seed color colors kind",
    "building": "x y w h roof_style variant seed shadow_color wall_color roof_color trim_color foundation_color depth roof_h foundation_h ground_shadow shadow_opacity shadow_dx shadow_dy windows timber_frame door dormer chimney smoke name architecture massing_only",
    "char_rig": "x y size dir pose perspective frame skin hair eye shirt pants shoes hat tool handle shadow_color hair_style outfit trim morphology posture",
    "portrait_rig": "x y width height style preset face_dir dir expression gesture hat scar beard hair_style headband cheek_marks fill_background skin skin_l skin_d hair hair_l hair_d shirt shirt_d garment garment_d accent eye_color hat_color hat_light hat_dark ink beard_color headband_color headband_plate headband_emblem background cheek_mark_color",
    "animal_rig": "x y species variant dir pose frame total_frames perspective body shade deep_shade nest_prop ground_prop emotes shadow_color",
    "item_rig": "x y kind item orientation size shine frame shadow_color color secondary_color glass_color cork_color fill_level state flame_color",
    "nature_rig": "x y kind variant stage sway ground_base frame w h seed color trunk_color accent_color shadow_color foliage_color bark_ramp band_colors ramp fruit bush_ramp shape layout r style growth trunk_only fracture fracture_only deposit",
    "ui_rig": "x y kind component theme state selected color count w h frame_width inner_fill fill value fill_color segmented filled composition",
    "tilemap": "x y tile_w tile_h mode map rows step_x step_y",
    "autotile": "x y tile_size inner outer lip seed",
    "emote": "x y kind frame",
    "iso_tile": "cx cy rx ry color border",
    "iso_box": "cx cy rx ry h top left right bevel ground_shadow door windows window roof",
    "iso_roof": "cx cy rx ry h left right style gable eave_shadow bevel chimney",
    "iso_wall_rect": "face x y w h color arch recessed role",
    "iso_structure": "origin_x origin_y items step_x step_y bevel ground_shadow",
}
for _name, _fields in _GENERATOR_FIELDS.items():
    OP_SPECS[_name]["optional"] = sorted((set(OP_SPECS[_name]["optional"]) | set(_fields.split())) - set(OP_SPECS[_name]["required"]))
    OP_SPECS[_name].pop("flexible", None)

OP_SPECS["nature_rig"]["notes"] = [
    "Optional fracture for kind:rock, native w>=32,h>=32: profile = slab|spire|wedge|block|shard|twin; cuts integer [1,5], angle [-75,75] degrees. Seed controls geometric cuts rather than pixel noise. Inactive legacy controls fail explicitly.",
    "Fracture variants: boulder (bare), ore and mossy (upper-facet exposure). fracture_only:true hides deposits. Ore deposit pattern = vein|network|junction, width [0.03,0.12], seams integer [1,3] <=cuts; junction requires a real >=3-facet intersection and cuts>=2, without seams. Moss deposit coverage [0.1,0.5], slope [-0.5,0.5]. Material controls cannot substitute for mass variety.",
    "Optional growth graph for oak/fruit/sakura: growth.profile = upright|forked|multi_stem|gnarled|leaning|windswept.",
    "growth.lean [-1,1], spread [0.6,1.25], thickness [0.6,1.8], root_span [0.6,1.5]; unknown growth fields are errors.",
    "Growth trees require native w>=32, h>=40. trunk_only:true requires growth and reveals the complete trunk/root structure for review.",
    "The same graph drives trunk geometry and canopy supports. Inspect trunk-only and full renders; profile differences do not certify artistic quality.",
]
OP_SPECS["char_rig"]["notes"] = [
    "Optional morphology for top-down native size>=32 only: body_plan = balanced|stocky|slender|compact|long_legged|broad_shouldered|heavy.",
    "Morphology independently controls head_width, head_height, shoulder_width, waist_width, pelvis_width, torso_length and leg_length. Unknown keys and proportions exceeding headroom fail.",
    "Head_height and torso_length accept [0.7,1.2], leg_length [0.65,1.3], widths [0.65,1.5]. All four views share the same body proportions and ground anchor.",
    "Equipment is moved rigidly and its grip fitted to the pose; it is not stretched by body proportions. Equipment fitting is recorded in anatomy graph metadata.",
    "Optional posture uses lean [-0.15,0.15] and crouch [0,1.5] in canonical 32px coordinates; requires top-down native size>=32 and defaults to balanced morphology when omitted. Feet on the ground line remain fixed; head mass translates rigidly. Set distinct posture values per authored frame for body anticipation and recovery.",
    "Inspect all required directions/actions. Body-plan variety does not certify natural anatomy, acting or commercial finish.",
]
OP_SPECS["building"]["notes"] = [
    "Optional architecture mode requires native w>=64,h>=64: profile = longhouse|l_wing|t_plan|courtyard|stepped|tower.",
    "architecture.rotation = 0|90|180|270; wall_height [0.8,1.2], roof_pitch [0.7,1.3]. Unknown or inactive legacy controls fail explicitly.",
    "massing_only:true requires architecture and removes doors/windows. Compare projected footprint corners, roof ridges and connected masses independently of palette and ornament.",
    "Architecture uses a fixed oblique projection and depth-tested faces; this is not a navigable interior, collision proof or commercial-quality certification.",
]
OP_SPECS["ui_rig"]["notes"] = [
    "Optional composition for panel/button/slot: profile = quiet|brackets|header|sidebar|footer|tab; native w>=32,h>=24 subject to content/cap clearance.",
    "Composition border integer [2,6], padding [2,8], motif = facet|stud|chevron (inactive for quiet), ornament_budget [0,4], content_min positive [width,height]. Unsupported legacy controls fail.",
    "All six states are explicit: normal|hover|pressed|selected|disabled|focus. Protected content remains clear; sparse motifs stay inside fixed corner caps for nine-slice resizing.",
    "Universal manifests export a source-bound UI contract for a single composition per frame. Use uicheck on actual exported pixels; preserved caps do not prove text fit, focus behavior or artistic quality.",
]
OP_SPECS["voxel_model"] = {
    "summary": "Deterministic sparse 3D voxel model with semantic layers, closed-palette ramps, and multi-angle projection.",
    "required": [],
    "optional": [
        "format", "source", "bounds", "pivot", "palette_ref", "ramps", "outline",
        "sockets", "layers", "yaw", "elevation", "oblique", "ppu", "origin_x", "origin_y",
        "smooth", "ao", "thresholds", "lights", "fluids",
    ],
    "example": {
        "op": "voxel_model",
        "bounds": {"w": 16, "d": 16, "h": 16},
        "ramps": [{"name": "stone", "colors": ["#596070", "#828c9e", "#b5bfd1"], "material": "solid"}],
        "layers": [{"id": "body_base", "role": "body", "priority": 0, "voxels": [[0, 0, 0, 2]]}],
        "yaw": 0,
        "elevation": 30,
    },
}



POST_OP_SPECS: dict[str, dict[str, Any]] = {
    "outline": {"required": ["color"], "optional": ["selout", "selout_amount", "auto_pad", "directional_selout", "clean_jaggies"]},
    "recolor_material": {"required": ["material"], "optional": ["target_colors", "reflectance", "recolor_outline"]},
    "drop_shadow": {"required": [], "optional": ["dx", "dy", "color"]},
    "pad": {"required": [], "optional": ["size"]},
    "shade": {"required": [], "optional": ["amount", "hue_shift"]},
    "cleanup": {"required": [], "optional": ["tol", "keep_lone"]},
    "pixel_perfect": {"required": [], "optional": []},
    "rim_light": {"required": [], "optional": ["ramp", "dir", "direction", "steps"]},
    "scale": {"required": ["factor"], "optional": []},
}


def lint_op_fields(op: dict[str, Any]) -> list[str]:
    """Return actionable warnings for unknown/misspelled fields on a drawing op."""
    kind = op.get("op")
    spec = OP_SPECS.get(str(kind))
    if not spec or spec.get("flexible"):
        return []
    allowed = UNIVERSAL_OP_FIELDS | set(spec["required"]) | set(spec["optional"])
    warnings: list[str] = []
    for key in op:
        if key not in allowed:
            match = difflib.get_close_matches(key, sorted(allowed), n=1, cutoff=0.55)
            hint = f"; did you mean {match[0]!r}?" if match else ""
            warnings.append(f"Unknown field {key!r} in op {kind!r}{hint}")
    return warnings


def lint_post_fields(post: dict[str, Any]) -> list[str]:
    """Return actionable warnings for unknown/misspelled fields on a post-processing op."""
    kind = post.get("op")
    spec = POST_OP_SPECS.get(str(kind))
    if not spec:
        return []
    allowed = {"op"} | set(spec["required"]) | set(spec["optional"])
    warnings: list[str] = []
    for key in post:
        if key not in allowed:
            match = difflib.get_close_matches(key, sorted(allowed), n=1, cutoff=0.55)
            hint = f"; did you mean {match[0]!r}?" if match else ""
            warnings.append(f"Unknown field {key!r} in post op {kind!r}{hint}")
    return warnings


def validate_managed_fields(spec: dict[str, Any]) -> None:
    """Reject unknown operation fields throughout a managed source spec."""
    def visit(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ("palette", "palette_ext", "colors", "map", "runtime", "clips"):
                    continue
                if key == "defs" and isinstance(child, dict):
                    for name, definition in child.items():
                        visit(definition, f"{path}.defs[{name}]")
                    continue
                if key in ("ops", "post"):
                    if not isinstance(child, list):
                        raise ValueError(f"{path}.{key} must be an array")
                    for index, operation in enumerate(child):
                        if not isinstance(operation, dict):
                            raise ValueError(f"{path}.{key}[{index}] must be an operation object")
                        registry = POST_OP_SPECS if key == "post" else OP_SPECS
                        if operation.get("op") not in registry:
                            raise ValueError(f"{path}.{key}[{index}]: unknown operation")
                        warnings = lint_post_fields(operation) if key == "post" else lint_op_fields(operation)
                        if warnings:
                            raise ValueError(f"{path}.{key}[{index}]: {'; '.join(warnings)}")
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
    visit(spec, "spec")


def format_op_list() -> str:
    """Return a compact, token-efficient list of all ops, post ops, and palettes."""
    lines = ["# pixelai-tools — Ops & Post-Processing Index", "", "## Drawing Ops (`ops`)"]
    for name, meta in OP_SPECS.items():
        lines.append(f"- `{name}`: {meta['summary']}")
    lines.append("")
    lines.append("## Post-Processing Ops (`post`)")
    lines.append("- " + ", ".join(f"`{k}`" for k in POST_OP_SPECS))
    lines.append("")
    lines.append("## Palettes")
    lines.append("- " + ", ".join(f"`{k}`" for k in list_palettes()))
    lines.append("")
    lines.append("Run `pixelai guide --op <name>` for detailed fields and an example.")
    return "\n".join(lines)


def format_op_guide(op_name: str) -> str:
    """Return focused documentation for a single drawing op or post-processing op."""
    import json

    key = op_name.strip().lower()
    if key in OP_SPECS:
        meta = OP_SPECS[key]
        lines = [
            f"# op: `{key}`",
            meta["summary"],
            f"- Required fields: {', '.join(meta['required']) or 'none'}",
            f"- Optional fields: {', '.join(meta['optional']) or 'none'}",
            f"- Universal flags: {', '.join(sorted(UNIVERSAL_OP_FIELDS - {'op'}))}",
            "",
            "Example:",
            json.dumps(meta["example"], indent=2),
        ]
        lines.extend(["", *meta.get("notes", [])])
        return "\n".join(lines)
    if key in POST_OP_SPECS:
        meta = POST_OP_SPECS[key]
        return "\n".join([
            f"# post op: `{key}`",
            f"- Required fields: {', '.join(meta['required']) or 'none'}",
            f"- Optional fields: {', '.join(meta['optional']) or 'none'}",
        ])
    all_names = sorted(set(OP_SPECS) | set(POST_OP_SPECS))
    match = difflib.get_close_matches(key, all_names, n=3, cutoff=0.5)
    hint = f" Did you mean: {', '.join(match)}?" if match else ""
    raise ValueError(f"Unknown op {op_name!r}.{hint}")


def build_json_schema() -> dict[str, Any]:
    """Build a JSON Schema (draft-07) for PixelAI-Tools declarative JSON specs."""
    op_names = sorted(OP_SPECS)
    post_names = sorted(POST_OP_SPECS)
    palette_names = sorted(list_palettes())
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "PixelAI-Tools Spec",
        "type": "object",
        "required": ["width", "height"],
        "properties": {
            "width": {"type": "integer", "minimum": 1},
            "height": {"type": "integer", "minimum": 1},
            "asset_id": {"type": "string", "minLength": 1},
            "runtime": {"type": "object", "properties": {"regions_from_structure": {"const": "footprints"}},
                        "dependentRequired": {"regions_from_structure": ["derive"]},
                        "anyOf": [{"required": ["pivot", "ground_anchor", "sort_origin"]}, {"required": ["derive"], "properties": {"derive": {"const": "structure"}}}]},
            "palette": {"oneOf": [{"type": "string", "enum": palette_names}, {"type": "object"}]},
            "palette_ext": {"type": "object", "additionalProperties": {"type": "string"}},
            "style": {"type": "string", "enum": ["ext_outline", "lineless"]},
            "style_profile": {"type": "string", "enum": ["cozy_modern", "16bit_cluster", "crisp_retro", "enchanted_hd"]},
            "outline_color": {"type": "string"},
            "auto_pad": {"type": "boolean"},
            "fresh": {"type": "boolean"},
            "material": {"type": "string"},
            "fps": {"type": "integer", "minimum": 1},
            "durations_ms": {"type": "array", "items": {"type": "integer", "minimum": 1}},
            "transitions": {"type": "array", "items": {"type": "object", "required": ["from", "to"], "properties": {"from": {"type": "string"}, "to": {"type": "string"}}}},
            "clips": {"type": "object", "additionalProperties": {"type": "object", "required": ["frames", "loop"], "properties": {
                "frames": {"type": "array", "minItems": 1, "items": {"type": "integer", "minimum": 0}},
                "loop": {"type": "boolean"}, "interruptible": {"type": "boolean"},
                "score": {"type": "object", "additionalProperties": False, "required": ["schema_version", "intent", "beats"], "properties": {
                    "schema_version": {"const": 1}, "intent": {"type": "string", "minLength": 1},
                    "beats": {"type": "array", "minItems": 1, "items": {"type": "object", "additionalProperties": False,
                        "required": ["name", "purpose", "start", "end"], "properties": {
                            "name": {"type": "string", "minLength": 1}, "purpose": {"type": "string", "minLength": 1},
                            "start": {"type": "integer", "minimum": 0}, "end": {"type": "integer", "minimum": 1}}}},
                    "events": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                        "required": ["id", "name", "at_ms"], "properties": {
                            "id": {"type": "string", "minLength": 1}, "name": {"type": "string", "minLength": 1},
                            "at_ms": {"type": "integer", "minimum": 0}, "socket": {"type": "string", "minLength": 1}}}}
                }}
            }}},
            "frame_count": {"type": "integer", "minimum": 1},
            "extends": {"type": "string"},
            "imports": {"type": "array", "items": {"type": "string"}},
            "defs": {"type": "object"},
            "ops": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["op"],
                    "properties": {"op": {"type": "string", "enum": op_names}},
                },
            },
            "post": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["op"],
                    "properties": {"op": {"type": "string", "enum": post_names}},
                },
            },
            "fx": {"type": "array", "items": {"type": "object"}},
            "frames": {"type": "array", "items": {"type": "object"}},
            "keyframes": {"type": "array", "items": {"type": "object"}},
            "layers": {"type": "array", "items": {"type": "object"}},
        },
    }
