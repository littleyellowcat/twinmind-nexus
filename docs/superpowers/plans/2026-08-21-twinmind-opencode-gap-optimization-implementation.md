# TwinMind opencode Gap Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 10 opencode-inspired engineering optimization areas for TwinMind Nexus as safe, local-first, testable features.

**Architecture:** Extend the existing harness layer with focused modules for dev environment diagnostics, policy v2, agent profiles, commands, timeline/export, artifact retention, provider resilience, and report-only GitHub automation. Keep all external operations dry-run or deterministic by default, and preserve TwinMind's product boundary as an archive/RAG/Agent evidence system rather than a coding agent.

**Tech Stack:** Python stdlib, dataclasses, JSON/JSONL, YAML when PyYAML is available with stdlib JSON fallback, FastAPI endpoints, React TypeScript types, pytest.

---

## File Structure

- Create `Makefile`: stable local verification entrypoints.
- Create `AGENTS.md`: repository-level engineering rules for agents.
- Create `llms.txt`: LLM-readable project navigation and constraints.
- Create `docs/twinmind_dev_environment.md`: dependency and verification guide.
- Create `docs/twinmind_github_runner.md`: report-only GitHub runner guide.
- Create `scripts/dev_env_doctor.py`: stdlib environment diagnostics.
- Create `scripts/harness_command.py`: safe command registry CLI.
- Create `scripts/harness_export.py`: harness export CLI.
- Create `scripts/harness_artifacts.py`: artifact validation/cleanup dry-run CLI.
- Create `scripts/github_report_runner.py`: deterministic report-only runner.
- Create `src/project_archive/harness_policy.py`: role/tool/resource policy evaluator.
- Create `src/project_archive/agent_profiles.py`: profile loading and validation.
- Create `src/project_archive/harness_commands.py`: safe command registry.
- Create `src/project_archive/harness_export.py`: timeline/export generation.
- Create `src/project_archive/harness_artifact_retention.py`: manifest and cleanup dry-run.
- Create `src/project_archive/provider_runtime.py`: provider guard/error sanitization helpers.
- Create `config/harness_policy.json`: default project policy overlay.
- Create `config/agent_profiles.json`: default role profiles.
- Modify `src/project_archive/harness_governance.py`: delegate capability matrix/policy check to policy/profile modules.
- Modify `src/project_archive/service.py`: expose policy/profile/commands/export/artifacts, and write ingestion/query/rag/report provider events.
- Modify `src/project_archive/api.py`: expose new read-only/dry-run endpoints.
- Modify `src/project_archive/scanner.py` or archive builder path: mark AGENTS/llms/project-rule files in evidence metadata.
- Modify `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/App.tsx`: add API bindings and compact panels/buttons where already appropriate.
- Modify `scripts/run_github_zip_regression.py`: include export/retention/provider summary if available.
- Modify `tests/unit/test_project_archive_harness.py`: pure behavior tests for all new harness modules.
- Modify `tests/unit/test_project_archive_api.py`: API contract tests where environment permits.

## Tasks

### Task 1: Dev Environment Reproducibility

- [x] Add failing tests for `inspect_dev_environment()`.
- [x] Implement `scripts/dev_env_doctor.py`.
- [x] Add `Makefile` verification targets.
- [x] Add `docs/twinmind_dev_environment.md`.
- [x] Verify doctor runs without project dependencies.

### Task 2: Project Rules

- [x] Add `AGENTS.md` and `llms.txt`.
- [x] Add scanner/archive metadata helper tests for project rule files.
- [x] Mark rule files with `rule_file: true` and priority metadata.
- [x] Surface rule sources in AgentEval metadata where deterministic.

### Task 3: Policy v2

- [x] Add tests for role/tool/action/resource policy evaluation.
- [x] Implement `src/project_archive/harness_policy.py`.
- [x] Add `config/harness_policy.json`.
- [x] Wire policy-check through policy v2.
- [x] Add API endpoint for policy inspection.

### Task 4: Agent Profiles

- [x] Add tests for profile loading and forbidden tool rejection.
- [x] Implement `src/project_archive/agent_profiles.py`.
- [x] Add `config/agent_profiles.json`.
- [x] Make capability matrix derive from profiles.
- [x] Add API endpoint for agent profiles.

### Task 5: Timeline and Export

- [x] Add tests for timeline ordering and redacted export.
- [x] Implement `src/project_archive/harness_export.py`.
- [x] Add CLI `scripts/harness_export.py`.
- [x] Add timeline/export API endpoints.
- [x] Add compact frontend export/timeline affordances.

### Task 6: Safe Commands

- [x] Add tests for command listing, dry-run, and denied raw shell.
- [x] Implement `src/project_archive/harness_commands.py`.
- [x] Add CLI `scripts/harness_command.py`.
- [x] Add command API endpoints.

### Task 7: Trace Events

- [x] Add tests that ingestion/query/report helpers emit harness events.
- [x] Add lightweight run context helper.
- [x] Instrument ingestion, query, RAG rebuild, and intelligence report paths with aggregate events.
- [x] Avoid per-chunk event spam.

### Task 8: Artifact Retention

- [x] Add tests for manifest rebuild, orphan detection, cleanup dry-run.
- [x] Implement `src/project_archive/harness_artifact_retention.py`.
- [x] Add CLI `scripts/harness_artifacts.py`.
- [x] Add artifacts API endpoints.

### Task 9: Provider Resilience

- [x] Add tests for provider call guard, sanitized errors, fake provider failure.
- [x] Implement `src/project_archive/provider_runtime.py`.
- [x] Add provider events around live-model-adjacent service calls where feasible.
- [x] Keep real provider calls out of default tests.

### Task 10: GitHub Report-only Runner

- [x] Add tests for markdown report generation from deterministic inputs.
- [x] Implement `scripts/github_report_runner.py`.
- [x] Add `.github/workflows/twinmind-report.yml`.
- [x] Add `docs/twinmind_github_runner.md`.

### Task 11: Final Verification

- [x] Run `tests/unit/test_project_archive_harness.py`.
- [x] Run stdlib CLI smoke tests.
- [x] Run Python 3.12 `py_compile` for touched Python files.
- [x] Run `git diff --check`.
- [x] Attempt API and frontend verification once, report dependency blockers without installing dependencies.

Verification note: backend harness/API checks passed. Frontend build was attempted and blocked by missing local frontend dependencies (`tsc: command not found`; `frontend/node_modules` absent), and no dependency installation was performed.
