"""2.5D voxel world runtime: tick simulation, doors, falling blocks, floaters, section cut, baking, and rendering."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from pixelai.canvas import Canvas
from pixelai.color import RGBA, parse_color
from pixelai.voxel.camera import VoxelCamera
from pixelai.voxel.daycycle import evaluate_day_cycle
from pixelai.voxel.fluid import ShallowWaterSim
from pixelai.voxel.lightmap import BakedLightmap, bake_lightmap
from pixelai.voxel.lighting import extract_emissive_lights
from pixelai.voxel.model import Coord3, VoxelLayer, VoxelModel
from pixelai.voxel.render import render_voxel_model
from pixelai.voxel.weather import apply_weather_overlay
from pixelai.voxel.worldgen import WorldRecipe, generate_world_model


@dataclass(slots=True)
class Door:
    coord: Coord3
    is_open: bool = False


@dataclass(slots=True)
class Floater:
    x: int
    y: int
    base_z: int
    offset_z: float = 0.0


@dataclass(slots=True)
class Particle:
    x: float
    y: float
    z: float
    vz: float = 0.15
    life: int = 10


@dataclass(slots=True)
class VoxelWorld:
    """Simulated 2.5D voxel world built from a WorldRecipe."""

    recipe: WorldRecipe
    model: VoxelModel
    meta: dict[str, Any] = field(default_factory=dict)
    tick: int = 0
    doors: list[Door] = field(default_factory=list)
    floaters: list[Floater] = field(default_factory=list)
    particles: list[Particle] = field(default_factory=list)
    water_sim: ShallowWaterSim | None = None
    lightmap: BakedLightmap | None = None

    @classmethod
    def from_recipe(cls, recipe: WorldRecipe) -> VoxelWorld:
        model, meta = generate_world_model(recipe)
        doors = [Door(coord=c) for c in meta.get("doors", [])]
        water_coords = meta.get("water_coords", [])
        floaters = [Floater(x=c[0], y=c[1], base_z=c[2]) for c in water_coords[:3]]
        water_sim = ShallowWaterSim(width=recipe.width, height=recipe.depth)
        if water_coords:
            water_sim.disturb(recipe.width // 2, recipe.depth // 2, 0.8)
        return cls(
            recipe=recipe,
            model=model,
            meta=meta,
            doors=doors,
            floaters=floaters,
            water_sim=water_sim,
        )

    def sway_offset(self, x: int, y: int) -> int:
        """Deterministic wind sway offset (-1, 0, +1) for vegetation at (x, y)."""
        val = math.sin(self.tick * 0.25 + x * 0.4 + y * 0.3)
        if val > 0.6:
            return 1
        if val < -0.6:
            return -1
        return 0

    def step(self, ticks: int = 1) -> None:
        """Advance world simulation deterministically by `ticks` steps."""
        for _ in range(max(0, ticks)):
            self.tick += 1
            if self.water_sim is not None:
                if self.tick % 10 == 0:
                    self.water_sim.disturb(self.recipe.width // 2, self.recipe.depth // 2, 0.4)
                self.water_sim.step(1)
                hx = self.recipe.width // 2
                hy = self.recipe.depth // 2
                for fl in self.floaters:
                    fl.offset_z = self.water_sim.height_at(fl.x + hx, fl.y + hy)
            # Advance particles
            next_particles: list[Particle] = []
            for p in self.particles:
                p.z += p.vz
                p.life -= 1
                if p.life > 0:
                    next_particles.append(p)
            self.particles = next_particles

    def section_cut(
        self,
        *,
        max_z: int | None = None,
        max_x: int | None = None,
        max_y: int | None = None,
    ) -> VoxelModel:
        """Return a cutaway copy of the world model clipped by max_z / max_x / max_y."""
        cut = VoxelModel(
            palette=self.model.palette,
            bounds=self.model.bounds,
            pivot=self.model.pivot,
            sockets=dict(self.model.sockets),
        )
        for src in self.model.layers:
            dst = VoxelLayer(
                id=src.id,
                role=src.role,
                priority=src.priority,
                visible=src.visible,
                locked=False,
            )
            for (x, y, z), val in src.voxels.items():
                if max_z is not None and z > max_z:
                    continue
                if max_x is not None and x > max_x:
                    continue
                if max_y is not None and y > max_y:
                    continue
                dst.voxels[(x, y, z)] = val
            dst.locked = src.locked
            cut.add_layer(dst)
        return cut

    def bake(self) -> BakedLightmap:
        """Bake the 3D lightmap for the current world state."""
        hour = self.recipe.hour if self.recipe.hour is not None else 12.0
        self.lightmap = bake_lightmap(self.model, hour=hour, include_emissive=True)
        return self.lightmap

    def info(self) -> dict[str, Any]:
        """Return JSON-serializable world summary (matching VoxPix `--info`)."""
        return {
            "theme": self.recipe.theme,
            "generator": self.recipe.generator,
            "seed": self.recipe.seed,
            "size": [self.recipe.width, self.recipe.depth, self.recipe.height],
            "tick": self.tick,
            "hour": self.recipe.hour,
            "weather": self.recipe.weather,
            "voxels": len(self.model.flatten()),
            "columns": len(self.meta.get("columns", [])),
            "furniture": len(self.meta.get("furniture", [])),
            "lights": len(self.meta.get("lights", [])),
            "vegetation": len(self.meta.get("vegetation", [])),
            "doors": len(self.doors),
            "ramps": [r.name for r in self.model.palette.ramps],
            "spawn": list(self.meta.get("spawn", (0, 0, 1))),
        }

    def render(
        self,
        *,
        width: int = 192,
        height: int = 128,
        at: tuple[int, int] | None = None,
        whole: bool = False,
        yaw: float = 35.0,
        elevation: float = 32.0,
        use_lights: bool = True,
        hour: float | None = None,
        weather: str | None = None,
        section_z: int | None = None,
        bg: str | RGBA | None = None,
        outline_mode: str = "outer",
    ) -> Canvas:
        """Render the world to a 2D pixel-art Canvas."""
        target_model = self.section_cut(max_z=section_z) if section_z is not None else self.model
        eff_hour = hour if hour is not None else (self.recipe.hour if self.recipe.hour is not None else 12.0)
        eff_weather = weather if weather is not None else (self.recipe.weather or "none")
        day = evaluate_day_cycle(eff_hour)

        ppu = 2 if whole else 3
        if at is not None:
            cam = VoxelCamera(yaw=yaw, elevation=elevation, ppu=ppu)
            target_model = VoxelModel(
                palette=target_model.palette,
                layers=target_model.layers,
                bounds=target_model.bounds,
                pivot=(int(at[0]), int(at[1]), 0),
                sockets=target_model.sockets,
            )
        else:
            cam = VoxelCamera(yaw=yaw, elevation=elevation, ppu=ppu)

        lights = extract_emissive_lights(target_model) if use_lights else None
        res = render_voxel_model(
            target_model,
            width=width,
            height=height,
            camera=cam,
            lights=lights,
            sun_shadow=use_lights and day.sun_intensity > 0.15,
            ambient_dark=use_lights and day.ambient_dark,
        )
        canvas = res.canvas

        bg_rgba: RGBA | None = None
        if isinstance(bg, str):
            bg_rgba = parse_color(bg)
        elif bg is not None:
            bg_rgba = bg
        else:
            bg_rgba = day.sky_color

        if bg_rgba is not None:
            for py in range(canvas.height):
                for px in range(canvas.width):
                    if canvas.get_pixel(px, py)[3] == 0:
                        canvas.set_pixel(px, py, bg_rgba)

        apply_weather_overlay(canvas, eff_weather, tick=self.tick, seed=self.recipe.seed)
        return canvas
