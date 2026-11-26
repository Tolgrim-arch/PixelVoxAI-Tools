"""Performance benchmarking utilities for voxel rendering and world simulation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class BenchmarkReport:
    """Collects per-step timing measurements in milliseconds."""

    steps: list[dict[str, Any]] = field(default_factory=list)

    def add(self, name: str, elapsed_ms: float, meta: dict[str, Any] | None = None) -> None:
        entry: dict[str, Any] = {"step": name, "ms": round(elapsed_ms, 3)}
        if meta:
            entry.update(meta)
        self.steps.append(entry)

    @property
    def total_ms(self) -> float:
        return round(sum(s["ms"] for s in self.steps), 3)

    def to_dict(self) -> dict[str, Any]:
        return {"total_ms": self.total_ms, "steps": list(self.steps)}

    def format_text(self) -> str:
        lines = [f"[bench] total={self.total_ms:.3f}ms"]
        for s in self.steps:
            lines.append(f"  - {s['step']}: {s['ms']:.3f}ms")
        return "\n".join(lines)


def measure_step(report: BenchmarkReport, name: str, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Execute `fn(*args, **kwargs)`, record its elapsed time in `report`, and return its result."""
    t0 = time.perf_counter()
    res = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    report.add(name, elapsed_ms)
    return res
