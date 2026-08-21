"""Bounded harness artifact retention for long reports and traces."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_MAX_PREVIEW_BYTES = 48 * 1024
ARTIFACT_DIRECTORY = "harness_artifacts"


@dataclass(frozen=True)
class HarnessArtifact:
    artifact_id: str
    project_id: str
    run_id: str
    kind: str
    path: str
    sha256: str
    bytes: int
    preview: str
    truncated: bool
    omitted_bytes: int
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class HarnessArtifactStore:
    """Write full content while returning a bounded provider/API preview."""

    def __init__(
        self,
        storage_dir: Path | str,
        *,
        max_preview_bytes: int = DEFAULT_MAX_PREVIEW_BYTES,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.max_preview_bytes = max(32, int(max_preview_bytes))

    def persist_text(
        self,
        *,
        project_id: str,
        run_id: str,
        kind: str,
        content: str,
    ) -> HarnessArtifact:
        encoded = content.encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        artifact_id = f"artifact_{digest[:16]}"
        directory = self.storage_dir / project_id / ARTIFACT_DIRECTORY / _safe_segment(run_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{_safe_segment(kind)}_{digest[:12]}.txt"
        path.write_text(content, encoding="utf-8")
        preview = _bounded_preview(content, self.max_preview_bytes)
        preview_bytes = len(preview.encode("utf-8"))
        return HarnessArtifact(
            artifact_id=artifact_id,
            project_id=project_id,
            run_id=run_id,
            kind=kind,
            path=str(path),
            sha256=digest,
            bytes=len(encoded),
            preview=preview,
            truncated=len(encoded) > self.max_preview_bytes,
            omitted_bytes=max(0, len(encoded) - preview_bytes),
            created_at=datetime.now(UTC).isoformat(),
        )


def _safe_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._") or "artifact"


def _bounded_preview(content: str, max_preview_bytes: int) -> str:
    encoded = content.encode("utf-8")
    if len(encoded) <= max_preview_bytes:
        return content
    marker = "\n\n... output truncated; full content saved as harness artifact ...\n\n"
    head_budget = max(8, (max_preview_bytes - len(marker.encode("utf-8"))) // 2)
    tail_budget = max(8, max_preview_bytes - len(marker.encode("utf-8")) - head_budget)
    return (
        _take_prefix(content, head_budget)
        + marker
        + _take_suffix(content, tail_budget)
    )


def _take_prefix(content: str, max_bytes: int) -> str:
    total = 0
    chars: list[str] = []
    for char in content:
        size = len(char.encode("utf-8"))
        if total + size > max_bytes:
            break
        total += size
        chars.append(char)
    return "".join(chars)


def _take_suffix(content: str, max_bytes: int) -> str:
    total = 0
    chars: list[str] = []
    for char in reversed(content):
        size = len(char.encode("utf-8"))
        if total + size > max_bytes:
            break
        total += size
        chars.append(char)
    return "".join(reversed(chars))
