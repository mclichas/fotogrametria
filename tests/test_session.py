"""Tests del estado de sesión del wizard (guardia de orden + persistencia D10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.errors import StepOrderError
from modules.session import (
    SessionState,
    latest_session,
    load_session,
    save_session,
    source_id_from_filename,
)


def test_orden_requiere_paso_anterior() -> None:
    state = SessionState(source_id="x")
    with pytest.raises(StepOrderError):
        state.require_previous("ingest")
    state.mark_completed("source")
    state.require_previous("ingest")  # no debe lanzar


def test_mark_completed_respeta_orden_y_unicidad() -> None:
    state = SessionState(source_id="x")
    state.mark_completed("source")
    state.mark_completed("ingest")
    state.mark_completed("ingest")
    assert state.completed_steps == ["source", "ingest"]
    assert state.next_step == "calibration"


def test_paso_desconocido_lanza_valueerror() -> None:
    with pytest.raises(ValueError):
        SessionState(source_id="x").mark_completed("zzz")


def test_session_roundtrip(tmp_path: Path) -> None:
    state = SessionState(source_id="20261005-081530_bano_principal")
    state.data["nota"] = "prueba"
    state.mark_completed("source")
    path = save_session(tmp_path, state)
    assert path.exists()
    loaded = load_session(tmp_path, state.source_id)
    assert loaded.completed_steps == ["source"]
    assert loaded.next_step == "ingest"
    assert loaded.data == {"nota": "prueba"}


def test_latest_session_detecta_la_mas_reciente(tmp_path: Path) -> None:
    older = SessionState(source_id="a")
    older.mark_completed("source")
    save_session(tmp_path, older)
    newer = SessionState(source_id="b")
    save_session(tmp_path, newer)
    found = latest_session(tmp_path)
    assert found is not None
    assert found.source_id == "b"


def test_latest_session_sin_archivos(tmp_path: Path) -> None:
    assert latest_session(tmp_path) is None


def test_source_id_valido_y_rechazo() -> None:
    assert (
        source_id_from_filename("20261005-081530_bano_principal.mp4")
        == "20261005-081530_bano_principal"
    )
    assert source_id_from_filename("video_sin_formato.mp4") is None