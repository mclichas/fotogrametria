"""Excepciones de dominio del pipeline (AGENTS.md §7.1).

Todas heredan de :class:`PipelineError` para que el wizard y el CLI puedan
capturarlas en un solo lugar y traducirlas a mensajes accionables en español.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base de todos los errores de dominio del pipeline."""


class InsufficientOverlapError(PipelineError):
    """Corte de cámara sostenido: el solapamiento entre frames no alcanza (M1)."""


class InvalidDimensionValueError(PipelineError):
    """Dimensión de calibración inválida: ancho/alto <= 0 o no numérico (M2)."""


class ReconstructionFailureError(PipelineError):
    """La reconstrucción no registró suficientes imágenes o falló (M3)."""


class SegmentationFailureError(PipelineError):
    """La segmentación no produjo entidades válidas (M5)."""


class CalibrationError(PipelineError):
    """La calibración no puede resolverse: frame faltante, distorsión, o bbox nulo (M2/M4)."""


class ExportError(PipelineError):
    """La exportación del plano (SVG V1 / DXF V2) o del reporte falló (M7)."""


class StepOrderError(PipelineError):
    """El wizard intentó ejecutar un paso sin haber completado el anterior (D4)."""