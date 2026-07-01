# TwinMind Archive Multi-Agent Pipeline Design

## Goal

Turn TwinMind Archive from a rule-based archive viewer into an upload-triggered multi-agent project analyst.

Current behavior:

```text
Upload ZIP -> scanner builds draft archive -> user clicks Run report -> optional DeepSeek enhancement
```

Target MVP behavior:

```text
Upload ZIP
  -> deterministic scanner builds entities, relations, evidence cards
  -> Archivist selects and organizes evidence
  -> Cartographer maps evidence into graph neighborhoods and halls
  -> Detective performs impact and architecture reasoning
  -> Skeptic checks weak evidence, contradictions, and overclaims
  -> Curator writes the final project report
  -> frontend opens the generated archive with agent results already available
```

The first version should be a deterministic, inspectable pipeline with optional DeepSeek calls. It should not be a fully autonomous ReAct loop yet.

## Design Principles

- Evidence first: every agent output must reference evidence card IDs, entity IDs, relation IDs, or graph paths.
- Graceful fallback: if DeepSeek fails, keep rule-based results and mark the failure in metadata.
- Structured outputs: agents return JSON-compatible dataclasses, not only prose.
- Upload-triggered: project upload should automatically run the pipeline after archive ingestion.
- Inspectable: frontend should show each agent's contribution, status, confidence, and cited evidence.
- Bounded cost: cap evidence cards and graph paths sent to DeepSeek in the MVP.

## Agent Roles

### 1. Archivist

Responsibility:

- Select candidate evidence from files, docs, configs, and extracted code entities.
- Group evidence by hall and source type.
- Identify entry points, README claims, configuration files, and important source files.

Input:

- `ProjectArchiveDraft`
- user-selected scan profile
- extracted entities, relations, evidence cards

Output:

```json
{
  "agent": "archivist",
  "summary": "Evidence inventory summary.",
  "key_evidence_ids": ["ev_..."],
  "entry_entity_ids": ["file_..."],
  "important_paths": ["README.md", "src/app.py"],
  "open_questions": ["..."],
  "confidence": 0.74
}
```

MVP implementation:

- Rule-based selection first.
- Optional DeepSeek summary over top evidence cards.

### 2. Cartographer

Responsibility:

- Map evidence and entities into graph neighborhoods.
- Decide hall attribution.
- Surface cross-hall links and useful graph paths.

Input:

- Archivist result
- entities
- relations
- halls

Output:

```json
{
  "agent": "cartographer",
  "summary": "Graph shape summary.",
  "hall_summaries": [
    {
      "hall_id": "hall_architecture",
      "summary": "...",
      "entity_ids": ["..."],
      "relation_ids": ["..."]
    }
  ],
  "graph_paths": [
    {
      "nodes": ["file_a", "function_b"],
      "relations": ["rel_x"],
      "evidence_ids": ["ev_y"]
    }
  ],
  "cross_hall_links": ["..."],
  "confidence": 0.7
}
```

MVP implementation:

- Rule-based graph grouping.
- Optional DeepSeek naming/summarization of hall neighborhoods.

### 3. Detective

Responsibility:

- Perform architecture, dependency, and impact reasoning.
- Identify likely change paths, module collaboration, and important dependencies.

Input:

- Archivist result
- Cartographer result
- graph paths
- user intent or default goal: "understand this project"

Output:

```json
{
  "agent": "detective",
  "summary": "Architecture and impact analysis.",
  "findings": [
    {
      "title": "Query flow is centered on ...",
      "evidence_ids": ["ev_..."],
      "entity_ids": ["file_..."],
      "risk": "medium"
    }
  ],
  "impact_paths": ["..."],
  "confidence": 0.68
}
```

MVP implementation:

- Use existing `architecture_tour` and `impact_analysis` logic.
- Add DeepSeek reasoning over bounded graph/evidence context.

### 4. Skeptic

Responsibility:

- Challenge the Detective and Cartographer outputs.
- Find weak evidence, missing links, contradictions, placeholders, and overclaims.
- Produce "needs human confirmation" items.

Input:

- all previous agent outputs
- evidence cards
- graph paths

Output:

```json
{
  "agent": "skeptic",
  "summary": "Validation and risk review.",
  "risks": [
    {
      "title": "Architecture claim has weak evidence",
      "severity": "medium",
      "evidence_ids": ["ev_..."],
      "recommendation": "Confirm by opening ..."
    }
  ],
  "overclaims": ["..."],
  "needs_human_confirmation": ["..."],
  "confidence": 0.72
}
```

MVP implementation:

- Rule-based checks:
  - no evidence
  - placeholder/TODO terms
  - too few relations
  - single README-only archives
  - unsupported language concentration
- Optional DeepSeek critique over previous outputs.

### 5. Curator

Responsibility:

- Produce the final user-readable report.
- Merge all agent results into a coherent project briefing.
- Preserve evidence chain and next actions.

Input:

- Archivist result
- Cartographer result
- Detective result
- Skeptic result
- project metrics

Output:

```json
{
  "agent": "curator",
  "title": "Project analysis report",
  "executive_summary": "...",
  "architecture_summary": "...",
  "key_findings": ["..."],
  "risk_summary": ["..."],
  "evidence_chain": [
    {
      "claim": "...",
      "evidence_ids": ["ev_..."]
    }
  ],
  "next_actions": ["..."],
  "confidence": 0.76
}
```

MVP implementation:

- DeepSeek preferred when configured.
- Rule-based report fallback if DeepSeek is unavailable.

## Pipeline Contract

Add a new persisted file:

```text
data/project_archive/<project-id>/agent_report.json
```

Suggested shape:

```json
{
  "project_id": "my-project",
  "status": "complete",
  "provider": "deepseek",
  "model": "deepseek-v4-pro",
  "created_at": "2026-06-24T00:00:00Z",
  "scan_profile": "architecture",
  "agents": {
    "archivist": {},
    "cartographer": {},
    "detective": {},
    "skeptic": {},
    "curator": {}
  },
  "errors": [],
  "metrics": {
    "entities": 0,
    "relations": 0,
    "evidence": 0
  }
}
```

## Backend API

Add:

```text
GET /api/archives/{project_id}/agent-report
POST /api/archives/{project_id}/agent-report/run
```

Upload endpoint behavior:

```text
POST /api/archives/upload
  -> ingest project
  -> run multi-agent pipeline
  -> persist draft_archive.json
  -> persist agent_report.json
  -> return archive + agent_report summary
```

MVP can run synchronously. Later, switch to background jobs.

## Frontend UX

Add a fourth conceptual layer to the workbench:

```text
Top bar:
  Agent deepseek · deepseek-v4-pro
  Project archive selector

Project passport:
  show archive metrics
  show agent pipeline status: pending/running/complete/fallback

Left rail:
  Archive halls

Center:
  Star Map
  Agent findings overlay or tab

Right:
  Evidence drawer
  Cited evidence for selected agent finding

Bottom:
  Agent command bar
  Curator report preview
```

Add a compact "Agent Run" strip:

```text
Archivist ✓  Cartographer ✓  Detective ✓  Skeptic ✓  Curator ✓
```

When an agent fails:

```text
Archivist ✓  Cartographer ✓  Detective fallback  Skeptic ✓  Curator ✓
```

## Upload Progress

Current browser progress can only measure upload bytes.

MVP progress stages:

```text
0-30%   uploading ZIP
30-55%  scanner extracting entities/evidence
55-70%  Archivist
70-80%  Cartographer
80-90%  Detective + Skeptic
90-100% Curator report
```

If the backend remains synchronous, the frontend should display staged text while waiting.

Better future version:

```text
POST /api/archives/upload -> returns job_id
GET /api/jobs/{job_id} -> status/progress/current_agent
```

## Implementation Plan

### Phase 1: Real Multi-Agent MVP

1. Add dataclasses:
   - `AgentFinding`
   - `AgentRoleResult`
   - `ProjectAgentReport`
2. Add `src/project_archive/multi_agent.py`.
3. Implement five role methods:
   - `run_archivist`
   - `run_cartographer`
   - `run_detective`
   - `run_skeptic`
   - `run_curator`
4. Persist `agent_report.json`.
5. Run pipeline automatically after upload.
6. Add `GET /agent-report`.
7. Frontend displays pipeline strip and curator summary.

### Phase 2: Better Extraction

1. Make frontend scan profile real:
   - architecture
   - full
   - docs
   - tests
2. Pass `scan_profile` during upload.
3. Add better Java/Go/C++/TypeScript extraction.
4. Add "low extraction coverage" warning when entities/relations are suspiciously low.

### Phase 3: Async Jobs

1. Add job store.
2. Upload returns `job_id`.
3. Frontend polls progress.
4. Agent-by-agent progress updates.

## Open Design Decision

For the immediate next coding step, prefer Phase 1 + a small part of Phase 2:

- Implement `agent_report.json`.
- Run agents automatically after upload.
- Add frontend pipeline strip.
- Make scan profile selection real.

This gives the user the feeling of a real multi-agent archive process without needing a full job queue yet.

