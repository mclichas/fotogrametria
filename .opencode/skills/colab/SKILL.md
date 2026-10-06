---
name: colab
description: Cómo trabajar con comodidad en Google Colab en este proyecto: abrir wizard_planimetria.ipynb desde GitHub (Open in Colab), montar Drive con la cuenta dedicada (D10), secrets (userdata), devolver cambios a GitHub (File → Save a copy in GitHub o git push con PAT), resguardo (qué se versiona y qué nunca, T11), límites del runtime (disco efímero, sesión) y patrón de copiar datos de Drive a /content. Usar al crear o editar celdas del notebook, al dar instrucciones de ejecución en Colab, o al resolver problemas del runtime (instalación, GPU, disco, userdata).
license: MIT
metadata:
  project: planimetria-canerias
  stack: python,colab,ipywidgets,matplotlib
---

# Trabajo cómodo en Google Colab

## Orden de lectura

1. `AGENTS.md`: fuente de verdad (D10 Drive, D11 Colab, D12 SVG, T11 privacidad).
2. La skill `planimetria-pipeline` para convenciones del pipeline y el wizard.

## Reglas que no se negocian

* El notebook **canónico vive en GitHub**, no en Drive. Se abre en Colab con:
  `https://colab.research.google.com/github/mclichas/fotogrametria/blob/main/wizard_planimetria.ipynb`
  Nunca se trabaja sobre la copia efímera pensando que quedó guardada: la sesión
  se borra. Los cambios vuelven a GitHub (ver «Git desde Colab») y el repo se
  re-clona en cada sesión (celda de configuración).
* El acceso a la cuenta de Google es **solo para este proyecto y solo dentro de
  la carpeta compartida**. Cualquier uso fuera de ese alcance pide autorización.
* **Nunca** subir a GitHub (repo **público**, §2.2 de AGENTS.md): videos, fotos,
  frames, nubes ni entregables de obra (T11). El resguardo cubre código +
  notebook + READMEs de estructura.
* Todas las celdas hablan en español; la lógica vive en `modules/` (testeable);
  las celdas solo presentan (AGENTS.md §12).

## Modelo de persistencia — qué vive dónde

| Componente | Dónde vive | ¿Persiste entre sesiones? |
| :--- | :--- | :--- |
| Notebook y código (`wizard_planimetria.ipynb`, `modules/`, `tests/`) | GitHub | **Sí** — versionado; la corrida lo re-clona |
| Entorno de ejecución (VM, GPU, `/content`, librerías instaladas) | Colab | **No** — efímero; se regenera en cada corrida |
| Datos y estado (`data/ingest`, `work/`, `outputs/`, `session.json`) | Google Drive (D10) | **Sí** — persistencia real del pipeline |

Consecuencia: cerrar la sesión de Colab **no pierde trabajo** — pierde el entorno.
La corrida retoma desde `work/<source_id>/session.json` (paso por paso). Si alguien
"no entiende cómo se corre desde GitHub con infra de Colab", esta tabla es la
respuesta: GitHub aporta el documento (el `colab.research.google.com/github/.../...ipynb`
lo abre y levanta runtime nuevo), Colab ejecuta (efímero), Drive guarda datos y
progreso. Los cambios al notebook vuelven a GitHub al final (ver «Git desde Colab»).

## Cómo se usa el wizard

1. Abrir el notebook desde GitHub (link de arriba) con la **cuenta dedicada**.
2. Celdas de configuración primero: clonan el repo a `/content/fotogrametria`,
   montan Drive y crean `data/ingest/`, `work/`, `outputs/` (exist_ok).
3. 8 pasos en orden; las guardias leen `work/<source_id>/session.json`
   (`modules/session.py`). La corrida es **resumible por paso**.
4. Los videos van a `data/ingest/` por **carga manual** (D10), nombre
   `AAAAMMDD-HHMMSS_descripcion.ext` (§8.1).

## Drive (D10)

* `from google.colab import drive; drive.mount('/content/drive')` con la cuenta
  dedicada; rutas: `/content/drive/MyDrive/Fotogrametria/{data/ingest,work,outputs}`.
* El montaje FUSE es **lento con miles de archivos chicos**: copiar el lote a
  `/content` (disco local del VM), procesar ahí y devolver solo resultados.
* Higiene (§2.3): originales + entregables + `session.json` se mantienen; los
  intermedios pesados (nubes, matches, máscaras) se limpian al exportar.

## Secrets (userdata)

* En Colab, panel izquierdo → ícono de clave → «Add new secret», y activar el
  acceso del notebook. Lectura: `from google.colab import userdata; userdata.get('NOMBRE')`.
* Conocido: en el primer «Run all» de la sesión, `userdata` puede fallar por
  timeout. Solución: correr la celda de nuevo.
* Secret del proyecto: `GITHUB_PAT` (Personal Access Token de GitHub, scope
  `repo`) para la celda «Resguardo en GitHub».

## Git desde Colab

* Vía 1 (cero configuración): menú **File → Save a copy in GitHub** del notebook.
  La primera vez Colab pide autorizar el acceso a GitHub (una sola vez y queda).
* Vía 2 (celda «Resguardo en GitHub» del notebook): con `GITHUB_PAT` en secrets,
  configura `user.name`/`user.email`, setea el remote con el token (queda en
  `.git/config`, disco efímero) y hace `git add/commit/push` del notebook +
  `modules/` + `tests/` + `AGENTS.md`. El token nunca se imprime.
* Config local recomendada: `user.name mclichas` / `user.email
  mclichas@users.noreply.github.com`.

## Límites del runtime

| Recurso | Límite | Mitigación |
| :--- | :--- | :--- |
| Disco | ~100 GB, **efímero** | Entregables a Drive; no dejar pesos en `/content` |
| Sesión | máx. ~12 h; ~90 min de inactividad la cortan | `session.json` para retomar (paso por paso) |
| GPU | T4 15 GB, **no garantizada** | Los pasos deben correr también en CPU si es necesario |
| Cuota Drive | 15 GB (cuenta dedicada, D10) | Mantener originales + entregables únicos |

## Instalación de dependencias

* En el runtime, `%pip install` en la celda de configuración (T1: fijar versiones
  exactas **reverificando en PyPI** antes de producción; D6: solo libs libres).
* El runtime ya trae numpy/pandas/matplotlib/opencv; instalar aparte:
  `pydantic`, `open3d`, `scipy`, `scikit-learn`, `ipywidgets`, y `torch` (build
  CPU explícita si se usa MoGe-2 — la build CUDA no sirve sin GPU NVIDIA).
* MoGe-2: pin del commit `b942f00bd` (main saltó a v3.0.0, CUDA-only con
  FlexGEMM); `utils3d` y `pipeline` se instalan desde git con commit fijado.
* No instalar nada en la máquina local del usuario (D11): todo corre en Colab.

## GUI (ipywidgets + matplotlib)

* Los trabajos pesados reportan progreso con `IntProgress` + log, nunca con
  variables compartidas entre celdas.
* Calibración: `matplotlib.RectangleSelector` sobre el primer frame aceptado.
* Validar con los `TC-MOD*` en `tests/` (correr `pytest -q` en el runtime).
* Mensajes de la GUI en español, desde `modules/` (nada de strings sueltos).

## Skills y herramientas externas útiles (búsqueda 2026-10-06)

Instalarlas en `.opencode/skills/` es **decisión del usuario**; no se autoinstalan.

| Recurso | Para qué |
| :--- | :--- |
| `marcinmiklitz/jupyter-notebooks-skill` | Editar `wizard_planimetria.ipynb` programáticamente (nbformat/nbclient/papermill, diffs git-friendly con nbdime) |
| `ali/claude-colab` | Bootstrappear un agente Claude dentro de Colab (skills `ipynb`/`customize`, comando checkpoint a Drive) |
| `google-colab-guide` / `jupyter-notebook-guide` (wentorai) | Guías de buenas prácticas de notebooks y Colab |
| `legout/data-agent-skills` → `working-in-notebooks` | Reproducibilidad y estructura de notebooks |
| `nils-holmberg/ipynb-mcp` | MCP para que un agente controle un Jupyter local vía REST/kernel WS |
| `Emile-Andre/colab-autopilot` | MCP para GPU de Colab headless (solo si se quiere agentizar el runt time; no es la vía actual) |