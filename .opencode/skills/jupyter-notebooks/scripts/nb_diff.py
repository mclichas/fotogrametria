#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nbformat>=5.8",
#   "nbdime>=4.0",
# ]
# ///

"""Content-aware notebook diff and merge operations using nbdime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1


MERGE_STRATEGIES = {"inline", "use-base", "use-local", "use-remote"}


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


def _load_nbdime():
    try:
        from nbdime.diffing.notebooks import diff_notebooks, set_notebook_diff_targets  # type: ignore
        from nbdime.prettyprint import PrettyPrintConfig, pretty_print_notebook_diff  # type: ignore
        from nbdime.merging.notebooks import merge_notebooks  # type: ignore
    except Exception as exc:  # pragma: no cover
        fail("Failed to import nbdime.", details={"exception": str(exc)})
    return (
        diff_notebooks,
        set_notebook_diff_targets,
        PrettyPrintConfig,
        pretty_print_notebook_diff,
        merge_notebooks,
    )


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Notebook diff/merge wrapper around nbdime.",
        epilog=(
            "Examples:\n"
            "  uv run scripts/nb_diff.py diff --base a.ipynb --remote b.ipynb\n"
            "  uv run scripts/nb_diff.py diff --base a.ipynb --remote b.ipynb --format json --source-only\n"
            "  uv run scripts/nb_diff.py merge --base base.ipynb --local local.ipynb --remote remote.ipynb --output merged.ipynb"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    diff_cmd = sub.add_parser("diff", help="Diff two notebooks.")
    diff_cmd.add_argument("--base", required=True, help="Base notebook path.")
    diff_cmd.add_argument("--remote", required=True, help="Remote notebook path.")
    diff_cmd.add_argument("--format", choices=["text", "json"], default="text")
    diff_cmd.add_argument(
        "--source-only",
        action="store_true",
        help="Ignore outputs/metadata/attachments/id/details.",
    )

    merge_cmd = sub.add_parser("merge", help="Three-way merge notebooks.")
    merge_cmd.add_argument("--base", required=True)
    merge_cmd.add_argument("--local", required=True)
    merge_cmd.add_argument("--remote", required=True)
    merge_cmd.add_argument("--output", required=True)
    merge_cmd.add_argument(
        "--strategy",
        choices=sorted(MERGE_STRATEGIES),
        default="inline",
        help="Conflict strategy.",
    )

    return parser


def run_diff(args: argparse.Namespace) -> dict[str, Any]:
    base_path = Path(args.base)
    remote_path = Path(args.remote)
    base_nb = load_notebook(base_path)
    remote_nb = load_notebook(remote_path)

    diff_notebooks, set_targets, PrettyPrintConfig, pretty_print_notebook_diff, _ = (
        _load_nbdime()
    )

    if args.source_only:
        set_targets(
            sources=True,
            outputs=False,
            attachments=False,
            metadata=False,
            identifier=False,
            details=False,
        )
    else:
        set_targets(
            sources=True,
            outputs=True,
            attachments=True,
            metadata=True,
            identifier=True,
            details=True,
        )

    diff_data = diff_notebooks(base_nb, remote_nb)

    if args.format == "json":
        rendered = diff_data
    else:

        class Writer:
            def __init__(self) -> None:
                self.parts: list[str] = []

            def write(self, text: str) -> None:
                self.parts.append(text)

            @property
            def value(self) -> str:
                return "".join(self.parts)

        writer = Writer()
        config = PrettyPrintConfig(out=writer, use_color=False)
        pretty_print_notebook_diff(
            str(base_path), str(remote_path), base_nb, diff_data, config
        )
        rendered = writer.value

    return {
        "ok": True,
        "action": "diff",
        "base": str(base_path),
        "remote": str(remote_path),
        "source_only": bool(args.source_only),
        "format": args.format,
        "diff": rendered,
    }


def run_merge(args: argparse.Namespace) -> dict[str, Any]:
    if args.strategy not in MERGE_STRATEGIES:
        fail(
            "Invalid merge strategy.",
            details={"strategy": args.strategy, "allowed": sorted(MERGE_STRATEGIES)},
        )

    base_nb = load_notebook(Path(args.base))
    local_nb = load_notebook(Path(args.local))
    remote_nb = load_notebook(Path(args.remote))

    _, _, _, _, merge_notebooks = _load_nbdime()

    class MergeArgs:
        ignore_transients = True
        merge_strategy = args.strategy
        input_strategy = None
        output_strategy = None
        log_level = "INFO"

    try:
        merged_nb, decisions = merge_notebooks(
            base_nb, local_nb, remote_nb, MergeArgs()
        )
    except Exception as exc:
        fail("Notebook merge failed.", details={"exception": str(exc)})

    conflict_count = 0
    for decision in decisions:
        if isinstance(decision, dict):
            if decision.get("conflict"):
                conflict_count += 1
        else:
            if getattr(decision, "conflict", False):
                conflict_count += 1

    output_path = Path(args.output)
    write_notebook(merged_nb, output_path)
    status(f"Wrote merged notebook: {output_path}")

    return {
        "ok": True,
        "action": "merge",
        "base": str(args.base),
        "local": str(args.local),
        "remote": str(args.remote),
        "output": str(output_path),
        "strategy": args.strategy,
        "decision_count": len(decisions),
        "conflict_count": conflict_count,
    }


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "diff":
        payload = run_diff(args)
    elif args.command == "merge":
        payload = run_merge(args)
    else:  # pragma: no cover
        fail("Unknown command.", details={"command": args.command})

    emit(payload)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
