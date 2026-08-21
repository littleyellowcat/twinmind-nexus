"""Inspect TwinMind harness command plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.project_archive.harness_commands import list_harness_commands, run_harness_command


def main() -> int:
    parser = argparse.ArgumentParser(description="List or dry-run TwinMind harness commands.")
    parser.add_argument("--run", default="", help="Command id to dry-run.")
    parser.add_argument("--project-id", default="unknown")
    parser.add_argument("--provider", default="configured")
    args = parser.parse_args()
    if not args.run:
        payload = {"commands": list_harness_commands()}
    else:
        payload = run_harness_command(
            args.run,
            {"project_id": args.project_id, "provider": args.provider},
            dry_run=True,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
