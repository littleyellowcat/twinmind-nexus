"""List TwinMind harness events from project storage.

This script intentionally uses only the Python standard library so it can run
even when the full application dependency set is unavailable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EVENT_FILE_NAME = "harness_events.jsonl"


def load_project_events(
    storage_dir: str | Path,
    project_id: str,
    *,
    event_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    events = _read_events(Path(storage_dir) / project_id / EVENT_FILE_NAME)
    if event_type:
        events = [event for event in events if event.get("type") == event_type]
    events = sorted(
        events,
        key=lambda event: int(event.get("sequence", 0) or 0),
    )[: max(1, min(int(limit), 500))]
    return {
        "project_id": project_id,
        "events": events,
        "metrics": {
            "events": len(events),
            "latest_sequence": int(events[-1].get("sequence", 0) or 0) if events else 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="List TwinMind project harness events.")
    parser.add_argument("project_id", help="Project archive id.")
    parser.add_argument(
        "--storage-dir",
        default="data/project_archive",
        help="Project archive storage directory.",
    )
    parser.add_argument("--event-type", default=None, help="Optional event type filter.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum events to print.")
    args = parser.parse_args()
    print(
        json.dumps(
            load_project_events(
                args.storage_dir,
                args.project_id,
                event_type=args.event_type,
                limit=args.limit,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


if __name__ == "__main__":
    raise SystemExit(main())
