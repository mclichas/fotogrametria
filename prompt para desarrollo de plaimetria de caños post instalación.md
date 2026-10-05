```markdown
# PROMPT REFINADO (CONFORME A ESPECIFICACIÓN SDD Y MATRIZ DE PRUEBAS)

```markdown
# ESPECIFICACIÓN DE DISEÑO DE SOFTWARE (SDD) Y PROMPT DE DESARROLLO: SISTEMA DE METROLOGÍA 3D Y VECTORIZACIÓN CAD DE CAÑERÍAS Y ENTORNO MEDIANTE FOTOGRAMETRÍA Y VIDEO

## 1. INTRODUCCIÓN Y ARQUITECTURA GENERAL DEL SISTEMA (SDD-1.0)

### 1.1 Propósito
Desarrollar una aplicación modular en Python para procesar videos monoculares de ambientes en remodelación, reconstruir la geometría 3D métricamente escalada, aislar la infraestructura de cañerías/artefactos y generar planos CAD (.DXF) y reportes dimensionales (.JSON).

### 1.2 Diagrama de Flujo de Datos (Pipeline Modular)
```
[Video MP4/MOV] ──> (Mod 1: Video Processor) ──> [Frames Seleccionados]
                                                        │
[Objeto Referencia] ──> (Mod 2: Scale Calibrator) ───> [Puntos Ref 2D/3D + Dim Real]
                                                        │
                                                (Mod 3: Reconstruction Engine)
                                                        │
                                                [Nube Densa Arbitraria]
                                                        │
                                                (Mod 4: Scale and Align)
                                                        │
                                                [Nube Densa Métrica (Z=0 Piso)]
                                                        │
                                                (Mod 5: Segmentation Engine)
                                                        │
                                        ┌───────────────┴───────────────┐
                                  [Geometría Entorno]             [Objetos/Caños]
                                 (Paredes/Piso/Techo)             (Cilindros/OBB)
                                        │                               │
                                        └───────────────┬───────────────┘
                                                        │
                                                (Mod 6: Spatial Analyzer)
                                                        │
                                                [Matriz de Distancias Métricas]
                                                        │
                                                (Mod 7: Exporter)
                                                        │
                                        ┌───────────────┴───────────────┐
                                  [floor_plan.dxf]              [metrics_report.json]
```

---

## 2. ESPECIFICACIÓN DETALLADA DE MÓDULOS, CASOS DE PRUEBA Y CRITERIOS DE APROBACIÓN (SDD-2.0)

---

### MÓDULO 1: INGESTA DE VIDEO Y SELECCIÓN DE KEYFRAMES (`modules/video_processor.py`)

#### A. Especificación Funcional e Interfaces
* **Entrada**: Ruta del archivo de video (`str`), `fps_sampling_rate` (`float`, default=2.0), `blur_threshold` (`float`, default=100.0).
* **Salida**: Directorio temporal con imágenes JPG extraídas y archivo `frame_metadata.json`.
* **Lógica / Algoritmo**:
  1. Decodificar video cuadro a cuadro usando `cv2.VideoCapture`.
  2. Muestrear según el intervalo de tiempo (ej. 2 frames por segundo de video).
  3. Calcular la varianza del operador Laplaciano: \\(V = \text{Var}(\nabla^2 I)\\) sobre escala de grises. Si \\(V < \text{blur\_threshold}\\), el cuadro se descarta.
  4. Extraer puntos clave ORB/SIFT y verificar un mínimo de 100 coincidencias con el cuadro anterior para garantizar solapamiento de visión estéreo (>60%).

#### B. Casos de Prueba (Test Cases)
* **TC-MOD1-01 (Prueba Unitaria - Extracción Básica)**:
  * *Entrada*: Video sintético de 10 segundos a 30 FPS (300 frames totales), 100% nítido, movimiento constante.
  * *Resultado Esperado*: Generar exactamente 20 cuadros extraídos a 2 FPS.
* **TC-MOD1-02 (Prueba de Inserción de Ruido - Filtrado de Desenfoque)**:
  * *Entrada*: Video donde el 50% de los cuadros tienen desenfoque de movimiento inducido (varianza Laplaciana < 40).
  * *Resultado Esperado*: Descarte del 100% de los cuadros borrosos. Registro en logs del conteo de cuadros omitidos.
* **TC-MOD1-03 (Prueba de Borde - Video Estático/Sin Solapamiento)**:
  * *Entrada*: Video con salto repentino de cámara (pérdida de continuidad espacial).
  * *Resultado Esperado*: Excepción controlada `InsufficientOverlapError` con aviso al usuario indicando el segundo exacto de la interrupción.

#### C. Criterios de Aprobación (Acceptance Criteria)
1. El módulo debe procesar un video de 1 minuto 1080p en menos de 15 segundos en CPU estándar.
2. Cero falsos positivos en la inclusión de cuadros con varianza Laplaciana < 80.
3. Garantizar un solapamiento espacial mínimo comprobado en la secuencia de imágenes resultante.

---

### MÓDULO 2: CALIBRACIÓN INTERACTIVA DE ESCALA (`modules/scale_calibrator.py`)

#### A. Especificación Funcional e Interfaces
* **Entrada**: Cuadro representativo `frame_001.jpg`, interfaz de usuario (GUI Tkinter/OpenCV).
* **Salida**: Objeto `CalibrationData` que contiene: `bounding_box_2d` \\([x_1, y_1, x_2, y_2]\\), `real_dimension_meters` (`float`), `reference_type` (`"ARUCO"` o `"MANUAL"`).
* **Lógica / Algoritmo**:
  1. Buscar marcadores ArUco (`cv2.aruco`) en el frame. Si se detecta un diccionario conocido y se configura su tamaño, retornar escala automática.
  2. Si no hay ArUco, desplegar la ROI interactiva (`cv2.selectROI` o canvas GUI).
  3. El usuario marca 2 puntos extremos sobre el objeto de referencia (ej. regla de 30 cm o caja de conexión de 10x10 cm) e ingresa el valor en metros mediante un campo de texto.

#### B. Casos de Prueba (Test Cases)
* **TC-MOD2-01 (Prueba Unitaria - Detección ArUco)**:
  * *Entrada*: Imagen con marcador ArUco ID=04 de \\(0.10\text{ m}\\) de lado impreso de forma plana.
  * *Resultado Esperado*: Detección automática de las 4 esquinas sin requerir intervención manual del usuario.
* **TC-MOD2-02 (Prueba Unitaria - Entrada Manual GUI)**:
  * *Entrada*: Selección manual de \\(200\text{ px}\\) en pantalla e ingreso de valor \\(0.50\text{ m}\\).
  * *Resultado Esperado*: Creación válida de estructura `CalibrationData` con razón \\(400\text{ px/m}\\).
* **TC-MOD2-03 (Prueba de Validación de Entrada - Errores de Usuario)**:
  * *Entrada*: Usuario ingresa caracteres no numéricos ("treinta cm") o valor negativo (\\(-0.5\\)).
  * *Resultado Esperado*: Bloqueo de confirmación en GUI y alerta `InvalidDimensionValueError`.

#### C. Criterios de Aprobación
1. Soporte dual comprobado: Detección ArUco automática y fallback a selección manual mediante ROI.
2. Imposibilidad de avanzar en la ejecución del pipeline con valores nulos, negativos o no numéricos.

---

### MÓDULO 3: MOTOR DE RECONSTRUCCIÓN 3D SfM (`modules/reconstruction_engine.py`)

#### A. Especificación Funcional e Interfaces
* **Entrada**: Directorio con imágenes filtradas del Módulo 1.
* **Salida**: Archivo `sparse_cloud.ply`, `dense_cloud.ply`, y matriz de poses de cámaras `cameras.json`.
* **Lógica / Algoritmo**:
  1. Invocar `pycolmap` (o ejecutable `colmap` mediante `subprocess`).
  2. `feature_extractor`: Extracción de descriptores SIFT.
  3. `exhaustive_matcher` o `sequential_matcher`: Coincidencia de pares con restricción de secuencia de video.
  4. `sparse_reconstructor`: Triangulación y optimización por ajuste de haces (*Bundle Adjustment*).
  5. `patch_match_stereo` y `stereo_fusion`: Generación de nube de puntos densa.

#### B. Casos de Prueba (Test Cases)
* **TC-MOD3-01 (Prueba de Integración - SfM Secuencial)**:
  * *Entrada*: Conjunto de 30 imágenes ordenadas con solapamiento > 70%.
  * *Resultado Esperado*: Estimación exitosa de pose para al menos el 90% de los cuadros (>= 27 imágenes alineadas) y generación de `dense_cloud.ply` no vacía.
* **TC-MOD3-02 (Prueba de Inestabilidad - Textura Homogénea)**:
  * *Entrada*: Secuencia de fotos de una pared blanca lisa sin detalles.
  * *Resultado Esperado*: Salida de error manejada `ReconstructionFailureError: Insufficient 3D Features`.

#### C. Criterios de Aprobación
1. La nube densa resultante debe contener más de 500,000 puntos para una escena de habitación estándar (\\(3\text{m} \times 3\text{m}\\)).
2. Tiempo máximo de procesamiento densificado: < 3 minutos para 40 imágenes en hardware de prueba con GPU/CPU habilitada.

---

### MÓDULO 4: TRANSFORMACIÓN MÉTRICA Y ALINEACIÓN GLOBAL (`modules/scale_and_align.py`)

#### A. Especificación Funcional e Interfaces
* **Entrada**: `dense_cloud.ply`, `CalibrationData` (del Módulo 2), `cameras.json`.
* **Salida**: Objeto `open3d.geometry.PointCloud` reescalado y reorientado donde el piso está en el plano \\(Z=0\\).
* **Lógica / Algoritmo**:
  1. Identificar las coordenadas 3D del objeto de referencia usando los datos de las cámaras y triangulación 2D-to-3D.
  2. Calcular distancia euclidiana en el modelo 3D: \\(D_{\text{modelo}} = \|P_a - P_b\|_2\\).
  3. Obtener factor de escala \\(S = \frac{D_{\text{real}}}{D_{\text{modelo}}}\\).
  4. Escalar nube de puntos: \\(P_{\text{escalado}} = P \cdot S\\).
  5. Detectar el plano horizontal dominante con mayor número de inliers mediante RANSAC plano. Su vector normal se define como \\(\vec{n} = (A, B, C)\\).
  6. Calcular matriz de rotación \\(R\\) que alinea \\(\vec{n}\\) con el vector vertical \\(\vec{k} = (0, 0, 1)\\). Aplicar translación \\(T\\) para que la coordenada \\(Z\\) promedio del piso sea exactamente \\(0.00\\).

#### B. Casos de Prueba (Test Cases)
* **TC-MOD4-01 (Prueba Unitaria - Precisión de Escalado)**:
  * *Entrada*: Nube de puntos arbitraria donde un segmento sintético mide 2.0 unidades. Dimensión real ingresada = 1.0 metro.
  * *Resultado Esperado*: Tras la transformación, la distancia euclidiana medida en el modelo escalado debe ser \\(1.0000 \pm 0.001\text{ m}\\).
* **TC-MOD4-02 (Prueba Unitaria - Alineación de Vector Normal de Piso)**:
  * *Entrada*: Nube de puntos con el piso inclinado a 45 grados respecto al eje Z original.
  * *Resultado Esperado*: Tras aplicar la matriz \\(R\\), la normal del plano del piso debe ser \\((0.00, 0.00, 1.00) \pm 0.01\\).

#### C. Criterios de Aprobación
1. Error de desviación de escala \\(< 1\%\\) en objetos de control de prueba.
2. El plano del piso alineado debe coincidir con \\(Z=0\\) con una varianza máxima de residuos en Z \\(< 0.015\text{ m}\\).

---

### MÓDULO 5: SEGMENTACIÓN GEOMÉTRICA Y EXTRACCIÓN DE ELEMENTOS (`modules/segmentation_engine.py`)

#### A. Especificación Funcional e Interfaces
* **Entrada**: Nube métrica alineada (`open3d.geometry.PointCloud`).
* **Salida**: Estructura `ExtractedEntities` conteniendo: `planes` (diccionario de ecuaciones de paredes, piso, techo), `pipes` (lista de modelos cilíndricos), `artifacts` (lista de Bounding Boxes 3D de cajas/artefactos).
* **Lógica / Algoritmo**:
  1. **Planos Estructurales**: Utilizar RANSAC iterativo (`distance_threshold=0.02 m`) para extraer piso (\\(Z \approx 0\\)), techo (\\(Z \approx Z_{\text{max}}\\)) y paredes (normales perpendiculares a Z).
  2. **Filtrado de Entorno**: Sustraer inliers de los planos para obtener la nube residual de infraestructura no plana.
  3. **Limpieza Estadística**: Aplicar `remove_statistical_outlier(nb_neighbors=30, std_ratio=1.5)` sobre la nube residual.
  4. **Clustering y RANSAC Cilíndrico**:
     * Agrupar puntos con **DBSCAN** (`eps=0.04 m`, `min_points=15`).
     * Para cada clúster, estimar normales y aplicar RANSAC de ajuste de cilindro para obtener: Punto de inicio \\(P_1\\), Punto de fin \\(P_2\\), Radio \\(R\\), Vector director \\(\vec{d}\\).
     * Si la desviación cuadrática media (RMSE) del ajuste de cilindro es \\(< 0.008\text{ m}\\), clasificar como `Pipe`; de lo contrario, clasificar como `Artifact` y obtener su Oriented Bounding Box (OBB).

#### B. Casos de Prueba (Test Cases)
* **TC-MOD5-01 (Prueba Unitaria - Segmentación de Planos Ortogonales)**:
  * *Entrada*: Nube sintética con 4 paredes a 90°, 1 piso y 1 techo.
  * *Resultado Esperado*: Identificación y clasificación correcta de los 6 planos principales sin superposición de inliers.
* **TC-MOD5-02 (Prueba Unitaria - Detección Cilíndrica de Cañería)**:
  * *Entrada*: Clúster de puntos en forma de tubo de radio \\(R=0.025\text{ m}\\) (1 pulgada) y longitud \\(1.5\text{ m}\\).
  * *Resultado Esperado*: Estimación del radio \\(R \in [0.023, 0.027]\text{ m}\\) y ajuste de la recta del eje con \\(R^2 > 0.98\\).
* **TC-MOD5-03 (Prueba de Inmunidad al Ruido)**:
  * *Entrada*: Inclusión de 5% de puntos aleatorios dispersos (*outliers*) en la nube residual.
  * *Resultado Esperado*: Filtrado total de los puntos dispersos mediante DBSCAN y remoción estadística; detección imperturbable del caño.

#### C. Criterios de Aprobación
1. Tasa de detección de cañerías visibles (diámetro \\(> 1/2"\\)) \\(\ge 90\%\\).
2. Falso positivo en detección de planos estructurales \\(< 2\%\\).

---

### MÓDULO 6: ANÁLISIS ESPACIAL Y CÓMPUTO DE DISTANCIAS (`modules/spatial_analyzer.py`)

#### A. Especificación Funcional e Interfaces
* **Entrada**: Objeto `ExtractedEntities` del Módulo 5.
* **Salida**: Objeto `SpatialMetricsReport` con vectores de medición ortogonal de cada elemento hacia los límites del ambiente.
* **Lógica / Algoritmo**:
  1. Para cada caño con eje definido por \\(P_1(x_1, y_1, z_1)\\) y \\(P_2(x_2, y_2, z_2)\\):
     * **Distancia al piso (\\(Z=0\\))**: \\(d_{\text{piso\_eje}} = \frac{z_1 + z_2}{2}\\); \\(d_{\text{piso\_libre}} = d_{\text{piso\_eje}} - R\\).
     * **Pendiente**: \\(M (\%) = \frac{|z_2 - z_1|}{\sqrt{(x_2-x_1)^2 + (y_2-y_1)^2}} \times 100\\).
     * **Distancia a Paredes**: Para cada pared con plano \\(Ax + By + Cz + D = 0\\), calcular la distancia punto-plano mínima desde \\(P_1\\) y \\(P_2\\):
       \\[d = \frac{|A x_p + B y_p + C z_p + D|}{\sqrt{A^2 + B^2 + C^2}} - R\\]
  2. Determinar el diámetro comercial aproximado comparando \\(2R\\) con la tabla de normas de tuberías (ANSI/ISO).

#### B. Casos de Prueba (Test Cases)
* **TC-MOD6-01 (Prueba Unitaria - Distancia Paralela)**:
  * *Entrada*: Caño horizontal a \\(Z = 0.50\text{ m}\\), radio \\(R = 0.02\text{ m}\\), plano del piso \\(Z = 0\\).
  * *Resultado Esperado*: \\(d_{\text{piso\_eje}} = 0.500\text{ m}\\); \\(d_{\text{piso\_libre}} = 0.480\text{ m}\\); Pendiente \\(= 0.00\%\\).
* **TC-MOD6-02 (Prueba Unitaria - Caño Inclinado)**:
  * *Entrada*: Caño con \\(P_1=(0,0,0.10)\\), \\(P_2=(1,0,0.15)\\), \\(R=0.01\\).
  * *Resultado Esperado*: Distancia en inicio \\(= 0.09\text{ m}\\), distancia en fin \\(= 0.14\text{ m}\\), pendiente \\(= 5.00\%\\).

#### C. Criterios de Aprobación
1. Tolerancia máxima permitida en el cálculo de distancias ortogonales: \\(\pm 5\text{ mm}\\) respecto a la geometría de la nube ajustada.
2. Formateo de salidas numéricas estrictamente redondeado a 3 decimales (precisión milimétrica).

---

### MÓDULO 7: EXPORTACIÓN Y GENERACIÓN DE ENTREGABLES (`modules/exporter.py`)

#### A. Especificación Funcional e Interfaces
* **Entrada**: `ExtractedEntities`, `SpatialMetricsReport`, ruta de salida.
* **Salida**: Archivo `floor_plan_3d.dxf` (formato DXF R2018) y `metrics_report.json`.
* **Lógica / Algoritmo**:
  1. Instanciar dibujo `ezdxf.new('R2018')`.
  2. Crear capas con colores estándar ACI (*AutoCAD Color Index*):
     * `PAREDES` (Color 7 - Blanco), `PISO_TECHO` (Color 8 - Gris), `CANERIAS` (Color 1 - Rojo), `ARTEFACTOS` (Color 5 - Azul), `ACOTACIONES` (Color 3 - Verde).
  3. Proyectar las intersecciones de paredes para generar el contorno cerrado del piso (Vista en Planta 2D).
  4. Dibujar los caños en 3D como cilindros o líneas de eje con anotaciones de cota (`ezdxf.layouts.Modelspace.add_linear_dim`).
  5. Serializar los datos métricos a un archivo JSON estructurado y validado mediante esquema `pydantic`.

#### B. Casos de Prueba (Test Cases)
* **TC-MOD7-01 (Prueba de Integración - Validez de Archivo DXF)**:
  * *Entrada*: Datos de entrada de prueba con 4 paredes y 2 cañerías.
  * *Resultado Esperado*: Generación de archivo `.dxf` interpretable sin errores ni advertencias de corrupción en AutoCAD / LibreCAD.
* **TC-MOD7-02 (Prueba Unitaria - Validación de Esquema JSON)**:
  * *Entrada*: Reporte de métricas procesado.
  * *Resultado Esperado*: Archivo `metrics_report.json` que pasa la validación contra el esquema Pydantic predefinido sin campos nulos requeridos.

#### C. Criterios de Aprobación
1. El archivo DXF debe abrirse limpiamente en visores CAD estándar mostrando las capas diferenciadas.
2. El archivo JSON debe contener la totalidad de los objetos detectados con sus correspondientes distancias al piso, techo y paredes.

---

## 3. DICCIONARIO DE DATOS Y ESQUEMA JSON DE SALIDA (SDD-3.0)

El módulo 7 debe generar la salida con la siguiente estructura JSON estricta:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "metadata": {
    "timestamp": "2026-10-05T11:00:00Z",
    "video_source": "obras_bano_01.mp4",
    "scale_factor_applied": 0.002315,
    "total_frames_processed": 35
  },
  "environment": {
    "floor_plane": {"A": 0.0, "B": 0.0, "C": 1.0, "D": 0.0},
    "ceiling_height_meters": 2.450,
    "walls_count": 4
  },
  "pipe_infrastructure": [
    {
      "id": "PIPE_001",
      "estimated_nominal_diameter": "1 inch",
      "radius_meters": 0.016,
      "length_meters": 1.250,
      "slope_percentage": 1.50,
      "start_point": {"x": 0.500, "y": 1.200, "z": 0.150},
      "end_point": {"x": 1.750, "y": 1.200, "z": 0.168},
      "distances": {
        "to_floor_clearance_meters": 0.134,
        "to_ceiling_clearance_meters": 2.284,
        "nearest_wall": {
          "wall_id": "WALL_NORTH",
          "clearance_meters": 0.085
        }
      }
    }
  ],
  "artifacts": [
    {
      "id": "BOX_001",
      "type": "ELECTRICAL_JUNCTION_BOX",
      "bounding_box_center": {"x": 0.800, "y": 0.050, "z": 1.100},
      "dimensions_meters": {"dx": 0.120, "dy": 0.120, "dz": 0.080},
      "distances": {
        "to_floor_center_meters": 1.100,
        "nearest_wall": {
          "wall_id": "WALL_EAST",
          "clearance_meters": 0.020
        }
      }
    }
  ]
}
```

---

## 4. MATRIZ GENERAL DE APROBACIÓN DEL SISTEMA (E2E)

| ID Criterio | Descripción del Criterio de Aprobación | Método de Verificación | Umbral de Aceptación |
| :--- | :--- | :--- | :--- |
| **CA-E2E-01** | **Precisión Métrica Global** | Medición manual con cinta métrica láser en obra vs. distancia calculada en software. | Error Relativo \\(< 1.5\%\\) o \\(\le 10\text{ mm}\\) en distancias \\(< 2\text{ m}\\). |
| **CA-E2E-02** | **Aislamiento Geométrico** | Eliminación de puntos correspondientes a paredes, pisos y techos. | \\(> 95\%\\) de la geometría estructural descartada sin eliminar caños. |
| **CA-E2E-03** | **Tiempo de Ejecución** | Tiempo total de procesamiento E2E para video de 1 min. | \\(< 8\text{ minutos}\\) en Intel i7/Ryzen 7 con GPU gama media o CPU 8-core. |
| **CA-E2E-04** | **Compatibilidad CAD** | Importación de `floor_plan_3d.dxf` en AutoCAD / Revit / LibreCAD. | Sin errores de sintaxis; capas de colores y cotas visibles. |
| **CA-E2E-05** | **Robustez a Fallas** | Manejo de videos de mala calidad o sin suficiente solapamiento. | Detención controlada con mensajes de error descriptivos sin *crashes* imprevistos. |

---

## 5. INSTRUCCIONES DE IMPLEMENTACIÓN PARA EL MODELO DE CÓDIGO
Escribe la solución completa en Python cumpliendo estrictamente con la especificación SDD descrita arriba. Crea la estructura de directorios, implementa cada módulo con las firmas y algoritmos detallados, escribe las pruebas unitarias correspondientes usando `pytest` para verificar cada caso de prueba (TC-MOD1 a TC-MOD7) y asegura que todos los criterios de aceptación se cumplan de manera comprobable.
```