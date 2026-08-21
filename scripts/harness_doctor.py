"""Inspect TwinMind harness storage without importing application dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.harness_events import load_project_events
except ModuleNotFoundError:  # pragma: no cover - direct script execution path.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from harness_events import load_project_events


def inspect_harness_storage(
    storage_dir: str | Path = "data/project_archive",
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    root = Path(storage_dir)
    project_ids = [project_id] if project_id else _discover_project_ids(root)
    projects = [_inspect_project(root, item) for item in project_ids]
    warnings = [
        warning
        for project in projects
        for warning in project.get("warnings", [])
    ]
    return {
        "storage_dir": str(root),
        "status": "warn" if warnings else "ok",
        "projects": projects,
        "warnings": warnings,
        "metrics": {
            "projects": len(projects),
            "projects_with_events": sum(1 for project in projects if project["harness"]["events"] > 0),
            "artifacts": sum(project["harness"]["artifacts"] for project in projects),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose TwinMind harness storage.")
    parser.add_argument(
        "--storage-dir",
        default="data/project_archive",
        help="Project archive storage directory.",
    )
    parser.add_argument("--project-id", default=None, help="Optional project archive id.")
    args = parser.parse_args()
    print(
        json.dumps(
            inspect_harness_storage(args.storage_dir, project_id=args.project_id),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _discover_project_ids(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and (path / "draft_archive.json").exists()
    )


def _inspect_project(root: Path, project_id: str) -> dict[str, Any]:
    project_dir = root / project_id
    events = load_project_events(root, project_id, limit=500)
    latest_event = events["events"][-1] if events["events"] else None
    eval_report = _read_json(project_dir / "agent_eval_report.json")
    artifact_count = len(list((project_dir / "harness_artifacts").glob("**/*"))) if (project_dir / "harness_artifacts").exists() else 0
    warnings: list[str] = []
    if not project_dir.exists():
        warnings.append(f"Project directory is missing: {project_id}")
    elif not (project_dir / "draft_archive.json").exists():
        warnings.append(f"Draft archive is missing for project: {project_id}")
    if not events["events"]:
        warnings.append(f"No harness events found for project: {project_id}")
    return {
        "project_id": project_id,
        "exists": project_dir.exists(),
        "draft_archive": str(project_dir / "draft_archive.json"),
        "harness": {
            "events": events["metrics"]["events"],
            "latest_sequence": events["metrics"]["latest_sequence"],
            "latest_event_type": latest_event.get("type") if latest_event else None,
            "artifacts": artifact_count,
        },
        "agent_eval": {
            "available": bool(eval_report),
            "id": eval_report.get("id") if eval_report else None,
            "status": eval_report.get("status") if eval_report else None,
        },
        "warnings": warnings,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
