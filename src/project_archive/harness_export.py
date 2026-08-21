"""Build redacted, portable TwinMind harness exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.project_archive.harness_artifact_retention import build_artifact_manifest
from src.project_archive.harness_events import HarnessEventStore


def build_harness_export(
    storage_dir: str | Path,
    project_id: str,
    *,
    limit: int = 500,
) -> dict[str, Any]:
    """Return a deterministic export with local absolute paths removed."""

    root = Path(storage_dir)
    events = HarnessEventStore(root).list_events(project_id, limit=limit)
    timeline = [
        _timeline_item(root, event.to_dict())
        for event in sorted(events, key=lambda item: item.sequence)
    ]
    manifest = _redact_paths(root, build_artifact_manifest(root, project_id))
    return {
        "project_id": project_id,
        "schema_version": "twinmind-harness-export-v1",
        "timeline": timeline,
        "artifacts_manifest": manifest,
        "metrics": {
            "events": len(timeline),
            "artifacts": len(manifest.get("artifacts", [])),
            "latest_sequence": timeline[-1]["sequence"] if timeline else 0,
        },
    }


def _timeline_item(root: Path, event: dict[str, Any]) -> dict[str, Any]:
    event_type = str(event.get("type", ""))
    category = event_type.split(".", 1)[0] if "." in event_type else event_type or "event"
    return {
        "id": event.get("id", ""),
        "project_id": event.get("project_id", ""),
        "run_id": event.get("run_id", ""),
        "type": event_type,
        "category": category,
        "sequence": int(event.get("sequence", 0) or 0),
        "created_at": event.get("created_at", ""),
        "data": _redact_paths(root, event.get("data", {})),
    }


def _redact_paths(root: Path, value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _redact_paths(root, item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_paths(root, item) for item in value]
    if isinstance(value, str):
        root_text = str(root.resolve())
        if value.startswith(root_text):
            try:
                return Path(value).resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                return value.replace(root_text, "<storage>")
        return value
    return value
