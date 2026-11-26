# VoxPix CLI Completion Progress (`PixelVoxAI-Tools`)

Este documento rastrea la implementación de las **5 áreas faltantes** de `andyeswong/voxpix` para completar `pixelvoxAI` como herramienta CLI 100% autónoma.

---

## Bloque 1: Pathfinding 2.5D por Niveles (`pixelai/voxel/paths.py`)
Equivalente a `src/world/paths.ts` y `src/world/levelpaths.ts` en `voxpix`.
- [x] **1.1 Motor de pathfinding 2.5D (`find_path_25d`)**:
  - Calcula la ruta más corta (A*) sobre la superficie caminable de un `VoxelModel` / `VoxelWorld`.
  - Soporta cambios de altura de ±1 vóxel (rampas/escaleras), evita agua profunda o bloques sólidos sin espacio libre arriba (2 vóxeles de altura libre para el agente), y respeta puertas abiertas/cerradas.
- [x] **1.2 Integración con `Agent` y `VoxelWorld` (`pixelai/voxel/sim.py`, `world.py`)**:
  - Método `world.find_path(start, goal)` y `agent.navigate_to(world, goal)` para asignar rutas automáticas a agentes.
- [x] **1.3 Pruebas unitarias** (`tests/test_voxpix_completion.py`).

---

## Bloque 2: Animación de Mundo Vivo y Seguimiento de Cámara (`pixelai world`)
Equivalente a `src/view/follow.ts` y `src/world/live.ts` en `voxpix`.
- [x] **2.1 Seguimiento de cámara (`CameraFollow` / `--follow <agente>`)**:
  - Permite centrar la vista de `pixelai world` dinámicamente en la posición `(x, y)` de un agente/entidad en cada tick.
- [x] **2.2 Exportación animada de mundo (`--gif <salida.gif>`, `--frames N`, `--ms 120`)**:
  - Avanza el mundo frame a frame (agua, olas, partículas, clima, agentes caminando, puertas, ciclo día/noche) y exporta un GIF animado directamente desde `pixelai world`.
- [x] **2.3 Pruebas CLI y unitarias** (`tests/test_voxpix_completion.py`).

---

## Bloque 3: Generador Procedural de Edificios Multi-Piso y Habitaciones (`pixelai/voxel/buildings.py`)
Equivalente a `src/worldgen/floors.ts`, `src/worldgen/rooms.ts`, `src/worldgen/shape.ts` en `voxpix`.
- [x] **3.1 Generador de edificios (`generate_building`)**:
  - Genera edificios de N pisos (`--floors`), con habitaciones interiores divididas por muros, puertas conectadas, ventanas, techo (plano o a dos aguas) y escaleras interiores entre pisos.
  - Soporta temas (`medieval`, `garden`, `neon`, `toxic`) y semilla determinista (`--seed`).
- [x] **3.2 Integración CLI (`pixelai voxel building`)** (`pixelai/voxel/cli_cmds.py`):
  - `pixelai voxel building <salida.json> [--width 16] [--depth 16] [--floors 2] [--theme medieval] [--seed 42]`.
- [x] **3.3 Pruebas unitarias y CLI** (`tests/test_voxpix_completion.py`).

---

## Bloque 4: Olas y Apariencia de Agua (`pixelai/voxel/fluid.py` / `render.py`)
Equivalente a `src/world/waves.ts` y `src/world/waterlook.ts` en `voxpix`.
- [x] **4.1 Simulación de olas periódicas (`apply_water_waves`)**:
  - Calcula altura/fase de ola determinista por tick `(x, y, tick)` y aplica variación sutil de tono/espuma en bordes de agua adyacentes a tierra sólida.
- [x] **4.2 Integración en `VoxelWorld.step()` y renderizado**.
- [x] **4.3 Pruebas unitarias** (`tests/test_voxpix_completion.py`).

---

## Bloque 5: Verificación Estricta de Paleta en `render` (`pixelai/voxel/render.py` / `cli_cmds.py`)
Equivalente a la validación de paleta de `voxpix render` (`docs/linea-de-comandos.md`).
- [x] **5.1 Validador `verify_image_palette(img, palette)`**:
  - Comprueba que todos los píxeles no-fondo de la imagen renderizada pertenezcan exactamente a la paleta del modelo (o reporta colores fuera de paleta).
- [x] **5.2 Flag `--verify-palette` en `pixelai voxel render`**.
- [x] **5.3 Pruebas unitarias y CLI** (`tests/test_voxpix_completion.py`).

---

## Bloque 6: Exportaciones, Pruebas Completas y Sync Git
- [x] Actualizar `pixelai/voxel/__init__.py` con todas las nuevas clases y funciones.
- [x] Ejecutar suite completa de pruebas (`unittest` / `pytest`).
- [x] Commit y push a `pixelvox/main` con trailers `Co-authored-by`.
