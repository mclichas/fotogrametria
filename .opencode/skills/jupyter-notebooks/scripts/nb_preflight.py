#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

"""Check environment readiness for jupyter-notebooks skill scripts."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_ISSUES = 1

CORE_PACKAGES = {
    "nbformat": "5.8",
    "nbclient": "0.8",
    "nbconvert": "7.0",
    "nbdime": "4.0",
}

OPTIONAL_PACKAGES = {
    "papermill": "2.5",
    "nbstripout": None,
}

KERNEL_CHECK_UV_DEPENDENCIES = [
    "jupyter_client>=8.0",
]


def status(message: str) -> None:
    print(message, file=sys.stderr)


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _check_python_version() -> dict[str, Any]:
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.version_info >= (3, 9)
    return {"version": version, "ok": ok, "required": ">=3.9"}


def _check_package(name: str, min_version: str | None) -> dict[str, Any]:
    try:
        mod = importlib.import_module(name)
    except ImportError:
        return {"installed": False, "version": None, "ok": False}

    version = getattr(mod, "__version__", getattr(mod, "version", None))
    if version is None:
        try:
            from importlib.metadata import version as meta_version

            version = meta_version(name)
        except Exception:
            version = "unknown"

    ok = True
    if min_version and version != "unknown":
        try:
            ok = _version_gte(version, min_version)
        except ValueError:
            ok = True

    return {"installed": True, "version": version, "ok": ok}


def _version_gte(current: str, minimum: str) -> bool:
    def parse(v: str) -> tuple[int, ...]:
        parts: list[int] = []
        for chunk in v.split("."):
            match = re.match(r"(\d+)", chunk)
            if not match:
                break
            parts.append(int(match.group(1)))
            if len(parts) == 3:
                break
        if not parts:
            raise ValueError("Could not parse version.")
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts)

    return parse(current) >= parse(minimum)


def _run_command(command: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "Command timed out.",
            "timed_out": True,
        }

    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": False,
    }


def _iter_notebook_scripts() -> list[Path]:
    scripts_dir = Path(__file__).resolve().parent
    return sorted(scripts_dir.glob("nb_*.py"))


def _check_python_runtime() -> dict[str, Any]:
    python = _check_python_version()
    core = {}
    core_missing = []
    for name, min_ver in CORE_PACKAGES.items():
        info = _check_package(name, min_ver)
        core[name] = info
        label = f"{name}>={min_ver}" if min_ver else name
        if not info["installed"]:
            core_missing.append(label)

    optional = {}
    optional_missing = []
    for name, min_ver in OPTIONAL_PACKAGES.items():
        info = _check_package(name, min_ver)
        optional[name] = info
        label = f"{name}>={min_ver}" if min_ver else name
        if not info["installed"]:
            optional_missing.append(label)

    ok = python["ok"] and all(p["ok"] for p in core.values())
    return {
        "python": python,
        "core": core,
        "optional": optional,
        "missing_core": core_missing,
        "missing_optional": optional_missing,
        "ok": ok,
    }


def _check_uv_runtime() -> dict[str, Any]:
    uv_version = _run_command(["uv", "--version"], timeout=10)
    available = uv_version["ok"]
    version = uv_version["stdout"].strip() if available else None

    script_help = {
        "checked": [],
        "failures": [],
        "ok": False,
    }
    if available:
        for script in _iter_notebook_scripts():
            script_str = str(script)
            script_help["checked"].append(script_str)
            result = _run_command(["uv", "run", script_str, "--help"], timeout=45)
            if not result["ok"]:
                script_help["failures"].append(
                    {
                        "script": script_str,
                        "returncode": result["returncode"],
                        "stderr": result["stderr"].strip(),
                    }
                )
        script_help["ok"] = len(script_help["failures"]) == 0

    return {
        "available": available,
        "version": version,
        "script_help": script_help,
        "ok": available and script_help["ok"],
        "details": None if available else uv_version["stderr"],
    }


def _check_kernels(use_uv: bool) -> dict[str, Any]:
    command = [sys.executable, "-m", "jupyter", "kernelspec", "list", "--json"]
    checked_with = "python"
    if use_uv:
        command = ["uv", "run"]
        for dependency in KERNEL_CHECK_UV_DEPENDENCIES:
            command.extend(["--with", dependency])
        command.extend(["python", "-m", "jupyter", "kernelspec", "list", "--json"])
        checked_with = "uv"

    result = _run_command(command, timeout=20)
    if result["ok"]:
        try:
            data = json.loads(result["stdout"])
        except json.JSONDecodeError:
            return {
                "available": False,
                "kernels": [],
                "checked_with": checked_with,
                "error": "Kernel list did not return valid JSON.",
            }
        kernels = list(data.get("kernelspecs", {}).keys())
        return {
            "available": len(kernels) > 0,
            "kernels": kernels,
            "checked_with": checked_with,
            "error": None,
        }

    return {
        "available": False,
        "kernels": [],
        "checked_with": checked_with,
        "error": result["stderr"].strip(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check environment readiness for jupyter-notebooks scripts.",
        epilog=(
            "Examples:\n"
            "  python scripts/nb_preflight.py\n"
            "  python scripts/nb_preflight.py --mode python\n"
            "  uv run scripts/nb_preflight.py --mode uv"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "python", "uv"],
        default="auto",
        help="Readiness target. auto=python or uv, python=interpreter packages, uv=uv-run workflow.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    status(f"Checking environment readiness (mode={args.mode})...")

    python_runtime: dict[str, Any] | None = None
    uv_runtime: dict[str, Any] | None = None
    if args.mode in {"auto", "python"}:
        python_runtime = _check_python_runtime()
        python_info = python_runtime["python"]
        status(
            f"  Python {python_info['version']} "
            f"{'ok' if python_info['ok'] else 'FAIL (need >=3.9)'}"
        )
        for name, min_ver in CORE_PACKAGES.items():
            info = python_runtime["core"][name]
            label = f"{name}>={min_ver}"
            if info["installed"]:
                status(f"  {label}: {info['version']} {'ok' if info['ok'] else 'OUTDATED'}")
            else:
                status(f"  {label}: MISSING")
        for name, min_ver in OPTIONAL_PACKAGES.items():
            info = python_runtime["optional"][name]
            label = f"{name}>={min_ver}" if min_ver else name
            if info["installed"]:
                status(f"  {label}: {info['version']} ok")
            else:
                status(f"  {label}: MISSING (optional)")

    if args.mode in {"auto", "uv"}:
        uv_runtime = _check_uv_runtime()
        if uv_runtime["available"]:
            status(f"  uv: {uv_runtime['version']}")
            status(
                "  uv-run script help checks: "
                f"{len(uv_runtime['script_help']['checked'])} checked, "
                f"{len(uv_runtime['script_help']['failures'])} failed"
            )
        else:
            status("  uv: not available")

    use_uv_for_kernels = args.mode == "uv"
    if args.mode == "auto":
        use_uv_for_kernels = bool(uv_runtime and uv_runtime["ok"] and not (python_runtime and python_runtime["ok"]))

    kernels = _check_kernels(use_uv=use_uv_for_kernels)
    if kernels["available"]:
        status(f"  Kernels ({kernels['checked_with']}): {', '.join(kernels['kernels'])}")
    else:
        status(
            f"  Kernels ({kernels['checked_with']}): none found "
            "(needed for nb_execute.py)"
        )
        if kernels["error"]:
            status(f"  Kernel check detail: {kernels['error']}")

    ok_python = python_runtime["ok"] if python_runtime is not None else None
    ok_uv = uv_runtime["ok"] if uv_runtime is not None else None
    if args.mode == "python":
        ready = bool(ok_python)
    elif args.mode == "uv":
        ready = bool(ok_uv)
    else:
        ready = bool(ok_python) or bool(ok_uv)

    install_hints: list[str] = []
    if python_runtime and python_runtime["missing_core"]:
        packages = " ".join(pkg.split(">=")[0] for pkg in python_runtime["missing_core"])
        install_hints.append(
            "Python mode missing core packages: "
            f"{packages}. Install with the project's package manager."
        )
    if uv_runtime and not uv_runtime["available"]:
        install_hints.append("Install uv to use `uv run` execution mode.")
    if uv_runtime and uv_runtime["available"] and not uv_runtime["script_help"]["ok"]:
        install_hints.append(
            "Some scripts fail under `uv run ... --help`; inspect `uv_runtime.script_help.failures`."
        )

    payload: dict[str, Any] = {
        "ok": ready,
        "mode": args.mode,
        "ok_python": ok_python,
        "ok_uv": ok_uv,
        "ok_execute": kernels["available"],
        "python_runtime": python_runtime,
        "uv_runtime": uv_runtime,
        "kernels": kernels,
    }
    if python_runtime and python_runtime["missing_core"]:
        payload["missing_core"] = python_runtime["missing_core"]
    if python_runtime and python_runtime["missing_optional"]:
        payload["missing_optional"] = python_runtime["missing_optional"]
    if install_hints:
        payload["install_hints"] = install_hints

    emit(payload)

    if ready:
        status("Environment ready for selected mode.")
    else:
        status("Environment NOT ready for selected mode. See output for details.")

    raise SystemExit(EXIT_OK if ready else EXIT_ISSUES)


if __name__ == "__main__":
    main()
