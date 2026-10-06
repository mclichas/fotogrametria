#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nbformat>=5.8",
# ]
# ///

"""Create Jupyter notebooks from blank/template/script sources."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1


def status(message: str) -> None:
    print(message, file=sys.stderr)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def fail(
    message: str, code: int = EXIT_ERROR, details: dict[str, Any] | None = None
) -> None:
    payload: dict[str, Any] = {"ok": False, "error": message}
    if details:
        payload["details"] = details
    emit(payload)
    raise SystemExit(code)


def _load_nbformat():
    try:
        import nbformat  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        fail(
            "Failed to import nbformat. Install dependencies first.",
            details={"exception": str(exc)},
        )
    return nbformat


def read_notebook(path: Path):
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


def parse_json(text: str | None, default: Any) -> Any:
    if text is None:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        fail("Invalid JSON payload.", details={"input": text, "exception": str(exc)})


def assets_template_path(template_name: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / "assets" / "templates" / f"{template_name}.ipynb"


def ensure_cell(
    nb: Any, source: str, cell_type: str = "code", position: int | None = None
) -> int:
    nbformat = _load_nbformat()
    if cell_type == "markdown":
        cell = nbformat.v4.new_markdown_cell(source=source)
    elif cell_type == "raw":
        cell = nbformat.v4.new_raw_cell(source=source)
    else:
        cell = nbformat.v4.new_code_cell(source=source)

    if position is None or position >= len(nb.cells):
        nb.cells.append(cell)
        return len(nb.cells) - 1

    if position < 0:
        fail("Position cannot be negative.", details={"position": position})
    nb.cells.insert(position, cell)
    return position


def create_blank_notebook(
    kernel_name: str, kernel_display_name: str, language: str
) -> Any:
    nbformat = _load_nbformat()
    nb = nbformat.v4.new_notebook()
    nb.metadata.setdefault("kernelspec", {})
    nb.metadata["kernelspec"].update(
        {
            "name": kernel_name,
            "display_name": kernel_display_name,
            "language": language,
        }
    )
    nb.metadata.setdefault("language_info", {})
    nb.metadata["language_info"].update({"name": language})
    return nb


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create notebooks from blank/template/script sources, or inject a script "
            "as a single cell into an existing notebook."
        ),
        epilog=(
            "Examples:\n"
            "  uv run scripts/nb_create.py --output tmp/blank.ipynb\n"
            "  uv run scripts/nb_create.py --template data-analysis --output tmp/eda.ipynb\n"
            "  uv run scripts/nb_create.py --from-script analysis_step.py --output tmp/from_script.ipynb\n"
            "  uv run scripts/nb_create.py --from-script step.py --inject-into notebook.ipynb --position 3 --in-place"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--output", help="Output notebook path.")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Write back to --inject-into when injecting.",
    )
    parser.add_argument(
        "--template",
        choices=["blank", "data-analysis", "parameterised", "report"],
        help="Create from built-in template.",
    )
    parser.add_argument(
        "--from-script", help="Create a notebook from a .py script as one code cell."
    )
    parser.add_argument(
        "--inject-into", help="Existing notebook path to inject generated cells into."
    )
    parser.add_argument(
        "--position",
        type=int,
        help="Insert position for injected cells (default: append).",
    )
    parser.add_argument(
        "--cells", nargs="*", default=[], help="Initial code cells to append."
    )
    parser.add_argument(
        "--markdown-cells",
        nargs="*",
        default=[],
        help="Initial markdown cells to append.",
    )
    parser.add_argument(
        "--kernel-name", default="python3", help="Kernel name (default: python3)."
    )
    parser.add_argument(
        "--kernel-display-name", default="Python 3", help="Kernel display name."
    )
    parser.add_argument(
        "--language", default="python", help="Notebook language (default: python)."
    )
    parser.add_argument(
        "--metadata-json",
        help="Additional notebook metadata as JSON object, merged at notebook level.",
    )
    return parser


def resolve_target_path(args: argparse.Namespace) -> Path:
    if args.inject_into:
        inject_path = Path(args.inject_into)
        if args.output:
            return Path(args.output)
        if args.in_place:
            return inject_path
        fail("Injection mode requires --output or --in-place.")

    if not args.output:
        fail("--output is required when not using --inject-into.")
    if args.in_place:
        fail("--in-place is only valid with --inject-into.")
    return Path(args.output)


def main() -> int:
    args = build_parser().parse_args()
    target = resolve_target_path(args)

    if args.inject_into:
        nb = read_notebook(Path(args.inject_into))
        action = "inject"
    else:
        action = "create"
        if args.template:
            template_path = assets_template_path(args.template)
            if not template_path.exists():
                fail(
                    "Template not found.",
                    details={"template": args.template, "path": str(template_path)},
                )
            nb = read_notebook(template_path)
            nb = deepcopy(nb)
        elif args.from_script:
            nb = create_blank_notebook(
                args.kernel_name, args.kernel_display_name, args.language
            )
        else:
            nb = create_blank_notebook(
                args.kernel_name, args.kernel_display_name, args.language
            )

    inserted_indexes: list[int] = []
    cursor = args.position

    if args.from_script:
        script_path = Path(args.from_script)
        if not script_path.exists():
            fail("Script file not found.", details={"path": str(script_path)})
        source = script_path.read_text(encoding="utf-8")
        idx = ensure_cell(nb, source=source, cell_type="code", position=cursor)
        inserted_indexes.append(idx)
        if cursor is not None:
            cursor += 1

    for source in args.cells:
        idx = ensure_cell(nb, source=source, cell_type="code", position=cursor)
        inserted_indexes.append(idx)
        if cursor is not None:
            cursor += 1

    for source in args.markdown_cells:
        idx = ensure_cell(nb, source=source, cell_type="markdown", position=cursor)
        inserted_indexes.append(idx)
        if cursor is not None:
            cursor += 1

    if not args.inject_into:
        nb.metadata.setdefault("kernelspec", {})
        nb.metadata["kernelspec"].update(
            {
                "name": args.kernel_name,
                "display_name": args.kernel_display_name,
                "language": args.language,
            }
        )
        nb.metadata.setdefault("language_info", {})
        nb.metadata["language_info"].update({"name": args.language})

    additional_metadata = parse_json(args.metadata_json, default={})
    if additional_metadata:
        if not isinstance(additional_metadata, dict):
            fail("--metadata-json must be a JSON object.")
        nb.metadata.update(additional_metadata)

    write_notebook(nb, target)
    status(f"Wrote notebook: {target}")

    emit(
        {
            "ok": True,
            "action": action,
            "output": str(target),
            "cell_count": len(nb.cells),
            "inserted_cell_indexes": inserted_indexes,
        }
    )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
