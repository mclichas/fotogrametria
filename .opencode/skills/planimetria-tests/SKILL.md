---
name: planimetria-tests
description: Estrategia de pruebas del pipeline de planimetría de cañerías: casos TC-MOD1 a TC-MOD7, criterios CA-E2E, generación de fixtures sintéticos (video y nubes de puntos) y cómo testear COLMAP sin depender del binario. Usar al escribir o revisar tests bajo tests/, al crear datos de prueba, al agregar un módulo nuevo o cuando pytest falla por dependencias externas.
license: MIT
metadata:
  project: planimetria-canerias
  stack: python,pytest,opencv,open3d
---

# Pruebas del pipeline de planimetría

## Principio

Ningún test requiere COLMAP instalado, GPU ni conexión. Si un test falla porque
falta un binario o una GPU, es un test mal diseñado.

Todo entra por una dependencia inyectable: `ColmapBackend` fake, `Open3D` para nubes
sintéticas generadas en memoria, video sintético escrito con `cv2.VideoWriter` a un
archivo temporal de `tmp_path`.

## Inventario de casos

Cada TC del SDD tiene su test con el **mismo ID** en el nombre.

| Módulo | TC | Qué verifica | Cómo construir el fixture |
| :--- | :--- | :--- | :--- |
| M1 | TC-MOD1-01 | 20 frames exactos a 2 FPS desde video de 10 s @30 FPS | texto aleatorio denso en movimiento |
| M1 | TC-MOD1-02 | 100 % de descarte de frames con var. Laplaciana < 40 | aplicar blur de movimiento a la mitad |
| M1 | TC-MOD1-03 | `InsufficientOverlapError` con el segundo exacto | salto de cámara con contenido distinto |
| M2 | TC-MOD2-01 | Detección ArUco sin intervención (reservado, no V1) | marcador generado con `cv2.aruco` |
| M2 | TC-MOD2-02 | `CalibrationData` con 200 px / 0.50 m = 400 px/m | imagen sintética con rectángulo conocido |
| M2 | TC-MOD2-03 | `InvalidDimensionValueError` con "treinta cm" y −0.5 | wizard en notebook: probar el validador puro, no el widget de ipywidgets |
| M3 | TC-MOD3-01 | ≥ 90 % de imágenes registradas + nube densa no vacía | `FakeColmapBackend` con `images.bin` de 30 entradas |
| M3 | TC-MOD3-02 | `ReconstructionFailureError` en textura homogénea | fake que devuelve 0 features |
| M4 | TC-MOD4-01 | 2.0 unidades → 1.0 m con ±0.001 m | nube de 2 puntos a distancia 2.0 |
| M4 | TC-MOD4-02 | normal del piso a (0,0,1) ±0.01 tras rotar | plano inclinado 45° |
| M5 | TC-MOD5-01 | 6 planos (4 paredes + piso + techo) sin overlap de inliers | nubes de plano sintéticas |
| M5 | TC-MOD5-02 | radio 0.025 m en [0.023, 0.027], eje con R² > 0.98 | cilindro de 1.5 m por muestreo de superficie |
| M5 | TC-MOD5-03 | 5 % de outliers no alteran la detección | añadir ruido uniforme al fixture de TC-MOD5-02 |
| M6 | TC-MOD6-01 | 0.500 / 0.480 / 0.00 % para caño horizontal | `ExtractedEntities` a mano, sin punto de entrada real |
| M6 | TC-MOD6-02 | 0.09 / 0.14 / 5.00 % para caño inclinado | ídem |
| M7 | TC-MOD7-01 | SVG de V1: XML bien formado, dimensiones en mm, capas correctas | entidades de prueba |
| M7 | TC-MOD7-02 | JSON valida contra el modelo Pydantic | `metrics_report` completo |

E2E: CA-E2E-01 a CA-E2E-05. CA-E2E-01 a CA-E2E-03 requieren datos reales de obra
y están marcados `skip` hasta que haya dataset (ver abajo).

## Fixtures sintéticos

Colocar generadores reusables en `tests/fixtures.py`, no inline en cada test.

```python
def make_synthetic_cloud(points: np.ndarray) -> o3d.geometry.PointCloud: ...

def make_plane(n=2000, size=3.0, normal=(0,0,1), offset=0.0) -> np.ndarray:
    """Rejilla aleatoria dentro de un plano de `size` x `size` metros."""

def make_cylinder(radius=0.025, length=1.5, axis=(1,0,0), n=3000, jitter=0.0) -> np.ndarray:
    """Muestreo uniforme sobre la superficie lateral + tapas opcionales."""

def make_room(walls=4, floor_z=0.0, ceiling_z=2.4, size=3.0) -> np.ndarray:
    """Ambiente cerrado: 4 paredes perpendiculares, piso y techo."""

def write_synthetic_video(path: Path, seconds=10, fps=30, n_features=400) -> Path:
    """Video con textura densa en paneo, para que ORB encuentre overlap."""
```

Detalles que importan:

* `make_plane` y `make_cylinder` devuelven `np.ndarray (N,3)` en **metros**.
* El ruido de `make_cylinder` debe ser **radial**, no isotrópico: si se aplica jitter
  gaussiano uniforme, el ajuste RANSAC cilíndrico funciona sobre datos que la nube
  densa real nunca producirá.
* `make_cylinder` con `jitter=0.002` sirve para probar el umbral `rmse_max=0.008`.

## Fixtures de video

* Resolución modesta (640×480) para velocidad; los umbrales de nitidez son relativos.
* La textura debe ser **rico en detalles**: un video de gradiente suave no produce
  keypoints y los tests de overlap fallan por la razón equivocada.
* Para blur: `cv2.filter2D(frame, -1, kernel)` con kernel de tamaño impar ≥ 3.
* Para el salto de cámara de TC-MOD1-03, cambiar el contenido, no sólo la posición:
  un paneo suave de la misma textura mantiene el overlap y el test no prueba lo que dice.

## Cómo testear COLMAP

```python
class FakeColmapBackend:
    """Escribe un modelo COLMAP mínimo y registra los comandos recibidos."""

    def __init__(self, registered_ratio: float = 1.0, n_features: int = 5000): ...

    def run(self, stage: str, args: Sequence[str]) -> None:
        self.calls.append((stage, list(args)))
        # escribe fixtures en el directorio de trabajo
```

Assert sobre `fake.calls` para verificar que se invocó la etapa correcta y con el
`matcher` esperado. El test de TC-MOD3-01 usa `registered_ratio=0.95`;
TC-MOD3-02 usa `n_features=0`.

## Marcar tests que dependen de datos reales

```python
@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.requires_real_data
def test_ca_e2e_01_metric_accuracy(...)
```

Registrar los marcadores en `pyproject.toml` para que `pytest -m "not e2e"` sea
la suite por defecto y `pytest -m e2e` la de validación en obra.

## Checklist antes de cerrar un módulo

- [ ] Todos sus TC existen con el ID del SDD en el nombre del test.
- [ ] El test falla si se rompe el código (verificado cambiando el valor esperado).
- [ ] Los tests del wizard validan la lógica, no el widget (extraer validadores puros).
- [ ] Sin `time.sleep`; usar mocks para lo asíncrono.
- [ ] Sin dependencia de rutas absolutas, del reloj del sistema ni del orden de ejecución.
- [ ] Los fixtures compartidos están en `tests/fixtures.py`.
- [ ] Los tests que dependen de COLMAP/GPU/datos reales llevan su marcador.