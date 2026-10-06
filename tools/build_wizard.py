"""Generador (bootstrap) del notebook wizard_planimetria.ipynb.

SOLO BOOTSTRAP — NO re-ejecutar sobre ediciones manuales.
El notebook `wizard_planimetria.ipynb` es la fuente de verdad del wizard: se
edita en Colab y se devuelve a GitHub. Este script se usó UNA vez (2026-10-06)
para generar el .ipynb de forma confiable; re-ejecutarlo pisa cualquier edición
manual. Usar únicamente si hace falta reconstruir el notebook desde cero:
    python tools/build_wizard.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "wizard_planimetria.ipynb"


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
        """# Wizard de Planimetría 3D de Cañerías — V1

Wizard de 8 pasos para documentar *as-built* (D9) una instalación de cañerías a
partir de un video de obra. V1 = un único video continuo (D1). El producto corre
entero en Colab: cómputo en GPU (T4) + GUI en notebook (ipywidgets + matplotlib) (D11).

**Cómo se usa (D10/D11):**
1. Entrá a Colab con la **cuenta dedicada del proyecto** (no la personal).
2. Corré las celdas en orden, de arriba hacia abajo. El estado de la corrida se
   guarda en `work/<source_id>/session.json` (en Drive): la sesión es **resumible
   por paso** si se corta.
3. Los videos de obra van a `data/ingest/` (carga manual, D10), con nombre
   `AAAAMMDD-HHMMSS_descripcion.ext` (§8.1).

**Reglas de esta cuenta:** el acceso a la cuenta de Google se usa **únicamente**
para este proyecto y **únicamente** dentro de la carpeta compartida del proyecto.
Nada fuera de la carpeta de trabajo. Ante cualquier limitación, pedir autorización
antes de seguir.

**Estado del código:** los pasos se habilitan a medida que se implementan los
módulos (`modules/`). Hasta entonces muestran «pendiente».

---

**Abrir en Colab (siempre la copia versionada de GitHub):**
https://colab.research.google.com/github/mclichas/fotogrametria/blob/main/wizard_planimetria.ipynb

El notebook vive en GitHub (resguardo del código; repo público). Los cambios se
devuelven a GitHub con `File → Save a copy in GitHub` o con la celda «Resguardo
en GitHub». Los videos y fotos de obra NO se suben a GitHub (T11): quedan solo
en Drive.

**Modelo de persistencia (qué vive dónde):**

| Componente | Dónde vive | ¿Persiste entre sesiones? |
| :--- | :--- | :--- |
| Notebook y código (`wizard_planimetria.ipynb`, `modules/`, `tests/`) | GitHub | Sí — versionado |
| Entorno de ejecución (VM, GPU, `/content`, librerías) | Colab | No — se regenera en cada corrida |
| Datos, intermedios y entregables (`data/ingest`, `work/`, `outputs/`, `session.json`) | Google Drive | Sí — D10 |

La sesión de Colab es efímera a propósito: al cerrarse se pierde el entorno, no
el trabajo. Cada corrida re-clona el código (celda de configuración), monta Drive
y retoma desde `work/<source_id>/session.json` paso por paso.
"""
    )
)

# ---------------------------------------------------------------- celda 1
cells.append(
    code(
        """# @title Configuración del runtime (una vez por sesión)
# Clona el repo en /content y deja el código listo para importar (D11, §11.3).
import os
import subprocess
from pathlib import Path

REPO_URL = "https://github.com/mclichas/fotogrametria.git"
REPO_DIR = Path("/content/fotogrametria")

if not (REPO_DIR / ".git").exists():
    print("Clonando el repositorio...")
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(REPO_DIR)], check=True)

os.chdir(REPO_DIR)
print(f"Repo en: {REPO_DIR}")

# Dependencias (T1: fijar versiones exactas antes de producción; D6: todas libres).
%pip install -q pydantic opencv-python open3d scipy scikit-learn ipywidgets matplotlib
"""
    )
)

# ---------------------------------------------------------------- celda 2
cells.append(
    code(
        """# @title Montar Google Drive (D10)
# Usá la cuenta DEDICADA del proyecto (no la personal).
from google.colab import drive

drive.mount("/content/drive")

print("Montado. Este acceso se usa SOLO para este proyecto y SOLO dentro de la")
print("carpeta compartida «Fotogrametria».")
"""
    )
)

# ---------------------------------------------------------------- celda 3
cells.append(
    code(
        """# @title Carpetas de trabajo en Drive (D10)
from pathlib import Path

# Si la carpeta compartida «Fotogrametria» vive en otra ruta de tu Drive,
# ajustá PROJECT_DIR y volvé a correr esta celda.
PROJECT_DIR = Path("/content/drive/MyDrive/Fotogrametria")
INGEST_DIR = PROJECT_DIR / "data" / "ingest"
WORK_DIR = PROJECT_DIR / "work"
OUTPUTS_DIR = PROJECT_DIR / "outputs"

for d in (INGEST_DIR, WORK_DIR, OUTPUTS_DIR):
    d.mkdir(parents=True, exist_ok=True)  # exist_ok: no pisa lo que ya existe

print("Estructura de trabajo:")
for d in (PROJECT_DIR, INGEST_DIR, WORK_DIR, OUTPUTS_DIR):
    print(f"  {d}")
"""
    )
)

# ---------------------------------------------------------------- celda 3.5
cells.append(
    code(
        """# @title Resguardo en GitHub (notebook + código)
import subprocess

print("=" * 70)
print("RESGUARDO EN GITHUB (repo público: solo código y notebook, nunca obra)")
print("=" * 70)
subprocess.run(["git", "status", "--short"])

pat = None
try:
    from google.colab import userdata
    pat = userdata.get("GITHUB_PAT")
except Exception:
    pat = None

if pat:
    subprocess.run(["git", "config", "user.name", "mclichas"])
    subprocess.run(["git", "config", "user.email", "mclichas@users.noreply.github.com"])
    # El token queda en .git/config del runtime (disco efímero: se borra al cerrar).
    token_url = f"https://x-access-token:{pat}@github.com/mclichas/fotogrametria.git"
    subprocess.run(["git", "remote", "set-url", "origin", token_url])
    subprocess.run(["git", "add", "wizard_planimetria.ipynb", "modules/", "tests/", "AGENTS.md"])
    subprocess.run(["git", "commit", "-m", "resguardo desde Colab (notebook)"])
    subprocess.run(["git", "push", "origin", "main"])
    print("Resguardo enviado. Revisá el commit en https://github.com/mclichas/fotogrametria")
else:
    print()
    print("Vía 1 — sin configuración: menú File → Save a copy in GitHub (una vez, autorizás a Colab).")
    print("Vía 2 — con token: creá un Personal Access Token (scope repo) y guardalo como")
    print("          secreto 'GITHUB_PAT' en Colab (ícono de clave, panel izquierdo).")
    print("          Después volvé a correr esta celda.")
print()
print("Abrir este notebook desde GitHub (copia versionada):")
print("https://colab.research.google.com/github/mclichas/fotogrametria/blob/main/wizard_planimetria.ipynb")
print()
print("NUNCA sube a GitHub: videos, fotos, frames ni entregables de obra (T11).")
"""
    )
)

# ---------------------------------------------------------------- celda 4
cells.append(
    md(
        """## Paso 1 — Selección de fuente

Elegí el video de obra desde `data/ingest/` (en Drive, D10). La convención de
nombre es `AAAAMMDD-HHMMSS_descripcion.ext` (§8.1). Al seleccionar, se crea
`work/<source_id>/` y se marca el paso como completo en `session.json`.
"""
    )
)

# ---------------------------------------------------------------- celda 5
cells.append(
    code(
        """# @title Paso 1 — Selección de fuente (V1: un video)
import ipywidgets as w
from IPython.display import display

from modules.session import load_session, save_session, source_id_from_filename

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}

candidates = sorted(
    p for p in INGEST_DIR.iterdir()
    if p.is_file() and p.suffix.lower() in VIDEO_EXTS
)

if not candidates:
    print("No hay videos en data/ingest/.")
    print("Subí el video a Drive con nombre AAAAMMDD-HHMMSS_descripcion.ext (carga manual, D10).")
else:
    dropdown = w.Dropdown(options=[(p.name, p) for p in candidates], description="Fuente:")
    button = w.Button(description="Usar esta fuente")
    out = w.Output()

    def on_select(_):
        with out:
            out.clear_output()
            path = dropdown.value
            sid = source_id_from_filename(path.name)
            if sid is None:
                print(f"Nombre inválido: «{path.name}»")
                print("Usá el formato AAAAMMDD-HHMMSS_descripcion.ext (§8.1).")
                return
            state = load_session(WORK_DIR, sid)
            state.source_id = sid
            state.source_path = str(path)
            state.mark_completed("source")
            save_session(WORK_DIR, state)
            print(f"Fuente: {sid}")
            print("Paso 1 completo. Siguiente: Paso 2 (Ingesta).")

    button.on_click(on_select)
    display(dropdown, button, out)
"""
    )
)

# ---------------------------------------------------------------- celda 6
cells.append(
    md(
        """## Paso 2 — Ingesta (M1)

Extrae frames del video, descarta los borrosos y valida el solapamiento
(`blur_threshold` y piso de overlap: T4, aún por fijar). Requiere el Paso 1.
"""
    )
)

# ---------------------------------------------------------------- celda 7
cells.append(
    code(
        """# @title Paso 2 — Ingesta (M1)
from modules.session import latest_session

SESSION = latest_session(WORK_DIR)

if SESSION is None:
    print("Primero completá el Paso 1 (Selección de fuente).")
else:
    try:
        SESSION.require_previous("ingest")
    except Exception as exc:
        print(str(exc))
    else:
        try:
            from modules.video_processor import run_ingest  # M1
            print("M1 implementado: ejecutando ingesta...")
            print("Progreso con IntProgress: ver AGENTS.md §12.")
        except ImportError:
            print("M1 (modules/video_processor.py) aún no está implementado.")
            print("Frames aceptados/rechazados y motivo de rechazo quedan para el módulo.")
"""
    )
)

# ---------------------------------------------------------------- celda 8
cells.append(
    md(
        """## Paso 3 — Calibración de escala (M2 / D3)

Sobre el primer frame aceptado, marcá el rectángulo del objeto de referencia e
ingresá su **ancho y alto reales** en metros. El sistema previsualiza `px/m` en
X e Y y alerta si la relación de aspecto está distorsionada.
"""
    )
)

# ---------------------------------------------------------------- celda 9
cells.append(
    code(
        """# @title Paso 3 — Calibración de escala (M2 / D3)
from modules.session import latest_session

SESSION = latest_session(WORK_DIR)

if SESSION is None:
    print("Primero completá el Paso 1 (Selección de fuente).")
else:
    try:
        SESSION.require_previous("calibration")
    except Exception as exc:
        print(str(exc))
    else:
        frames_dir = WORK_DIR / SESSION.source_id / "frames"
        if not frames_dir.is_dir():
            print("Faltan los frames: completá el Paso 2 (Ingesta).")
        else:
            try:
                from modules.scale_calibrator import run_calibration  # M2
                print("M2 implementado: matplotlib.RectangleSelector sobre el frame.")
            except ImportError:
                print("M2 (modules/scale_calibrator.py) aún no está implementado.")
                print("Requiere el rectángulo del objeto de referencia + ancho y alto reales (D3).")
"""
    )
)

# ---------------------------------------------------------------- celda 10
cells.append(
    md(
        """## Paso 4 — Reconstrucción (M3)

Motor de reconstrucción. **Pendiente de decisión (T2):** MoGe-2 vs COLMAP vs
híbrido — bloqueado por la validación T3 (medir el error sobre un caño real).
"""
    )
)

# ---------------------------------------------------------------- celda 11
cells.append(
    code(
        """# @title Paso 4 — Reconstrucción (M3)
from modules.session import latest_session

SESSION = latest_session(WORK_DIR)

if SESSION is None:
    print("Primero completá el Paso 1 (Selección de fuente).")
else:
    try:
        SESSION.require_previous("reconstruction")
    except Exception as exc:
        print(str(exc))
    else:
        try:
            from modules.reconstruction_engine import run_reconstruction  # M3
            print("M3 implementado.")
        except ImportError:
            print("M3 (modules/reconstruction_engine.py) aún no está implementado.")
            print("Depende de T2 (motor) y T3 (validación de MoGe-2). Ver AGENTS.md §6.")
"""
    )
)

# ---------------------------------------------------------------- celda 12
cells.append(
    md(
        """## Paso 5 — Alineación (M4)

Aplica la escala de calibración (D3) y ajusta el plano de piso a Z=0.
Residuo de piso < 0.015 m (criterio §11.2).
"""
    )
)

# ---------------------------------------------------------------- celda 13
cells.append(
    code(
        """# @title Paso 5 — Alineación (M4)
from modules.session import latest_session

SESSION = latest_session(WORK_DIR)

if SESSION is None:
    print("Primero completá el Paso 1 (Selección de fuente).")
else:
    try:
        SESSION.require_previous("alignment")
    except Exception as exc:
        print(str(exc))
    else:
        try:
            from modules.scale_and_align import run_alignment  # M4
            print("M4 implementado.")
        except ImportError:
            print("M4 (modules/scale_and_align.py) aún no está implementado.")
"""
    )
)

# ---------------------------------------------------------------- celda 14
cells.append(
    md(
        """## Paso 6 — Segmentación (M5)

Detecta planos estructurales, caños y artefactos. Umbral RANSAC de piso: T5.
Ajuste cilíndrico: T22. Detección de cañerías > 1/2\": ≥ 90 % (§11.2).
"""
    )
)

# ---------------------------------------------------------------- celda 15
cells.append(
    code(
        """# @title Paso 6 — Segmentación (M5)
from modules.session import latest_session

SESSION = latest_session(WORK_DIR)

if SESSION is None:
    print("Primero completá el Paso 1 (Selección de fuente).")
else:
    try:
        SESSION.require_previous("segmentation")
    except Exception as exc:
        print(str(exc))
    else:
        try:
            from modules.segmentation_engine import run_segmentation  # M5
            print("M5 implementado.")
        except ImportError:
            print("M5 (modules/segmentation_engine.py) aún no está implementado.")
            print("Bloqueado por T22 (ajuste cilíndrico) y T5 (RANSAC de piso).")
"""
    )
)

# ---------------------------------------------------------------- celda 16
cells.append(
    md(
        """## Paso 7 — Análisis espacial (M6)

Tabla de cotas con su incertidumbre estimada (T17). Las cotas con incertidumbre
> 10 mm (D7) se marcan como **no confiables** (§11.1 bis).
"""
    )
)

# ---------------------------------------------------------------- celda 17
cells.append(
    code(
        """# @title Paso 7 — Análisis espacial (M6)
from modules.session import latest_session

SESSION = latest_session(WORK_DIR)

if SESSION is None:
    print("Primero completá el Paso 1 (Selección de fuente).")
else:
    try:
        SESSION.require_previous("analysis")
    except Exception as exc:
        print(str(exc))
    else:
        try:
            from modules.spatial_analyzer import run_analysis  # M6
            print("M6 implementado.")
        except ImportError:
            print("M6 (modules/spatial_analyzer.py) aún no está implementado.")
            print("Bloqueado por T17 (incertidumbre de cada cota, §11.1 bis).")
"""
    )
)

# ---------------------------------------------------------------- celda 18
cells.append(
    md(
        """## Paso 8 — Exportación (M7 / D12)

Genera `floor_plan_3d.svg` (SVG escrito a mano, XML, sin dependencia nueva) +
`metrics_report.json` en `outputs/` de Drive. Cada cota lleva su ± y su marca de
confiabilidad. DXF (`ezdxf`) queda para V2.
"""
    )
)

# ---------------------------------------------------------------- celda 19
cells.append(
    code(
        """# @title Paso 8 — Exportación (M7 / D12)
from modules.session import latest_session

SESSION = latest_session(WORK_DIR)

if SESSION is None:
    print("Primero completá el Paso 1 (Selección de fuente).")
else:
    try:
        SESSION.require_previous("export")
    except Exception as exc:
        print(str(exc))
    else:
        try:
            from modules.exporter import run_export  # M7
            print("M7 implementado: exportando a outputs/ ...")
        except ImportError:
            print("M7 (modules/exporter.py) aún no está implementado.")
            print("Salida V1: floor_plan_3d.svg + metrics_report.json (D12).")
"""
    )
)

# ---------------------------------------------------------------- celda 20
cells.append(
    md(
        """## Estado del pipeline y próximos pasos

* Pasos 1-3 funcionan cuando existan M1/M2; los pasos 4-8 se habilitan al
  implementar M3-M7 (bloqueados por T2/T3/T17/T22, AGENTS.md §13).
* La corrida se retoma desde `work/<source_id>/session.json` (D10).
* Cuenta dedicada: uso exclusivo para este proyecto y esta carpeta; cualquier
  limitación requiere autorización antes de seguir.
"""
    )
)

# ---------------------------------------------------------------- celda 21
cells.append(
    code(
        """# @title Estado de la corrida actual
from modules.session import latest_session, STEPS

s = latest_session(WORK_DIR)
if s is None:
    print("Todavía no hay ninguna sesión en work/.")
else:
    hecho = s.completed_steps
    pendiente = [p for p in STEPS if p not in hecho]
    print(f"Fuente: {s.source_id}")
    print(f"Completados: {', '.join(hecho) if hecho else '—'}")
    print(f"Pendientes:  {', '.join(pendiente)}")
"""
    )
)

nb = {
    "cells": cells,
    "metadata": {
        "colab": {"provenance": []},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("OK:", OUT)
print("Celdas:", len(cells))