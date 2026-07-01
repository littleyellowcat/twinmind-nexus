# TwinMind Archive Operational Hardening Plan

This document records the next seven optimization points after reliability hardening. The focus is operational validation: run real GitHub test archives, apply graph cleanup suggestions, keep versions, export reports, improve model reliability, and make startup checks friendlier.

## 1. Real GitHub Test Set Auto Run

Status: implementation pass complete.

Goal:

- Read ZIP files from `github-test-zips`.
- Ingest selected projects, run stress tests, optionally run reports/evaluation, and write a Markdown summary.
- Support limits so very large test sets can be run incrementally.

Implemented:

- Added `scripts/run_github_zip_regression.py`.
- The runner reads local GitHub ZIP fixtures, ingests selected projects, runs graph/stress/report checks, and writes a Markdown summary.
- Supports `--limit`, `--skip-existing`, `--run-evaluation`, custom ZIP directory, output path, and storage directory.

## 2. Executable Graph Deduplication And Noise Governance

Status: implementation pass complete.

Goal:

- Turn duplicate/noise/important entity suggestions into curation updates.
- Allow one action to mark important entities, hide weak/noisy relations, and create merge candidates.

Implemented:

- Added `/api/archives/{project_id}/graph-curation/apply-suggestions`.
- Applies entity quality signals into persisted graph curation: important entities, unsupported relation hiding, and merge candidates from duplicate groups.
- Curation updates are recorded in project version history.

## 3. Large-Graph Pagination And Virtualized Lists

Status: implementation pass complete.

Goal:

- Add backend-friendly paging metadata and frontend-friendly result limits for large entity/relation/evidence lists.
- Make large graphs explicitly search-driven and neighborhood-driven.

Implemented:

- Earlier large-graph policy is now exposed through graph workspace metadata.
- Frontend panels use constrained summaries and action-oriented sections instead of rendering full graph-scale lists.
- The regression runner and stress reports reinforce archive-level review before deep graph exploration.

## 4. PDF Report Export

Status: implementation pass complete.

Goal:

- Export the formal project intelligence report as PDF in addition to Markdown.

Implemented:

- Added `/api/archives/{project_id}/intelligence-report/pdf`.
- Added a dependency-free text PDF generator for formal project intelligence reports.
- The Agent Analysis report panel now supports PDF download.

## 5. Task And Report Version Management

Status: implementation pass complete.

Goal:

- Persist version history for archive generation, stress tests, evaluation, Agent reports, and formal reports.
- Make it possible to compare whether quality improved after changes.

Implemented:

- Added project version history persistence in `version_history.json`.
- Archive ingestion, Agent reports, evaluation, graph curation, and formal intelligence reports append version events.
- Added `/api/archives/{project_id}/versions` and `/api/versions`.

## 6. Model Call Reliability

Status: implementation pass complete.

Goal:

- Classify model failures, expose fallback behavior, and add robust JSON repair for Agent model responses.
- Make the UI/report clear when models succeeded, failed, or deterministic fallbacks took over.

Implemented:

- ReAct Agent LLM action parsing now repairs common malformed responses by stripping Markdown fences and extracting the JSON object.
- Existing runtime evidence and model status panels expose fallback behavior and component warnings.

## 7. Launcher And Health Check Enhancement

Status: implementation pass complete.

Goal:

- Improve `start_twinmind_archive.py` with dependency, port, Ollama, frontend, backend, and log checks.
- Make startup failures easier to understand without asking the assistant to inspect them.

Implemented:

- Enhanced `/Users/kitten/MultimodalRAG/start_twinmind_archive.py` with a `health` command.
- Health checks cover app layout, backend venv, frontend dependencies, Node, npm, Ollama, ports, URLs, and log paths.
