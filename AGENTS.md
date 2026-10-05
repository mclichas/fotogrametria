# AGENTS.md — Sistema de Planimetría 3D y Vectorización CAD de Cañerías

Memoria del proyecto. Leer este archivo antes de tocar código.
Especificación funcional de origen: `prompt para desarrollo de plaimetria de caños post instalación.md` (SDD 1.0–3.0 + matriz de pruebas).
Repositorio: https://github.com/mclichas/fotogrametria

---

## 1. Propósito

Aplicación modular en Python que procesa video/fotografías de ambientes en remodelación,
reconstruye la geometría 3D métricamente escalada, aísla cañerías y artefactos, y exporta
planos CAD (`.dxf`) y reportes dimensionales (`.json`).

Salida principal: **documentación de la obra tal como quedó** (*as-built*). El cañería
ya está instalado; el sistema registra dónde quedó realmente.

**No se compara contra los planos del proyecto.** El objetivo es documentar, no determinar
si la instalación cumple lo proyectado (D9). Ver §1.1.

**Tolerancia máxima de error: 10 mm** (decisión D7, §11.1).

### 1.1 Qué es y qué no es el entregable

| Es | No es |
| :--- | :--- |
| Registro de la ubicación real de cada caño | Juicio de cumplimiento del proyecto |
| Cotas métricas con incertidumbre asociada | Comparación contra planos de referencia |
| Insumo para obra futura,Ampliación o mantenimiento | Certificación de calidad de la instalación |

El segundo punto tiene una consecuencia fuerte: **sin una referencia contra la cual
comparar, la única forma que tiene el lector de saber si un número es un hecho o una
estimación es la incertidumbre que el propio sistema reporta.** Por eso §11.1 bis.

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
| D7 | **Tolerancia máxima de error: 10 mm.** Es un techo, no un objetivo | Por encima de 10 mm el plano no sirve para el propósito. Ver §11.1 |
| D8 | **Python 3.12** para el venv | `open3d` llega a cp314 pero `ezdxf` se detiene en cp313 — §5.1 |
| D9 | **El producto documenta una instalación ya realizada, no guía una instalación.** Sin comparación contra los planos del proyecto: no se ingestan planos de referencia ni se emite juicio de cumplimiento | Confirmado por el usuario 2026-10-05. Ver §1 y §11.1 bis |

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
| Nube de puntos, RANSAC planos, OBB | `open3d` | MIT | Wheels win_amd64 hasta cp314. **0.20.0** — ver §5.1 |
| Geometría métrica monocular (candidata) | `moge-2` (Microsoft) | MIT | Sustituto o complemento de COLMAP — ver §6 |
| Clustering DBSCAN | `scikit-learn` | BSD-3-Clause | Open3D no expone DBSCAN |
| Optimización numérica (ajuste cilíndrico) | `scipy` | BSD-3-Clause | `scipy.optimize.least_squares` |
| Exportación DXF | `ezdxf` | MIT | Único mantenedor activo de DXF en Python |
| Validación de datos | `pydantic` v2 | MIT | Modelos de entrada/salida |
| GUI | `tkinter` (stdlib) | PSF | + `opencv` para visualización de imagen |
| Tests | `pytest` | MIT | |

**Rechazadas y por qué:**
* `opencv-contrib-python` / SIFT → licencia y dependencia extra (D5/D6).
* `python-pcl` → pesadilla de build en Windows, sin ventaja sobre Open3D.
* ~~`pyransac3d` → proyecto poco mantenido~~ → **CORREGIDO 2026-10-05, ver §6 bis.**
  La razón real era evitar una dependencia extra, no la actividad del proyecto:
  `pyRANSAC-3D` tiene 670 stars, licencia Apache-2.0 (libre, D6 OK), es NumPy puro,
  y commits de 2026-08. **No estaba poco mantenido.** La decisión queda abierta como **T22**:
  usar `pyRANSAC-3D` para el ajuste cilíndrico de M5, o escribirlo con `scipy`.

### 5.1 Versiones verificadas en PyPI (2026-10-05)

Verificado contra la API de PyPI. **No asumir versiones: comprobar antes de fijar.**

| Paquete | Última | Wheels win_amd64 | Nota |
| :--- | :--- | :--- | :--- |
| `open3d` | 0.20.0 | cp310–cp314 | **Sí tiene wheel para 3.14.** R1 estaba exagerado |
| `opencv-python` | 5.0.0.93 | `cp37-abi3` | ABI3: sirve para cualquier Python ≥ 3.7. No es un conflicto |
| `scipy` | 1.18.1 | cp312–cp315 | **1.18.1 NO tiene cp310.** Si se usa 3.10, fijar `scipy==1.15.3` |
| `scikit-learn` | 1.9.1 | cp311–cp315 | Si se usa 3.10, fijar `scikit-learn==1.5.2` |
| `ezdxf` | 1.4.4 | cp310–cp313 | **No llega a cp314.** Límite duro si se usa 3.14 |
| `pydantic` | 2.13.5 | — | `pydantic-core` es binario, pero publica wheel universal vía del core |
| `torch` | 2.14.1 | cp310–cp314 | Instalar la build de CPU explícita (§6) |

**Consecuencia para elegir la versión de Python:** hay un conflicto real.

`open3d` llega hasta cp314, pero `ezdxf` **se detiene en cp313**. Un proyecto que necesita
ambos no puede usar 3.14. Las opciones son 3.10 (instalada) o 3.12/3.13.

Recomendación: **3.12**, porque tiene wheels de todo y evita fijar versiones antiguas
de scipy y scikit-learn que ya no son la última. 3.10 funciona pero obliga a tres
versiones pinneadas por falta de wheel.

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

**Advertencia de los propios autores de MoGe-2**, textual de su paper (NeurIPS 2025,
"Limitations"): *"struggles with capturing extremely fine structures, such as thin lines
and hair, and with maintaining straight and aligned structures under a significant scale
difference between the foreground and background."*

Esto es literalmente nuestro caso: un caño de 1/2" son 25 mm de radio, estructura delgada
en un ambiente con fondo cercano y lejano. **El riesgo conocido del candidato principal
está confirmado por su propia documentación.** Por eso T3 no es opcional antes de escribir
M3: hay que medir si el error del radio del caño entra en 10 mm antes de construir el resto.

Corolario sobre el modelo: `vits` (35M params) es el que entra en disco, pero es también
el de menor detalle fino. Si `vits` falla la prueba de T3, el resultado no dice "MoGe-2
no sirve", dice "hace falta `vitb` (400 MB) o MoGe-3". Distinguir esos dos casos cuesta
una prueba de 134 MB.

Rendimiento esperado: el README cita 60 ms por imagen en A100 o RTX 3090 con FP16. En un
i7-10610U la cifra será dos órdenes de magnitud mayor, del orden de **3-8 s por frame** con
el modelo `vits`. Un video de 1 min a 2 FPS son 120 frames: ~16 min sólo de inferencia.

Eso rompe por sí solo el criterio E2E de < 8 min del SDD. Hay que medir el balance real
antes de prometer ese criterio (T10).

**Referencia publicada para COLMAP, del paper de Maalek & Lichti** (§6 bis), medido por
ellos en su máquina: *"300 4K images can take up to 10 hours to process, which is equivalent
to analyzing only 5 seconds of video recording at 60 fps"*. Es decir, **~2 min por imagen
4K**. No es el mismo hardware que el nuestro y no aclara si usaron GPU.

Sirve igual como orden de magnitud: **el SfM clásico es de minutos por imagen, no de
segundos.** Cualquier criterio de tiempo del SDD que asuma minutos para docenas de frames
está descartado por esta sola cifra. Y explica por qué los dos caminos convergen en lo
mismo: o submuestramos fuerte, o el E2E se mide en horas.

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

### 6 bis. Estado del arte en repositorios públicos (búsqueda 2026-10-05)

Búsqueda por API de GitHub (stars, licencia, última actividad) y lectura de abstracts.
**No se clonó ni instaló nada**: el disco sigue intacto. Sirve para no reinventar y para
saber qué se midió en la literatura antes de medirlo nosotros.

#### El precedente más cercano: video de celular → point cloud → caños

**Maalek & Lichti, "Towards Automatic Digital Documentation and Progress Reporting of
Mechanical Construction Pipes using Smartphones"** (2020). Es exactamente nuestro caso:
video de celular, escala métrica definida a mano, extracción de caños de la nube, clasificación
por radio contra un BOM.

Sus números medidos en obra (58 caños, no laboratorio):

| Métrica | Resultado |
| :--- | :--- |
| Radio del caño | error **5.4 mm** |
| Clasificación de caños | F-measure **96.4 %** |
| Longitud | error **5.0 %** |
| Condición | **≥ 95 % de solapamiento** entre imágenes |

Dos lecturas. La buena: **5.4 mm de error de radio está por debajo de nuestra tolerancia de
10 mm (D7), y con escala manual.** Nuestro criterio no es arbitrario: hay precedente publicado.

La mala: **exige 95 % de solapamiento entre frames.** Eso es muy superior al
`fps_sampling_rate` de cualquier video de celular normal, y tiene costo computacional
directo. Es el criterio que rompe el E2E de < 8 min (R12). Queda como referencia para
dimensionar T4: el solapamiento no es un parámetro libre, es el que decide la precisión.

También relevante: un paper de 2023 sobre pipelines reconstruye **desde los bordes de
la imagen, no desde la nube**, porque *"the low texture of the pipes usually results in a
very sparse point cloud"*. Es el riesgo inverso al de MoGe: si la textura del caño es baja,
COLMAP/MVS no densifica nada. Otra razón para medir T2 en vez de suponerlo.

#### Repositorios que confirman nuestro stack

| Repos | Stars | Licencia | Activo | Veredicto |
| :--- | ---: | :--- | :--- | :--- |
| `microsoft/MoGe` | 3004 | MIT (+ DINOv2 Apache-2.0) | 2026-09 | Motor candidato. Licencia D6 OK |
| `leomariga/pyRANSAC-3D` | 670 | Apache-2.0 | 2026-08 | **Revisa la decisión de §5.** Ver abajo |
| `LTTM/Scan-to-BIM` | 131 | sin declarar | 2025-03 | BIM-Net++, requiere GPU y pesos entrenados |
| `mac999/scan_to_bim_pipeline` | 56 | MIT | 2026-07 | Pipeline Open3D, RANSAC + DL. Referencia de estructura |
| `ZENULI/PyPipes` | 40 | MIT | **2022-02** | DeepPipes. Abandonado 4 años, no usar |
| `humantecheu/pystruct3d` | 37 | MIT | 2026-06 | Ajuste de OBB para scan-to-BIM. Charsetrecho |
| `weiykong/cylfit` | 1 | MIT | 2026-09 | Ajuste cilíndrico con MAGSAC/PROSAC. Charsetrecho |

**Corrección a §5.** Registré `pyransac3d` como descartado por "poco mantenido". Los datos
dicen otra cosa: 670 stars, Apache-2.0, con commits en 2026-08. **No estaba poco mantido.**
Mi razón real era evitar una dependencia extra, pero `pyRANSAC-3D` es Apache-2.0 (libre,
D6 OK), pura NumPy, y ya resuelve el ajuste cilíndrico que §5 describe como "código propio".

Esto no está decido. Es una pregunta abierta con impacto directo en M5: usar `pyRANSAC-3D`
o escribir el ajuste a mano con `scipy`. Lo anoté como **T22**.

#### Sobre el ajuste cilíndrico

`weiykong/cylfit` (MIT, 1 star, muy reciente) es el código más cercano a lo que necesitamos:
MAGSAC + PROSAC + refinamiento Levenberg-Marquardt con jacobiano analítico, expone
`residuals`, `rmse` e `inlier_mask`. Es exactamente el insumo de T17: **la dispersión de
los residuales es una estimación de incertidumbre de la cota.**

Advertencia técnica relevante y transferible, de una PR a PCL (#6338): el ajuste de
cilindro por mínimos cuadrados con residuo **al cuadrado de la distancia** (`r̂² - (r+ε)²`)
introduce **sesgo sistemático** que sobreestima el radio como `√(r² + σ²)`. Con ruido
bajo y radio grande es despreciable, pero **con radio de 25 mm y σ de pocos milímetros
empieza a importar**. Si escribimos el ajuste, el residuo debe ser lineal en la distancia
al eje, no su cuadrado.

#### Datasets

| Dataset | Qué es | Licencia |
| :--- | :--- | :--- |
| **OpenTrench3D** | 310 nubes fotogramétricas de video de celular, 528M puntos, redes de cañerías segmentadas. 5 clases | **CC BY-NC 4.0** |
| CLOI | Nubes de interiores con OBB anotadas | — |

OpenTrench3D es el más parecido a nuestro insumo, y su construcción es casi idéntica:
video de celular, GCP marcados con spray, app que procesa el video a la nube.

**No usarlo**: la licencia es **NC (no comercial)**, y documentar obra de clientes es
uso comercial. D6 y R10 lo impiden. Sirve como referencia metodológica, no como datos.

#### Conclusión de la búsqueda

1. Nuestro criterio de 10 mm **tiene precedente publicado** (5.4 mm en radio, con escala
   manual y video). No es arbitrario.
2. El riesgo de MoGe-2 con estructuras delgadas **está confirmado por sus autores**.
   T3 es bloqueante real.
3. La secuencia correcta sigue siendo: no escribir M3/M4 antes de medir el motor.
4. Aparece un riesgo nuevo (R13): solapamiento insuficiente por baja textura del caño.

#### Ficha completa del precedente principal

El desarrollo anterior está en `docs/referencias/maalek-lichti-2021-video-celular.md`:
pipeline, herramientas, resultados por nivel de solapamiento, problemas que enfrentaron y
qué queda de esto para el proyecto. **Es material de referencia, no parte del sistema**
(ver la regla de §8). Dos puntos que conviene tener presentes al retomar:

* Descartan el registro scan-vs-BIM porque presupone un BIM siempre actualizado y "no puede
  incorporar el impacto de los errores de construcción". Es el mismo razonamiento que llevó
  a D9, por el mismo grupo de investigación.
* Definen la escala **durante** el SfM, con blancos circulares físicos colocados en obra.
  Choca con D3. Su método es más preciso; el nuestro es practicable sin llevar marcadores.

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
├── docs/
│   └── referencias/              # fichas de papers y repos. CONTEXTO, no requisito
├── work/                         # generado: frames, nubes, intermedios
└── outputs/                      # entregables: .dxf y .json
```

Regla dura: **nada generado se escribe en `data/`**. `work/` es desechable y se puede
borrar sin perder el original.

Regla sobre `docs/referencias/`: es **contexto, no requisito**. Contiene fichas de papers
y repositorios con lo que midieron otros. No se importa nada de ahí, no define contratos, y
ningún número de esos archivos es un criterio de aceptación. Si una ficha contradice una
decisión de §4, **manda la decisión** y se corrige la ficha.

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
| R1 | **Conflicto de wheels por versión de Python.** `open3d` llega a cp314 pero `ezdxf` se detiene en cp313 | Usar Python **3.12** (D8). Verificar antes de fijar dependencias — §5.1 |
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
| R13 | **Baja textura del caño** produce nubes ralas: *"low texture of the pipes usually results in a very sparse point cloud"* (literatura 2023). Es el riesgo inverso al de MoGe y afecta a COLMAP/MVS | Medir en T3 la densidad real **sobre un caño**, no la densidad global de la escena (§6 bis) |
| R14 | El precedente publicado con 5.4 mm de error de radio **exige ≥ 95 % de solapamiento** entre frames, más de lo que da un video de celular normal | Dimensionar T4 con ese número como techo. Medir el solapamiento real de la captura antes de fijar `fps_sampling_rate` |

---

## 10. Convenciones de código

* Python 3.12 (D8). Tipos con `from __future__ import annotations`.
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

### 11.1 Precisión métrica — decisión D7

**La tolerancia máxima de error aceptable es 10 mm.** Confirmado por el usuario el 2026-10-05.

Fundamento: por encima de 10 mm el contraste entre el relevamiento y el proyecto deja de
ser confiable para señalar un desvío real. No es un número arbitrario del SDD sino el
umbral de utilidad práctica del documento final.

Consecuencia: **10 mm es un techo, no un objetivo.** El objetivo debe estar por debajo.
Si el error medido en obra se acerca a 10 mm, el resultado es inaceptable aunque formalmente
cumpla el criterio.

### 11.1 bis La incertidumbre es parte del dato, no un adorno

Antes (D9 v1) el producto comparaba contra los planos del proyecto. Se descartó: el
objetivo es documentar cómo quedó la obra, no juzgar si cumple lo proyectado.

Eso elimina el módulo de comparación y, con él, la necesidad de distinguir *error de
medición* de *desvío de obra*. Pero deja un problema peor:

**Una cota sin incertidumbre es indistinguible de un dato medido con cinta métrica.**

El entregable son números en milímetros sobre un DXF que alguien va a usar para picar,
ampliar o mantenimiento. Si el sistema escribe `x = 1247 mm` sin decir cuánto vale esa
cifra, está presentando una estimación con la misma autoridad que una medición directa.
No hay contra qué contrastar, así que **la incertidumbre es el único mecanismo de
honestidad del documento**.

De ahí tres requisitos concretos, que el SDD no pedía:

1. Cada cota reporta su **incertidumbre estimada** (`±` en metros), no sólo su valor.
2. Las cotas cuya incertidumbre supere la tolerancia de 10 mm se marcan
   explícitamente como **no confiables**. No se ocultan ni se redondean: se rotulan.
3. El reporte declara un **veredicto de calidad global** del relevamiento, para que el
   lector sepa si el documento completo sirve o si hay que repetir la captura.

Regla de redacción: en el JSON y en el DXF, un número sin incertidumbre asociada es un
error de formato, no un detalle de estilo.

### 11.2 Criterios numéricos

| Criterio | Umbral | Ámbito |
| :--- | :--- | :--- |
| Error de escala global | **< 1 %** | Controles de prueba |
| Desviación del plano de piso vs `Z=0` | residuos **< 0.015 m** | M4 |
| Detección de cañerías > 1/2" | **≥ 90 %** | M5 |
| Falsos positivos de planos estructurales | **< 2 %** | M5 |
| Formateo numérico | 3 decimales | Sólo presentación (R5) |

### 11.3 Requisitos por consumidor

Los criterios de la SDD se mezclan en un solo número. En la práctica hay tres capas
distintas, y confundirlas produce uninhabitables:

| Capa | Tolerancia | Qué mide | Quién lo verifica |
| :--- | :--- | :--- | :--- |
| **A. Algoritmo** | **± 5 mm** | Error interno del cálculo: ajuste de escala, punto-plano, RANSAC | Tests unitarios (TC-MOD4, TC-MOD6) |
| **B. Reconstrucción** | **± 10 mm** | Error de la geometría extraída: nube, ajuste cilíndrico, radios | Validación contra puntos de control en obra |
| **C. Extremo a extremo** | **± 10 mm** o **< 1.5 %** | Lo que lee el instalador en el DXF | CA-E2E-01 con cinta métrica |

La diferencia importa: si la nube tiene error de 8 mm pero el algoritmo calcula sin error,
el fallo es de reconstrucción, no de cálculo. Un pipeline con ± 5 mm en capa A y una nube
de 30 mm va a fallar en la C sin que ningún test unitario lo detecte.

**Regla de diagnóstico:** cuando el error E2E exceda 10 mm, hay que aislar en qué capa
aparece antes de tocar código. Medir contra puntos de control intermedios, no sólo contra
la cinta en el final.

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
7. **Análisis espacial** — tabla de cotas, cada una con su incertidumbre. Las que superan
   la tolerancia de 10 mm se muestran marcadas como no confiables.
8. **Exportación** — rutas de salida y botón para abrir carpeta.

Son 8 pasos. **No hay paso de comparación con el proyecto** (D9).

Reglas:
* Ningún paso avanza con datos inválidos: validación con mensajes en español y el error concreto.
* El estado de la sesión se persiste en `work/<source_id>/session.json` para poder retomar.
* El pipeline debe ser **resumible** por paso.

---

## 13. TODO — decisiones pendientes de definición

### 13.1 Bloqueantes (resolver antes de escribir código del módulo correspondiente)

* [ ] **T1** Crear venv con Python 3.12 (D8) y fijar versiones exactas en `pyproject.toml`.
      Requiere **instalar Python 3.12**: la máquina tiene 3.14.2 y 3.10.4, no 3.12.
      Las versiones están verificadas en §5.1 — volver a comprobar antes de fijar.
* [ ] **T2** **Decidir el motor de reconstrucción** (ver §6): MoGe-2, COLMAP sparse + MoGe-2,
      o mantener COLMAP completo. Bloquea el diseño de M3 y M4.
* [ ] **T3** Validar MoGe-2 sobre una imagen real de obra con cotas conocidas: medir error
      real sobre un caño antes de prometer los umbrales del SDD (ver §6).
* [ ] **T4** Fijar umbrales de calidad de video: `fps_sampling_rate`, `blur_threshold`,
      nº mínimo de matches ORB para declarar solapamiento válido. **El solapamiento es el
      parámetro más sensible del sistema**, no el más trivial: el único precedente con
      error de 5.4 mm exige ≥ 95 % (R14). Ver §6 bis.
* [ ] **T5** Definir `distance_threshold` del RANSAC de piso para suelos irregulares.
* [ ] **T6** Definir parametrización de DBSCAN y del ajuste cilíndrico (radio, RMSE)
      para diámetros reales de 1/2" a 3".
* [ ] **T7** Definir representación de caños en DXF: eje + radio en cota, o poliedro aproximado.
* [ ] **T8** Tabla de diámetros comerciales (¿ANSI, ISO, o ambos?) para `estimated_nominal_diameter`.
* [x] **T9** Git inicializado con `.gitignore` y `.gitattributes`, rama `main`, remoto
      `mclichas/fotogrametria`. Completado 2026-10-05.
* [ ] **T10** Recalibrar los umbrales de densidad y tiempo del SDD contra esta máquina,
      o documentar explícitamente que quedan fuera de alcance sin GPU NVIDIA (§2.1).
* [ ] **T11** Definir la política de datos de obra: qué se sube a terceros, qué queda local
      (relevante si en el futuro se evalúa OpenDroneMap en VPS, §6).
* [ ] **T17** **Definir cómo se estima y reporta la incertidumbre de cada cota** (§11.1 bis).
      **Bloqueante de M6/M7.** Sin referencia externa de comparación (D9), la incertidumbre
      es el único mecanismo de honestidad del documento. Sin ella se entrega una estimación
      vestida de dato medido. Candidatos: dispersión de residuales del ajuste cilíndrico,
      variación de la escala entre frames, o error de reproyección del motor.
* [ ] **T19** Definir qué se hace con los caños parcialmente ocultos o cortados por el
      encuadre: ¿se reportan con marca de baja confianza, o se omiten?
* [ ] **T21** Definir la **identificación del relevamiento** en el JSON de salida: qué
      datos identifican la obra (ambiente, fecha, responsable, lote) para que el documento
      sea rastreable. Con T17 forma el bloque de metadatos del reporte.
* [ ] **T22** Decidir si el ajuste cilíndrico de M5 usa `pyRANSAC-3D` (Apache-2.0,
      670 stars, NumPy puro) o implementación propia con `scipy`. **Bloqueante de M5.**
      Ver §6 bis: la decisión anterior de descartarlo se basó en un dato equivocado.
      Si se usa la librería, verificar que sea el cilindro de eje + radio que necesitamos
      y no una variante de cono o elipse.

### 13.2 Mejoras de V2

* [ ] **T12** Ingesta multi-fuente: varios videos, y mix video + fotografías.
* [ ] **T13** Ordenación cronológica de fotos por EXIF `DateTimeOriginal`.
* [ ] **T14** Soporte ArUco como modo de referencia adicional (queda reservado, no en V1).
* [ ] **T15** Métrica de calidad por frame y mapa de calor de solapamiento en la GUI.
* [ ] **T16** Reevaluar MoGe-3 si en el futuro hay GPU NVIDIA o más disco: apunta
      específicamente a estructuras delgadas, que es el caso de los caños (ver §6).

### 13.3 Descartado — no reabrir sin motivo del usuario

* [x] **T18** Formato de entrada del proyecto de referencia. **Descartado 2026-10-05.**
      El usuario aclaró que no se usan los planos del proyecto. No hay módulo de
      comparación, ni ingesta de DXF de referencia, ni capa de desvíos.
* [x] **T20** Módulo de comparación con el proyecto. **Descartado** por lo mismo. La V1
      queda en los 7 módulos de la SDD, sin ampliación de alcance.

### 13.4 Decisiones ya resueltas (no reabrir sin motivo)

* [x] D1–D9 (§4). Licencia libre, ORB, escala manual con ancho/alto, GUI wizard,
      nombres con fecha y hora, V1 de un solo video, tolerancia 10 mm, Python 3.12,
      documentación as-built sin comparación con planos del proyecto.
* [x] **T9** Git inicializado, rama `main`, remote en `mclichas/fotogrametria`. 2 commits pusheados.

### 13.5 Antes de instalar cualquier cosa

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

---

## 14. Cómo trabajar en este proyecto

1. Leer `AGENTS.md` y la sección de la SDD del módulo que se va a tocar.
2. Revisar el TODO (§13): si el módulo depende de un ítem sin resolver, decirlo antes de codificar.
3. Implementar módulo + tests de sus TC en el mismo cambio.
4. No agregar librerías sin verificar licencia y actualizar §5.
5. No inventar tolerancias: si un criterio de aceptación no está definido, ir a §13.
6. Antes de usar el motor de reconstrucción, leer §6. COLMAP no está confirmado.