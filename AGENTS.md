# AGENTS.md — Sistema de Planimetría 3D y Vectorización CAD de Cañerías

Memoria del proyecto. Leer este archivo antes de tocar código.
Especificación funcional de origen: `prompt para desarrollo de plaimetria de caños post instalación.md` (SDD 1.0–3.0 + matriz de pruebas).
Repositorio: https://github.com/mclichas/fotogrametria

---

## 1. Propósito

Aplicación modular en Python que procesa video/fotografías de ambientes en remodelación,
reconstruye la geometría 3D métricamente escalada, aísla cañerías y artefactos, y exporta
planos CAD (`.dxf`) y reportes dimensionales (`.json`).

Salida principal: plano de cañerías post instalación con cotas métricas confiables
(error relativo < 1.5 % o ≤ 10 mm en distancias < 2 m).

---

## 2. Estado actual

| Aspecto | Estado |
| :--- | :--- |
| Especificación (SDD) | Completa, en `prompt para desarrollo de plaimetria de caños post instalación.md` |
| Decisiones de arquitectura | Definidas (ver §4) |
| Motor de reconstrucción | **Por decidir** — ver §6 |
| Código | **No iniciado** |
| Entorno objetivo | Windows, Python 3.12 (aún no creado) |
| Hardware | Intel i7-10610U, 4 núcleos, 15.6 GB RAM, **GPU Intel integrada, sin NVIDIA** |
| Disco libre | **~17.7 GB** — restricción activa (R11) |
| COLMAP | No instalado |
| Git | Instalado en la máquina. Repo remoto existe; **local sin inicializar** (T9) |

### 2.1 Hardware de la máquina de trabajo

Restricción determinante para la arquitectura. Sin GPU NVIDIA, `patch_match_stereo` de COLMAP
no es viable, y el criterio del SDD de > 500,000 puntos de nube densa en < 3 min es inalcanzable
aquí. Cualquier criterio de aceptación que dependa de densidad o tiempo debe medirse en esta
máquina antes de asumirlo.

### 2.2 Repositorio

* Remoto: https://github.com/mclichas/fotogrametria (owner `mclichas`)
* Local: aún no inicializado. Al hacerlo, `origin` apunta a esa URL.

---

## 3. Alcance de la V1

**V1 = un único video continuo.**

Las estructuras de datos **deben** soportar desde el inicio el caso general
(varios videos, y mezcla de videos + fotografías), aunque la V1 solo lo ejecute
con un video. No se debe diseñar una API de un solo archivo.

### 3.1 Ingesta admitida (diseño) vs. ejecutada (V1)

| Tipo de fuente | V1 | Soporte en modelo de datos |
| :--- | :--- | :--- |
| Video continuo (`.mp4`, `.mov`, `.avi`) | Sí | Completo |
| Varios videos | No (V2) | Completo |
| Fotos sueltas / mix video+fotos | No (V2) | Completo |

Campos que deben existir ya en los modelos aunque la V1 no los use:
`source_id`, `source_index`, `frame_index`, `timestamp_s`, `sampling_mode`
(`"time"` para video, `"frame"` para fotos), `sequence_index`.

---

## 4. Decisiones tomadas (congeladas)

| # | Decisión | Motivo |
| :--- | :--- | :--- |
| D1 | Un solo video continuo en V1 | Simplicidad; el modelo de datos ya contempla multi-fuente |
| D2 | Nombres de archivo de ingesta con **fecha y hora** | Orden cronológico verificable, sin colisiones entre fuentes |
| D3 | Escala por **modo MANUAL**: el usuario marca un objeto de referencia en una imagen e ingresa **ancho y alto** reales | El usuario no quiere depender de marcadores ArUco impresos en obra |
| D4 | **GUI obligatoria**: asistente (wizard) paso a paso, con visualización del estado del proceso | El usuario debe guiar el proceso, no solo ver logs |
| D5 | Detector de features **ORB** | Libre de patentes. El usuario no quiere licencias ni software restringido |
| D6 | **Política de software 100 % libre** (ver §5). Nada de SIFT vía `opencv-contrib`, ni alternativas proprietarias | Requisito explícito del usuario |

### 4.1 Consecuencia de D3 sobre el modelo `CalibrationData`

La SDD original definía `bounding_box_2d` + `real_dimension_meters` + 2 puntos.
Se cambia a:

```text
CalibrationData
  image_id            : str    # nombre del frame usado en la reconstrucción
  bbox_2d             : BBox2D # x1, y1, x2, y2 en píxeles
  width_meters        : float  # ancho real del objeto de referencia (> 0)
  height_meters       : float  # alto real del objeto de referencia (> 0)
  reference_type      : "MANUAL"        # único valor en V1; "ARUCO" queda reservado
  n_corners           : int    # 4 (rectángulo) — extensible a 2 puntos
```

La escala se deriva de la **relación de aspecto conocida**: ancho y alto permiten
detectar si el rectángulo marcado está distorsionado (px/m distinto en X y en Y) y
alertar al usuario, en lugar de aceptar una escala falsa.

---

## 5. Librerías y licencias

Todas con licencia libre. No agregar dependencias sin verificar su licencia.

| Uso | Librería | Licencia | Notas |
| :--- | :--- | :--- | :--- |
| Video, features ORB, homografía | `opencv-python` | Apache-2.0 | Sin `opencv-contrib` (D5/D6) |
| Reconstrucción SfM | COLMAP (binario) | BSD-3-Clause | Estado del arte. **No instalado** |
| Binding SfM (opcional) | `pycolmap` | BSD-3-Clause | Sin wheels para Python 3.14 — ver §9 |
| Nube de puntos, RANSAC planos, OBB | `open3d` | MIT | Sin soporte oficial Python 3.14 — ver §9 |
| Geometría métrica monocular (candidata) | `moge-2` (Microsoft) | MIT | Sustituto o complemento de COLMAP — ver §6 |
| Clustering DBSCAN | `scikit-learn` | BSD-3-Clause | Open3D no expone DBSCAN |
| Optimización numérica (ajuste cilíndrico) | `scipy` | BSD-3-Clause | `scipy.optimize.least_squares` |
| Exportación DXF | `ezdxf` | MIT | Único mantenedor activo de DXF en Python |
| Validación de datos | `pydantic` v2 | MIT | Modelos de entrada/salida |
| GUI | `tkinter` (stdlib) | PSF | + `opencv` para visualización de imagen |
| Tests | `pytest` | MIT | |

**Rechazadas y por qué:**
* `opencv-contrib-python` / SIFT → licencia y dependencia extra (D5/D6).
* `pyransac3d` → licencia MIT pero proyecto poco mantenido; el ajuste cilíndrico se
  implementa con `scipy` + RANSAC propio para evitar dependencia extra.
* `python-pcl` → pesadilla de build en Windows, sin ventaja sobre Open3D.

---

## 6. Motor de reconstrucción — evaluación 2026-10-05

El SDD especifica COLMAP. **COLMAP está en evaluación, no confirmado.** El motivo es el
hardware: sin GPU NVIDIA, la densificación no llega a los umbrales del SDD.

### Candidatos

| Candidato | Licencia | CPU viable | Estado |
| :--- | :--- | :--- | :--- |
| **MoGe-2** (Microsoft) | MIT | Sí | **Candidato principal** |
| **Metric3D v2** | BSD-2-Clause | Sí, con ONNX | Alternativa a MoGe-2 |
| COLMAP sparse (sólo poses) | BSD-3-Clause | Sí | Complemento: poses más precisas |
| OpenMVS | MPL-2.0 | Lento | Descartado |
| OpenDroneMap (Docker en VPS) | GPL-2.0 | Sólo en servidor | Requiere VPS con GPU |

### MoGe-2 — por qué es el candidato principal

Estima geometría **métrica** desde una sola imagen, en una sola pasada: point map, depth map,
normales y FOV. El point map sale ya en escala métrica, con intrínsecas estimadas.

Tamaños reales de los pesos en HuggingFace (verificados 2026-10-05):

| Modelo | Peso | Params | Licencia |
| :--- | :--- | :--- | :--- |
| `Ruicheng/moge-2-vits-normal` | 134 MB | 35M | MIT |
| `Ruicheng/moge-2-vitb-normal` | 400 MB | 104M | MIT |
| `Ruicheng/moge-2-vitl-normal` | 2.5 GB | 331M | MIT |

Punto de partida: **`moge-2-vits-normal`**. Es el único que entra cómodo en esta máquina.

Implicación arquitectónica: **si MoGe-2 da la geometría, COLMAP deja de ser necesario.**
ORB se conserva sólo para validar solapamiento entre frames en M1.

### Requisitos de instalación de MoGe-2

Python ≥ 3.9 (3.12 va bien). Dependencias de la versión 2.0.0 del paquete:

```text
torch>=2.0.0, torchvision, opencv-python, scipy, numpy, pillow,
matplotlib, trimesh, click, huggingface_hub, gradio,
utils3d   (git+https://github.com/EasternJournalist/utils3d.git@3fab839)
pipeline  (git+https://github.com/EasternJournalist/pipeline.git@866f059)
```

Tres trampas al instalar:

1. **PyTorch debe ser la build de CPU**, explícita. Sin
   `pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`,
   pip descarga la build de CUDA (~2.5 GB) que no sirve sin GPU NVIDIA.
2. **`utils3d` y `pipeline` no están en PyPI**: se instalan desde git con commit fijado.
   Requiere `git` en el PATH (ya está instalado en la máquina) y acceso a GitHub.
3. **`moge@main` ya no sirve: la versión actual es 3.0.0 y depende de `FlexGEMM`, que es
   sólo-CUDA** (Triton, requiere NVIDIA). Hay que instalar MoGe-2 desde el commit
   `b942f00bd` (octubre 2025), que es el estado del repo antes del salto a la V3.

### MoGe-3 — actualizar la evaluación anterior

Corrección: MoGe-3 **ya publicó pesos**. Ya no es "coming soon".

| Modelo | Peso | Licencia |
| :--- | :--- | :--- |
| `Ruicheng/moge-3-vitl` | 1.4 GB | MIT |
| `Ruicheng/moge-3-vitg` | 4.7 GB | MIT |

MoGe-3 ataca específicamente la estructura delgada y del detalle fino, que es exactamente el
caso de un caño de 25 mm de radio. Es el candidato técnicamente más adecuado. Pero:

* `moge-3-vitl` pesa 1.4 GB: no entra cómodamente en el disco disponible (ver R11).
* Su dependencia `FlexGEMM` requiere GPU NVIDIA. Descartado para ejecución local aquí.

Conclusión: MoGe-3 queda como opción a reevaluar si en el futuro hay hardware con GPU
o una máquina con más disco. Para esta máquina, MoGe-2 `vits`.

### Riesgo principal

Ningún modelo monocular garantiza el error < 1.5 % / ≤ 10 mm del SDD. Sobre la fidelidad
hay que medir, no suponer: validar con una imagen real de obra con cotas conocidas (T3).

Rendimiento esperado: el README cita 60 ms por imagen en A100 o RTX 3090 con FP16. En un
i7-10610U la cifra será dos órdenes de magnitud mayor, del orden de **3-8 s por frame** con
el modelo `vits`. Un video de 1 min a 2 FPS son 120 frames: ~16 min sólo de inferencia.

Eso rompe por sí solo el criterio E2E de < 8 min del SDD. Hay que medir el balance real
antes de prometer ese criterio (T10).

### Consecuencias sobre el diseño de M3 y M4

La SDD define M3 como SfM con `sparse_cloud.ply` + `dense_cloud.ply` + `cameras.json`.
Si el motor es MoGe-2, ese contrato cambia:

* No hay `cameras.json`. Cada frame produce su propio point map en coordenadas de cámara,
  y las poses entre frames hay que derivarlas de la consistencia de la nube.
* La escala deja de ser "escalar la nube al final" y pasa a "corregir un sesgo por frame",
  porque MoGe-2 ya devuelve metros por imagen y el error acumulado por frame es el
  problema real.
* `CalibrationData` (D3) pasa a ser más valiosa: es la única referencia de escala absoluta.

Por eso T2 y T3 van antes que cualquier código de M3/M4. Escribir esos módulos contra el
contrato viejo implica rehacerlos.

### Collada

Alternativa a considerar si MoGe-2 no da la fidelidad necesaria: 3D Gaussian Splatting o NeRF
dan muy buena geometría aparente pero **no métrica ni topológicamente correcta**. Un caño
renderizado bonito no sirve para tomar una cota de instalación. Descartados para este
propósito.

### Servicios en la nube — descartados

Se evaluaron APIs REST de fotogrametría en la nube. **Descartadas por D6**: todas son
comerciales y se cobran por consumo, y varias prohiben uso sin suscripción comercial.
Las fotos de obra son datos de cliente, lo que añade un factor de confidencialidad.

| Servicio | API | Motivo del descarte |
| :--- | :--- | :--- |
| PIX4Dengine Cloud | REST oficial | Comercial. Estándar de industria, pero con costo y licencia |
| EveryPoint | REST, acepta MP4 | Comercial |
| Autodesk APS / ReCap | API oficial | Comercial, tiers de pago |
| Immersal | REST | Comercial, orientado a RA |
| DroneDeploy | API pública | Comercial |
| Reali3 | REST, acepta MP4 | Comercial, proyecto poco documentado |
| OpenScan Cloud | API abierta | Abierto y gratuito, pero sin SLA y capacidad limitada |

Excepción que sí respeta D6: **OpenDroneMap** es GPL-2.0 y se puede self-hostear en una VPS
con GPU, manteniendo la política de software libre. Costo pasa a ser la VPS.

### Modelos de IA de lenguaje — descartados

Los modelos conectados vía OpenCode no ejecutan OpenCV, ni SfM, ni generan nubes de puntos.
La tarea no existe en su conjunto de capacidades. Sirven para escribir el código del pipeline,
nada más. No reconsiderar como motor de reconstrucción.

---

## 7. Arquitectura del pipeline

> M3 y M4 están condicionados al motor que se elija (§6, T2). El diagrama de abajo es el
> del SDD y sigue siendo válido si se confirma COLMAP. Si el motor es MoGe-2, cambia.

```
[Video/Fotos] ─> M1 video_processor ─> frames + frame_metadata.json
                                          │
                              M2 scale_calibrator (GUI, manual)
                                          │ CalibrationData
                                          v
                              M3 reconstruction_engine (COLMAP)
                                          │ cameras.json + dense_cloud.ply
                                          v
                              M4 scale_and_align ─> nube métrica, piso Z=0
                                          │
                              M5 segmentation_engine ─> ExtractedEntities
                                          │
                              M6 spatial_analyzer ─> SpatialMetricsReport
                                          │
                              M7 exporter ─> floor_plan_3d.dxf + metrics_report.json
```

Cada módulo es un archivo en `modules/` con dataclasses/pydantic explícitas
de entrada y salida, y excepciones de dominio propias.

### 7.1 Excepciones de dominio (todas en `modules/errors.py`)

`InsufficientOverlapError`, `InvalidDimensionValueError`, `ReconstructionFailureError`,
`SegmentationFailureError`, `CalibrationError`, `ExportError`.

---

## 8. Estructura de directorios

```text
.
├── AGENTS.md                     # esta memoria
├── .opencode/skills/             # skills de proyecto (pipeline, tests)
├── pyproject.toml                # deps, ruff, pytest
├── prompt para desarrollo ...md  # SDD de origen (no editar)
├── modules/                      # código de los 7 módulos
├── tests/                        # pytest, TC-MOD1..TC-MOD7
├── data/
│   └── ingest/                   # VÍDEOS Y FOTOS DE ENTRADA (el usuario coloca aquí)
├── work/                         # generado: frames, nubes, intermedios
└── outputs/                      # entregables: .dxf y .json
```

Regla dura: **nada generado se escribe en `data/`**. `work/` es desechable y se puede
borrar sin perder el original.

### 8.1 Convención de nombres en `data/ingest/`

```text
AAAAMMDD-HHMMSS_<descripcion>.<ext>

20261005-081530_bano_principal.mp4
20261005-094210_bano_principal_detalle_01.mp4
```

* Timestamp = hora local de la captura/grabación.
* Sin espacios ni acentos en `<descripcion>` (snake_case).
* El pipeline **no** renombra los originales; deriva un nombre interno por frame:
  `{source_id}_{seq:04d}_{frame:06d}.jpg` para evitar colisiones entre fuentes.

---

## 9. Riesgos conocidos

| # | Riesgo | Mitigación |
| :--- | :--- | :--- |
| R1 | **Python 3.14 sin wheels** de `open3d` ni `pycolmap` | Crear venv con **Python 3.12** para el proyecto. Verificar antes de fijar dependencias |
| R2 | COLMAP no instalado en Windows | Sólo aplica si se confirma COLMAP como motor (§6). Descarga del binario (GUI o CLI) |
| R3 | Criterio "< 3 min densificación de 40 imágenes" sin GPU es optimista | Medir en la máquina real y recalibrar el umbral (T10) |
| R4 | `eps=0.04 m` en DBSCAN depende de densidad de la nube densa | Hacerlo parámetro configurable, no constante |
| R5 | Redondeo a 3 decimales en el JSON puede ocultar errores > 1 mm | Redondear solo en el formateo, nunca en el cálculo |
| R6 | Repo git remoto existe pero el local no está inicializado | `git init` + `remote add origin` antes de escribir código (T9) |
| R7 | **Sin GPU NVIDIA**: la nube densa del SDD no es alcanzable localmente | Motivo principal de la evaluación de motores en §6 |
| R8 | Un modelo monocular no garantiza el error métrico del SDD | Medir con cotas reales de obra antes de prometer umbrales (T3) |
| R9 | Si el motor es MoGe-2, el contrato de M3 del SDD queda obsoleto | Resolver T2 antes de escribir M3/M4, o se rehace el trabajo |
| R10 | Datos de obra son confidenciales del cliente | Subir a terceros sólo con autorización explícita (T11) |
| R11 | **Disco libre escaso: ~17.7 GB.** PyTorch CPU ~2 GB, pesos MoGe ~134 MB a 2.5 GB, COLMAP nocuda ~3.1 GB descomprimido | No instalar nada sin medir antes. Preferir el modelo `vits` (134 MB). No evaluar MoGe-3 aquí |
| R12 | Latencia de MoGe-2 en CPU (~3-8 s/frame) rompe el criterio E2E de < 8 min por sí sola | Reducir nº de frames con ORB (submuestreo) o recortar el criterio (T10) |

---

## 10. Convenciones de código

* Python ≥ 3.11 (máximo probado 3.12 por R1). Tipos con `from __future__ import annotations`.
* Modelos de datos: `pydantic.BaseModel` para lo que cruza la frontera de un módulo
  (entrada/salida, serialización JSON); `dataclass(frozen=True)` para geometría interna.
* Nombres de archivo en `snake_case`; módulos en inglés; documentación y comentarios en español.
* Todo parámetro de algoritmo tiene default explícito y está declarado en la config del pipeline,
  nunca "magic number" en el cuerpo de la función.
* Proyecciones siempre en **metros**, `Z=0` en el piso. Las coordenadas de píxel se convierten
  a metros una sola vez, en M4.
* El archivo DXF se crea con unidades métricas: `ezdxf` y `$INSUNITS = 6` (metros).
* Todo módulo debe ser testeable sin ejecutar COLMAP: la llamada a COLMAP va detrás de una
  interfaz inyectable (`ColmapBackend`), con un fake para tests.

---

## 11. Criterios de calidad no negociables

* Tolerancia de distancias ortogonales: **± 5 mm**.
* Error de escala global: **< 1 %** en controles de prueba.
* Desviación del plano de piso respecto a `Z=0`: varianza de residuos **< 0.015 m**.
* Detección de cañerías de diámetro > 1/2": **≥ 90 %**.
* Falsos positivos de planos estructurales: **< 2 %**.
* E2E video de 1 min: **< 8 min**.
* Pruebas: `pytest` cubriendo TC-MOD1-01 a TC-MOD7-02 + criterios E2E CA-E2E-01..05.

Comandos esperados (a definir en `pyproject.toml`):

```bash
pytest -q                # suite completa
ruff check . && ruff format --check .
python -m modules.pipeline data/ingest/<video>.mp4   # ejecución E2E
```

---

## 12. Flujo GUI (wizard paso a paso) — requisito D4

Una única ventana Tkinter con barra de progreso y panel de estado. Orden de pasos,
cada uno desbloqueando el siguiente:

1. **Selección de fuente** — elegir video/fotos desde `data/ingest/`.
2. **Ingesta** — progreso de extracción, cantidad de frames aceptados/rechazados, motivo de rechazo.
3. **Calibración de escala** — mostrar un frame, el usuario dibuja el rectángulo del objeto
   de referencia, ingresa ancho y alto en metros, previsualiza `px/m` en X e Y.
4. **Reconstrucción** — progreso de COLMAP por sub-etapa (features, matching, sparse, dense).
5. **Alineación** — factor de escala aplicado, residuo del plano de piso.
6. **Segmentación** — nº de planos, caños y artefactos detectados; lista con checkboxes.
7. **Análisis espacial** — tabla de cotas.
8. **Exportación** — rutas de salida y botón para abrir carpeta.

Reglas:
* Ningún paso avanza con datos inválidos: validación con mensajes en español y el error concreto.
* El estado de la sesión se persiste en `work/<source_id>/session.json` para poder retomar.
* El pipeline debe ser **resumible** por paso.

---

## 13. TODO — decisiones pendientes de definición

### 13.1 Bloqueantes (resolver antes de escribir código del módulo correspondiente)

* [ ] **T1** Crear venv con Python 3.12 y fijar versiones exactas en `pyproject.toml` (R1).
* [ ] **T2** **Decidir el motor de reconstrucción** (ver §6): MoGe-2, COLMAP sparse + MoGe-2,
      o mantener COLMAP completo. Bloquea el diseño de M3 y M4.
* [ ] **T3** Validar MoGe-2 sobre una imagen real de obra con cotas conocidas: medir error
      real sobre un caño antes de prometer los umbrales del SDD (ver §6).
* [ ] **T4** Fijar umbrales de calidad de video: `fps_sampling_rate`, `blur_threshold`,
      nº mínimo de matches ORB para declarar solapamiento válido.
* [ ] **T5** Definir `distance_threshold` del RANSAC de piso para suelos irregulares.
* [ ] **T6** Definir parametrización de DBSCAN y del ajuste cilíndrico (radio, RMSE)
      para diámetros reales de 1/2" a 3".
* [ ] **T7** Definir representación de caños en DXF: eje + radio en cota, o poliedro aproximado.
* [ ] **T8** Tabla de diámetros comerciales (¿ANSI, ISO, o ambos?) para `estimated_nominal_diameter`.
* [ ] **T9** Inicializar git local apuntando a `https://github.com/mclichas/fotogrametria`
      y añadir `.gitignore` (R6).
* [ ] **T10** Recalibrar los umbrales de densidad y tiempo del SDD contra esta máquina,
      o documentar explícitamente que quedan fuera de alcance sin GPU NVIDIA (§2.1).
* [ ] **T11** Definir la política de datos de obra: qué se sube a terceros, qué queda local
      (relevante si en el futuro se evalúa OpenDroneMap en VPS, §6).

### 13.2 Mejoras de V2

* [ ] **T12** Ingesta multi-fuente: varios videos, y mix video + fotografías.
* [ ] **T13** Ordenación cronológica de fotos por EXIF `DateTimeOriginal`.
* [ ] **T14** Soporte ArUco como modo de referencia adicional (queda reservado, no en V1).
* [ ] **T15** Métrica de calidad por frame y mapa de calor de solapamiento en la GUI.
* [ ] **T16** Reevaluar MoGe-3 si en el futuro hay GPU NVIDIA o más disco: apunta
      específicamente a estructuras delgadas, que es el caso de los caños (ver §6).

### 13.4 Antes de instalar cualquier cosa

El disco es escaso (~17.7 GB, R11). **No instalar dependencias sin medir el espacio
disponible primero** y sin que el usuario lo autorice. Presupuesto aproximado:

| Paquete | Espacio | Veredicto |
| :--- | --- | --- |
| PyTorch build CPU | ~2 GB | Necesario si se elige MoGe |
| `moge-2-vits-normal` | 134 MB | Aceptable |
| `moge-2-vitb-normal` | 400 MB | Aceptable |
| `moge-2-vitl-normal` | 2.5 GB | Evitar |
| COLMAP nocuda descomprimido | ~3.1 GB | Evitar salvo decisión explícita |
| Open3D | ~400 MB | Necesario en cualquier escenario |

### 13.3 Decisiones ya resueltas (no reabrir sin motivo)

* [x] D1–D6 (§4). Licencia libre, ORB, escala manual con ancho/alto, GUI wizard,
      nombres con fecha y hora, V1 de un solo video.

---

## 14. Cómo trabajar en este proyecto

1. Leer `AGENTS.md` y la sección de la SDD del módulo que se va a tocar.
2. Revisar el TODO (§13): si el módulo depende de un ítem sin resolver, decirlo antes de codificar.
3. Implementar módulo + tests de sus TC en el mismo cambio.
4. No agregar librerías sin verificar licencia y actualizar §5.
5. No inventar tolerancias: si un criterio de aceptación no está definido, ir a §13.
6. Antes de usar el motor de reconstrucción, leer §6. COLMAP no está confirmado.