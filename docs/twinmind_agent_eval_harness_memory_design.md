# TwinMind Archive AgentEval, Harness Engineering, and Memory Design

## Goal

Build a project-understanding harness that can run Agent analysis repeatedly, measure quality regressions, persist durable project memory, and explain whether the system is trustworthy for a given archive.

## Harness Engineering Layers

### 1. Memory and Filesystem

TwinMind memory is file-backed and project-scoped by default. Each archive owns a durable `agent_memory.json` file containing:

- stable facts from the latest archive, evaluation, Agent report, Hybrid RAG status, and missions;
- recurring risks and warnings;
- confirmed evidence IDs, entity IDs, and relation IDs;
- prior harness run summaries;
- recommendations for future runs.

The memory file is deliberately separate from model context. It survives process restarts and can be inspected, diffed, and versioned.

### 2. Verification and Guardrails

AgentEval combines several deterministic guardrails:

- archive evaluation score from golden questions;
- evidence coverage and graph coverage;
- Agent trust claims and unsupported/low-confidence counts;
- ReAct verifier and critic signals when missions exist;
- Hybrid RAG readiness and stale/low-coverage warnings;
- multimodal readiness.

The first implementation is deterministic and reproducible. LLM-as-judge can be added later as a second-layer evaluator, not as the only source of truth.

### 3. Sandbox and Breakers

Harness runs are bounded:

- project count and evaluation question count are limited by request schema;
- runs produce finite JSON reports;
- missing Agent reports, missing RAG status, or missing evaluation data become explicit warnings instead of crashing the harness;
- repeated runs update a bounded history file.

Future breaker work should add runtime budgets, cancellation, and regression severity thresholds per suite.

### 4. Tool Interfaces

Harness consumes existing tool surfaces:

- archive loader;
- Hybrid RAG status;
- evaluation runner;
- Agent report loader/runner;
- Agent trust checker;
- multimodal insights;
- mission trace/verifier summaries;
- stress test summary.

The public API exposes:

- `POST /api/archives/{project_id}/agent-eval/run`
- `GET /api/archives/{project_id}/agent-eval`
- `GET /api/archives/{project_id}/agent-memory`

## AgentEval Report Contract

Each report includes:

- project ID and run ID;
- quality gates with pass/warn/fail status;
- metrics for evaluation, trust, RAG, graph, multimodal, and mission evidence;
- regression status versus the previous harness run;
- recommendations;
- memory update summary.

## Quality Regression Rules

The first-pass regression rules are:

- fail if evaluation score drops by 0.15 or more;
- warn if evaluation score drops by 0.05 or more;
- warn if Hybrid RAG indexed chunks drop;
- warn if unsupported Agent claims increase;
- pass if no meaningful negative delta is detected.

## Memory Strategy

Memory is intentionally structured rather than conversational:

- `facts`: concise stable statements;
- `entities`, `relations`, `evidence`: IDs worth reusing;
- `risks`: recurring project or harness risks;
- `harness_runs`: compact run history;
- `recommendations`: next actions.

This keeps memory inspectable and prevents hidden, unbounded model context from becoming the system of record.
