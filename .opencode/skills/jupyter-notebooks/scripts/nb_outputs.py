#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nbformat>=5.8",
# ]
# ///

"""Inspect, strip, and extract notebook outputs."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1

MUTATING_COMMANDS = {"strip-all", "strip-cells", "clear-counts"}


IMAGE_MIME_TO_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/svg+xml": "svg",
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


def write_notebook(nb: Any, path: Path) -> None:
    nbformat = _load_nbformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, path)


def parse_indexes(raw: str) -> list[int]:
    try:
        values = [int(v.strip()) for v in raw.split(",") if v.strip()]
    except ValueError as exc:
        fail(
            "Invalid --indexes list. Use comma-separated integers.",
            details={"input": raw, "exception": str(exc)},
        )
    if any(v < 0 for v in values):
        fail("Indexes must be non-negative.", details={"indexes": values})
    return values


def output_size_bytes(output: dict[str, Any]) -> int:
    total = 0
    output_type = output.get("output_type")

    if output_type == "stream":
        text = output.get("text", "")
        if isinstance(text, list):
            text = "".join(str(x) for x in text)
        total += str(text).encode("utf-8").__len__()

    if output_type in {"display_data", "execute_result"}:
        data = output.get("data", {})
        if isinstance(data, dict):
            for value in data.values():
                if isinstance(value, bytes):
                    total += len(value)
                elif isinstance(value, list):
                    total += "".join(str(x) for x in value).encode("utf-8").__len__()
                else:
                    total += str(value).encode("utf-8").__len__()

    if output_type == "error":
        traceback_lines = output.get("traceback", [])
        if isinstance(traceback_lines, list):
            total += (
                "\n".join(str(x) for x in traceback_lines).encode("utf-8").__len__()
            )

    return total


def gather_outputs(nb: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        for out_idx, output in enumerate(cell.get("outputs", [])):
            data = output.get("data", {}) if isinstance(output, dict) else {}
            mime_types = sorted(data.keys()) if isinstance(data, dict) else []
            items.append(
                {
                    "cell_index": idx,
                    "output_index": out_idx,
                    "output_type": output.get("output_type"),
                    "mime_types": mime_types,
                    "size_bytes": output_size_bytes(output),
                }
            )
    return items


def resolve_write_path(args: argparse.Namespace) -> Path | None:
    if args.command not in MUTATING_COMMANDS:
        return None
    if args.output:
        return Path(args.output)
    if args.in_place:
        return Path(args.input)
    fail(
        "Mutating command requires --output or --in-place.",
        details={"command": args.command},
    )
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage notebook outputs (list, strip, extract images, size).",
        epilog=(
            "Examples:\n"
            "  uv run scripts/nb_outputs.py --input notebook.ipynb list\n"
            "  uv run scripts/nb_outputs.py --input notebook.ipynb strip-all --in-place\n"
            "  uv run scripts/nb_outputs.py --input notebook.ipynb strip-cells --indexes 2,3\n"
            "  uv run scripts/nb_outputs.py --input notebook.ipynb extract-images --output-dir tmp/images"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Input notebook path.")
    parser.add_argument("--output", help="Output notebook for mutating commands.")
    parser.add_argument(
        "--in-place", action="store_true", help="Write mutations to --input."
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all outputs with cell index/type/size.")
    sub.add_parser("size", help="Total output byte size summary.")
    sub.add_parser("strip-all", help="Clear all code-cell outputs.")

    strip_cells = sub.add_parser(
        "strip-cells", help="Clear outputs from selected code-cell indexes."
    )
    strip_cells.add_argument(
        "--indexes", required=True, help="Comma-separated cell indexes, e.g. 1,4,7"
    )

    extract = sub.add_parser(
        "extract-images", help="Extract image outputs (png/jpg/svg) to files."
    )
    extract.add_argument(
        "--output-dir", required=True, help="Directory for extracted images."
    )

    sub.add_parser(
        "clear-counts", help="Set all code cell execution_count values to null."
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    nb = load_notebook(input_path)
    cmd = args.command

    result: dict[str, Any]

    if cmd == "list":
        outputs = gather_outputs(nb)
        result = {
            "ok": True,
            "action": cmd,
            "output_count": len(outputs),
            "total_size_bytes": sum(item["size_bytes"] for item in outputs),
            "outputs": outputs,
        }

    elif cmd == "size":
        outputs = gather_outputs(nb)
        result = {
            "ok": True,
            "action": cmd,
            "output_count": len(outputs),
            "total_size_bytes": sum(item["size_bytes"] for item in outputs),
            "largest_outputs": sorted(
                outputs, key=lambda x: x["size_bytes"], reverse=True
            )[:10],
        }

    elif cmd == "strip-all":
        changed_cells = 0
        removed_outputs = 0
        for cell in nb.cells:
            if cell.cell_type != "code":
                continue
            if cell.get("outputs"):
                changed_cells += 1
                removed_outputs += len(cell.get("outputs", []))
            cell.outputs = []
        result = {
            "ok": True,
            "action": cmd,
            "changed_cells": changed_cells,
            "removed_outputs": removed_outputs,
        }

    elif cmd == "strip-cells":
        indexes = parse_indexes(args.indexes)
        invalid = [idx for idx in indexes if idx >= len(nb.cells)]
        if invalid:
            fail(
                "Some indexes are out of range.",
                details={"invalid_indexes": invalid, "cell_count": len(nb.cells)},
            )

        changed_cells = 0
        removed_outputs = 0
        for idx in indexes:
            cell = nb.cells[idx]
            if cell.cell_type != "code":
                continue
            if cell.get("outputs"):
                changed_cells += 1
                removed_outputs += len(cell.get("outputs", []))
            cell.outputs = []
        result = {
            "ok": True,
            "action": cmd,
            "requested_indexes": indexes,
            "changed_cells": changed_cells,
            "removed_outputs": removed_outputs,
        }

    elif cmd == "extract-images":
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        extracted: list[dict[str, Any]] = []

        for cell_idx, cell in enumerate(nb.cells):
            if cell.cell_type != "code":
                continue
            for out_idx, output in enumerate(cell.get("outputs", [])):
                data = output.get("data", {}) if isinstance(output, dict) else {}
                if not isinstance(data, dict):
                    continue
                for mime, ext in IMAGE_MIME_TO_EXT.items():
                    if mime not in data:
                        continue
                    value = data[mime]
                    file_path = (
                        out_dir / f"cell_{cell_idx:03d}_output_{out_idx:03d}.{ext}"
                    )
                    if mime in {"image/png", "image/jpeg"}:
                        raw = "".join(value) if isinstance(value, list) else str(value)
                        try:
                            file_path.write_bytes(base64.b64decode(raw))
                        except Exception as exc:
                            fail(
                                "Failed to decode image output.",
                                details={
                                    "mime": mime,
                                    "cell_index": cell_idx,
                                    "exception": str(exc),
                                },
                            )
                    else:  # svg
                        raw_text = (
                            "".join(value) if isinstance(value, list) else str(value)
                        )
                        file_path.write_text(raw_text, encoding="utf-8")

                    extracted.append(
                        {
                            "cell_index": cell_idx,
                            "output_index": out_idx,
                            "mime": mime,
                            "path": str(file_path),
                            "size_bytes": file_path.stat().st_size,
                        }
                    )

        result = {
            "ok": True,
            "action": cmd,
            "output_dir": str(out_dir),
            "extracted_count": len(extracted),
            "files": extracted,
        }

    elif cmd == "clear-counts":
        changed_cells = 0
        for cell in nb.cells:
            if cell.cell_type != "code":
                continue
            if cell.get("execution_count") is not None:
                changed_cells += 1
            cell.execution_count = None
        result = {"ok": True, "action": cmd, "changed_cells": changed_cells}

    else:  # pragma: no cover
        fail("Unknown command.", details={"command": cmd})

    out_path = resolve_write_path(args)
    if out_path is not None:
        write_notebook(nb, out_path)
        status(f"Wrote notebook: {out_path}")
        result["output"] = str(out_path)

    emit(result)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
