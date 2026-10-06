#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nbformat>=5.8",
# ]
# ///

"""Cell CRUD and search operations for Jupyter notebooks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1


MUTATING_COMMANDS = {
    "add",
    "update",
    "delete",
    "move",
    "insert-bulk",
    "delete-range",
    "metadata-set",
    "tags-add",
    "tags-remove",
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
        fail("Invalid JSON input.", details={"input": value, "exception": str(exc)})


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


def build_preview(source: str, max_len: int = 120) -> str:
    first_line = source.splitlines()[0] if source.splitlines() else ""
    first_line = first_line.strip()
    return (
        (first_line[: max_len - 1] + "…") if len(first_line) > max_len else first_line
    )


def new_cell(cell_type: str, source: str, metadata: dict[str, Any] | None = None):
    nbformat = _load_nbformat()
    metadata = metadata or {}
    if cell_type == "markdown":
        cell = nbformat.v4.new_markdown_cell(source=source)
    elif cell_type == "raw":
        cell = nbformat.v4.new_raw_cell(source=source)
    else:
        cell = nbformat.v4.new_code_cell(source=source)
    cell.metadata.update(metadata)
    return cell


def list_cells(nb: Any) -> dict[str, Any]:
    items = []
    for i, cell in enumerate(nb.cells):
        tags = list(cell.metadata.get("tags", []))
        items.append(
            {
                "index": i,
                "cell_type": cell.cell_type,
                "preview": build_preview(cell.source),
                "tags": tags,
                "execution_count": getattr(cell, "execution_count", None),
            }
        )
    return {"ok": True, "action": "list", "cell_count": len(nb.cells), "cells": items}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cell CRUD, metadata/tag management, and search for .ipynb files.",
        epilog=(
            "Examples:\n"
            "  uv run scripts/nb_cells.py --input notebook.ipynb list\n"
            "  uv run scripts/nb_cells.py --input notebook.ipynb add --cell-type code --source \"print('hi')\"\n"
            "  uv run scripts/nb_cells.py --input notebook.ipynb move --from-index 3 --to-index 1\n"
            '  uv run scripts/nb_cells.py --input notebook.ipynb search --pattern "read_csv" --regex'
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Input notebook path.")
    parser.add_argument(
        "--output", help="Optional output notebook path for mutating commands."
    )
    parser.add_argument(
        "--in-place", action="store_true", help="Write mutations to --input."
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "list", help="List cells with index/type/preview/tags/execution_count."
    )

    get_cmd = sub.add_parser("get", help="Get full cell content by index.")
    get_cmd.add_argument("--index", type=int, required=True)

    add_cmd = sub.add_parser("add", help="Add a cell at position or append.")
    add_cmd.add_argument(
        "--cell-type", choices=["code", "markdown", "raw"], default="code"
    )
    add_cmd.add_argument("--source", required=True)
    add_cmd.add_argument(
        "--position", type=int, help="Insert position; default append."
    )
    add_cmd.add_argument(
        "--metadata-json", help="Optional JSON object for cell metadata."
    )

    update_cmd = sub.add_parser(
        "update", help="Replace cell source and optionally cell type."
    )
    update_cmd.add_argument("--index", type=int, required=True)
    update_cmd.add_argument("--source", required=True)
    update_cmd.add_argument(
        "--cell-type",
        choices=["code", "markdown", "raw"],
        help="Optional replacement type.",
    )

    delete_cmd = sub.add_parser("delete", help="Delete one cell by index.")
    delete_cmd.add_argument("--index", type=int, required=True)

    move_cmd = sub.add_parser("move", help="Move cell from index A to index B.")
    move_cmd.add_argument("--from-index", type=int, required=True)
    move_cmd.add_argument("--to-index", type=int, required=True)

    bulk_cmd = sub.add_parser(
        "insert-bulk", help="Insert multiple cells from JSON array."
    )
    bulk_cmd.add_argument(
        "--cells-json",
        required=True,
        help='JSON array like [{"cell_type":"code","source":"x=1"}].',
    )
    bulk_cmd.add_argument(
        "--position", type=int, help="Insert start position; default append."
    )

    range_cmd = sub.add_parser(
        "delete-range", help="Delete cells in inclusive index range."
    )
    range_cmd.add_argument("--start", type=int, required=True)
    range_cmd.add_argument("--end", type=int, required=True)

    meta_get = sub.add_parser("metadata-get", help="Get cell metadata at index.")
    meta_get.add_argument("--index", type=int, required=True)

    meta_set = sub.add_parser("metadata-set", help="Set a metadata key on a cell.")
    meta_set.add_argument("--index", type=int, required=True)
    meta_set.add_argument("--key", required=True)
    meta_set.add_argument("--value-json", required=True)

    tags_add = sub.add_parser("tags-add", help="Add one or more tags to a cell.")
    tags_add.add_argument("--index", type=int, required=True)
    tags_add.add_argument("--tags", nargs="+", required=True)

    tags_remove = sub.add_parser(
        "tags-remove", help="Remove one or more tags from a cell."
    )
    tags_remove.add_argument("--index", type=int, required=True)
    tags_remove.add_argument("--tags", nargs="+", required=True)

    search_cmd = sub.add_parser(
        "search", help="Search cell sources for pattern or regex."
    )
    search_cmd.add_argument("--pattern", required=True)
    search_cmd.add_argument("--regex", action="store_true")
    search_cmd.add_argument("--ignore-case", action="store_true")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    notebook_path = Path(args.input)
    nb = load_notebook(notebook_path)
    result: dict[str, Any]

    cmd = args.command

    if cmd == "list":
        result = list_cells(nb)

    elif cmd == "get":
        validate_index(nb, args.index)
        cell = nb.cells[args.index]
        result = {
            "ok": True,
            "action": "get",
            "index": args.index,
            "cell": {
                "cell_type": cell.cell_type,
                "source": cell.source,
                "metadata": dict(cell.metadata),
                "outputs": list(getattr(cell, "outputs", []))
                if cell.cell_type == "code"
                else [],
                "execution_count": getattr(cell, "execution_count", None),
            },
        }

    elif cmd == "add":
        metadata = parse_json(args.metadata_json) if args.metadata_json else {}
        if metadata and not isinstance(metadata, dict):
            fail("--metadata-json must be a JSON object.")
        cell = new_cell(args.cell_type, args.source, metadata=metadata)
        if args.position is None or args.position >= len(nb.cells):
            nb.cells.append(cell)
            idx = len(nb.cells) - 1
        else:
            if args.position < 0:
                fail("--position cannot be negative.")
            nb.cells.insert(args.position, cell)
            idx = args.position
        result = {
            "ok": True,
            "action": "add",
            "index": idx,
            "cell_count": len(nb.cells),
        }

    elif cmd == "update":
        validate_index(nb, args.index)
        original = nb.cells[args.index]
        target_type = args.cell_type or original.cell_type
        replacement = new_cell(
            target_type, args.source, metadata=dict(original.metadata)
        )
        if target_type == "code":
            replacement.outputs = list(getattr(original, "outputs", []))
            replacement.execution_count = getattr(original, "execution_count", None)
        nb.cells[args.index] = replacement
        result = {"ok": True, "action": "update", "index": args.index}

    elif cmd == "delete":
        validate_index(nb, args.index)
        del nb.cells[args.index]
        result = {
            "ok": True,
            "action": "delete",
            "deleted_index": args.index,
            "cell_count": len(nb.cells),
        }

    elif cmd == "move":
        validate_index(nb, args.from_index)
        if args.to_index < 0 or args.to_index > len(nb.cells):
            fail(
                "--to-index out of range.",
                details={"to_index": args.to_index, "cell_count": len(nb.cells)},
            )
        cell = nb.cells.pop(args.from_index)
        insert_at = args.to_index
        if insert_at > len(nb.cells):
            insert_at = len(nb.cells)
        nb.cells.insert(insert_at, cell)
        result = {
            "ok": True,
            "action": "move",
            "from_index": args.from_index,
            "to_index": insert_at,
        }

    elif cmd == "insert-bulk":
        cells_data = parse_json(args.cells_json)
        if not isinstance(cells_data, list):
            fail("--cells-json must be a JSON array.")
        insert_at = len(nb.cells) if args.position is None else args.position
        if insert_at < 0 or insert_at > len(nb.cells):
            fail(
                "--position out of range.",
                details={"position": insert_at, "cell_count": len(nb.cells)},
            )

        created = []
        for entry in cells_data:
            if not isinstance(entry, dict) or "source" not in entry:
                fail("Each bulk cell entry must be an object with at least 'source'.")
            ctype = entry.get("cell_type", "code")
            cmeta = entry.get("metadata", {})
            if cmeta and not isinstance(cmeta, dict):
                fail("Cell metadata must be an object.")
            created.append(new_cell(ctype, str(entry["source"]), metadata=cmeta))
        nb.cells[insert_at:insert_at] = created
        result = {
            "ok": True,
            "action": "insert-bulk",
            "inserted": len(created),
            "position": insert_at,
            "cell_count": len(nb.cells),
        }

    elif cmd == "delete-range":
        start = args.start
        end = args.end
        if start < 0 or end < 0 or start > end or end >= len(nb.cells):
            fail(
                "Invalid delete range.",
                details={"start": start, "end": end, "cell_count": len(nb.cells)},
            )
        deleted = end - start + 1
        del nb.cells[start : end + 1]
        result = {
            "ok": True,
            "action": "delete-range",
            "start": start,
            "end": end,
            "deleted": deleted,
            "cell_count": len(nb.cells),
        }

    elif cmd == "metadata-get":
        validate_index(nb, args.index)
        result = {
            "ok": True,
            "action": "metadata-get",
            "index": args.index,
            "metadata": dict(nb.cells[args.index].metadata),
        }

    elif cmd == "metadata-set":
        validate_index(nb, args.index)
        value = parse_json(args.value_json)
        nb.cells[args.index].metadata[args.key] = value
        result = {
            "ok": True,
            "action": "metadata-set",
            "index": args.index,
            "key": args.key,
            "value": value,
        }

    elif cmd == "tags-add":
        validate_index(nb, args.index)
        tags = list(nb.cells[args.index].metadata.get("tags", []))
        for tag in args.tags:
            if tag not in tags:
                tags.append(tag)
        nb.cells[args.index].metadata["tags"] = tags
        result = {"ok": True, "action": "tags-add", "index": args.index, "tags": tags}

    elif cmd == "tags-remove":
        validate_index(nb, args.index)
        tags = list(nb.cells[args.index].metadata.get("tags", []))
        remaining = [tag for tag in tags if tag not in set(args.tags)]
        nb.cells[args.index].metadata["tags"] = remaining
        result = {
            "ok": True,
            "action": "tags-remove",
            "index": args.index,
            "tags": remaining,
        }

    elif cmd == "search":
        flags = re.IGNORECASE if args.ignore_case else 0
        matches = []
        if args.regex:
            try:
                pattern = re.compile(args.pattern, flags=flags)
            except re.error as exc:
                fail(
                    "Invalid regular expression.",
                    details={"pattern": args.pattern, "exception": str(exc)},
                )

            def finder(src: str) -> bool:
                return bool(pattern.search(src))

        else:
            needle = args.pattern.lower() if args.ignore_case else args.pattern

            def finder(src: str) -> bool:
                haystack = src.lower() if args.ignore_case else src
                return needle in haystack

        for i, cell in enumerate(nb.cells):
            if finder(cell.source):
                matches.append(
                    {
                        "index": i,
                        "cell_type": cell.cell_type,
                        "preview": build_preview(cell.source),
                        "tags": list(cell.metadata.get("tags", [])),
                    }
                )
        result = {
            "ok": True,
            "action": "search",
            "pattern": args.pattern,
            "regex": args.regex,
            "match_count": len(matches),
            "matches": matches,
        }

    else:  # pragma: no cover
        fail("Unknown command.", details={"command": cmd})

    output_path = resolve_write_path(args)
    if output_path is not None:
        write_notebook(nb, output_path)
        status(f"Wrote notebook: {output_path}")
        result["output"] = str(output_path)

    emit(result)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
