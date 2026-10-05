---
name: planimetria-pipeline
description: Convenciones, contratos de datos y criterios de aceptación del pipeline de planimetría 3D de cañerías por fotogrametría. Usar al crear o modificar cualquier archivo bajo modules/, al diseñar modelos Pydantic o dataclasses del pipeline, al integrar COLMAP u Open3D, o al tocar la GUI Tkinter del asistente paso a paso. También al revisar tolerancias, esquema JSON o capas DXF.
license: MIT
metadata:
  project: planimetria-canerias
  stack: python,opencv,colmap,open3d,ezdxf,pydantic
---

# Pipeline de Planimetría 3D de Cañerías

## Orden de lectura

1. Leer `AGENTS.md` en la raíz. Es la fuente de verdad de decisiones.
2. Leer la sección de la SDD del módulo a tocar en
   `prompt para desarrollo de plaimetria de caños post instalación.md`.

## Reglas que no se negocian

* Software **100 % libre**. Nada de SIFT ni `opencv-contrib-python`. Detector: ORB.
* **Nunca** escribir archivos generados en `data/`. Entradas en `data/ingest/`,
  intermedios en `work/`, entregables en `outputs/`.
* Los originales de `data/ingest/` son intocables: no renombrar, no mover.
* Todo parámetro de algoritmo con default explícito en la config. Cero magic numbers.
* Proyecciones en metros, `Z=0` en el piso. Píxel → metro sólo en M4.
* Validación de entrada con Pydantic; errores de dominio en `modules/errors.py`.
* Redondear **sólo al formatear**, nunca durante el cálculo.
* Nada de strings hardcodeados al usuario: todos los mensajes de la GUI en español,
  sleídos de un módulo central.

## V1 vs. V2 — no confundir

La V1 procesa **un solo video continuo**. Pero los modelos de datos ya llevan estos
campos aunque la V1 no los use:

```text
source_id      # id único de la fuente
source_index   # posición en la lista de fuentes
frame_index    # índice dentro de la fuente
timestamp_s    # segundos desde el inicio de la fuente
sampling_mode  # "time" (video) | "frame" (fotos)
sequence_index # posición global en la secuencia ordenada
```

Nunca escribir una función cuya firma asuma un único archivo. Recibir
`Sequence[SourceRef]` o `Sequence[Path]` siempre.

## Módulos y contratos

| Módulo | Archivo | Entrada | Salida |
| :--- | :--- | :--- | :--- |
| M1 Ingesta | `modules/video_processor.py` | `Sequence[Path]`, `IngestConfig` | dir de frames + `frame_metadata.json` |
| M2 Escala | `modules/scale_calibrator.py` | frame + interacción GUI | `CalibrationData` |
| M3 SfM | `modules/reconstruction_engine.py` | dir de frames | `dense_cloud.ply`, `cameras.json` |
| M4 Métrica | `modules/scale_and_align.py` | nube + `CalibrationData` + poses | nube escalada, piso en `Z=0` |
| M5 Segmentación | `modules/segmentation_engine.py` | nube métrica | `ExtractedEntities` |
| M6 Cotas | `modules/spatial_analyzer.py` | `ExtractedEntities` | `SpatialMetricsReport` |
| M7 Export | `modules/exporter.py` | entidades + reporte | `.dxf` + `.json` |

## Puntos donde se rompe el código en la práctica

### COLMAP no es una llamada de Python

Va detrás de una interfaz inyectable, porque los tests no pueden depender del binario:

```python
class ColmapBackend(Protocol):
    def run(self, stage: str, args: Sequence[str]) -> None: ...

class SubprocessColmapBackend:      # producción: colmap.exe
    ...

class FakeColmapBackend:            # tests: escribe fixtures, no ejecuta nada
    ...
```

El constructor recibe el backend; el default es `SubprocessColmapBackend`.
El `search_path` de COLMAP se resuelve desde config, no hardcodeado.

### M2 depende del nombre de archivo, no del índice

El usuario marca un rectángulo sobre **un frame de la secuencia**. La reconstrucción
en M3 reordena y renombra imágenes internamente. El vínculo se rompe si se guarda un
índice. Guardar siempre `CalibrationData.image_id` = **nombre del frame** y resolver
la correspondencia con `cameras.json` por nombre en M4. Si no aparece, lanzar
`CalibrationError` con mensaje accionable.

### Escala manual: ancho **y** alto

`width_meters` y `height_meters` no son redundantes. Sirven para validar que el
rectángulo marcado no está distorsionado:

```text
px_per_m_x = bbox.width_px  / width_meters
px_per_m_y = bbox.height_px / height_meters
distortion = abs(px_per_m_x - px_per_m_y) / max(px_per_m_x, px_per_m_y)
```

Si `distortion` supera el umbral, avisar al usuario antes de aceptar. Usar la media
de ambos ejes como factor de escala único.

### M4: piso con RANSAC, no con el percentil Z

La nube no está orientada. El plano del piso es el plano dominante con más inliers;
su normal se alinea con `(0,0,1)` y se translada el Z para que la media del piso sea 0.
El umbral RANSAC está sin definir (TODO T5) → configurable, nunca constante.

### M5: no hay cilindro RANSAC en Open3D

Open3D trae RANSAC de planos y OBB, **no** de cilindros. El ajuste cilíndrico es
código propio: hipótesis aleatorias + `scipy.optimize.least_squares`, con
`rmse < umbral` como criterio de clasificación Pipe vs Artifact. DBSCAN viene de
`scikit-learn`, no de Open3D.

Orden correcto: planos → restar inliers → limpieza estadística → DBSCAN → cilindro
por clúster → clasificar.

### M6: distancia a plano de caño es punto-plano menos radio

```text
d = |A·x + B·y + C·z + D| / sqrt(A²+B²+C²) − R
```

La pendiente es siempre en %, sobre la proyección horizontal, no sobre la longitud 3D.

### M7: DXF es metres, con capas fijas

`$INSUNITS = 6` (metros). Capas con color ACI fijo:
`PAREDES` 7, `PISO_TECHO` 8, `CANERIAS` 1, `ARTEFACTOS` 5, `ACOTACIONES` 3.
No inventar capas nuevas sin pedirlas.

## GUI

Una sola ventana Tkinter con wizard de 8 pasos (§11 de AGENTS.md). Reglas:

* Cada paso sólo habilita el siguiente cuando el actual es válido.
* Los trabajos pesados corren en hilo; la GUI se actualiza vía `after()`.
  Nunca llamar a COLMAP ni a Open3D en el hilo principal.
* El progreso se reporta por una cola de mensajes, no por variables compartidas.
* El estado se persiste en `work/<source_id>/session.json`; el pipeline es resumible.

## Antes de dar por terminado un módulo

- [ ] Sus TC del SDD pasan (`TC-MODn-xx`).
- [ ] `pytest -q` verde.
- [ ] `ruff check .` y `ruff format --check .` limpios.
- [ ] Docstrings con unidades en todo parámetro numérico (`# metros`, `# m/s`, `# segundos`).
- [ ] Mensajes de error en español y accionables.
- [ ] AGENTS.md actualizado si cambió una decisión o apareció un TODO nuevo.

## Motor de reconstrucción: leer antes de tocar M3 o M4

COLMAP **no está confirmado**. Se evalúa MoGe-2 (MIT, geometría métrica monocular) porque
la máquina de trabajo no tiene GPU NVIDIA y la densificación de COLMAP no llega a los
umbrales del SDD.

Si el motor termina siendo MoGe-2, el contrato de M3 del SDD queda obsoleto: no hay
`cameras.json`, cada frame devuelve su propio point map en coordenadas de cámara, y la
escala pasa de "escalar la nube al final" a "corregir el sesgo por frame".

Ver AGENTS.md §6 y los TODOs T2/T3 antes de escribir M3, M4 o sus tests.

## Referencias

- Contratos de datos, parámetros por módulo y valores por defecto: [contracts.md](contracts.md)
- Esquema JSON de salida y capas DXF: [contracts.md](contracts.md) (secciones finales)
- Decisiones, licencias y TODOs: `AGENTS.md` §4, §5, §13
- Evaluación del motor de reconstrucción: `AGENTS.md` §6