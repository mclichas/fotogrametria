#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nbformat>=5.8",
# ]
# ///

"""Notebook and cell metadata operations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1

MUTATING_COMMANDS = {
    "set-kernel",
    "set-notebook-key",
    "delete-notebook-key",
    "set-cell-key",
    "delete-cell-key",
    "add-tag",
    "remove-tag",
    "tag-parameters",
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


def parse_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        fail("Invalid JSON value.", details={"input": value, "exception": str(exc)})


def validate_index(nb: Any, index: int) -> None:
    if index < 0 or index >= len(nb.cells):
        fail(
            "Cell index out of range.",
            details={"index": index, "cell_count": len(nb.cells)},
        )


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
        description="Read/write notebook and cell metadata, including tags.",
        epilog=(
            "Examples:\n"
            "  uv run scripts/nb_metadata.py --input notebook.ipynb show-notebook\n"
            "  uv run scripts/nb_metadata.py --input notebook.ipynb set-kernel --name python3 --display-name 'Python 3' --language python\n"
            "  uv run scripts/nb_metadata.py --input notebook.ipynb add-tag --index 2 --tag parameters"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Input notebook path.")
    parser.add_argument(
        "--output", help="Optional output notebook for mutating commands."
    )
    parser.add_argument(
        "--in-place", action="store_true", help="Write mutations to --input."
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show-notebook", help="Show notebook-level metadata.")

    get_key = sub.add_parser("get-notebook-key", help="Get notebook metadata key.")
    get_key.add_argument("--key", required=True)

    set_key = sub.add_parser(
        "set-notebook-key", help="Set notebook metadata key to JSON value."
    )
    set_key.add_argument("--key", required=True)
    set_key.add_argument("--value-json", required=True)

    del_key = sub.add_parser(
        "delete-notebook-key", help="Delete notebook metadata key."
    )
    del_key.add_argument("--key", required=True)

    set_kernel = sub.add_parser(
        "set-kernel", help="Set notebook kernelspec and language_info."
    )
    set_kernel.add_argument("--name", required=True)
    set_kernel.add_argument("--display-name", required=True)
    set_kernel.add_argument("--language", required=True)

    show_cell = sub.add_parser("show-cell", help="Show metadata for a specific cell.")
    show_cell.add_argument("--index", type=int, required=True)

    set_cell = sub.add_parser(
        "set-cell-key", help="Set cell metadata key to JSON value."
    )
    set_cell.add_argument("--index", type=int, required=True)
    set_cell.add_argument("--key", required=True)
    set_cell.add_argument("--value-json", required=True)

    del_cell = sub.add_parser("delete-cell-key", help="Delete cell metadata key.")
    del_cell.add_argument("--index", type=int, required=True)
    del_cell.add_argument("--key", required=True)

    list_tags = sub.add_parser(
        "list-tags", help="List all tags and their cell indexes."
    )
    list_tags.add_argument("--index", type=int, help="Optional cell index filter.")

    add_tag = sub.add_parser("add-tag", help="Add tag to a cell.")
    add_tag.add_argument("--index", type=int, required=True)
    add_tag.add_argument("--tag", required=True)

    remove_tag = sub.add_parser("remove-tag", help="Remove tag from a cell.")
    remove_tag.add_argument("--index", type=int, required=True)
    remove_tag.add_argument("--tag", required=True)

    param_tag = sub.add_parser(
        "tag-parameters", help="Add papermill 'parameters' tag to a cell."
    )
    param_tag.add_argument("--index", type=int, required=True)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    nb = load_notebook(input_path)
    cmd = args.command

    result: dict[str, Any]

    if cmd == "show-notebook":
        result = {"ok": True, "action": cmd, "metadata": dict(nb.metadata)}

    elif cmd == "get-notebook-key":
        result = {
            "ok": True,
            "action": cmd,
            "key": args.key,
            "exists": args.key in nb.metadata,
            "value": nb.metadata.get(args.key),
        }

    elif cmd == "set-notebook-key":
        nb.metadata[args.key] = parse_json(args.value_json)
        result = {
            "ok": True,
            "action": cmd,
            "key": args.key,
            "value": nb.metadata[args.key],
        }

    elif cmd == "delete-notebook-key":
        existed = args.key in nb.metadata
        if existed:
            del nb.metadata[args.key]
        result = {"ok": True, "action": cmd, "key": args.key, "deleted": existed}

    elif cmd == "set-kernel":
        nb.metadata.setdefault("kernelspec", {})
        nb.metadata["kernelspec"].update(
            {
                "name": args.name,
                "display_name": args.display_name,
                "language": args.language,
            }
        )
        nb.metadata.setdefault("language_info", {})
        nb.metadata["language_info"]["name"] = args.language
        result = {
            "ok": True,
            "action": cmd,
            "kernelspec": dict(nb.metadata.get("kernelspec", {})),
            "language_info": dict(nb.metadata.get("language_info", {})),
        }

    elif cmd == "show-cell":
        validate_index(nb, args.index)
        result = {
            "ok": True,
            "action": cmd,
            "index": args.index,
            "metadata": dict(nb.cells[args.index].metadata),
        }

    elif cmd == "set-cell-key":
        validate_index(nb, args.index)
        value = parse_json(args.value_json)
        nb.cells[args.index].metadata[args.key] = value
        result = {
            "ok": True,
            "action": cmd,
            "index": args.index,
            "key": args.key,
            "value": value,
        }

    elif cmd == "delete-cell-key":
        validate_index(nb, args.index)
        existed = args.key in nb.cells[args.index].metadata
        if existed:
            del nb.cells[args.index].metadata[args.key]
        result = {
            "ok": True,
            "action": cmd,
            "index": args.index,
            "key": args.key,
            "deleted": existed,
        }

    elif cmd == "list-tags":
        if args.index is not None:
            validate_index(nb, args.index)
            tags = list(nb.cells[args.index].metadata.get("tags", []))
            result = {"ok": True, "action": cmd, "index": args.index, "tags": tags}
        else:
            tag_map: dict[str, list[int]] = {}
            for idx, cell in enumerate(nb.cells):
                for tag in cell.metadata.get("tags", []):
                    tag_map.setdefault(tag, []).append(idx)
            result = {"ok": True, "action": cmd, "tags": tag_map}

    elif cmd == "add-tag":
        validate_index(nb, args.index)
        tags = list(nb.cells[args.index].metadata.get("tags", []))
        if args.tag not in tags:
            tags.append(args.tag)
        nb.cells[args.index].metadata["tags"] = tags
        result = {"ok": True, "action": cmd, "index": args.index, "tags": tags}

    elif cmd == "remove-tag":
        validate_index(nb, args.index)
        tags = list(nb.cells[args.index].metadata.get("tags", []))
        nb.cells[args.index].metadata["tags"] = [t for t in tags if t != args.tag]
        result = {
            "ok": True,
            "action": cmd,
            "index": args.index,
            "tags": list(nb.cells[args.index].metadata.get("tags", [])),
        }

    elif cmd == "tag-parameters":
        validate_index(nb, args.index)
        tags = list(nb.cells[args.index].metadata.get("tags", []))
        if "parameters" not in tags:
            tags.append("parameters")
        nb.cells[args.index].metadata["tags"] = tags
        result = {"ok": True, "action": cmd, "index": args.index, "tags": tags}

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
