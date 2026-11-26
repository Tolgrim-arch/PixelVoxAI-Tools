# VoxPix Complete Parity Progress (`PixelVoxAI-Tools`)

Este documento rastrea la implementación de las **5 áreas faltantes** de `andyeswong/voxpix` para que `pixelvoxAI` sea una herramienta CLI 100% completa.

---

## Bloque 1: API/CLI de Edición Programática de Modelos (`pixelai/voxel/editor.py` + `pixelai voxel edit`)
Equivalente a `src/agent` (`window.voxpix`) en `voxpix`.
- [x] **1.1 Motor de edición (`pixelai/voxel/editor.py`)**:
  - `VoxelEditor(model)` con historial `undo()` / `redo()` basado en snapshots deterministas.
  - Primitivas: `paint(x, y, z, color)`, `erase(x, y, z)`, `repaint(x, y, z, color)`, `box(x0, y0, z0, x1, y1, z1, color, hollow=False)`, `flood_fill(x, y, z, color, max_voxels=...)`, `mirror(axis='x'|'y'|'z')`, `add_light(x, y, z, color, radius, intensity)`, `resize(w, d, h)` (hasta 256×256×256), `eyedropper(x, y, z)`.
  - Integración con fluidos: `pour(x, y, z, color, steps)`, `tap(x, y, z, color, ticks)`, `fill_level(x, y, z, color, level_z)`.
  - `apply_operations(model, ops)` para ejecutar lotes de operaciones desde JSON/CLI.
- [x] **1.2 Subcomando CLI `pixelai voxel edit`**:
  - `pixelai voxel edit <modelo.json|sample> <salida.json> [--ops ops.json | --op '{"type":"box",...}']` con `--help` completo.
- [x] **1.3 Pruebas unitarias y CLI** (`tests/test_voxel_editor.py`).

---

## Bloque 2: Animación de Personajes y Walk Cycles (`pixelai/voxel/anim.py` + `pixelai voxel animate`)
Equivalente a `src/anim` y `scripts/maia-walk.ts` en `voxpix`.
- [x] **2.1 Motor de animación (`pixelai/voxel/anim.py`)**:
  - `generate_walk_frames(model, frames=4, stride=2, bob=1)`: genera cuadros de animación procedural (oscilación vertical *bob*, balanceo de extremidades/cuerpo por fase) manteniendo la paleta intacta.
  - `generate_idle_frames(model, frames=4, bob=1)`: respiración/flotación sutil.
  - `export_animation_sheet(...)` y `export_animation_gif(...)`.
- [x] **2.2 Subcomando CLI `pixelai voxel animate`**:
  - `pixelai voxel animate <modelo.json|sample> <salida.png|salida.gif> [--cycle walk|idle] [--frames 4] [--scale 4] [--ms 120] [--yaw 0] [--elev 30]`.
- [x] **2.3 Pruebas unitarias y CLI** (`tests/test_voxel_anim.py`).

---

## Bloque 3: Simulación Avanzada de Mundo (`pixelai/voxel/sim.py` + `pixelai world`)
Equivalente a `src/sim` en `voxpix`.
- [x] **3.1 Motor de simulación (`pixelai/voxel/sim.py`)**:
  - `mine_block(world, x, y, z)`: bloques destructibles en partida (remueve vóxel, genera partículas de escombro y actualiza estado).
  - `find_path(world, start, goal, max_step_up=1)`: pathfinding A* 2.5D sobre el terreno/niveles del mundo.
  - `WorldAgent`: entidad con posición, objetivo y movimiento paso a paso en `VoxelWorld.step()`.
- [x] **3.2 Integración en `pixelai/voxel/world.py` y CLI `pixelai world`**:
  - Soporte de acciones `--mine x,y,z` y agentes con ruta en `VoxelWorld`.
- [x] **3.3 Pruebas unitarias** (`tests/test_voxel_sim.py`).

---

## Bloque 4: Generador de Terreno Independiente (`pixelai/voxel/terrain.py` + `pixelai voxel terrain`)
Equivalente a `src/terrain` en `voxpix`.
- [x] **4.1 Generador de terreno (`pixelai/voxel/terrain.py`)**:
  - `generate_terrain_model(width, depth, height, seed=42, theme='medieval', river=True, trees=True, path=True)`: genera un `VoxelModel` independiente con mapa de altura determinista, río/lago, camino, y árboles paramétricos.
- [x] **4.2 Subcomando CLI `pixelai voxel terrain`**:
  - `pixelai voxel terrain <salida.json> [--size 48x48x32] [--seed 42] [--theme medieval|garden|neon|toxic] [--no-river] [--no-trees] [--no-path]`.
- [x] **4.3 Pruebas unitarias y CLI** (`tests/test_voxel_terrain.py`).

---

## Bloque 5: Diagnóstico y Benchmarks CLI (`pixelai/voxel/bench.py` + `--bench`)
Equivalente a `scripts/bench-*.ts` en `voxpix`.
- [x] **5.1 Utilidades de benchmark (`pixelai/voxel/bench.py`)**:
  - `measure_step(name, fn)` y `BenchmarkReport` con tiempos en ms, conteo de vóxeles/píxeles y salida JSON o texto.
- [x] **5.2 Integración CLI (`--bench`)**:
  - Flag `--bench` en `pixelai voxel render` y `pixelai world` para reportar tiempos de carga, horneado de lightmap, simulación de agua/ticks y renderizado.
- [x] **5.3 Pruebas unitarias y CLI** (`tests/test_voxel_bench.py`).

---

## Bloque 6: Integración Final, Exportaciones y Sync Git
- [x] Actualizar `pixelai/voxel/__init__.py` con todas las nuevas clases y funciones.
- [x] Ejecutar suite completa: `python3 -m pytest tests/test_voxel*.py`.
- [x] Commit final y push a `origin/main` con trailers `Co-authored-by`.
