# TwinMind Archive Productization Optimization Plan

This document records the next seven optimization directions after the second-stage implementation pass. The focus of this stage is to make TwinMind Archive easier to trust on real large projects, easier to operate during long-running ingestion, and more useful as a polished project-intelligence workspace.

## 1. Real Large-Project End-To-End Stress Testing

Status: implementation pass complete.

Goal:

- Build a fixed cross-language test set for Python, Java, TypeScript, Go, Rust, and C++.
- Run archive generation, graph exploration, Hybrid RAG, multimodal extraction, Agent analysis, and evaluation on each project.
- Produce an ingestion quality report for every run.

Acceptance signals:

- A user can run one command or UI action and see whether each test project produced a useful archive.
- Sparse halls, missing relations, failed vision, failed Hybrid RAG, and extraction gaps are reported with actionable recommendations.

Implemented in this pass:

- Added `/api/stress-test/run` and `/api/stress-test/latest` for persisted archive health reports.
- Stress reports summarize per-project graph quality, evaluation status, Hybrid RAG readiness, multimodal readiness, entity/relation/evidence counts, warnings, and recommendations.
- The Task Center page now includes an Archive Stress Test panel with a one-click run action and latest report summary.

## 2. Graph Quality Score

Status: implementation pass complete.

Goal:

- Add a deterministic Graph Quality Score for each archive.
- Score entity coverage, relation density, isolated node ratio, evidence coverage, Tree-sitter success, Hybrid RAG health, and multimodal support.
- Show the score in the UI so users know whether an archive is healthy before trusting it.

Acceptance signals:

- Every archive has a quality score and grade.
- The UI explains why the score is high or low.
- The score helps diagnose "large project but sparse graph" cases.

Implemented in this pass:

- Backend `graph/workspace` now returns a deterministic `quality` report with grade, weighted component scores, diagnostic signals, warnings, and recommendations.
- Frontend graph insight panel shows the quality grade and the first actionable warning/recommendation.
- API coverage asserts the quality payload is present.

## 3. Upload And Analysis Task Center

Status: implementation pass complete.

Goal:

- Add a task center for running, completed, failed, and cancelled jobs.
- Show progress, stage history, project ID, failure reason, and retry/cancel actions.
- Separate project-local task history from global task history.

Acceptance signals:

- Users can tell whether archive generation is still running, failed, completed, or cancelled.
- Failed jobs show the stage and error instead of disappearing.

Implemented in this pass:

- Added a dedicated Task Center tab for global and current-project archive jobs.
- The page shows running, complete, failed, and cancelled counts, progress bars, stage history, error details, refresh, and cancel actions.
- The UI uses the existing job list/cancel APIs, so upload and analysis task state is no longer trapped in page-local side panels.

## 4. Formal Project Intelligence Report

Status: implementation pass complete.

Goal:

- Turn Agent output into a structured project understanding report.
- Include project overview, architecture layers, core modules, call chains, config dependencies, risks, evidence chain, RAG citations, multimodal evidence, and next actions.
- Support Markdown export first, then PDF export later.

Acceptance signals:

- A user can export a readable report after running Agent analysis.
- Claims without evidence are explicitly marked.

Implemented in this pass:

- Added `/api/archives/{project_id}/intelligence-report`, `/run`, and `/markdown`.
- The report compiles graph quality, architecture layers, entry points, config dependencies, call chains, risks, evidence chain, Hybrid RAG status, multimodal evidence, coverage, and next actions.
- Reports are persisted as both `project_intelligence_report.json` and `project_intelligence_report.md`.
- The Agent Analysis page now includes a formal report panel with generate/refresh and Markdown download.

## 5. Intelligent Graph Entry Points

Status: implementation pass complete.

Goal:

- Recommend "start here" paths for unfamiliar projects.
- Surface core modules, high-risk regions, important call chains, configuration centers, external dependency entry points, and likely service boundaries.

Acceptance signals:

- Users do not need to know search keywords before exploring.
- The graph page provides meaningful first clicks for large archives.

Implemented in this pass:

- Graph workspace reports now include `entry_points` for runtime entries, configuration centers, documentation anchors, dependency surfaces, service/API boundaries, and weak-evidence regions.
- Each entry point carries category, title, reason, score, entity list, and suggested action.
- The graph insight panel surfaces the top entry paths before the user searches.

## 6. Stronger Multimodal Understanding

Status: implementation pass complete.

Goal:

- Improve OCR, diagram node extraction, image relation extraction, and entity alignment between images and code/config/docs.
- Mark answers and Agent claims that are supported by image-derived evidence.

Acceptance signals:

- Architecture diagrams can contribute candidate graph nodes and relations.
- The UI explains whether image understanding came from vision, OCR, fallback metadata, or all of them.

Implemented in this pass:

- Multimodal insights now include understanding method counts, image-to-entity alignment, and evidence support status.
- Image evidence is aligned to graph entities through linked evidence, OCR text, diagram tokens, file names, entity names, and source paths.
- The UI shows alignment counts, supported image evidence status, and method distribution.

## 7. ReAct Agent Visualization Upgrade

Status: implementation pass complete.

Goal:

- Make ReAct missions easier to inspect visually.
- Show why each step ran, which tool was called, what came back, what was learned, where self-correction happened, and which conclusions remain unsupported.

Acceptance signals:

- Agent work feels auditable rather than magical.
- Users can distinguish model reasoning, deterministic tools, graph evidence, Hybrid RAG evidence, and fallback behavior.

Implemented in this pass:

- Added `/api/agent-missions/{mission_id}/visualization`.
- The visualization report groups trace events into planning, action, observation, verification, and final phases.
- It records task cards, tool timeline, trace counts, tool calls, evidence/entity/relation counts, errors, critic reviews, retries, supported tasks, unsupported tasks, and warnings.
- The ReAct Agent panel now renders a visual audit summary and phase grid in addition to the raw trace.

## Recommended Implementation Order

1. Graph Quality Score.
2. Upload And Analysis Task Center.
3. Real Large-Project End-To-End Stress Testing.
4. Intelligent Graph Entry Points.
5. Formal Project Intelligence Report.
6. Stronger Multimodal Understanding.
7. ReAct Agent Visualization Upgrade.

The first two items should land first because they make every later optimization easier to test: users need to know whether the archive is good and whether long-running work is still alive.
