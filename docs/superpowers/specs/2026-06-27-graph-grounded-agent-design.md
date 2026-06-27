# TwinMind Archive Graph-Grounded Agent Design

Date: 2026-06-27

## Proposal

TwinMind Archive should evolve from a rule-first archive analyzer into a real agentic project analyst. The current system already has strong deterministic foundations: project ZIP ingestion, multi-language Tree-sitter extraction, semantic graph enrichment, Hybrid RAG, evidence cards, graph exploration, and a five-role Agent report pipeline. The missing piece is not another free-form chat agent. The missing piece is a bounded Agent runtime that can plan, inspect graph/RAG evidence, choose tools, verify claims, and leave an auditable trace.

This design adopts the lightweight OpenSpec idea of aligning on proposal, behavior, design, and tasks before implementation, while keeping the existing TwinMind documentation structure. It does not introduce an `openspec/` directory or OpenSpec CLI dependency.

The recommended paradigm is:

```text
Deterministic ingestion
  -> Knowledge graph + Hybrid RAG + evidence store
  -> Supervisor Plan-and-Execute
  -> Graph-grounded ReAct loops inside bounded tasks
  -> Critic / Verifier
  -> Curator report and frontend trace
```

In short: Plan-and-Execute controls the full mission, ReAct handles local exploration, and Verifier prevents unsupported claims.

## Current System

The current Agent system has three parts:

- `AgentWorkflow` in `src/project_archive/agents.py`: rule-based query modes with optional DeepSeek enhancement.
- `MultiAgentPipeline` in `src/project_archive/multi_agent.py`: sequential roles `archivist -> cartographer -> detective -> skeptic -> curator`.
- `run_architecture_mission` in `src/project_archive/autonomous_mission.py`: deterministic bounded task queue for architecture exploration.

These are useful, but they are not yet true ReAct:

- The Agent does not choose tools dynamically from observations.
- Tool calls are not modeled as first-class trace events.
- Planning is mostly fixed rather than adaptive.
- The verifier is a role in the report pipeline, not a reusable claim checker.
- The frontend shows reports and history, but not a rich Agent reasoning trajectory.

## Goals

The new Agent runtime must:

- Let the system explore an unfamiliar project without the user knowing what entity to search first.
- Use project graph and Hybrid RAG tools as the Agent's action space.
- Store every tool call, observation summary, evidence reference, and final answer.
- Keep the Agent bounded by step count, tool-call count, timeout, and evidence requirements.
- Preserve deterministic ingestion. Source scanning, Tree-sitter parsing, vision captioning, graph construction, and indexing must remain reproducible.
- Support the existing five specialist roles without deleting the current pipeline in one large rewrite.
- Make the frontend answer "what did the Agent actually do?"

## Non-Goals

This change will not:

- Turn project ingestion into an LLM-driven process.
- Show raw chain-of-thought text in the frontend.
- Allow unbounded autonomous loops.
- Let the LLM execute shell commands or arbitrary code.
- Replace graph/RAG retrieval with model memory.
- Replace the existing report pipeline in the first implementation pass.
- Require LangGraph or another heavy orchestration framework for the first version.

## Paradigm Comparison

### Option 1: Pure ReAct

Pure ReAct would run one Agent loop where the model repeatedly reasons, chooses a tool, observes the result, and eventually answers.

This is simple conceptually, but it is not the best top-level architecture for TwinMind Archive. Large project analysis needs global planning, durable task state, and validation. Pure ReAct can wander, over-query, or stop too early.

### Option 2: Plan-and-Execute With Graph-Grounded ReAct

The Supervisor first creates a bounded mission plan. Each task then runs a local ReAct loop over allowed tools such as graph search, graph neighborhood, Hybrid RAG, evidence lookup, and specialist role execution.

This is the recommended architecture. It keeps global control while still giving each task real exploration ability.

### Option 3: State-Graph Agent Runtime

A LangGraph-style runtime would model each phase as an explicit state node: plan, retrieve, inspect graph, verify, report, stop.

This is a strong future direction, but it is heavier than needed for the first implementation. The first version should use explicit dataclasses and service methods, then migrate to a state graph only if complexity demands it.

## Behavioral Specification

### Requirement: Mission Planning

The system SHALL create a bounded mission plan before running ReAct exploration.

#### Scenario: Default architecture mission

- GIVEN a generated project archive
- WHEN the user starts an architecture Agent mission
- THEN the system creates a mission with ordered tasks
- AND each task has an objective, allowed tools, input hints, budget, and status

#### Scenario: User question mission

- GIVEN a user asks a project-level question
- WHEN the question needs multi-step investigation
- THEN the system creates a short mission plan from the question
- AND the final answer cites evidence from the explored project archive

### Requirement: Graph-Grounded ReAct Loop

The system SHALL run ReAct loops inside bounded tasks using only approved TwinMind tools.

#### Scenario: Tool selection

- GIVEN a task objective and current observations
- WHEN the Agent chooses the next action
- THEN the selected action MUST be one of the registered project tools
- AND the action input MUST be JSON-serializable
- AND the action result MUST be stored as an observation event

#### Scenario: Evidence-first answer

- GIVEN a ReAct task reaches a final conclusion
- WHEN it produces findings
- THEN each finding SHOULD cite evidence card IDs, entity IDs, relation IDs, or retrieval result IDs
- AND unsupported claims MUST be marked as uncertain

### Requirement: Verification

The system SHALL verify findings before final mission completion.

#### Scenario: Unsupported claim

- GIVEN a finding has no evidence reference
- WHEN the verifier checks the task output
- THEN the finding is marked as unsupported
- AND the mission either requests more evidence or reports the uncertainty

#### Scenario: Sparse graph

- GIVEN a project has few relations in the selected scope
- WHEN the Agent tries to explain architecture
- THEN the verifier flags sparse relation coverage
- AND the final answer must say that confidence is limited

### Requirement: Frontend Trace

The frontend SHALL show an inspectable Agent trajectory without exposing raw hidden reasoning.

#### Scenario: Running task

- GIVEN a mission is running
- WHEN the Agent calls tools
- THEN the frontend shows task status, tool name, observation summary, evidence count, and elapsed time

#### Scenario: Completed mission

- GIVEN a mission completes
- WHEN the user opens Agent Analysis
- THEN the frontend shows plan, completed tasks, tool timeline, verifier results, evidence chain, and final report

## Architecture

### Core Components

```text
ProjectArchiveService
  ├─ AgentMissionService
  │   ├─ MissionPlanner
  │   ├─ ReActTaskRunner
  │   ├─ AgentToolRegistry
  │   ├─ EvidenceVerifier
  │   └─ MissionStore
  ├─ Existing graph explorer
  ├─ Existing Hybrid RAG index
  └─ Existing MultiAgentPipeline
```

### Mission Planner

The planner converts a user goal into bounded tasks. The first implementation should use deterministic templates with optional LLM enhancement.

Example task plan:

```json
[
  {
    "task_type": "find_entry_points",
    "objective": "Find likely entry points and startup paths.",
    "allowed_tools": ["graph_summary", "graph_search", "inspect_entity"],
    "max_steps": 3
  },
  {
    "task_type": "map_core_modules",
    "objective": "Map high-degree modules and their relations.",
    "allowed_tools": ["graph_neighborhood", "list_halls", "get_evidence"],
    "max_steps": 4
  },
  {
    "task_type": "explain_architecture",
    "objective": "Produce an evidence-backed architecture explanation.",
    "allowed_tools": ["hybrid_search", "run_specialist_agent", "get_evidence"],
    "max_steps": 4
  }
]
```

### ReAct Task Runner

Each task runs a bounded loop:

```text
1. Build task context from mission state and archive summary.
2. Ask model for a structured next action.
3. Validate action against registered tools and task budget.
4. Execute tool.
5. Store observation summary and evidence references.
6. Continue until final answer, verifier stop, or budget exhaustion.
```

The model response must be structured JSON:

```json
{
  "thought_summary": "Need to inspect entry point neighbors.",
  "action": {
    "tool": "graph_neighborhood",
    "input": {
      "focus_entity_id": "file_123",
      "depth": 1,
      "node_limit": 40
    }
  },
  "stop": false
}
```

The system stores `thought_summary`, not raw chain-of-thought. The prompt must tell the model to provide concise rationale only.

### Tool Registry

The first tool set should wrap existing project services:

- `list_halls(project_id)`: returns hall IDs, names, entity counts.
- `graph_summary(project_id)`: returns metrics and recommended starts.
- `graph_search(project_id, query, limit)`: searches entities.
- `graph_neighborhood(project_id, focus_entity_id, hall_id, depth, relation_types)`: returns scoped graph.
- `hybrid_search(project_id, query, hall_id, top_k)`: retrieves vector/BM25/RRF context.
- `get_evidence(project_id, evidence_ids)`: returns evidence cards.
- `inspect_entity(project_id, entity_id)`: returns entity details, relations, linked evidence.
- `run_specialist_agent(project_id, role, task_context)`: invokes deterministic specialist logic for archivist/cartographer/detective/skeptic/curator.

The first version should not expose arbitrary shell tools, filesystem tools, or network tools to the Agent.

### Evidence Verifier

The verifier checks task outputs and final reports:

- Every finding has at least one evidence reference, or is explicitly marked `uncertain`.
- Evidence IDs exist in the current project archive.
- Entity and relation IDs exist in the current graph.
- Claims about dependencies, entry points, and modules cite either graph relations or retrieved evidence.
- Low graph density, timeout, or budget exhaustion lowers confidence.

The verifier can be deterministic first. Optional DeepSeek critique can be added later.

### Mission Store

Persist mission state under the existing project archive storage:

```text
data/project_archive/<project_id>/missions/<mission_id>.json
```

The existing mission JSON should be extended rather than replaced. New trace records can be added through backward-compatible optional fields.

## Data Model

Add or extend dataclasses in `src/project_archive/types.py`.

### AgentMission

Represents the full run:

- `id`
- `project_id`
- `goal`
- `status`
- `created_at`
- `completed_at`
- `budget`
- `tasks`
- `trace_events`
- `verifier_result`
- `final_report`
- `metadata`

### AgentTask

Represents one planned task:

- `id`
- `mission_id`
- `task_type`
- `objective`
- `status`
- `allowed_tools`
- `max_steps`
- `steps_used`
- `input_entity_ids`
- `output_entity_ids`
- `evidence_ids`
- `findings`
- `risks`
- `confidence`

### AgentTraceEvent

Represents inspectable ReAct activity:

- `id`
- `mission_id`
- `task_id`
- `sequence`
- `event_type`: `plan`, `action`, `observation`, `verification`, `final`
- `tool_name`
- `tool_input`
- `observation_summary`
- `evidence_ids`
- `entity_ids`
- `relation_ids`
- `started_at`
- `completed_at`
- `error`

## Backend API

Add endpoints under the existing FastAPI app:

- `POST /api/archives/{project_id}/agent-missions`
  - starts a graph-grounded Agent mission
  - body: `goal`, `mode`, `max_tasks`, `max_steps_per_task`
- `GET /api/agent-missions/{mission_id}`
  - returns mission state and final report if available
- `GET /api/agent-missions/{mission_id}/trace`
  - returns trace events
- `POST /api/agent-missions/{mission_id}/pause`
- `POST /api/agent-missions/{mission_id}/resume`
- `POST /api/agent-missions/{mission_id}/stop`

The existing mission endpoints can remain for compatibility. The new endpoints should either wrap or supersede them through a clearer Agent mission model.

## Frontend UX

The Agent Analysis page should gain a real ReAct mission panel:

- Mission header: project, goal, status, model, budget, elapsed time.
- Plan view: ordered tasks with status and confidence.
- Tool timeline: action, observation summary, evidence count, duration.
- Evidence chain: clickable evidence cards used by the current task.
- Verifier panel: supported findings, uncertain claims, sparse graph warnings.
- Final report: concise architecture explanation with citations.

The frontend must not show raw hidden chain-of-thought. It should show:

- task objective
- concise thought summary
- tool selected
- observation summary
- evidence references
- verifier result

## Error Handling

The Agent runtime must degrade gracefully:

- If the LLM times out, the task falls back to deterministic specialist logic.
- If model JSON is invalid, the repair parser gets one attempt, then the task records a structured failure.
- If a tool fails, the trace records the error and the Agent may choose another tool within budget.
- If evidence is missing, the verifier lowers confidence and marks the claim uncertain.
- If budget is exhausted, the mission returns a partial result with next recommended actions.

## Implementation Tasks

### Phase 1: Runtime Foundation

- Add Agent mission dataclasses.
- Add `AgentToolRegistry`.
- Wrap existing graph/RAG/evidence capabilities as tools.
- Add mission persistence with trace events.
- Add deterministic mission planner.

### Phase 2: ReAct Runner

- Add structured model prompt for next action.
- Add JSON parsing and repair fallback.
- Add step budgeting and stop conditions.
- Add action validation against allowed tools.
- Add trace event persistence.

### Phase 3: Verifier

- Add deterministic evidence verifier.
- Validate evidence/entity/relation references.
- Mark unsupported findings as uncertain.
- Add confidence calculation.

### Phase 4: API Integration

- Add mission start/read/trace endpoints.
- Keep old mission endpoints working.
- Add tests for mission lifecycle and trace shape.

### Phase 5: Frontend Integration

- Add Agent mission panel to Agent Analysis.
- Show plan, timeline, verifier, evidence chain, final report.
- Add loading, failure, partial-result, and budget-exhausted states.

### Phase 6: Upgrade Specialist Agents

- Let specialist roles run inside ReAct tasks.
- Preserve existing `MultiAgentPipeline` as a compatibility path.
- Gradually move report generation to Supervisor-managed missions.

## Acceptance Criteria

The implementation is successful when:

- Starting an Agent mission creates a durable plan and task queue.
- At least one task performs multiple tool calls chosen from observations.
- Tool calls are stored as trace events and visible through API.
- Final findings cite valid evidence IDs or are marked uncertain.
- Budget limits stop runaway loops.
- The system can answer "what did the Agent do?" from stored trace data.
- The frontend shows the mission timeline, not only final prose.
- Existing upload, archive viewing, graph explorer, and report APIs continue to work.

## Testing Plan

Backend tests:

- Planner creates bounded tasks for architecture and custom questions.
- Tool registry rejects unknown tools and invalid inputs.
- ReAct runner records action and observation events.
- Runner stops at max steps.
- Verifier detects missing evidence and invalid IDs.
- Mission persistence round-trips through JSON.
- API returns mission state and trace events.

Frontend tests:

- Agent Analysis renders mission plan and trace.
- Tool timeline displays action, observation, evidence count, and error states.
- Verifier warnings are visible.
- Partial and failed missions remain inspectable.

Manual validation:

- Run a mission on `java__apache__dubbo.zip`.
- Confirm it explores entry points, modules, dependencies, and evidence.
- Confirm final report cites evidence and graph entities.
- Confirm no raw chain-of-thought is displayed.

## First-Version Decisions

To keep the implementation focused, the first version will use these decisions:

- Agent missions run through FastAPI background tasks, matching the existing upload and report job style.
- Specialist roles are exposed through one `run_specialist_agent` tool with a `role` argument.
- DeepSeek is used for structured next-action JSON and final task summaries. Deterministic fallbacks remain available for every task.
- Old deterministic missions and new Agent missions appear in one Agent Analysis timeline, with old missions marked as legacy records.
- The runtime uses explicit dataclasses and services, not LangGraph, for the first implementation.

## Future Options

Later versions may add:

- A lightweight worker queue for long-running missions.
- Separate tools for each specialist role.
- A state-graph runtime if mission branching becomes hard to maintain.
- A richer verifier that uses DeepSeek to critique evidence coverage after deterministic checks pass.
