# Contratos de datos y parámetros

Referencia técnica del pipeline. Complementa la SDD; donde el SDD y este documento
difieren, manda `AGENTS.md` (decisiones) y esta tabla de parámetros.

---

## Modelos compartidos

```python
class SourceRef(BaseModel):
    """Una fuente de entrada: video continuo o juego de fotos."""
    source_id: str            # slug derivado del nombre, p.ej. "20261005-081530_bano_principal"
    path: Path                # archivo original, read-only
    source_index: int         # posición en la lista de fuentes
    kind: Literal["video", "image_dir", "image"]
    sampling_mode: Literal["time", "frame"]

class FrameRecord(BaseModel):
    """Un frame extraído, listo para M3."""
    source_id: str
    source_index: int
    sequence_index: int       # posición global tras ordenar
    frame_index: int          # índice dentro de la fuente
    timestamp_s: float        # segundos desde el inicio de la fuente
    path: Path                # jpg en work/<source_id>/frames/
    sharpness: float          # varianza del Laplaciano
    n_matches_prev: int       # matches ORB contra el frame anterior
```

### Nombres internos de frame

```text
{source_id}_{sequence_index:04d}_{frame_index:06d}.jpg
20261005-081530_bano_principal_0000_000000.jpg
```

`sequence_index` adelante garantiza orden lexicográfico correcto.

---

## M1 `video_processor.py`

```python
class IngestConfig(BaseModel):
    fps_sampling_rate: float = 2.0      # frames por segundo de video (SDD)
    blur_threshold: float = 100.0       # varianza Laplaciano mínima (SDD)
    min_matches_overlap: int = 100      # matches ORB vs frame previo (SDD)
    orb_n_features: int = 2000          # nº máximo de features ORB por frame
    orb_scale_factor: float = 1.2       # pirámide de ORB
    max_consecutive_failures: int = 5   # cortes de cámara tolerados antes de abortar
    jpeg_quality: int = 95
    frame_name_pattern: str = "{source_id}_{sequence_index:04d}_{frame_index:06d}.jpg"
```

Algoritmo:
1. `cv2.VideoCapture` decodifica cuadro a cuadro.
2. Muestreo por tiempo: extraer si `t - ultima_t >= 1/fps_sampling_rate`.
3. `cv2.Laplacian(gray, cv2.CV_64F)` → `Var`. Si `Var < blur_threshold`, descartar
   y anotar el motivo en `frame_metadata.json`.
4. ORB + `BFMatcher.knnMatch` contra el frame anterior aceptado (no el índice anterior
   crudo). Si `matches < min_matches_overlap`, es un corte de cámara: no es error fatal
   por sí solo; se registra y se sigue. Si supera `max_consecutive_failures` seguidos,
   lanzar `InsufficientOverlapError` con el timestamp exacto.

Salida: `work/<source_id>/frames/*.jpg` + `work/<source_id>/frame_metadata.json`.

```json
{
  "source_id": "20261005-081530_bano_principal",
  "fps": 30.0,
  "frames_extracted": 120,
  "frames_rejected_blur": 14,
  "overlap_breaks": [{ "sequence_index": 42, "timestamp_s": 21.4 }],
  "frames": [ { "...": "FrameRecord serializado" } ]
}
```

> Nota: `frame_metadata.json` es el índice de referencia para resolver
> `CalibrationData.image_id` en M4.

---

## M2 `scale_calibrator.py`

```python
class BBox2D(BaseModel):
    x1: float; y1: float; x2: float; y2: float   # píxeles

    @property
    def width_px(self) -> float: ...
    @property
    def height_px(self) -> float: ...

class CalibrationData(BaseModel):
    image_id: str                    # nombre del frame (vincula con cameras.json)
    bbox_2d: BBox2D
    width_meters: float              # ancho real, > 0
    height_meters: float             # alto real, > 0
    reference_type: Literal["MANUAL", "ARUCO"] = "MANUAL"
    n_corners: int = 4

    @property
    def px_per_m_x(self) -> float: ...   # width_px / width_meters
    @property
    def px_per_m_y(self) -> float: ...
    @property
    def distortion(self) -> float: ...   # |x - y| / max(x, y)
```

Validación: `width_meters > 0`, `height_meters > 0`, `width_px > 0`, `height_px > 0`.
Cualquier violations → `InvalidDimensionValueError` con el valor recibido en el mensaje.

Interacción GUI: canvas con rectángulo arrastrable, campos de ancho y alto,
previsualización en vivo de `px/m` por eje y de la distorsión.

---

## M3 `reconstruction_engine.py`

```python
class ReconstructionConfig(BaseModel):
    colmap_executable: Path = Path("colmap")     # o ruta absoluta configurada
    use_gpu: bool = True
    quality: Literal["low", "medium", "high", "extreme"] = "high"
    matcher: Literal["sequential", "exhaustive"] = "sequential"   # video → sequential
    overlap_window: int = 10         # ventana de emparejamiento para sequential
    min_num_tri_points: int = 50
    dense_fusion: bool = True
```

Etapas (progreso reportable a la GUI, 1:1 con este orden):

```text
1 feature_extractor       → work/<source_id>/colmap/database.db
2 image_sequencer         → sólo con matcher="sequential"
3 <sequential|exhaustive>_matcher
4 mapper  (triangulación + bundle adjustment) → cameras.bin/images.bin/points3D.bin
5 image_undistorter       → reconstructor filaments + makert model
6 patch_match_stereo      → si use_gpu o CPU suficiente
7 stereo_fusion           → dense_cloud.ply
```

Errores: menos del 50 % de imágenes registradas → `ReconstructionFailureError` con el
conteo real y la causa probable (textura insuficiente, overlap, o luz).

Contrato de salida que consume M4:

```text
work/<source_id>/colmap/sparse/0/       images.bin, cameras.bin, points3D.bin
work/<source_id>/colmap/dense/fused.ply
```

---

## M4 `scale_and_align.py`

```python
class ScaleAlignConfig(BaseModel):
    floor_ransac_threshold: float = 0.02     # metros (TODO T5: definir con datos reales)
    floor_ransac_iterations: int = 1000
    floor_min_inliers_ratio: float = 0.15    # un plano con menos inliers no es el piso
    max_distortion_warning: float = 0.05     # 5 % de diferencia px/m entre ejes
    reference_triangulation_tolerance_px: float = 2.0
```

Secuencia:
1. Localizar los 4 vértices de `bbox_2d` en la imagen del `image_id` (refinar con
   ORB + homografía si hace falta; tolerancia `reference_triangulation_tolerance_px`).
2. Triangular contra la cámara de esa imagen usando el modelo de COLMAP.
3. `S = D_real / D_modelo` con la diagonal del rectángulo como distancia de control
   (más estable que un solo lado).
4. `P_escalado = P · S`.
5. RANSAC de plano dominante → normal `(A,B,C)`.
6. Rotación `R` que alinea la normal con `(0,0,1)`; traslación `T` para que el Z medio
   del piso sea exactamente 0.

Salida: `PointCloud` escalada + `floor_plane` (`A,B,C,D` normalizado) + `scale_factor`.

---

## M5 `segmentation_engine.py`

```python
class SegmentationConfig(BaseModel):
    plane_ransac_threshold: float = 0.02   # metros (SDD)
    plane_ransac_iterations: int = 1000
    ceiling_tolerance: float = 0.15        # metros sobre Z_max para declarar techo
    statistical_nb_neighbors: int = 30     # SDD
    statistical_std_ratio: float = 1.5     # SDD
    dbscan_eps: float = 0.04               # metros (TODO T6)
    dbscan_min_points: int = 15            # SDD
    cylinder_min_radius: float = 0.008     # 1/2 pulgada ~ 15 mm diámetro
    cylinder_max_radius: float = 0.075     # ~6 pulgadas
    cylinder_rmse_max: float = 0.008       # metros, clasifica Pipe vs Artifact
    cylinder_ransac_iterations: int = 500
    cylinder_min_inliers_ratio: float = 0.6
```

Clasificación de clúster:
- **Pipe**: ajuste cilíndrico con `rmse <= cylinder_rmse_max` y radio en rango.
- **Artifact**: si no, OBB con `open3d.geometry` sobre los puntos del clúster.

```python
class Pipe(BaseModel):
    id: str
    start_point: Point3D
    end_point: Point3D
    radius_meters: float
    direction: Vector3D       # unitario
    rmse: float
    n_inliers: int

class Artifact(BaseModel):
    id: str
    center: Point3D
    dimensions_meters: Vector3D   # dx, dy, dz del OBB
    rotation: Matrix3x3           # orientation del OBB
    n_points: int

class ExtractedEntities(BaseModel):
    floor_plane: PlaneEquation
    walls: list[PlaneEquation]
    ceiling: PlaneEquation | None
    pipes: list[Pipe]
    artifacts: list[Artifact]
```

---

## M6 `spatial_analyzer.py`

```python
class SpatialAnalyzerConfig(BaseModel):
    nominal_diameter_tolerance: float = 0.002   # metros, para clasificar comercial
    slope_alert_percent: float = 2.0            # slope > esto es drenaje, no instalación
```

Por cada `Pipe`:

```text
d_piso_eje    = (z1 + z2) / 2
d_piso_libre  = d_piso_eje − R
d_techo_libre = Z_techo − max(z1, z2) + R
pendiente_%   = |z2 − z1| / sqrt((x2−x1)² + (y2−y1)²) × 100
d_pared       = |A·x + B·y + C·z + D| / sqrt(A²+B²+C²) − R     # por cada extremo
```

Los nombres de pared (`WALL_NORTH`, etc.) se derivan de la normal del plano de pared
proyectada en el plano XY, no de un orden arbitrario de la lista.

Tabla de diámetros comerciales: TODO T8 (ANSI / ISO / ambos).

---

## M7 `exporter.py`

**V1 (D12): salida en SVG**, escrito a mano (XML, sin dependencia). **V2: DXF** con
`ezdxf.new("R2018")`, `doc.header["$INSUNITS"] = 6` (metros).

Capas con color fijo (mismas en SVG y DXF, con `svg:stroke`/`fill` o ACI):

| Capa | color/ACI | Contenido |
| :--- | :--- | :--- |
| `PAREDES` | 7 | contorno de paredes, planta + alzado |
| `PISO_TECHO` | 8 | contorno del piso, altura de techo |
| `CANERIAS` | 1 | ejes de caños (3D) |
| `ARTEFACTOS` | 5 | OBB de artefactos |
| `ACOTACIONES` | 3 | cotas lineales y radio |

SVG (V1): `<svg width/height>` en **mm**, coordenadas en mm, cotas como texto vectorial
(`<text>`), cada capa en un `<g id="...">`. Planta 2D: proyectar a `Z=0`. Cañas: línea de
eje en `CANERIAS` + cota de radio en `ACOTACIONES` (TODO T7: definir representación final).

---

## Esquema JSON de salida (`metrics_report.json`)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "metadata": {
    "timestamp": "2026-10-05T11:00:00Z",
    "video_source": "obras_bano_01.mp4",
    "source_ids": ["20261005-081530_bano_principal"],
    "scale_factor_applied": 0.002315,
    "total_frames_processed": 35,
    "tool_version": "0.1.0"
  },
  "environment": {
    "floor_plane": { "A": 0.0, "B": 0.0, "C": 1.0, "D": 0.0 },
    "ceiling_height_meters": 2.45,
    "walls_count": 4
  },
  "pipe_infrastructure": [
    {
      "id": "PIPE_001",
      "estimated_nominal_diameter": "1 inch",
      "radius_meters": 0.016,
      "length_meters": 1.25,
      "slope_percentage": 1.5,
      "start_point": { "x": 0.5, "y": 1.2, "z": 0.15 },
      "end_point": { "x": 1.75, "y": 1.2, "z": 0.168 },
      "distances": {
        "to_floor_axis_meters": 0.159,
        "to_floor_clearance_meters": 0.134,
        "to_ceiling_clearance_meters": 2.284,
        "nearest_wall": { "wall_id": "WALL_NORTH", "clearance_meters": 0.085 }
      }
    }
  ],
  "artifacts": [
    {
      "id": "BOX_001",
      "type": "ELECTRICAL_JUNCTION_BOX",
      "bounding_box_center": { "x": 0.8, "y": 0.05, "z": 1.1 },
      "dimensions_meters": { "dx": 0.12, "dy": 0.12, "dz": 0.08 },
      "distances": {
        "to_floor_center_meters": 1.1,
        "nearest_wall": { "wall_id": "WALL_EAST", "clearance_meters": 0.02 }
      }
    }
  ]
}
```

Validar con Pydantic v2. `distances.to_floor_axis_meters` se separó de
`to_floor_clearance_meters` para no perder información al redondear a 3 decimales (R5).

### Cada cota lleva su incertidumbre (D9, §11.1 bis)

El producto **no compara contra los planos del proyecto**: documenta cómo quedó la obra.
Por eso la incertidumbre es el único mecanismo de honestidad del documento. Sin ella,
una estimación aparece con la misma autoridad que una medición con cinta métrica.

Forma del dato en `SpatialMetricsReport`, a definir en T17:

```python
class Measurement(BaseModel):
    value_meters: float
    uncertainty_meters: float      # 1 sigma o intervalo, documentar cuál en T17
    reliable: bool                 # uncertainty_meters <= 0.010 (D7)
```

Reglas de contrato:

* **Ninguna cota se serializa sin `uncertainty_meters`.** Un campo `float` desnudo en
  `distances` es un error de revisión, no un detalle de estilo.
* `reliable=False` **no oculta la cota**: se reporta igual, marcada. Ocultarla deja un
  hueco sin explicar en el documento.
* El `metadata` del reporte incluye un veredicto global de calidad. Si la mayoría de las
  cotas son `unreliable`, el veredicto dice que hay que repetir la captura.
* La identificación del relevamiento (obra, ambiente, fecha, responsable — T21) va en
  `metadata`, para que el documento sea rastreable meses después.

Esto agrega campos a los modelos de M6 y a la capa `ACOTACIONES` del plano (SVG V1 / DXF
V2). Resolver T17 antes de escribir M6/M7.