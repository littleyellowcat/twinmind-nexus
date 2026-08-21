"""Deterministic report-only runner for GitHub automation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def render_report_markdown(payload: dict[str, Any]) -> str:
    project_id = str(payload.get("project_id") or "unknown")
    summary = dict(payload.get("summary") or {})
    harness = dict(payload.get("harness") or {})
    artifacts = list(payload.get("artifacts") or [])
    lines = [
        f"# TwinMind Report: {project_id}",
        "",
        "Report-only runner",
        "",
        "No code changes were generated.",
        "",
        f"- Status: {payload.get('status', 'unknown')}",
        f"- Entities: {summary.get('entities', 0)}",
        f"- Relations: {summary.get('relations', 0)}",
        f"- Evidence cards: {summary.get('evidence', 0)}",
        f"- Harness status: {harness.get('status', 'unknown')}",
        f"- Latest harness sequence: {harness.get('latest_sequence', 0)}",
        f"- Artifacts: {len(artifacts)}",
    ]
    if artifacts:
        lines.extend(["", "## Artifacts"])
        for artifact in artifacts:
            item = dict(artifact)
            lines.append(f"- {item.get('kind', 'artifact')}: {item.get('path', '')}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a TwinMind report-only markdown summary.")
    parser.add_argument("--input", required=True, help="JSON payload path.")
    parser.add_argument("--output", default="", help="Markdown output path.")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    markdown = render_report_markdown(payload if isinstance(payload, dict) else {})
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
