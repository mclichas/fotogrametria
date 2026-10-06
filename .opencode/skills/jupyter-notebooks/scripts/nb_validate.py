#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nbformat>=5.8",
# ]
# ///

"""Validate notebook schema and operational lint rules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_ISSUES = 1
EXIT_RUNTIME = 2


def status(message: str) -> None:
    print(message, file=sys.stderr)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def fail_runtime(message: str, details: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"ok": False, "error": message}
    if details:
        payload["details"] = details
    emit(payload)
    raise SystemExit(EXIT_RUNTIME)


def _load_nbformat():
    try:
        import nbformat  # type: ignore
    except Exception as exc:  # pragma: no cover
        fail_runtime("Failed to import nbformat.", details={"exception": str(exc)})
    return nbformat


def issue(
    code: str, severity: str, message: str, cell_index: int | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "message": message,
    }
    if cell_index is not None:
        payload["cell_index"] = cell_index
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Schema validation and operational linting for .ipynb notebooks.",
        epilog=(
            "Examples:\n"
            "  uv run scripts/nb_validate.py --input notebook.ipynb\n"
            "  uv run scripts/nb_validate.py --input notebook.ipynb --forbid-outputs\n"
            "  uv run scripts/nb_validate.py --input notebook.ipynb --max-lines-per-cell 250"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Notebook path.")
    parser.add_argument(
        "--max-lines-per-cell",
        type=int,
        default=400,
        help="Warn when cells exceed this many lines (0 disables).",
    )
    parser.add_argument(
        "--forbid-outputs",
        action="store_true",
        help="Flag any cell output as an error.",
    )
    parser.add_argument(
        "--allow-empty-cells",
        action="store_true",
        help="Disable empty source cell rule.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    path = Path(args.input)
    nbformat = _load_nbformat()

    if not path.exists():
        fail_runtime("Notebook not found.", details={"path": str(path)})

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail_runtime(
            "Failed to parse notebook JSON.",
            details={"path": str(path), "exception": str(exc)},
        )

    issues: list[dict[str, Any]] = []

    nbformat_version = raw.get("nbformat")
    if not isinstance(nbformat_version, int) or nbformat_version < 4:
        issues.append(
            issue(
                "E_NBFORMAT",
                "error",
                "Notebook format is older than v4 or missing nbformat.",
            )
        )

    try:
        nb = nbformat.from_dict(raw)
    except Exception as exc:
        issues.append(
            issue("E_PARSE", "error", f"Failed to convert JSON to notebook node: {exc}")
        )
        emit(
            {
                "ok": False,
                "input": str(path),
                "valid_schema": False,
                "issues": issues,
                "summary": {
                    "total": len(issues),
                    "error": sum(1 for i in issues if i["severity"] == "error"),
                    "warning": sum(1 for i in issues if i["severity"] == "warning"),
                    "info": sum(1 for i in issues if i["severity"] == "info"),
                },
            }
        )
        return EXIT_ISSUES

    valid_schema = True
    try:
        nbformat.validate(nb)
    except Exception as exc:
        valid_schema = False
        issues.append(issue("E_SCHEMA", "error", f"Schema validation failed: {exc}"))

    kernelspec = (
        nb.metadata.get("kernelspec", {}) if isinstance(nb.metadata, dict) else {}
    )
    if not isinstance(kernelspec, dict) or not kernelspec.get("name"):
        issues.append(
            issue("E_KERNEL", "error", "Missing notebook metadata.kernelspec.name.")
        )

    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()

    for idx, cell in enumerate(nb.cells):
        cell_id = cell.get("id")
        if isinstance(cell_id, str):
            if cell_id in seen_ids:
                duplicate_ids.add(cell_id)
            seen_ids.add(cell_id)

        source = cell.get("source", "")
        if (
            not args.allow_empty_cells
            and isinstance(source, str)
            and source.strip() == ""
        ):
            issues.append(
                issue("W_EMPTY", "warning", "Cell source is empty.", cell_index=idx)
            )

        if args.max_lines_per_cell > 0 and isinstance(source, str):
            line_count = len(source.splitlines())
            if line_count > args.max_lines_per_cell:
                issues.append(
                    issue(
                        "W_LONG",
                        "warning",
                        f"Cell has {line_count} lines (threshold={args.max_lines_per_cell}).",
                        cell_index=idx,
                    )
                )

        if cell.get("cell_type") != "code":
            continue

        outputs = cell.get("outputs", [])
        execution_count = cell.get("execution_count")

        if execution_count is not None and not outputs:
            issues.append(
                issue(
                    "W_STALE_EXEC_COUNT",
                    "warning",
                    "Code cell has execution_count but no outputs.",
                    cell_index=idx,
                )
            )

        if execution_count is None and outputs:
            issues.append(
                issue(
                    "W_STALE_OUTPUTS",
                    "warning",
                    "Code cell has outputs but execution_count is null.",
                    cell_index=idx,
                )
            )

        if outputs:
            sev = "error" if args.forbid_outputs else "info"
            issues.append(
                issue(
                    "I_OUTPUTS" if not args.forbid_outputs else "E_OUTPUTS",
                    sev,
                    "Code cell contains outputs.",
                    cell_index=idx,
                )
            )

    if duplicate_ids:
        issues.append(
            issue(
                "E_DUPLICATE_ID",
                "error",
                f"Duplicate cell ids detected: {sorted(duplicate_ids)}",
            )
        )

    summary = {
        "total": len(issues),
        "error": sum(1 for i in issues if i["severity"] == "error"),
        "warning": sum(1 for i in issues if i["severity"] == "warning"),
        "info": sum(1 for i in issues if i["severity"] == "info"),
    }

    status(f"Validated notebook: {path}")
    emit(
        {
            "ok": summary["error"] == 0 and summary["warning"] == 0,
            "input": str(path),
            "valid_schema": valid_schema,
            "issues": issues,
            "summary": summary,
        }
    )

    blocking_issue_count = summary["error"] + summary["warning"]
    return EXIT_ISSUES if blocking_issue_count > 0 else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
