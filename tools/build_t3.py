"""Generador (bootstrap) del notebook experimento T3: Validación de MoGe-2.

SOLO BOOTSTRAP — NO re-ejecutar sobre ediciones manuales.
El notebook `experimentos/t3_moge2_validacion.ipynb` es la fuente de verdad del
experimento: si se ajusta la medición, se edita el .ipynb (en Colab y se devuelve
a GitHub), no se regenera. Este script se usó para el bootstrap inicial.

Uso (solo si hace falta reconstruir desde cero):
    python tools/build_t3.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "experimentos" / "t3_moge2_validacion.ipynb"


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


cells = []

# ---------------------------------------------------------------- celda 0
cells.append(
    md(
        """# Experimento T3 — Validación de MoGe-2 (error métrico sobre un caño)

Prueba de decisión del TODO **T3** (AGENTS.md §13.1): medir si la geometría métrica
de MoGe-2 entra en la tolerancia de **10 mm** (D7) sobre un caño real, ANTES de
decidir el motor de reconstrucción (T2) y de escribir M3/M4 (R9).

**Reglas:**
* La foto es de obra/objeto **propio**, nunca de un cliente (T11 no aplica con foto propia).
* La foto vive en Drive (D10) y **nunca** sube a GitHub (repo público). Este notebook
  es SOLO código: se versiona sin datos.
* Esto **no es el producto** (el wizard): es un experimento. Su lógica de medición
  migrará a `modules/` cuando se cierre T2.

**Qué mide y contra qué criterio:**

| Métrica | Criterio |
| :--- | :--- |
| Error de escala global (objeto de referencia, ancho **y** alto) | **< 1 %** (§11.2) |
| Diámetro del caño medido vs. real (cota con calibre/cinta) | **≤ 10 mm** (D7 es techo; objetivo menor) |
| Densidad de puntos **sobre el caño** (R13/R15) | suficiente para el ajuste de radio |
| Distorsión px/m X vs. Y del rectángulo de referencia | umbral D3 (§7.1) |

**Cómo se abre:** https://colab.research.google.com/github/mclichas/fotogrametria/blob/main/experimentos/t3_moge2_validacion.ipynb
(con la **cuenta dedicada** del proyecto).

Se corren las celdas en orden. El hardware se declara en el reporte (T10): con o sin
GPU corre — una imagen con `vits` tarda ~3-8 s en CPU y decenas de ms en GPU con FP16.
"""
    )
)

# ---------------------------------------------------------------- celda 1 (chequeo de recursos)
cells.append(
    code(
        """# @title 0. Chequeo de recursos de esta sesión (CORRER PRIMERO, antes de instalar)
# Colab solo deja leer sus propios recursos desde dentro de la sesión, por eso este
# chequeo. Umbrales para esta prueba: disco libre >= 5 GB (usa < 2 GB) y RAM libre
# >= 2 GB (usa < 2 GB). Si algo queda corto: Runtime -> Restablecer entorno (factory
# reset) y reabrir el notebook desde GitHub.
import shutil, time, datetime
import psutil, torch

_disk = shutil.disk_usage("/content")
_mem = psutil.virtual_memory()
print("=== Sesión Colab ===")
print("hora      :", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("uptime VM :", time.strftime("%H:%M:%S", time.gmtime(time.time() - psutil.boot_time())))
print()
print("=== Disco (/content, efímero) ===")
print(f"libres {_disk.free/1e9:.1f} GB | total {_disk.total/1e9:.0f} GB | usados {_disk.used/1e9:.1f} GB")
print()
print("=== RAM ===")
print(f"libres {_mem.available/1e9:.1f} GB | total {_mem.total/1e9:.1f} GB | usados {_mem.used/1e9:.1f} GB")
print()
print("=== torch / GPU ===")
print("torch:", torch.__version__, "| cuda:", torch.cuda.is_available())
if torch.cuda.is_available():
    _p = torch.cuda.get_device_properties(0)
    print("GPU  :", torch.cuda.get_device_name(0), f"| VRAM {_p.total_memory/1e9:.1f} GB")
"""
    )
)

# ---------------------------------------------------------------- celda 2
cells.append(
    code(
        """# @title 1. Instalar MoGe-2 al commit fijado (una vez por sesión)
# D6: todo libre (MIT/BSD). NO reinstalar torch: Colab ya trae la build CUDA;
# reinstalarla rompería la GPU. MoGe V3 (main) es CUDA-only (FlexGEMM): por eso se
# pinnea el commit b942f00bd, estado pre-V3 (AGENTS.md §6).
import subprocess, sys

def pip(*args):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *args], check=True)

pip("opencv-python", "scipy", "numpy", "pillow", "matplotlib", "trimesh", "click", "huggingface_hub")
pip("git+https://github.com/EasternJournalist/utils3d.git@3fab839")
pip("git+https://github.com/EasternJournalist/pipeline.git@866f059")
pip("git+https://github.com/microsoft/MoGe.git@b942f00bd")
print("Dependencias listas. NO se tocó torch (queda la de Colab).")
"""
    )
)

# ---------------------------------------------------------------- celda 2
cells.append(
    code(
        """# @title 2. Entorno: hardware y versiones (se declara en el reporte — regla T10)
import platform, time, json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import matplotlib.pyplot as plt
import torch

print("python   :", platform.python_version())
print("sistema  :", platform.platform())
print("torch    :", torch.__version__)
_has_cuda = torch.cuda.is_available()
print("cuda     :", _has_cuda)
if _has_cuda:
    print("gpu      :", torch.cuda.get_device_name(0))
"""
    )
)

# ---------------------------------------------------------------- celda 3
cells.append(
    code(
        """# @title 3. Montar Drive y elegir la foto de prueba (D10)
# Si el popup de autorización no aparece o tarda, Colab aborta con
# 'credential propagation was unsuccessful'. En ese caso: re-ejecutá esta celda
# y completá el popup con la cuenta DEDICADA del proyecto sin demorarte; también
# permití popups de colab.research.google.com en el navegador.
import os
from google.colab import drive

_MNT = "/content/drive"
if not os.path.isdir(f"{_MNT}/MyDrive"):
    print(f"Montando Drive en {_MNT}... completá el popup con la cuenta dedicada.")
    drive.mount(_MNT)
else:
    print(f"Drive ya montado en {_MNT} (no se vuelve a pedir autorización).")

from ipywidgets import widgets
from IPython.display import display

# Ajustar si la carpeta compartida «Fotogrametria» vive en otra ruta.
PROJECT_DIR = Path("/content/drive/MyDrive/Fotogrametria")
INGEST_DIR = PROJECT_DIR / "data" / "ingest"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "experimentos"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_img_exts = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
OPCIONES = sorted(p for p in INGEST_DIR.iterdir() if p.suffix.lower() in _img_exts) if INGEST_DIR.exists() else []
print(f"Ingesta: {INGEST_DIR}")
print(f"Fotos: {len(OPCIONES)}")
for p in OPCIONES:
    print("  -", p.name)

sel = widgets.Dropdown(options=[p.name for p in OPCIONES], description="Foto:")
display(sel)
"""
    )
)

# ---------------------------------------------------------------- celda 4
cells.append(
    code(
        """# @title 4. Cargar y mostrar la foto seleccionada
if not OPCIONES:
    raise SystemExit("No hay fotos en data/ingest. Subí la foto de prueba a Drive (carga manual, D10).")
ruta_img = INGEST_DIR / sel.value
_img = cv2.imread(str(ruta_img))
assert _img is not None, "No se pudo leer la imagen"
img_rgb = cv2.cvtColor(_img, cv2.COLOR_BGR2RGB)
H, W = img_rgb.shape[:2]
print(f"{ruta_img.name}: {W}x{H} px")

plt.figure(figsize=(10, 8))
plt.imshow(img_rgb)
plt.title("Foto de prueba. Revisá nitidez, luz y encuadre.")
plt.axis("off")
plt.show()
"""
    )
)

# ---------------------------------------------------------------- celda 5
cells.append(
    code(
        """# @title 5. Cargar MoGe-2 (vits 134 MB; vitb 400 MB si vits falla — distinguir casos)
# §6 de AGENTS: si vits no alcanza el detalle fino, el resultado NO dice «MoGe-2 no
# sirve», dice «hace falta vitb o MoGe-3». Si vits da mal, cambiá MODEL_ID al modelo
# de abajo y recorrré el notebook.
MODEL_ID = "Ruicheng/moge-2-vits-normal"
# MODEL_ID = "Ruicheng/moge-2-vitb-normal"

# API real del commit b942f00bd (MoGe 2.0.0): la clase se obtiene con el selector
# de versión; `from_pretrained` NO acepta dtype/device (descarga `model.pt` del
# repo HF) y los pesos salen fp32 en CPU — mover device/dtype después de cargar.
from moge.model import import_model_class_by_version
MoGeModel = import_model_class_by_version("v2")

_device = "cuda" if _has_cuda else "cpu"
_dtype = torch.float16 if _has_cuda else torch.float32
model = MoGeModel.from_pretrained(MODEL_ID).to(_device).eval()
if _dtype == torch.float16:
    model.half()
print(f"Modelo  : {MODEL_ID}")
print(f"device  : {_device} | dtype: {next(model.parameters()).dtype}")
"""
    )
)

# ---------------------------------------------------------------- celda 6
cells.append(
    code(
        """# @title 6. Inferencia: point map métrico (una pasada por imagen)
# `infer` devuelve dict: points, depth, mask, intrinsics, normal. En b942f00bd NO
# existe `return_scale`: la escala métrica ya está aplicada dentro de `infer` (el
# metric_scale del checkpoint). Pre-proceso oficial: dividir por 255 (idéntico a
# moge/scripts/infer.py del commit). apply_mask=False: si no, las regiones con
# máscara falsa quedan en torch.inf y rompen las distancias de las celdas 8 y 10.
t0 = time.time()
_img_t = torch.from_numpy(img_rgb).permute(2, 0, 1).float().div_(255).unsqueeze(0)
out = model.infer(_img_t, apply_mask=False, use_fp16=bool(_has_cuda))
te = time.time()
print(f"claves del output: {sorted(out.keys())}")
print(f"tiempo inferencia: {te - t0:.2f} s")

depth = np.asarray(out.get("depth")).squeeze()
pts = np.asarray(out.get("points")).squeeze()
intrinsics = np.asarray(out.get("intrinsics")).squeeze()
normals = np.asarray(out.get("normal")).squeeze()
print(f"depth shape: {depth.shape} | point map shape: {pts.shape}")

plt.figure(figsize=(12, 5))
plt.subplot(1, 2, 1); plt.imshow(img_rgb); plt.title("RGB"); plt.axis("off")
plt.subplot(1, 2, 2); plt.imshow(depth, cmap="turbo"); plt.title("Depth"); plt.axis("off")
plt.show()
"""
    )
)

# ---------------------------------------------------------------- celda 7
cells.append(
    code(
        """# @title 7. Marcar el objeto de referencia (ancho y alto conocidos — D3)
# Colab con backend inline NO despacha eventos de mouse (el RectangleSelector no
# responde) y %matplotlib ipympl no siempre está disponible (ValueError). Esta
# versión NO depende del backend: 4 sliders (x1,x2,y1,y2) + vista previa con el
# rectángulo ROJO. Ajustá hasta que envuelva la caja azul (cara de frente),
# cargá ancho/alto reales y corré la celda 8.
from ipywidgets import widgets
from IPython.display import display
import matplotlib.patches as mpatches

x1_w = widgets.IntSlider(value=0, min=0, max=W - 1, description="x1")
x2_w = widgets.IntSlider(value=W - 1, min=0, max=W - 1, description="x2")
y1_w = widgets.IntSlider(value=0, min=0, max=H - 1, description="y1")
y2_w = widgets.IntSlider(value=H - 1, min=0, max=H - 1, description="y2")
ancho_w = widgets.FloatText(value=0.0, description="ancho real (m)")
alto_w = widgets.FloatText(value=0.0, description="alto real (m)")
_out_vista = widgets.Output()

def _vista(_=None):
    with _out_vista:
        _out_vista.clear_output(wait=True)
        _fig, _ax = plt.subplots(figsize=(10, 8))
        _ax.imshow(img_rgb)
        _ax.add_patch(mpatches.Rectangle((x1_w.value, y1_w.value),
                                         x2_w.value - x1_w.value,
                                         y2_w.value - y1_w.value,
                                         fill=False, edgecolor="red", linewidth=2))
        _ax.set_title("Rectángulo rojo = caja azul (cara de frente). Ajustá los sliders.")
        plt.show()

for _w in (x1_w, x2_w, y1_w, y2_w):
    _w.observe(_vista)
_vista(None)
display(widgets.VBox([widgets.HBox([x1_w, x2_w]), widgets.HBox([y1_w, y2_w]),
                      _out_vista, widgets.HBox([ancho_w, alto_w])]))
print("Ajustá los sliders; después poné ancho 0.078 y alto 0.138 y corré la celda 8.")
"""
    )
)

# ---------------------------------------------------------------- celda 8
cells.append(
    code(
        """# @title 8. Escala: px/m, distorsión (D3) y error métrico del objeto de referencia
assert ancho_w.value > 0 and alto_w.value > 0, "Falta el ancho/alto reales (celda 7)."
x1, y1, x2, y2 = x1_w.value, y1_w.value, x2_w.value, y2_w.value
_wpx, _hpx = x2 - x1, y2 - y1
assert _wpx > 0 and _hpx > 0, "Rectángulo inválido (x2>x1, y2>y1)."

pxmx = _wpx / ancho_w.value
pxmy = _hpx / alto_w.value
dist = abs(pxmx - pxmy) / max(pxmx, pxmy)
print(f"px/m X = {pxmx:.1f} | px/m Y = {pxmy:.1f} | distorsión = {dist * 100:.2f} %")
if dist > 0.02:
    print("  ⚠ distorsión alta: revisá que el objeto esté DE FRENTE a la cámara (D3, §7.1).")

# Error métrico de MoGe: distancia 3D entre esquinas del rectángulo (point map).
_c = lambda u, v: pts[min(v, H - 1), min(u, W - 1)]
_p_tl, _p_tr = _c(x1, y1), _c(x2, y1)
_p_bl, _p_br = _c(x1, y2), _c(x2, y2)
ancho_3d = (np.linalg.norm(_p_tr - _p_tl) + np.linalg.norm(_p_br - _p_bl)) / 2
alto_3d = (np.linalg.norm(_p_bl - _p_tl) + np.linalg.norm(_p_br - _p_tr)) / 2
err_w = (ancho_3d - ancho_w.value) / ancho_w.value * 100
err_h = (alto_3d - alto_w.value) / alto_w.value * 100
print(f"ancho 3D = {ancho_3d * 1000:.1f} mm (real {ancho_w.value * 1000:.0f} mm) → {err_w:+.2f} %")
print(f"alto 3D  = {alto_3d * 1000:.1f} mm (real {alto_w.value * 1000:.0f} mm) → {err_h:+.2f} %")
print("Criterio escala: |error| < 1 % (§11.2).")
"""
    )
)

# ---------------------------------------------------------------- celda 9
cells.append(
    code(
        """# @title 9. Medir el caño (diámetro real en mm)
# Igual que la celda 7 (sliders, sin backend interactivo). Ajustá el rectángulo
# ROJO para que envuelva un TRAMO LIMPIO del caño verde (sin codos ni fittings),
# con el caño cruzando la imagen y el eje ~perpendicular a la cámara.
# CARGÁ EL DIÁMETRO EXTERIOR REAL del caño. Decisión 2026-10-06: asumido 25 mm para
# esta prueba — si lo medís con calibre y da otro valor, gana el calibre. Ojo: el
# veredicto se lee contra el número que cargás; un «1/2 pulgada» comercial mide
# ~15.9 mm (CTS: CPVC/PEX/cobre) o ~21.3 mm (IPS: PVC); en PPR verde, Ø25 es el
# «3/4 pulgada» comercial. El interior del caño no interviene en la prueba.
from ipywidgets import widgets
from IPython.display import display
import matplotlib.patches as mpatches

cx1_w = widgets.IntSlider(value=0, min=0, max=W - 1, description="x1")
cx2_w = widgets.IntSlider(value=W - 1, min=0, max=W - 1, description="x2")
cy1_w = widgets.IntSlider(value=0, min=0, max=H - 1, description="y1")
cy2_w = widgets.IntSlider(value=H - 1, min=0, max=H - 1, description="y2")
diam_w = widgets.FloatText(value=25.0, description="diámetro real (mm)")
_out_vista2 = widgets.Output()

def _vista2(_=None):
    with _out_vista2:
        _out_vista2.clear_output(wait=True)
        _fig2, _ax2 = plt.subplots(figsize=(10, 8))
        _ax2.imshow(img_rgb)
        _ax2.add_patch(mpatches.Rectangle((cx1_w.value, cy1_w.value),
                                          cx2_w.value - cx1_w.value,
                                          cy2_w.value - cy1_w.value,
                                          fill=False, edgecolor="red", linewidth=2))
        _ax2.set_title("Rectángulo rojo = tramo del caño a medir (sin fittings).")
        plt.show()

for _w in (cx1_w, cx2_w, cy1_w, cy2_w):
    _w.observe(_vista2)
_vista2(None)
display(widgets.VBox([widgets.HBox([cx1_w, cx2_w]), widgets.HBox([cy1_w, cy2_w]),
                      _out_vista2, widgets.HBox([diam_w])]))
print("Ajustá el rectángulo sobre un tramo limpio del caño y corré la celda 10.")
"""
    )
)

# ---------------------------------------------------------------- celda 10
cells.append(
    code(
        """# @title 10. Cálculo del caño: cordón 3D, densidad y veredicto parcial
assert diam_w.value > 0, "Falta el diámetro real (celda 9)."
_x1, _y1, _x2, _y2 = cx1_w.value, cy1_w.value, cx2_w.value, cy2_w.value
assert _x2 > _x1, "Caja inválida (x2 > x1)."
y0 = (_y1 + _y2) // 2
_cols = np.arange(_x1, _x2 + 1)
_d_row = pts[y0, _cols, 2]  # profundidad sobre la fila media de la caja

# Cluster más cercano a la cámara = superficie del caño (R13/R15: medir la densidad
# SOBRE el caño, no en la escena).
_d_min = float(_d_row.min())
_tol = float(diam_w.value / 1000) * 1.5 + 0.01
_mask = _d_row <= _d_min + _tol
n_pipe = int(_mask.sum())
print(f"puntos sobre el caño: {n_pipe} de {len(_cols)}")
if n_pipe < 50:
    print("  ⚠ densidad baja sobre el caño: revisá encuadre/luz o el diámetro real (R13/R15).")

if n_pipe >= 2:
    _run = _cols[_mask]
    _i0, _i1 = int(_run[0]), int(_run[-1])
    d_3d_auto_mm = float(np.linalg.norm(pts[y0, _i0] - pts[y0, _i1])) * 1000
else:
    d_3d_auto_mm = float("nan")
d_3d_clicks_mm = float(np.linalg.norm(pts[y0, _x1] - pts[y0, _x2])) * 1000

print(f"diámetro 3D (auto, borde del caño) = {d_3d_auto_mm:.1f} mm")
print(f"diámetro 3D (caja, fila media)     = {d_3d_clicks_mm:.1f} mm")
print(f"diámetro real                      = {diam_w.value:.1f} mm")
err_mm = d_3d_auto_mm - diam_w.value
print(f"error del diámetro                 = {err_mm:+.1f} mm  (criterio D7: ≤ 10 mm)")
"""
    )
)

# ---------------------------------------------------------------- celda 11
cells.append(
    code(
        """# @title 11. Reporte a Drive y veredicto
_escala_ok = abs(err_w) < 1.0 and abs(err_h) < 1.0
_canio_ok = abs(err_mm) <= 10.0
_dens_ok = n_pipe >= 50

_veredicto = []
if _escala_ok:
    _veredicto.append("escala OK (< 1 %)")
else:
    _veredicto.append(f"escala FALLA (ancho {err_w:+.2f} %, alto {err_h:+.2f} %)")
if _canio_ok:
    _veredicto.append(f"caño OK (|{err_mm:+.1f} mm| <= 10 mm)")
else:
    _veredicto.append(f"caño FALLA ({err_mm:+.1f} mm > 10 mm)")
if not _dens_ok:
    _veredicto.append(f"densidad baja sobre el caño ({n_pipe} pts)")

reporte = {
    "experimento": "t3_moge2_validacion",
    "timestamp": datetime.now().isoformat(timespec="seconds"),
    "imagen": ruta_img.name,
    "modelo": MODEL_ID,
    "hardware": {
        "cuda": _has_cuda,
        "gpu": torch.cuda.get_device_name(0) if _has_cuda else None,
        "torch": torch.__version__,
        "tiempo_inferencia_s": round(te - t0, 3),
    },
    "calibracion": {
        "bbox_px": [x1, y1, x2, y2],
        "ancho_real_m": ancho_w.value,
        "alto_real_m": alto_w.value,
        "px_per_m_x": round(pxmx, 3),
        "px_per_m_y": round(pxmy, 3),
        "distorsion_pct": round(dist * 100, 3),
        "error_escala_ancho_pct": round(err_w, 3),
        "error_escala_alto_pct": round(err_h, 3),
    },
    "canio": {
        "diametro_real_mm": diam_w.value,
        "diametro_3d_mm_auto": round(d_3d_auto_mm, 3),
        "diametro_3d_mm_caja": round(d_3d_clicks_mm, 3),
        "error_mm": round(err_mm, 3),
        "n_puntos_canio": n_pipe,
    },
    "veredicto": {
        "escala_ok": bool(_escala_ok),
        "canio_ok": bool(_canio_ok),
        "densidad_ok": bool(_dens_ok),
        "texto": ", ".join(_veredicto),
    },
}

_archivo = OUTPUT_DIR / f"t3_{ruta_img.stem}_{datetime.now():%Y%m%d-%H%M%S}.json"
_archivo.write_text(json.dumps(reporte, indent=2, ensure_ascii=False))
print("Reporte:", _archivo)
print()
print("VEREDICTO:", ", ".join(_veredicto))
"""
    )
)

# ---------------------------------------------------------------- celda 12
cells.append(
    md(
        """## Interpretación y siguientes pasos

**El resultado decide T2 (motor):**

| Resultado | Lectura | Siguiente paso |
| :--- | :--- | :--- |
| Escala < 1 % **y** caño ≤ 10 mm | MoGe-2 `vits` es viable | Cerrar T3 → T2 se inclina a MoGe-2 → T4 con presupuesto ~15× más barato que COLMAP (§6 bis) |
| Escala OK, caño no | `vits` no alcanza el detalle fino | Repetir con `vitb` (400 MB): cambiar `MODEL_ID` en la celda 5 |
| Ni escala ni caño | MoGe-2 no da métrica confiable acá | Reevaluar motor: COLMAP sparse + MoGe, o COLMAP completo (T2) |

**Antes / después de la corrida:**
* La foto NO se sube a GitHub (repo público, T11). Solo el notebook (código) se puede
  devolver con `File → Save a copy in GitHub` o la celda de resguardo del wizard.
* El reporte queda en `outputs/experimentos/t3_*.json` (Drive) — es el insumo para
  actualizar AGENTS (cerrar T3) con el hardware declarado (T10).
* Si Colab no asigna GPU, la prueba corre igual en CPU (más lento, un solo frame).
* Recordar: la cuenta dedicada se usa SOLO para este proyecto y SOLO en la carpeta
  compartida (D10).
"""
    )
)

nb = {
    "cells": cells,
    "metadata": {
        "colab": {"provenance": []},
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"OK: {OUT} ({len(cells)} celdas)")