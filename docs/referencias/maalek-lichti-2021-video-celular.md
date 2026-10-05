# Referencia: Maalek & Lichti — documentación de cañerías desde video de celular

> **Material de referencia. No es parte del sistema.**
> No hay código acá, no hay contrato, no se importa nada de este archivo. Sirve para saber
> qué midieron otros antes de medirlo nosotros, y para sustentar las decisiones de AGENTS.md
> cuando haga falta recordar el origen de un número.
> Nada de lo que dice aquí es un requisito del producto: es contexto, con su fecha.

Ficha del precedente más cercano al proyecto. Escribí esto después de leer el abstract, el
preprint de arXiv y los papers complementarios del mismo equipo. No se instaló ni clonó nada.

---

## 1. Identificación

| Campo | Valor |
| :--- | :--- |
| Título | Towards Automatic Digital Documentation and Progress Reporting of Mechanical Construction Pipes using Smartphones |
| Autores | Reza Maalek (KIT), Derek D. Lichti (Univ. Calgary), Shahrokh Maalek |
| Revista | Automation in Construction, vol. 127, art. 103735 (julio 2021) |
| DOI | `10.1016/j.autcon.2021.103735` (Elsevier, pago) |
| Preprint | **arXiv:2012.10958** — v1 2020-12-20, v2 2021-03-30 |
| Licencia del preprint | **CC BY 4.0** (legible y reutilizable) |
| Citas | ~22 |

**Importante:** el preprint en arXiv es CC BY 4.0. Se puede leer, citar y reutilizar el
método. Lo que es pago es la versión de la editorial.

### Papers complementarios del mismo equipo (mismo grupo, no el mismo paper)

Estos tres son los que contienen el detalle algorítmico real:

| Paper | Revista | Qué aporta |
| :--- | :--- | :--- |
| Robust Detection of Non-overlapping Ellipses... | ISPRS J. Photogrammetry 176:83–108 (2021) | **Algoritmo 3**: detección de caños desde la nube |
| New Confocal Hyperbola-based Ellipse Fitting... | Pattern Recognition 116:107948 (2021) | **Ajuste de elipse** que subyace al anterior |
| Automated Calibration of Smartphone Cameras... | Photogrammetric Record 36(174):124–146 (2021) | Calibración y **`COLMAP` confirmado** como motor SfM |

Cuando este documento dice "el método", se refiere al algoritmo del paper principal; cuando
cita comportamiento concreto del motor, proviene del paper de calibración.

---

## 2. Qué problema ataca

**No es el nuestro, y ahí está lo interesante.**

Ellos quieren automatizar el **reporte de avance de obra**: el oficial de la cuadrilla
mide a mano los metros de caño instalado de cada diámetro, los carga en una tablet, y eso
alimenta el control de proyecto y la facturación. *"The manual estimation of the length of
installed pipe, however, contains an inherent margin"* de error.

Nosotros queremos **documentar dónde quedó cada caño** (D9). Es otro producto: ellos
miden longitudes para pagar, nosotros registramos ubicación para intervenir.

La diferencia importa porque explica por qué su pipeline termina clasificando por radio:
el pago se hace por diámetro, así que el radio es la variable que importa.

---

## 3. Limitaciones que identifican de los enfoques previos

Citation textual del paper (numeradas como en el original):

1. *"Manual detection of pipe lengths from point clouds can be time consuming and might
   introduce an additional error source due to subjectivity of the manual intervention."*
2. *(omitido en las fuentes consultadas)*
3. *(omitido en las fuentes consultadas)*
4. *"Photogrammetric point clouds generated from images require an accurate scale
   definition for metric reconstruction, which is predominantly performed manually."*
5. *"Even though high resolution point clouds are ideal for accurate as-built modeling and
   object detection, they impose an additional obstacle related to storage and analysis of
   big data."*

### Y el descarte de scan-vs-BIM — el más relevante para nosotros

Revisan el enfoque dominante (registrar la nube contra el BIM del proyecto) y lo rechazan.
El argumento es textual:

> *"The underlying assumption is, however, that an up-to-date BIM with sufficient level of
> development, is consistently available, and cannot incorporate the impact of construction
> errors or changes in design specifications – that are not yet updated in the BIM."*

Traducción: el enfoque scan-vs-BIM ** presupone que el BIM está siempre actualizado**, y
precisamente no puede registrar errores de construcción ni cambios no reflejados en el
modelo.

Además, requiere al menos 3 correspondencias de puntos clave más un refinamiento ICP.

**Esto es exactamente el motivo por el que el usuario descartó los planos de referencia (D9).**
Suena a que el mismo grupo de investigación llegó a la misma conclusión por el mismo
camino. Vale la pena citarlo cuando se retome el tema.

---

## 4. El pipeline: cuatro etapas

### Etapa 1 — Optimizar el número de frames (`Algorithm 1`)

Inventan una **definición nueva de solapamiento entre imágenes** para poder elegir qué
frames usar del video, en vez de tomar todos. El objetivo declarado es mejorar la
calidad de la nube *"while preserving computational efficiency"*.

Solapamientos evaluados: **70 % → 95 % en pasos de 5 %**, con el máximo fijado en
`mínimo + 2.5 %`.

### Etapa 2 — Definición automática de escala (`Algorithm 2: Scale Definition in SfM`)

Este es el aporte metodológico más importante para nosotros.

**No escalan la nube al final.** Definen la escala durante el SfM, usando los parámetros
exteriores de orientación (EOP) de las imágenes:

1. Detectan **elipses** en las imágenes (los blancos circulares de los blinding targets se
   proyectan como elipses).
2. Estiman los parámetros geométricos de cada elipse con el método de **hipérbola
   confocal**.
3. Emparejan las elipses entre vistas.
4. Resuelven la escala desde las EOP junto con las IOP.
5. Definen la escala a partir de la distancia conocida entre los centros de dos targets.

Resultado declarado: **precisión sub-milimétrica en el radio**, y de ahí el 5.4 mm en obra
(véase §6: el sub-milimétrico es **en laboratorio**, no en obra).

**Detalle crítico para nuestro caso: este método requiere blancos circulares físicos
colocados en la obra.** El ground truth de la distancia entre dos targets lo midieron con
un escáner TLS Leica HDS6100.

Esto choca con D3, donde el usuario decidió **no** depender de marcadores impresos o ArUco.
Nuestro rectángulo manual con ancho y alto es un enfoque distinto para el mismo problema.
Es una divergencia real, no una diferencia de detalle: su método es más preciso, el nuestro
es más practicable en obra.

### Etapa 3 — Detección de caños desde la nube (`Algorithm 3`)

Basado en Maalek & Lichti (ISPRS 2021). La idea es reducir 3D a 2D:

1. Proyectar los puntos sobre **planos de corte** que atraviesan los cilindros.
2. Cada plano corta el cilindro en una **elipse** (teorema de Dandelin).
3. Detectar elipses robustas en esos cortes.
4. Ajustar la elipse por **distancia de hipérbola confocal**.
5. Recuperar los parámetros del cilindro (radio, centro, eje) desde los de la elipse.

Contraste con otras detecciones de elipses robustas en imágenes reales: **F-measure 99.3 %**
propio, contra 42.4 %, 65.6 % y 59.2 % de Fornaciari, Pǎtrǎucean y Panagiotakis.

### Etapa 4 — Clasificación por radio (k-means)

Agrupan los cilindros detectados en las clases de radios exteriores conocidos que vienen
del **pliego de cañerías del presupuesto (BOM)**. Es un k-means clásico.

**Consecuencia para nosotros:** si no queremos depender de planos ni de pliegos, este paso
no se puede copiar. T8 (tabla de diámetros comerciales) sigue siendo necesaria, pero como
referencia técnica propia, no como entrada del presupuesto.

---

## 5. Herramientas

| Rol | Herramienta | Licencia |
| :--- | :--- | :--- |
| SfM + densa | **COLMAP** | BSD-3-Clause |
| Ajuste de elipse | confocal hyperbola (propio) | — |
| Detección de elipse | no-overlapping ellipse (propio) | — |
| Clasificación | k-means | — |
| Terrestre de referencia | Leica HDS6100 TLS, FARO Focus TLS | comercial (solo referencia) |
| Celulares probados | iPhone 11, Huawei P30, Samsung S10 | — |

**COLMAP confirmado textualmente** en el paper de calibración: *"COLMAP, an open-source
software package comprised of many computational and scientific improvements to traditional
SfM methods, was utilised."*

Eso valida que la elección del SDD original era la estándar de la literatura. No la
resuelve para esta máquina sin GPU.

### Detalle computacional

El paper de ajuste de elipse reporta sus corridas en **AMD Ryzen 5-2600X, 64 GB RAM,
SSD NVMe 1 TB**. Referencia útil: es una máquina de escritorio, no un portátil de 4 núcleos.

### Captura

Video 4K, **1 fps**, dividido en tramos de 30 s, en modo retrato y apaisado, con la cámara
girada 90° sobre su eje óptico a distinta altura. Esa rotación deliberada es para que la
auto-calibración *in situ* de COLMAP tenga oportunidad de estimar la distorsión radial.

---

## 6. Resultados

### En obra (58 caños)

| Métrica | Resultado | Condición |
| :--- | :--- | :--- |
| Clasificación de caños (F-measure) | **96.4 %** | ≥ 95 % solapamiento |
| Error de radio (RMSE) | **5.4 mm** | ≥ 95 % solapamiento |
| Error de longitud | **5.0 %** | ≥ 95 % solapamiento |

### Efecto del solapamiento (el hallazgo central)

Probado de 70 % a 95 %:

| Solapamiento | Lectura |
| :--- | :--- |
| 70 % | **Insuficiente** incluso para precisión sub-milimétrica |
| 80–85 % | Error de longitud apenas baja de 10 % |
| 90 % | Estable |
| 95 % | Prácticamente idéntico a 90 %, con leve mejora en longitud |

Causas que ellos dan para la mejora:

1. Mayor densidad de puntos → más puntos redundantes → mejor ajuste cilíndrico.
2. Más *tie points* → mejor estimación de las EOP.

**Y un hallazgo que nos afecta directo:** *"the radius estimation accuracies for the
smallest pipe was impacted more by the increase in the image overlap, than say the largest
pipe"*, porque la menor densidad de puntos penaliza más a los objetos pequeños.

Es decir: **el caño chico es el primero en sufrir cuando bajamos el solapamiento.**
Nuestro caso es justamente el extremo: 25 mm de radio contra caños industriales de 100 mm
o más de sus experimentos.

---

## 7. Problemas que enfrentaron

### 7.1 Oclusión — resuelto, con números

*"Given that mechanical pipes are commonly attached from one side to a wall, the
reconstructed point cloud of the pipes are only partially visible."*

Su método lo maneja, y publican los números:

* Ajuste de elipse a arcos **parcialmente ocluidos**: error de radio dentro de **3.4 mm**,
  centro **4.7 mm**, eje **3.9°**, sobre **30 000 configuraciones** con ruido variable.
* Detección robusta de cilindros: fiable con aproximación inicial del eje dentro de **7°**,
  aun con outliers.

Esto responde parcialmente a **T19** (caños ocultos o cortados por el encuadre). No es
"omitirlos": es reportarlos con la degradación medida. Coincide con el criterio que ya
escribimos en §11.1 bis de AGENTS.md — no ocultar, marcar.

### 7.2 Selección manual de planos de corte

En el dataset TLS: *"Three planes that intersected with the cylinders were manually
selected"*. Es un paso manual dentro de un método que se presenta como automático.

### 7.3 Calibración de cámara — el error más grande

Su paper complementario compara contra la auto-calibración *in situ* de COLMAP
(`COLMAP-radial`, con los dos primeros términos de distorsión radial e intrínsecas
iniciales del EXIF):

| Métrica | Resultado |
| :--- | :--- |
| Puntos inlier del cilindro | ~1.3× más con pre-calibración |
| Exactitud del radio | **~45 % mejor** con pre-calibración |
| Orden entre celulares | iPhone 11 > Huawei P30 > Samsung S10 |

Explicación de ese orden: **número de features detectadas por imagen.** El Samsung S10
tenía menos, el iPhone 11 más. Y la causa propuesta incluye el códec de compresión de
video (H.265 en iPhone, H.264 en Huawei).

**Traducción a nuestro caso:** la calidad del video de origen —codec, resolución, features
detectables— mueve el error del radio casi un factor dos. Eso es un argumento fuerte para
fijar `jpeg_quality`, resolución y el umbral de blur en T4, no como detalles de captura
sino como parámetros que mueven la precisión final.

### 7.4 Rolling shutter

No lo tratan como problema, pero un paper de 2026 sobre shutter en pipelines de
fotogrametría muestra que el obturador electrónico degrada la orientación exterior y la
malla incluso cuando el defecto es imperceptible en la imagen. Los celulares de 2020-2021
usan obturador electrónico.

---

## 8. Qué queda de esto para el proyecto

| Hallazgo | Efecto |
| :--- | :--- |
| Descartan scan-vs-BIM por presuponer BIM actualizado | **Respalda D9.** El mismo razonamiento llegó el mismo grupo |
| 5.4 mm de error de radio en obra, con escala manual | **Tu tolerancia de 10 mm tiene precedente.** D7 no es arbitraria |
| Exigen ≥ 95 % de solapamiento | **R14.** El solapamiento es el parámetro crítico, no el `fps_sampling_rate` |
| El caño pequeño sufre más con poco solapamiento | Nuestro caso es el peor. Refuerza medir en T3 con caño real, no sintético |
| RMSE del mejor cilindro ajustado = "la incertidumbre" | **Respuesta parcial a T17.** Ver abajo |
| 45 % de diferencia por calibración de cámara | La captura es un parámetro de precisión, no un detalle |
| Escala requiere blancos físicos en obra | Choca con D3. Nuestro enfoque manual es menos preciso y más practicable |

### Sobre T17 (incertidumbre)

En el paper de calibración, textual:

> *"The root mean square error (RMSE) of the best-fitting cylinder, representing the
> uncertainty, and the corresponding ground-truth pipe radius were 0.3 and 57.3 mm"*

Es decir: **el RMSE del ajuste es su incertidumbre**, dicho de forma explícita. Y en el
paper de elipses reportan el error de parámetro como L2-norma del vector de parámetros
estimado contra el verdadero, en porcentaje.

Esto valida la opción que ya figuraba primera en T17: **dispersión de los residuales del
ajuste cilíndrico**. Es lo que hace la literatura, no una invención nuestra.

Lo que la literatura **no** hace y nosotros sí necesitamos: incertidumbre de las **cotas
derivadas** (distancia a pared, holgura al techo, longitud), no solo del radio del
cilindro. Eso es propagación de errores a través de las fórmulas de M6, y sigue abierto.

### Límite de esta referencia

Es un paper de **2021 con software propietario del grupo**. El algoritmo de detección de
cilindros depende de tres papers previos de los mismos autores, con código no publicado.
**No podemos reutilizar su implementación.** Lo que aprovechamos es: las métricas que
midieron, los umbrales que encontraron, y la confirmación de que el problema es soluble
con video de celular y escala manual.