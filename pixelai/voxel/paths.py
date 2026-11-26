"""2.5D A* pathfinding across walkable voxel surfaces, ramps, and doors."""
from __future__ import annotations

import heapq
from typing import Iterable

from .model import VoxelModel


def _surface_z(flat: dict[tuple[int, int, int], int], size: tuple[int, int, int], x: int, y: int) -> int | None:
    """Return the walkable Z height (one above the highest solid voxel) at (x, y), or None."""
    w, d, h = size
    if not (0 <= x < w and 0 <= y < d):
        return None
    for z in range(h - 1, -1, -1):
        if (x, y, z) in flat:
            walk_z = z + 1
            if walk_z < h and (x, y, walk_z) not in flat:
                return walk_z
            return None
    return None


def find_path_25d(
    model: VoxelModel,
    start: tuple[int, int, int],
    goal: tuple[int, int, int],
    *,
    blocked: Iterable[tuple[int, int, int]] = (),
    max_step_up: int = 1,
    max_step_down: int = 1,
    allow_diagonal: bool = False,
) -> list[tuple[int, int, int]]:
    """Find a shortest 2.5D path from start to goal on walkable voxel surfaces.

    Each step moves to an adjacent (x, y) whose surface Z differs by at most
    `max_step_up` / `max_step_down` and is not in `blocked`.
    Returns a list of (x, y, z) coordinates including start and goal, or [] if unreachable.
    """
    sx, sy, sz = int(start[0]), int(start[1]), int(start[2])
    gx, gy, gz = int(goal[0]), int(goal[1]), int(goal[2])
    if (sx, sy, sz) == (gx, gy, gz):
        return [(sx, sy, sz)]

    blocked_set = {(int(bx), int(by), int(bz)) for bx, by, bz in blocked}
    if (gx, gy, gz) in blocked_set:
        return []

    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if allow_diagonal:
        dirs.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])

    def heuristic(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])

    open_heap: list[tuple[float, int, tuple[int, int, int]]] = []
    counter = 0
    heapq.heappush(open_heap, (heuristic((sx, sy, sz), (gx, gy, gz)), counter, (sx, sy, sz)))
    came_from: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    g_score: dict[tuple[int, int, int], float] = {(sx, sy, sz): 0.0}

    flat = model.flatten()
    size = model.bounds

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current[0] == gx and current[1] == gy and abs(current[2] - gz) <= max_step_up:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        cx, cy, cz = current
        for dx, dy in dirs:
            nx, ny = cx + dx, cy + dy
            nz = _surface_z(flat, size, nx, ny)
            if nz is None:
                continue
            dz = nz - cz
            if dz > max_step_up or -dz > max_step_down:
                continue
            nxt = (nx, ny, nz)
            if nxt in blocked_set:
                continue
            step_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
            if dz != 0:
                step_cost += 0.25
            tentative_g = g_score[current] + step_cost
            if tentative_g < g_score.get(nxt, float("inf")):
                came_from[nxt] = current
                g_score[nxt] = tentative_g
                counter += 1
                f = tentative_g + heuristic(nxt, (gx, gy, gz))
                heapq.heappush(open_heap, (f, counter, nxt))

    return []
