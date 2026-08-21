# TwinMind Nexus Agent Instructions

## Product Boundary

TwinMind Nexus is an archive, graph, RAG, and evidence-analysis system. It may borrow engineering patterns from coding agents, but TwinMind agents must not become code execution agents.

## Safety Rules

- Prefer deterministic, local-first workflows for tests, scans, harness exports, and report generation.
- Do not install dependencies, call paid providers, push Git changes, deploy, delete artifacts, or mutate production systems without explicit user confirmation.
- Keep report-only GitHub automation read-only with respect to source code.
- Do not expose API keys, bearer tokens, or absolute local storage paths in harness exports or provider failure payloads.
- Use role profiles and harness policy checks before any live-provider-adjacent action.

## Engineering Rules

- Preserve existing module boundaries in `src/project_archive`.
- Use stdlib-only scripts for diagnostics and harness inspection whenever possible.
- Add or update focused tests for behavior changes.
- Prefer artifacts plus bounded previews for long reports and traces.
- Keep harness events aggregate-level; avoid per-chunk event spam.

## Validation

- Run `make harness-test` for harness changes.
- Run `make py-compile` when Python modules or scripts change.
- Run `make diff-check` before claiming completion.
- Attempt API/frontend verification once, but do not install missing dependencies unless the user confirms.
