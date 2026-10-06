#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "nbformat>=5.8",
#   "nbclient>=0.8",
#   "jupyter_client>=8.0",
#   "papermill>=2.5",
# ]
# ///

"""Execute Jupyter notebooks with nbclient or papermill."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1


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


def parse_json_map(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail("Invalid JSON in --params.", details={"exception": str(exc), "input": raw})
    if not isinstance(value, dict):
        fail("--params must be a JSON object.")
    return value


def collect_error_cells(nb: Any, offset: int = 0) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        for output in cell.get("outputs", []):
            if output.get("output_type") == "error":
                failures.append(
                    {
                        "index": i + offset,
                        "ename": output.get("ename"),
                        "evalue": output.get("evalue"),
                    }
                )
                break
    return failures


def resolve_kernel_name(kernel: str | None) -> str | None:
    if not kernel:
        return None
    kernel_path = Path(kernel)
    if not kernel_path.exists():
        return kernel

    try:
        from jupyter_client.kernelspec import KernelSpecManager  # type: ignore
    except Exception as exc:
        fail(
            "Failed to import jupyter_client for kernel path resolution.",
            details={"exception": str(exc)},
        )

    manager = KernelSpecManager()
    all_specs = manager.get_all_specs()
    resolved = kernel_path.resolve()
    for name, spec in all_specs.items():
        resource_dir = Path(spec.get("resource_dir", ""))
        if resource_dir and resource_dir.resolve() == resolved:
            return name

    fail(
        "Kernel path did not match any installed kernelspec resource directory.",
        details={
            "kernel": kernel,
            "hint": "Use kernel name from `jupyter kernelspec list` or a valid kernelspec path.",
        },
    )
    return None


def execute_with_nbclient(
    nb: Any,
    *,
    kernel_name: str | None,
    timeout: int,
    startup_timeout: int,
    allow_errors: bool,
    working_dir: str | None,
):
    try:
        from nbclient import NotebookClient  # type: ignore
    except Exception as exc:
        fail("Failed to import nbclient.", details={"exception": str(exc)})

    kwargs = {
        "timeout": timeout,
        "startup_timeout": startup_timeout,
        "allow_errors": allow_errors,
    }
    if kernel_name:
        kwargs["kernel_name"] = kernel_name
    if working_dir:
        kwargs["resources"] = {"metadata": {"path": working_dir}}

    client = NotebookClient(nb, **kwargs)
    return client.execute()


def parse_range(
    start: int | None, end: int | None, cell_count: int
) -> tuple[int, int] | None:
    if start is None and end is None:
        return None
    s = 0 if start is None else start
    e = (cell_count - 1) if end is None else end
    if s < 0 or e < 0 or s > e or e >= cell_count:
        fail(
            "Invalid execution range.",
            details={"start_index": s, "end_index": e, "cell_count": cell_count},
        )
    return s, e


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute Jupyter notebooks with nbclient (default) or papermill.",
        epilog=(
            "Examples:\n"
            "  uv run scripts/nb_execute.py --input in.ipynb --output out.ipynb\n"
            "  uv run scripts/nb_execute.py --input in.ipynb --start-index 3 --end-index 7\n"
            "  uv run scripts/nb_execute.py --input in.ipynb --allow-errors --timeout 120\n"
            '  uv run scripts/nb_execute.py --input template.ipynb --output run.ipynb --papermill --params \'{"ticker":"AAPL"}\''
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Input notebook.")
    parser.add_argument(
        "--output", help="Output notebook path (default: in-place for nbclient mode)."
    )
    parser.add_argument(
        "--in-place", action="store_true", help="Write result back to --input."
    )

    parser.add_argument(
        "--kernel", help="Kernel name or installed kernelspec directory path."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Per-cell execution timeout in seconds.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=60,
        help="Kernel startup timeout in seconds.",
    )
    parser.add_argument(
        "--allow-errors",
        action="store_true",
        help="Continue on execution errors and capture tracebacks.",
    )
    parser.add_argument(
        "--working-dir", help="Working directory for notebook execution."
    )

    parser.add_argument(
        "--start-index", type=int, help="Start cell index for selective execution."
    )
    parser.add_argument(
        "--end-index",
        type=int,
        help="End cell index for selective execution (inclusive).",
    )

    parser.add_argument(
        "--papermill", action="store_true", help="Use papermill execution mode."
    )
    parser.add_argument("--params", help="JSON object of papermill parameters.")
    return parser


def resolve_output_path(args: argparse.Namespace) -> Path:
    input_path = Path(args.input)
    if args.output:
        return Path(args.output)
    if args.in_place or not args.papermill:
        return input_path
    return input_path.with_name(f"{input_path.stem}.executed{input_path.suffix}")


def run_papermill(args: argparse.Namespace, output_path: Path) -> dict[str, Any]:
    if args.start_index is not None or args.end_index is not None:
        fail("Selective cell range execution is not supported in --papermill mode.")

    params = parse_json_map(args.params)
    kernel_name = resolve_kernel_name(args.kernel)

    try:
        import papermill as pm  # type: ignore
    except Exception as exc:
        fail("Failed to import papermill.", details={"exception": str(exc)})

    status(f"Executing with papermill: {args.input} -> {output_path}")
    try:
        pm.execute_notebook(
            input_path=str(args.input),
            output_path=str(output_path),
            parameters=params,
            kernel_name=kernel_name,
            cwd=args.working_dir,
        )
    except Exception as exc:
        fail("Papermill execution failed.", details={"exception": str(exc)})

    executed = load_notebook(output_path)
    failures = collect_error_cells(executed)

    return {
        "ok": True,
        "action": "execute",
        "mode": "papermill",
        "input": str(args.input),
        "output": str(output_path),
        "params": params,
        "kernel": kernel_name,
        "executed_cell_count": len(executed.cells),
        "failed_cells": failures,
        "failed_cell_count": len(failures),
    }


def run_nbclient(args: argparse.Namespace, output_path: Path) -> dict[str, Any]:
    input_path = Path(args.input)
    source_nb = load_notebook(input_path)

    selected = parse_range(args.start_index, args.end_index, len(source_nb.cells))
    kernel_name = resolve_kernel_name(args.kernel)

    if selected is None:
        status(f"Executing full notebook with nbclient: {input_path}")
        working_nb = copy.deepcopy(source_nb)
        try:
            execute_with_nbclient(
                working_nb,
                kernel_name=kernel_name,
                timeout=args.timeout,
                startup_timeout=args.startup_timeout,
                allow_errors=args.allow_errors,
                working_dir=args.working_dir,
            )
        except Exception as exc:
            fail("Notebook execution failed.", details={"exception": str(exc)})

        failures = collect_error_cells(working_nb)
        write_notebook(working_nb, output_path)
        status(f"Wrote executed notebook: {output_path}")

        return {
            "ok": True,
            "action": "execute",
            "mode": "nbclient",
            "input": str(input_path),
            "output": str(output_path),
            "kernel": kernel_name,
            "range": None,
            "executed_cell_count": len(working_nb.cells),
            "failed_cells": failures,
            "failed_cell_count": len(failures),
        }

    start_index, end_index = selected
    status(
        "Executing selective range with context preservation: "
        f"target={start_index}:{end_index}, executed_prefix=0:{end_index}"
    )

    prefix_nb = copy.deepcopy(source_nb)
    prefix_nb.cells = copy.deepcopy(source_nb.cells[: end_index + 1])

    try:
        execute_with_nbclient(
            prefix_nb,
            kernel_name=kernel_name,
            timeout=args.timeout,
            startup_timeout=args.startup_timeout,
            allow_errors=args.allow_errors,
            working_dir=args.working_dir,
        )
    except Exception as exc:
        fail(
            "Selective range execution failed.",
            details={
                "exception": str(exc),
                "start_index": start_index,
                "end_index": end_index,
            },
        )

    result_nb = copy.deepcopy(source_nb)
    for idx in range(start_index, end_index + 1):
        result_nb.cells[idx] = copy.deepcopy(prefix_nb.cells[idx])

    failures = [
        f
        for f in collect_error_cells(prefix_nb)
        if start_index <= f["index"] <= end_index
    ]
    write_notebook(result_nb, output_path)
    status(f"Wrote executed notebook: {output_path}")

    return {
        "ok": True,
        "action": "execute",
        "mode": "nbclient",
        "input": str(input_path),
        "output": str(output_path),
        "kernel": kernel_name,
        "range": {
            "start_index": start_index,
            "end_index": end_index,
            "execution_strategy": "execute_prefix_then_apply_target_range",
        },
        "executed_cell_count": end_index + 1,
        "updated_cell_count": end_index - start_index + 1,
        "failed_cells": failures,
        "failed_cell_count": len(failures),
    }


def main() -> int:
    args = build_parser().parse_args()
    output_path = resolve_output_path(args)

    if args.papermill:
        payload = run_papermill(args, output_path)
    else:
        payload = run_nbclient(args, output_path)

    emit(payload)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
