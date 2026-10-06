"""Estado de sesión del wizard y guardias de orden de pasos (D4/D10/D11).

El estado del pipeline vive en ``work/<source_id>/session.json`` y es la
única fuente de verdad para saber en qué paso está la corrida y permitir
retomarla tras un reinicio de Colab (D10). El notebook (las celdas) solo
muestra widgets y llama a los módulos; toda la lógica de orden y persistencia
vive acá y es testeable sin GUI (AGENTS.md §12).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from modules.errors import StepOrderError

SESSION_FILENAME = "session.json"

# Orden estricto de los pasos del wizard (AGENTS.md §12).
STEPS: tuple[str, ...] = (
    "source",
    "ingest",
    "calibration",
    "reconstruction",
    "alignment",
    "segmentation",
    "analysis",
    "export",
)

PENDING_MESSAGE = (
    "Este paso aún no está implementado: el módulo correspondiente no existe o el "
    "motor está por decidir. Ver AGENTS.md §6 (T2/T3) y §13."
)


class SessionState(BaseModel):
    """Estado persistido del pipeline para un ``source_id``."""

    source_id: str | None = Field(
        default=None, description="Identificador de la fuente (V1: un único video)."
    )
    source_path: str | None = Field(
        default=None, description="Ruta del original en Drive, solo lectura."
    )
    completed_steps: list[str] = Field(
        default_factory=list, description="Pasos terminados, en orden."
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="Resultados serializables por paso."
    )

    @property
    def next_step(self) -> str | None:
        done = set(self.completed_steps)
        for step in STEPS:
            if step not in done:
                return step
        return None

    def is_completed(self, step: str) -> bool:
        return step in self.completed_steps

    def mark_completed(self, step: str) -> None:
        if step not in STEPS:
            raise ValueError(f"Paso desconocido: {step!r}. Válidos: {', '.join(STEPS)}")
        if step not in self.completed_steps:
            self.completed_steps.append(step)

    def require_previous(self, step: str) -> None:
        """Guarda de orden: lanza StepOrderError si el paso anterior no terminó."""
        if step not in STEPS:
            raise ValueError(f"Paso desconocido: {step!r}")
        idx = STEPS.index(step)
        if idx > 0 and not self.is_completed(STEPS[idx - 1]):
            raise StepOrderError(
                f"El paso «{step}» requiere completar antes «{STEPS[idx - 1]}». "
                "Ejecutá las celdas en orden, de arriba hacia abajo."
            )


def session_path(work_dir: Path, source_id: str) -> Path:
    """work/<source_id>/session.json (D10)."""
    return work_dir / source_id / SESSION_FILENAME


def load_session(work_dir: Path, source_id: str) -> SessionState:
    """Lee la sesión; si no existe el archivo, devuelve una vacía (resumible, D10)."""
    path = session_path(work_dir, source_id)
    if not path.exists():
        return SessionState(source_id=source_id)
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    data["source_id"] = data.get("source_id") or source_id
    return SessionState.model_validate(data)


def save_session(work_dir: Path, state: SessionState) -> Path:
    """Persiste la sesión. Crea el directorio si hace falta (exist_ok=True)."""
    if not state.source_id:
        raise ValueError("No se puede persistir una sesión sin source_id.")
    path = session_path(work_dir, state.source_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(state.model_dump(mode="json"), fh, ensure_ascii=False, indent=2)
    return path


def latest_session(work_dir: Path) -> SessionState | None:
    """Devuelve la sesión más reciente (por mtime de session.json) o None."""
    candidates = sorted(
        work_dir.glob(f"*/{SESSION_FILENAME}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None
    path = candidates[0]
    data = json.loads(path.read_text(encoding="utf-8"))
    data["source_id"] = data.get("source_id") or path.parent.name
    return SessionState.model_validate(data)


_SOURCE_RE = re.compile(r"^(?P<ts>\d{8}-\d{6})_(?P<name>[a-z0-9_]+)$")


def source_id_from_filename(filename: str) -> str | None:
    """Deriva el source_id de un original 'AAAAMMDD-HHMMSS_desc' (AGENTS.md §8.1).

    Devuelve None si el nombre no sigue la convención; el wizard lo rechaza con
    el mensaje de nombre válido.
    """
    stem = Path(filename).stem
    return stem if _SOURCE_RE.match(stem) else None