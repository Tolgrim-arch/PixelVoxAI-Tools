"""Advanced 2.5D world simulation: destructible blocks (mining), A* pathfinding, and agents."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pixelai.voxel.world import VoxelWorld


def _surface_z(world: VoxelWorld, x: int, y: int) -> int | None:
    """Return the highest solid Z at (x, y) in the world model, or None if empty."""
    best: int | None = None
    for layer in world.model.layers:
        for (vx, vy, vz) in layer.voxels:
            if vx == x and vy == y:
                if best is None or vz > best:
                    best = vz
    return best


def mine_block(world: VoxelWorld, x: int, y: int, z: int) -> bool:
    """Destroy a voxel at (x, y, z) in the world and spawn debris particles."""
    removed = False
    for layer in world.model.layers:
        if layer.get(x, y, z) != 0:
            layer.set(x, y, z, 0)
            removed = True
    if removed:
        from pixelai.voxel.world import Particle

        for _ in range(3):
            world.particles.append(
                Particle(x=float(x), y=float(y), z=float(z) + 0.5, vz=0.4, life=6)
            )
    return removed


def find_path(
    world: VoxelWorld,
    start: tuple[int, int],
    goal: tuple[int, int],
    max_step_up: int = 1,
    max_nodes: int = 2048,
) -> list[tuple[int, int]]:
    """2.5D A* pathfinding over the world's surface heightmap."""
    if start == goal:
        return [start]
    start_z = _surface_z(world, start[0], start[1])
    goal_z = _surface_z(world, goal[0], goal[1])
    if start_z is None or goal_z is None:
        return []

    def h(a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    open_heap: list[tuple[int, int, tuple[int, int]]] = [(h(start, goal), 0, start)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], int] = {start: 0}
    visited = 0

    while open_heap and visited < max_nodes:
        _, cur_g, cur = heapq.heappop(open_heap)
        visited += 1
        if cur == goal:
            path = [cur]
            while cur in came_from:
                cur = came_from[cur]
                path.append(cur)
            path.reverse()
            return path

        cur_z = _surface_z(world, cur[0], cur[1])
        if cur_z is None:
            continue

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (cur[0] + dx, cur[1] + dy)
            nb_z = _surface_z(world, nb[0], nb[1])
            if nb_z is None:
                continue
            if abs(nb_z - cur_z) > max_step_up:
                continue
            tentative_g = cur_g + 1
            if tentative_g < g_score.get(nb, 10**9):
                came_from[nb] = cur
                g_score[nb] = tentative_g
                heapq.heappush(open_heap, (tentative_g + h(nb, goal), tentative_g, nb))
    return []


@dataclass(slots=True)
class WorldAgent:
    """Autonomous entity that follows a 2.5D path in VoxelWorld."""

    x: int
    y: int
    z: int = 0
    path: list[tuple[int, int]] = field(default_factory=list)

    def step(self, world: VoxelWorld) -> bool:
        """Advance one step along `path`. Returns True if moved."""
        if not self.path:
            return False
        nx, ny = self.path.pop(0)
        nz = _surface_z(world, nx, ny)
        self.x = nx
        self.y = ny
        if nz is not None:
            self.z = nz + 1
        return True
