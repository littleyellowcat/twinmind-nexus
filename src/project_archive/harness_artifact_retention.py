"""Manifest and retention helpers for TwinMind harness artifacts."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from src.project_archive.harness_artifacts import ARTIFACT_DIRECTORY

_DIGEST_SUFFIX = re.compile(r"^(?P<kind>.+)_(?P<prefix>[a-f0-9]{12})\.[A-Za-z0-9]+$")


def build_artifact_manifest(storage_dir: str | Path, project_id: str) -> dict[str, Any]:
    """Return a deterministic manifest of recognized harness artifact files."""

    root = Path(storage_dir)
    artifacts = [
        _artifact_record(root, project_id, path)
        for path in _artifact_files(root, project_id)
        if _is_recognized_artifact(path)
    ]
    artifacts = sorted(
        artifacts,
        key=lambda item: (str(item.get("run_id", "")), str(item.get("kind", "")), str(item.get("path", ""))),
    )
    return {
        "project_id": project_id,
        "artifact_root": _relative_path(root, root / project_id / ARTIFACT_DIRECTORY),
        "artifacts": artifacts,
        "metrics": {
            "artifacts": len(artifacts),
            "bytes": sum(int(item.get("bytes", 0) or 0) for item in artifacts),
        },
    }


def validate_artifacts(storage_dir: str | Path, project_id: str) -> dict[str, Any]:
    """Find recognized artifacts and orphan files without mutating storage."""

    root = Path(storage_dir)
    artifacts = build_artifact_manifest(root, project_id)["artifacts"]
    orphans = [
        _orphan_record(root, path)
        for path in _artifact_files(root, project_id)
        if not _is_recognized_artifact(path)
    ]
    orphans = sorted(orphans, key=lambda item: str(item.get("path", "")))
    return {
        "project_id": project_id,
        "status": "warn" if orphans else "ok",
        "artifacts": artifacts,
        "orphans": orphans,
        "metrics": {
            "artifacts": len(artifacts),
            "orphans": len(orphans),
        },
    }


def cleanup_artifacts(
    storage_dir: str | Path,
    project_id: str,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Delete orphan artifacts only when explicitly called with ``dry_run=False``."""

    root = Path(storage_dir)
    validation = validate_artifacts(root, project_id)
    candidates = list(validation["orphans"])
    deleted: list[dict[str, Any]] = []
    if not dry_run:
        for item in candidates:
            path = root / str(item.get("path", ""))
            if path.exists() and path.is_file():
                path.unlink()
                deleted.append(item)
    return {
        "project_id": project_id,
        "dry_run": dry_run,
        "candidates": candidates,
        "deleted": deleted,
        "metrics": {
            "candidates": len(candidates),
            "deleted": len(deleted),
        },
    }


def _artifact_files(root: Path, project_id: str) -> list[Path]:
    artifact_root = root / project_id / ARTIFACT_DIRECTORY
    if not artifact_root.exists():
        return []
    return sorted(path for path in artifact_root.rglob("*") if path.is_file())


def _is_recognized_artifact(path: Path) -> bool:
    if path.parent.name == "orphan":
        return False
    return bool(_DIGEST_SUFFIX.match(path.name))


def _artifact_record(root: Path, project_id: str, path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    match = _DIGEST_SUFFIX.match(path.name)
    kind = match.group("kind") if match else path.stem
    return {
        "artifact_id": f"artifact_{digest[:16]}",
        "project_id": project_id,
        "run_id": path.parent.name,
        "kind": kind,
        "path": _relative_path(root, path),
        "sha256": digest,
        "bytes": len(data),
    }


def _orphan_record(root: Path, path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": _relative_path(root, path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "reason": "unrecognized_harness_artifact_name",
    }


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
