# VoxPix Parity Progress (`PixelVoxAI-Tools`)

Este documento registra el progreso completo de la implementación de las funciones de `andyeswong/voxpix` en `PixelVoxAI-Tools` para convertirlo en una herramienta CLI 100% completa.

---

## Fase 1: Paletas Externas (`.hex` / `.gpl` Lospec) y Escena `sample` Integrada
- [x] **1.1 Importador de paletas externas (`pixelai/voxel/palettes_io.py`)**:
  - Parseo de archivos `.hex` (Lospec) y `.gpl` (GIMP Palette).
  - Presets integrados de comunidad (`pico8`, `endesga32`, `aap64`, `medieval`) convertibles a `VoxelPalette` con rampas por giro de tono (`ramp_from_color`).
  - Validación de colores de salida contra la paleta activa (`verify_palette_colors`).
- [x] **1.2 Escena `sample` integrada (`pixelai/voxel/samples.py`)**:
  - Modelo medieval de muestra (`sample` / `medieval`) listo para usar desde CLI sin JSON previo: terreno, torre, casa, río, puente, árboles y luces emisivas.
  - Presets adicionales (`torch`, `tree`, `house`) para pruebas rápidas.
- [x] **1.3 Pruebas unitarias** (`tests/test_voxel_palettes_samples.py`).

---

## Fase 2: Subcomandos CLI Directos para Voxel (`pixelai voxel ...`)
- [x] **2.1 `pixelai voxel render <modelo.json|sample> <salida.png>`**:
  - Flags: `--yaw`, `--elev`, `--scale`, `--turn N` (tira horizontal de N ángulos), `--size WxH` (auto-encuadre si se omite), `--origin x,y`, `--outline outer|none`, `--bg #rrggbb`, `--lights`, `--ambient`, `--palette <archivo.hex|.gpl|preset>`, `--verify-palette`.
- [x] **2.2 `pixelai voxel turntable <modelo.json|sample> <salida.gif>`**:
  - GIF giratorio 360° con `--frames`, `--scale`, `--elev`, `--ms`, `--lights`, `--ambient`, `--outline`, `--bg`.
- [x] **2.3 `pixelai voxel palette`**:
  - Listar presets (`--list`), importar `.hex`/`.gpl` a JSON de paleta `VoxelPalette` con rampas generadas.
- [x] **2.4 Pruebas CLI** (`tests/test_voxel_voxpix_parity.py`).

---

## Fase 3: Puente Bidireccional `pxl` (`.px.js`)
- [x] **3.1 Exportador e Importador (`pixelai/voxel/pxl_bridge.py`)**:
  - `export_pxl(model, ...)`: exporta un `VoxelModel` a `.px.js` ya sea por ángulos (`--turn N`) o por capas de altura (`--stack <prefijo>`, generando `<prefijo>_zNN` vistas desde arriba con norte arriba). Incluye directivas `// voxpix: outline #rrggbb` y `// voxpix: emissive <rampas>`.
  - `import_pxl(source_text, ...)`: importa un `.px.js` leyendo directivas `// voxpix:`, paleta y sprites (`--stack`, `--plane front|top --z N`, o `-` para solo paleta).
- [x] **3.2 Subcomandos CLI**:
  - `pixelai voxel export-pxl <modelo.json|sample> <salida.px.js> [--turn N | --stack prefijo] [--name nombre]`
  - `pixelai voxel import-pxl <arte.px.js> <sprite|-> <modelo.json> [--stack prefijo] [--plane front|top] [--z N] [--outline #rrggbb]`
- [x] **3.3 Pruebas unitarias y CLI** (`tests/test_voxel_voxpix_parity.py`).

---

## Fase 4: Simulación de Fluidos 3D y Agua Superficial
- [x] **4.1 Motor de fluidos ampliado (`pixelai/voxel/fluid.py`)**:
  - `pour_fluid`: verter fluido desde un punto con propagación por gravedad y derrame lateral determinista.
  - `tap_fluid`: simular un grifo continuo durante N ticks.
  - `fill_to_level` / `fill_basin`: llenar una cuenca hasta una altura `water_level_z`.
  - `ShallowWaterSim`: simulación de agua superficial 2D con `disturb`, `step` y `water_surface_shade`.
- [x] **4.2 Pruebas unitarias** (`tests/test_voxel_voxpix_parity.py` y `tests/test_voxel_lighting_fluid.py`).

---

## Fase 5: Iluminación Avanzada, Ciclo Día/Noche, Lightmap y Clima
- [x] **5.1 Ciclo día/noche (`pixelai/voxel/daycycle.py`)**:
  - `evaluate_day_cycle(hour)`: calcula dirección del sol, intensidad, nivel ambiental, fase (`dawn`, `day`, `dusk`, `night`) y color del cielo.
- [x] **5.2 Lightmap horneado (`pixelai/voxel/lightmap.py`)**:
  - `BakedLightmap` y `bake_lightmap`: pre-calcula y almacena la contribución de luz (sol + luces puntuales + vóxeles emisivos con oclusión) para consulta O(1).
- [x] **5.3 Clima y precipitación (`pixelai/voxel/weather.py`)**:
  - `apply_weather_overlay`: lluvia, nieve y niebla deterministas con soporte de `tick`.
- [x] **5.4 Pruebas unitarias** (`tests/test_voxel_voxpix_parity.py`).

---

## Fase 6: Motor de Mundos 2.5D Procedurales (`pixelai/voxel/worldgen.py` y `world.py`) + CLI `pixelai world`
- [x] **6.1 Generador procedural por receta y semilla (`pixelai/voxel/worldgen.py`)**:
  - Receta JSON (`WorldRecipe`): `generator` (`terrain`, `rooms`, `courtyard`, `labyrinth`), `seed`, `size`, `theme` (`medieval`, `garden`, `neon`, `toxic`, `office`), `colors`, `columns`, `vegetation`, `lights`, `weather`, `hour`.
- [x] **6.2 Simulación de mundo y corte de sección (`pixelai/voxel/world.py`)**:
  - `VoxelWorld`: simulación por `ticks`, `Door`, `Floater`, `Particle`, `sway_offset`, `ShallowWaterSim`, `section_cut`, `bake`, `info`, y `render`.
- [x] **6.3 Subcomando CLI `pixelai world`**:
  - `pixelai world <receta.json|theme> <salida.png|-> [--at x,y] [--size WxH] [--ticks N] [--scale S] [--whole] [--lights yes|no] [--hour H] [--weather none|rain|snow|fog] [--section-z Z] [--bake] [--info info.json]`
- [x] **6.4 Pruebas unitarias y CLI** (`tests/test_voxel_voxpix_parity.py`).

---

## Fase 7: Integración Final, Verificación Completa y Sync Git
- [x] Actualizar exportaciones en `pixelai/voxel/__init__.py` y documentación `--help`.
- [x] Ejecutar suite completa de pruebas (`python3 -m pytest tests/test_voxel*.py` → 25 passed).
- [x] Commit final y push a `origin/main` con trailers `Co-authored-by`.
