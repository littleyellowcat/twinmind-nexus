"""Durable project-scoped harness event stream."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


EVENT_FILE_NAME = "harness_events.jsonl"


@dataclass(frozen=True)
class HarnessEvent:
    id: str
    project_id: str
    run_id: str
    type: str
    sequence: int
    created_at: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HarnessEvent":
        return cls(
            id=str(data.get("id", "")),
            project_id=str(data.get("project_id", "")),
            run_id=str(data.get("run_id", "")),
            type=str(data.get("type", "")),
            sequence=int(data.get("sequence", 0)),
            created_at=str(data.get("created_at", "")),
            data=dict(data.get("data", {})),
        )


class HarnessEventStore:
    """Append-only JSONL event stream for one TwinMind storage root."""

    def __init__(self, storage_dir: Path | str) -> None:
        self.storage_dir = Path(storage_dir)

    def append(
        self,
        *,
        project_id: str,
        run_id: str,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> HarnessEvent:
        path = self._event_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        event = HarnessEvent(
            id=f"hevt_{uuid4().hex}",
            project_id=project_id,
            run_id=run_id,
            type=event_type,
            sequence=self._next_sequence(path),
            created_at=datetime.now(UTC).isoformat(),
            data=dict(data or {}),
        )
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def list_events(
        self,
        project_id: str,
        *,
        event_type: str | None = None,
        limit: int = 200,
    ) -> list[HarnessEvent]:
        path = self._event_path(project_id)
        if not path.exists():
            return []
        events: list[HarnessEvent] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = HarnessEvent.from_dict(json.loads(line))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if event_type and event.type != event_type:
                continue
            events.append(event)
        bounded_limit = max(1, min(limit, 500))
        return sorted(events, key=lambda event: event.sequence)[-bounded_limit:]

    def _event_path(self, project_id: str) -> Path:
        return self.storage_dir / project_id / EVENT_FILE_NAME

    def _next_sequence(self, path: Path) -> int:
        if not path.exists():
            return 1
        latest = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                latest = max(latest, int(json.loads(line).get("sequence", 0)))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return latest + 1
