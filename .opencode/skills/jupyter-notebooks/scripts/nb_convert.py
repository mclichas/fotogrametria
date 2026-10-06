#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nbformat>=5.8",
#   "nbconvert>=7.0",
# ]
# ///

"""Convert notebooks to other formats via nbconvert."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1


EXPORTER_MAP = {
    "html": "HTMLExporter",
    "pdf": "PDFExporter",
    "latex": "LatexExporter",
    "script": "ScriptExporter",
    "markdown": "MarkdownExporter",
    "rst": "RSTExporter",
    "slides": "SlidesExporter",
}


def status(message: str) -> None:
    print(message, file=sys.stderr)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def fail(
    message: str, details: dict[str, Any] | None = None, code: int = EXIT_ERROR
) -> None:
    payload: dict[str, Any] = {"ok": False, "error": message}
    if details:
        payload["details"] = details
    emit(payload)
    raise SystemExit(code)


def _load_nbformat():
    try:
        import nbformat  # type: ignore
    except Exception as exc:  # pragma: no cover
        fail("Failed to import nbformat.", details={"exception": str(exc)})
    return nbformat


def load_notebook(path: Path):
    nbformat = _load_nbformat()
    if not path.exists():
        fail("Notebook not found.", details={"path": str(path)})
    try:
        nb = nbformat.read(path, as_version=4)
        nbformat.validate(nb)
    except Exception as exc:
        fail(
            "Input file is not a valid .ipynb notebook.",
            details={"path": str(path), "exception": str(exc)},
        )
    return nb


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert notebooks to HTML/PDF/LaTeX/script/markdown/rst/slides.",
        epilog=(
            "Examples:\n"
            "  uv run scripts/nb_convert.py --input notebook.ipynb --to html\n"
            "  uv run scripts/nb_convert.py --input notebook.ipynb --to pdf --output report.pdf\n"
            "  uv run scripts/nb_convert.py --input notebook.ipynb --to markdown --strip-output\n"
            "  uv run scripts/nb_convert.py --input notebook.ipynb --to html --execute --kernel python3"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Input notebook path.")
    parser.add_argument(
        "--to",
        required=True,
        choices=sorted(EXPORTER_MAP.keys()),
        help="Target format.",
    )
    parser.add_argument("--output", help="Output file path.")
    parser.add_argument("--template", help="Optional nbconvert template name/path.")

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute notebook before conversion using nbconvert.",
    )
    parser.add_argument("--kernel", help="Kernel name used with --execute.")
    parser.add_argument(
        "--timeout", type=int, default=300, help="Per-cell timeout for --execute."
    )
    parser.add_argument("--working-dir", help="Working directory for --execute.")

    parser.add_argument(
        "--strip-output",
        action="store_true",
        help="Clear outputs and execution counts before export.",
    )
    return parser


def get_exporter_class(format_name: str):
    try:
        from nbconvert import exporters  # type: ignore
    except Exception as exc:
        fail("Failed to import nbconvert exporters.", details={"exception": str(exc)})

    class_name = EXPORTER_MAP[format_name]
    exporter_cls = getattr(exporters, class_name, None)
    if exporter_cls is None:
        fail(
            "Unsupported exporter.",
            details={"format": format_name, "exporter": class_name},
        )
    return exporter_cls


def maybe_execute(nb: Any, args: argparse.Namespace) -> Any:
    if not args.execute:
        return nb

    try:
        from nbconvert.preprocessors import ExecutePreprocessor  # type: ignore
    except Exception as exc:
        fail(
            "Failed to import nbconvert ExecutePreprocessor.",
            details={"exception": str(exc)},
        )

    status("Executing notebook before conversion (nbconvert --execute behavior).")
    ep = ExecutePreprocessor(timeout=args.timeout, kernel_name=args.kernel)
    resources = (
        {"metadata": {"path": args.working_dir}}
        if args.working_dir
        else {"metadata": {}}
    )

    try:
        ep.preprocess(nb, resources)
    except Exception as exc:
        fail("Execution during conversion failed.", details={"exception": str(exc)})
    return nb


def maybe_strip_output(nb: Any) -> Any:
    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
    return nb


def resolve_output_path(
    input_path: Path, args: argparse.Namespace, exporter: Any
) -> Path:
    if args.output:
        return Path(args.output)
    ext = exporter.file_extension or ""
    if not ext.startswith(".") and ext:
        ext = f".{ext}"
    if not ext:
        ext = ".txt"
    return input_path.with_suffix(ext)


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    nb = load_notebook(input_path)
    working_nb = copy.deepcopy(nb)

    if args.strip_output:
        working_nb = maybe_strip_output(working_nb)

    if args.execute:
        working_nb = maybe_execute(working_nb, args)

    exporter_cls = get_exporter_class(args.to)
    exporter = exporter_cls()
    if args.template:
        setattr(exporter, "template_name", args.template)

    try:
        body, resources = exporter.from_notebook_node(working_nb)
    except Exception as exc:
        details = {"exception": str(exc), "format": args.to}
        if args.to == "pdf":
            details["hint"] = (
                "PDF conversion requires external tools (e.g., pandoc/TeX or webpdf stack) configured for nbconvert."
            )
        fail("Notebook conversion failed.", details=details)

    output_path = resolve_output_path(input_path, args, exporter)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(body, bytes):
        output_path.write_bytes(body)
        size_bytes = len(body)
    else:
        output_path.write_text(body, encoding="utf-8")
        size_bytes = len(body.encode("utf-8"))

    status(f"Converted notebook: {input_path} -> {output_path}")
    emit(
        {
            "ok": True,
            "action": "convert",
            "input": str(input_path),
            "output": str(output_path),
            "format": args.to,
            "executed": bool(args.execute),
            "stripped_output": bool(args.strip_output),
            "size_bytes": size_bytes,
            "resources_keys": sorted(list((resources or {}).keys())),
        }
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
