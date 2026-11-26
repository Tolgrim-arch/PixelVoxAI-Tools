# VoxPix Final Parity Progress (`PixelVoxAI-Tools`)

Este documento rastrea la implementación de las **7 áreas restantes** de `andyeswong/voxpix` para que `pixelvoxAI` sea una herramienta CLI 100% completa.

---

## Bloque 1: Exponer `--mine` y `--bench` en `pixelai world`
- [x] **1.1 Flag `--mine x,y,z` en `pixelai world`** (`pixelai/voxel/cli_cmds.py`):
  - Permite minar/destruir bloques en el mundo desde la CLI (acepta múltiples `--mine`), invocando `mine_block(world, x, y, z)` de `pixelai/voxel/sim.py` antes de avanzar los ticks y renderizar.
- [x] **1.2 Flag `--bench` en `pixelai world`** (`pixelai/voxel/cli_cmds.py`):
  - Mide y reporta tiempos en ms de generación de mundo, minado, horneado de lightmap, simulación de ticks/agua y renderizado usando `BenchmarkReport` de `pixelai/voxel/bench.py`.
- [x] **1.3 Pruebas CLI** (`tests/test_voxel_final_parity.py`).

---

## Bloque 2: Persistencia de Mundos (`--save` / `--load`)
Equivalente a `src/world/save.ts` en `voxpix`.
- [x] **2.1 Serialización completa de `VoxelWorld`** (`pixelai/voxel/world.py`):
  - `VoxelWorld.to_dict()` y `VoxelWorld.from_dict(data)` (y `save_world(path)` / `load_world(path)`): guarda receta, semilla, tick actual, hora, clima, modelo/vóxeles modificados, puertas, flotadores, partículas, estado de agua superficial y agentes.
- [x] **2.2 Flags `--save <world.json>` y `--load <world.json>` en `pixelai world`** (`pixelai/voxel/cli_cmds.py`):
  - Permite cargar un mundo guardado, avanzar ticks o minar, y volver a guardarlo o renderizarlo.
- [x] **2.3 Pruebas unitarias y CLI** (`tests/test_voxel_final_parity.py`).

---

## Bloque 3: Regiones Infinitas / Streaming y Autotiling (`pixelai/voxel/regions.py`)
Equivalente a `src/world/regiongen.ts`, `src/terrain/regions.ts`, `src/terrain/autotile.ts`, `src/terrain/waterTiles.ts` en `voxpix`.
- [x] **3.1 Motor de regiones y autotiling** (`pixelai/voxel/regions.py`):
  - `autotile_mask(grid, x, y, predicate)`: calcula máscara de 4/8 vecinos para bordes de terreno y agua (`water_tile_edges`).
  - `RegionManager(seed, chunk_size=16, theme='medieval')`: genera chunks bajo demanda (`get_or_generate_region(rx, ry)`) de forma determinista y los ensambla en un `VoxelModel` alrededor de una coordenada central (`build_window_model(cx, cy, radius)`).
- [x] **3.2 Integración CLI (`pixelai voxel region`)** (`pixelai/voxel/cli_cmds.py`):
  - Subcomando `pixelai voxel region <salida.json> [--center x,y] [--radius 1] [--chunk-size 16] [--seed 42] [--theme medieval|garden|neon|toxic]`.
- [x] **3.3 Pruebas unitarias y CLI** (`tests/test_voxel_final_parity.py`).

---

## Bloque 4: Física de Caída y Aplastamiento (`pixelai/voxel/physics.py`)
Equivalente a `src/world/fall.ts` y `src/world/crush.ts` en `voxpix`.
- [x] **4.1 Motor de física de bloques** (`pixelai/voxel/physics.py`):
  - `step_falling_blocks(model, anchored_colors=None, ground_z=0)`: detecta vóxeles sin soporte inferior (opcionalmente filtrando bloques flotantes/anclados) y los hace caer 1 nivel por tick de forma determinista.
  - `detect_crush(model, falling_coords, entities)`: detecta si un bloque en caída impacta sobre una entidad/agente y retorna eventos de aplastamiento.
- [x] **4.2 Integración en `VoxelWorld.step()` y flag `--gravity` en `pixelai world`**.
- [x] **4.3 Pruebas unitarias** (`tests/test_voxel_final_parity.py`).

---

## Bloque 5: Animación con Rig 3D Articulado (`pixelai/voxel/rig.py`)
Equivalente a `src/anim/rig.ts` y `src/anim/walk.ts` en `voxpix`.
- [x] **5.1 Sistema de Rig 3D** (`pixelai/voxel/rig.py`):
  - `RigPart(name, voxels, pivot, offset)` y `VoxelRig(parts, palette)`: permite definir personajes articulados (cabeza, torso, brazo_izq, brazo_der, pierna_izq, pierna_der, item_mano).
  - `pose_rig(rig, angles)` y `generate_rig_walk_frames(rig, frames=4)` / `generate_rig_idle_frames(rig, frames=4)`: rota/desplaza cada parte alrededor de su pivote y compone un `VoxelModel` por cuadro.
  - `default_humanoid_rig(palette)`: rig humanoide de muestra listo para usar desde CLI.
- [x] **5.2 Integración CLI (`pixelai voxel rig`)** (`pixelai/voxel/cli_cmds.py`):
  - `pixelai voxel rig <rig.json|humanoid> <salida.png|salida.gif> [--cycle walk|idle] [--frames 4] [--scale 4] [--ms 120]`.
- [x] **5.3 Pruebas unitarias y CLI** (`tests/test_voxel_final_parity.py`).

---

## Bloque 6: Generador Modular de Piezas y Follaje (`pixelai/voxel/foliage.py`)
Equivalente a `src/core/foliage.ts` y `src/samples/pieces.ts` en `voxpix`.
- [x] **6.1 Generador de follaje y piezas** (`pixelai/voxel/foliage.py`):
  - `generate_foliage(kind='oak'|'pine'|'bush'|'flower_patch', seed=42, scale=1)`: genera árboles, arbustos y parches de flores con variación orgánica determinista.
  - `generate_piece(kind='wall'|'pillar'|'arch'|'stairs'|'bridge', width=8, depth=8, height=10, theme='medieval')`: genera piezas arquitectónicas modulares listas para ensamblar.
- [x] **6.2 Integración CLI (`pixelai voxel foliage` y `pixelai voxel piece`)** (`pixelai/voxel/cli_cmds.py`).
- [x] **6.3 Pruebas unitarias y CLI** (`tests/test_voxel_final_parity.py`).

---

## Bloque 7: Soporte de `vox` Global en `import-pxl` (`pixelai/voxel/pxl_bridge.py`)
Equivalente a `src/pxl/voxmap.ts` en `voxpix`.
- [x] **7.1 Parser de mapa `vox` en `.px.js`** (`pixelai/voxel/pxl_bridge.py`):
  - Soporte para directivas/bloques `vox.box(...)`, `vox.set(...)`, `vox.fill(...)` y `vox.cylinder(...)` dentro de `.px.js` al importar con `import_pxl` / `pixelai voxel import-pxl`.
- [x] **7.2 Pruebas unitarias** (`tests/test_voxel_final_parity.py`).

---

## Bloque 8: Exportaciones, Pruebas Completas y Sync Git
- [x] Actualizar `pixelai/voxel/__init__.py` con todas las nuevas clases y funciones.
- [x] Ejecutar suite completa de pruebas (`pytest tests/test_voxel*.py`).
- [x] Commit final y push a `origin/main` con trailers `Co-authored-by`.
