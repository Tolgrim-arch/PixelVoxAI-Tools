"""Data-driven voxel material definitions ported from VoxPix (MIT).

Each material is a row of orthogonal properties queried by lighting, fluid,
and collision subsystems without type-branching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VoxelMaterial:
    """Physical and optical properties of a voxel ramp material."""

    name: str
    light: float = 0.0       # Light transmission per voxel [0.0 = opaque, 1.0 = clear]
    backlit: float = 0.0     # Backlit face luminance boost [0.0..1.0]
    bed: bool = True         # Whether fluids treat this material as floor/wall
    blocks: bool = True      # Whether entities/collision are blocked
    emissive: bool = False   # Self-illuminated (bypasses world darkening)
    reflect: float = 0.0     # Reserved specular/reflection factor [0.0..1.0]

    def with_overrides(self, props: dict[str, Any] | None = None) -> VoxelMaterial:
        """Return a copy with bounded property overrides applied."""
        if not props:
            return self
        light = float(props.get("light", self.light))
        backlit = float(props.get("backlit", self.backlit))
        reflect = float(props.get("reflect", self.reflect))
        if not (0.0 <= light <= 1.0):
            raise ValueError(f"Material 'light' must be in [0, 1], got {light}")
        if not (0.0 <= backlit <= 1.0):
            raise ValueError(f"Material 'backlit' must be in [0, 1], got {backlit}")
        if not (0.0 <= reflect <= 1.0):
            raise ValueError(f"Material 'reflect' must be in [0, 1], got {reflect}")
        return VoxelMaterial(
            name=self.name,
            light=light,
            backlit=backlit,
            bed=bool(props.get("bed", self.bed)),
            blocks=bool(props.get("blocks", self.blocks)),
            emissive=bool(props.get("emissive", self.emissive)),
            reflect=reflect,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "light": self.light,
            "backlit": self.backlit,
            "bed": self.bed,
            "blocks": self.blocks,
            "emissive": self.emissive,
            "reflect": self.reflect,
        }


MATERIALS: dict[str, VoxelMaterial] = {
    "solid": VoxelMaterial(name="solid", light=0.0, backlit=0.0, bed=True, blocks=True, emissive=False, reflect=0.0),
    "foliage": VoxelMaterial(name="foliage", light=0.5, backlit=0.25, bed=False, blocks=False, emissive=False, reflect=0.0),
    "bush": VoxelMaterial(name="bush", light=0.5, backlit=0.25, bed=False, blocks=True, emissive=False, reflect=0.0),
    "glass": VoxelMaterial(name="glass", light=0.85, backlit=0.0, bed=True, blocks=True, emissive=False, reflect=0.0),
    "metal": VoxelMaterial(name="metal", light=0.0, backlit=0.0, bed=True, blocks=True, emissive=False, reflect=0.6),
    "emissive": VoxelMaterial(name="emissive", light=0.0, backlit=0.0, bed=True, blocks=True, emissive=True, reflect=0.0),
}

# Spanish aliases from VoxPix for smooth interop
_ALIASES: dict[str, str] = {
    "solido": "solid",
    "follaje": "foliage",
    "arbusto": "bush",
    "vidrio": "glass",
}


def resolve_material(
    name: str | None = None,
    props: dict[str, Any] | None = None,
    emissive: bool = False,
) -> VoxelMaterial:
    """Resolve a material preset by name with optional property overrides."""
    key = (name or "solid").strip().lower()
    key = _ALIASES.get(key, key)
    if key not in MATERIALS:
        available = ", ".join(sorted(MATERIALS))
        raise ValueError(f"Unknown voxel material {name!r}. Available: {available}")
    mat = MATERIALS[key]
    merged_props = dict(props) if props else {}
    if emissive:
        merged_props["emissive"] = True
    return mat.with_overrides(merged_props)
