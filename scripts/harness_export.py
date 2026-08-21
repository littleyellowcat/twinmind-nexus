"""Export a TwinMind harness timeline and artifact manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.project_archive.harness_export import build_harness_export


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a redacted TwinMind harness export.")
    parser.add_argument("project_id")
    parser.add_argument("--storage-dir", default="data/project_archive")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    payload = build_harness_export(args.storage_dir, args.project_id)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
