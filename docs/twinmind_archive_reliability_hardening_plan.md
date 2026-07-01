# TwinMind Archive Reliability Hardening Plan

This document records the next seven optimization points after the productization implementation pass. The focus is real-project reliability: making large uploaded projects easier to validate, clean, understand, and audit.

## 1. Real Large-Project Batch Regression Testing

Status: implementation pass complete.

Goal:

- Run a reusable regression check across all selected archives.
- Compare graph quality, entity/relation/evidence scale, Hybrid RAG readiness, multimodal readiness, evaluation status, language coverage, and blocking failures.
- Persist the result so regressions are visible after refresh.

Acceptance signals:

- A user can run one action and see which archives are healthy, sparse, noisy, or missing RAG/evaluation.
- The report explains what to fix before trusting Agent analysis.

Implemented:

- Stress test reports now include `regression_matrix`, `language_coverage`, and `blocking_failures`.
- Per-project stress rows include quality, evaluation, Hybrid RAG, multimodal, entity/relation/evidence counts, warnings, and language structure.
- The Task Center stress panel shows blocking failures and language coverage.

## 2. Graph Entity Quality Governance

Status: implementation pass complete.

Goal:

- Detect duplicate entity candidates, noisy low-value entities, unsupported relations, isolated hubs, and important entities.
- Surface entity quality in the graph workspace.
- Feed quality signals into curation and report generation.

Acceptance signals:

- Large graphs are not just bigger; they are cleaner and easier to inspect.
- The UI shows duplicate/noise/importance signals instead of making the user guess.

Implemented:

- Graph workspace reports now include `entity_quality`.
- The report detects duplicate candidates, noisy entities, unsupported relations, isolated entities, important entities, score, grade, and recommendations.
- The graph insight panel shows noise, duplicate, and entity quality signals.

## 3. Report Readability Enhancement

Status: implementation pass complete.

Goal:

- Improve the formal project intelligence report structure.
- Add section summaries, table-of-contents-like sections, evidence index, risk index, and clearer Markdown output.

Acceptance signals:

- Exported reports read like technical project analysis, not raw JSON summaries.
- Important claims remain tied to evidence.

Implemented:

- Formal project intelligence reports now include `sections`, `risk_index`, and `evidence_index`.
- Markdown export includes a contents section, risk index, and evidence index.
- Existing report panels continue to show summary, metrics, risks, evidence, and next actions.

## 4. More Real Agent Task Queue

Status: implementation pass complete.

Goal:

- Generate a deterministic project-specific Agent task plan before running ReAct.
- Base the queue on graph entry points, quality warnings, Hybrid RAG status, multimodal status, and evaluation gaps.
- Display the planned queue so Agent work feels deliberate.

Acceptance signals:

- Before running Agent analysis, users can see what the system intends to inspect and why.
- Task plans adapt to sparse graphs, missing RAG, missing evaluation, and image-heavy projects.

Implemented:

- Added `/api/archives/{project_id}/agent-task-plan`.
- The task planner uses graph entry points, quality warnings, entity quality, Hybrid RAG status, multimodal status, and evaluation availability.
- The Agent Analysis page now shows an Agent task plan panel before the ReAct mission controls.

## 5. Multi-Language Structure Signal Enhancement

Status: implementation pass complete.

Goal:

- Make Tree-sitter and language extraction health more visible.
- Report per-language structure signals such as files parsed, classes/functions/imports/interfaces/structs/enums/packages/namespaces, and semantic relation hints.

Acceptance signals:

- Users can tell whether Java, C++, TypeScript/JavaScript, Go, Rust, Python, configs, and docs were actually recognized.
- Sparse results can be traced to parsing gaps instead of mystery.

Implemented:

- Graph workspace reports now include `language_structure`.
- Language structure summarizes per-language files, entities, relations, evidence, Tree-sitter support, top entity types, top relation types, semantic relation hints, and warnings.
- Graph insight shows the first recognized language structure signals.

## 6. Frontend Performance And Large-Graph Interaction

Status: implementation pass complete.

Goal:

- Add more large-graph guardrails in the UI: entity quality summary, default result limits, relation/noise hints, and navigation affordances.
- Keep the graph workspace search-driven and neighborhood-driven.

Acceptance signals:

- Users can work with huge archives without expecting the whole graph to render at once.
- The UI shows why only a subset is visible.

Implemented:

- Graph workspace metadata now includes `large_graph_policy` with mode, default node/relation limits, reason, noise hints, and duplicate hints.
- The graph insight panel surfaces entity-quality guardrails that explain why search/neighborhood exploration is preferred.
- Layout styles were tightened for task plans, runtime evidence, and expanded stress metrics on mobile and desktop.

## 7. Runtime Evidence Transparency

Status: implementation pass complete.

Goal:

- Add a clear runtime evidence panel showing which model, embedding, vector store, BM25/RRF, graph store, vision path, and fallback paths were used.
- Make fallback behavior and failed components visible.

Acceptance signals:

- Users can answer: "Did this run use DeepSeek? Ollama vision? Chroma? BM25? RRF? Neo4j? Fallback?"
- Reports and UI expose configuration gaps before users trust conclusions.

Implemented:

- System config checks now include `metadata.runtime_evidence`.
- Runtime evidence reports LLM, embedding, vector store, Hybrid retrieval, graph store, vision, and fallback warnings.
- The System page renders a Runtime Evidence panel.

## Recommended Implementation Order

1. Batch regression testing.
2. Entity quality governance.
3. Runtime evidence transparency.
4. Multi-language structure signals.
5. Agent task queue.
6. Report readability.
7. Large-graph frontend refinements.
