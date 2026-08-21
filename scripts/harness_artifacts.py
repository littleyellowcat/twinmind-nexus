"""Validate and dry-run cleanup of TwinMind harness artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.project_archive.harness_artifact_retention import (
    build_artifact_manifest,
    cleanup_artifacts,
    validate_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect TwinMind harness artifacts.")
    parser.add_argument("project_id")
    parser.add_argument("--storage-dir", default="data/project_archive")
    parser.add_argument("--cleanup", action="store_true", help="List cleanup candidates.")
    parser.add_argument("--apply", action="store_true", help="Delete cleanup candidates.")
    args = parser.parse_args()
    if args.cleanup:
        payload = cleanup_artifacts(args.storage_dir, args.project_id, dry_run=not args.apply)
    else:
        payload = {
            "manifest": build_artifact_manifest(args.storage_dir, args.project_id),
            "validation": validate_artifacts(args.storage_dir, args.project_id),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
