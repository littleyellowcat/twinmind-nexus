"""Stdlib-only developer environment diagnostics for TwinMind Nexus."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any


PYTHON_MODULES = ["pytest", "fastapi", "jieba"]
COMMANDS = ["python3", "node", "npm"]


def inspect_dev_environment(
    project_root: str | Path = ".",
    *,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    root = Path(project_root)
    python_version_ok = sys.version_info >= (3, 9)
    modules = {
        name: _module_available(name)
        for name in PYTHON_MODULES
    }
    commands = {
        name: _command_available(name)
        for name in COMMANDS
    }
    frontend_node_modules = (root / "frontend" / "node_modules").exists()
    missing_modules = [name for name, available in modules.items() if not available]
    missing_commands = [name for name, available in commands.items() if not available]
    if not frontend_node_modules:
        missing_commands.append("frontend/node_modules")
    status = "ok" if python_version_ok and not missing_modules and not missing_commands else "warn"
    return {
        "status": status,
        "project_root": str(root),
        "python_executable": python_executable,
        "checks": {
            "python_version": {
                "ok": python_version_ok,
                "version": ".".join(str(part) for part in sys.version_info[:3]),
                "required": ">=3.9 for this stdlib doctor; >=3.10 for the full project runtime",
            },
            "python_modules": modules,
            "commands": commands,
            "frontend_node_modules": frontend_node_modules,
        },
        "missing": {
            "python_modules": missing_modules,
            "commands": missing_commands,
        },
        "policy": {
            "auto_install": False,
            "reason": "Dependency installation is a high-risk operation and requires explicit user confirmation.",
        },
        "recommended_commands": [
            "python3 -m pytest tests/unit/test_project_archive_harness.py -q",
            "/Users/kitten/.local/bin/python3.12 -m py_compile src/project_archive/service.py",
            "cd frontend && npm install",
            "cd frontend && npm run build",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose TwinMind development environment.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    report = inspect_dev_environment(args.project_root)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"status: {report['status']}")
        for module in report["missing"]["python_modules"]:
            print(f"missing python module: {module}")
        for command in report["missing"]["commands"]:
            print(f"missing command/path: {command}")
        print(f"auto_install: {report['policy']['auto_install']}")
    return 0


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _command_available(name: str) -> bool:
    return shutil.which(name) is not None


if __name__ == "__main__":
    raise SystemExit(main())
