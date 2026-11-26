"""Tests for pixelai.voxel.terrain and pixelai.voxel.bench."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pixelai.voxel.bench import BenchmarkReport, measure_step
from pixelai.voxel.terrain import generate_terrain_model


def test_generate_terrain_model_and_cli(tmp_path: Path) -> None:
    model = generate_terrain_model(width=16, depth=16, height=10, seed=99, theme="garden")
    assert len(model.layers[0].voxels) > 0

    out_json = tmp_path / "terrain.json"
    proc = subprocess.run(
        [sys.executable, "-m", "pixelai", "voxel", "terrain", str(out_json), "--size", "16x16x10", "--seed", "99"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out_json.exists() and out_json.stat().st_size > 0


def test_benchmark_report() -> None:
    report = BenchmarkReport()
    res = measure_step(report, "add", lambda a, b: a + b, 2, 3)
    assert res == 5
    assert len(report.steps) == 1
    assert report.total_ms >= 0.0
    assert "[bench]" in report.format_text()
