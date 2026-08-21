# TwinMind GitHub Report-only Runner

The GitHub runner is intentionally report-only. It may inspect repository state and publish a markdown summary artifact, but it must not generate patches, push commits, deploy services, or call live model providers by default.

## Local Smoke Test

```bash
python3 scripts/github_report_runner.py --input docs/examples/twinmind_report_payload.json
```

## CI Behavior

- Runs dependency-free Python diagnostics.
- Renders a deterministic markdown report from JSON input.
- Uploads report artifacts for review.
- Includes the statement `No code changes were generated`.

## Live Provider Boundary

Any workflow that wants live model calls, paid APIs, or source mutation must be a separate explicitly approved workflow. The default report-only runner stays inside the local evidence and reporting boundary.
