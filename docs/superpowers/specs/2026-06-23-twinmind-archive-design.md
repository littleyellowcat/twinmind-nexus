# TwinMind Archive Design

Date: 2026-06-23

## Summary

TwinMind Archive is an agentic multimodal GraphRAG workspace for creating a project knowledge digital twin. It turns a project directory into an explorable knowledge archive: source code, documentation, configuration, diagrams, screenshots, and later issues or commits become structured evidence, graph entities, relationships, and archive halls.

The system builds on the existing Modular RAG MCP Server. It keeps the existing hybrid retrieval foundation while adding a project knowledge graph, human-correctable archive generation, multi-agent reasoning workflows, and an archive-first visual workspace.

One-sentence positioning:

> Turn a project into an explorable, evidence-backed knowledge archive for architecture tours, impact analysis, risk audits, and traceable Q&A.

## Product Direction

TwinMind Archive is not a generic document Q&A bot. It is a project knowledge twin:

- Users import a project directory.
- The system scans code, documentation, and configuration.
- The system generates a draft archive with halls, entities, relationships, evidence cards, and a confirmation report.
- Users can correct low-confidence entities or relationships.
- Users query the archive through four work modes.
- Answers include conclusions, evidence cards, graph paths, agent traces, risks, and next actions.

The first demo project should be `MODULAR-RAG-MCP-SERVER` itself. This creates a strong meta demo: a RAG system reads and builds a digital twin of a RAG system.

## Visual Metaphor

Primary metaphor: archive or museum.

- Archive halls represent modules, themes, or project areas.
- Artifacts represent functions, files, APIs, concepts, decisions, and risks.
- Evidence cards represent original source snippets, documentation excerpts, configuration values, image captions, commits, or issues.
- Agents act like archive roles that retrieve, map, investigate, challenge, and curate knowledge.

Secondary metaphor: star map.

- The star map shows cross-hall relationships, concept clusters, multi-hop paths, and hidden connections.
- It is an auxiliary view, not the MVP's main workflow.

MVP visual layout:

- Left: archive hall navigation.
- Center: graph canvas showing the current evidence path.
- Right: evidence cards.
- Bottom: agent timeline.
- Top: question input and work mode selector.

## Work Modes

TwinMind Archive supports four work modes. The MVP should implement all four at a useful level, while emphasizing impact analysis and risk audit as differentiators.

### Architecture Tour

For users who import a project and want to understand it quickly.

Example questions:

- What is this project's core architecture?
- What are the main modules?
- How does a query request flow through the system?
- Which files are the most important entry points?

Output:

- Architecture summary.
- Core modules.
- Data flow.
- Key entry files.
- Module graph.
- Evidence cards.

### Impact Analysis

For users who want to add or change functionality.

Example questions:

- If I add a knowledge graph layer, which modules are affected?
- If I add Java project parsing, where should I make changes?
- If I replace Chroma with Milvus, what is the impact path?

Output:

- Affected modules.
- Relevant interfaces.
- Dependency paths.
- Recommended implementation order.
- Risks.
- Evidence cards.
- Graph paths.

This is a primary MVP showcase mode.

### Risk Audit

For users who want to detect contradictions, gaps, and implementation risks.

Example questions:

- Does the README match the real code?
- Which documented features are not fully implemented?
- Are provider options in config consistent with factory implementations?

Output:

- Risk list with severity.
- Documentation evidence.
- Code evidence.
- Contradiction or gap explanation.
- Suggested fix.
- Skeptic agent notes.

The current repository already has a useful example: `main.py` still looks like an early placeholder entry point, while the real MCP stdio server is implemented in `src/mcp_server/server.py`.

### Evidence Q&A

For direct project questions.

Example questions:

- Which LLM providers are supported?
- Where does image captioning happen?
- What MCP tools are exposed?

Output:

- Direct answer.
- Source citations.
- Evidence cards.
- Relevant entities.
- Optional graph path.
- Evidence completeness note.

## Architecture

The system has five layers:

```text
Project Ingestion Layer
  -> Multimodal RAG Layer
  -> Project Knowledge Graph Layer
  -> Agent Orchestration Layer
  -> TwinMind Archive Workspace
```

### 1. Project Ingestion Layer

This layer turns project materials into indexable and extractable source units.

Phase 1 inputs:

- Python source files.
- Markdown documents such as `README.md` and `DEV_SPEC.md`.
- Configuration files such as `pyproject.toml`, YAML, and TOML.

Phase 2 inputs:

- Architecture diagrams.
- Flowcharts.
- Screenshots.
- PDF images and image captions.

Phase 3 inputs:

- Git commit logs.
- Issues.
- Changelogs.
- Task notes.

The existing project is PDF-oriented, so TwinMind Archive needs project-aware loaders:

- `ProjectScanner`
- `CodeLoader`
- `MarkdownLoader`
- `ConfigLoader`
- later `ImageArtifactLoader`
- later `GitHistoryLoader`

### 2. Multimodal RAG Layer

This layer finds evidence.

Reuse existing capabilities:

- Dense embedding retrieval.
- BM25 sparse retrieval.
- RRF fusion.
- Optional reranking.
- Image captions as searchable text.
- ChromaDB vector storage.
- Existing trace patterns.

Retrieval results become evidence cards, not just chunks. They feed graph expansion and agent reasoning.

### 3. Project Knowledge Graph Layer

This layer organizes relationships.

The graph answers questions that plain chunk retrieval cannot answer well:

- Which chunk supports which decision?
- Which config affects which module?
- Which file defines which API?
- Which function or module is affected by a proposed change?
- Which documentation claim contradicts implementation?

The graph store must be pluggable:

- MVP default: `KuzuGraphStore`.
- Fallback: `SQLiteGraphStore`.
- Phase 2 advanced mode: `Neo4jGraphStore`.

The `GraphStore` interface should hide backend-specific details from ingestion, agents, and UI.

### 4. Agent Orchestration Layer

This layer decides how to reason.

MVP should use deterministic workflows plus LLM reasoning steps, not a fully autonomous ReAct loop. This keeps outputs stable and testable.

Agents:

- `ArchivistAgent`: retrieves evidence through RAG.
- `CartographerAgent`: maps evidence to graph entities and paths.
- `DetectiveAgent`: performs impact analysis and multi-hop tracing.
- `SkepticAgent`: checks contradictions, missing evidence, and overreach.
- `CuratorAgent`: produces the final user-facing report.

All agents must return structured JSON-like results. Natural language alone is not enough.

### 5. TwinMind Archive Workspace

This layer shows the archive.

MVP should extend the existing Streamlit dashboard with a `TwinMind Archive` page:

- Project import status.
- Archive hall navigation.
- Work mode selector.
- Graph path canvas.
- Evidence card panel.
- Agent timeline.
- Draft archive confirmation report.

Later phases can move to React, React Flow, Cytoscape, and Three.js for stronger archive and star-map visuals.

## MVP Scope

MVP goal: project skeleton twin.

Inputs:

- Python source code.
- Markdown documentation.
- YAML/TOML configuration.

Outputs:

- Archive halls.
- Entities.
- Relationships.
- Evidence cards.
- Draft archive confirmation report.
- Four work modes.
- Streamlit workspace.

Out of scope for MVP:

- Full 3D metaverse.
- VR or multiplayer workspace.
- Enterprise permission system.
- Full issue and commit timeline.
- Deep multi-language static analysis.
- Perfect automatic knowledge graph extraction.

MVP success depends on visible evidence chains, correctable graph output, and clear work modes, not on perfect graph extraction.

## Data Flow

```text
Import project directory
  -> ProjectScanner
  -> Loader routing
       -> CodeLoader
       -> MarkdownLoader
       -> ConfigLoader
  -> Parsing / chunking
       -> document chunks
       -> code structure blocks
       -> config blocks
  -> RAG indexing
       -> dense embeddings
       -> BM25 index
       -> Chroma upsert
  -> KG extraction
       -> entity extraction
       -> relationship extraction
       -> evidence binding
  -> Draft archive generation
       -> archive halls
       -> confirmation report
  -> User confirmation
       -> entity edits
       -> relationship edits
       -> hall assignment edits
  -> Query workspace
       -> hybrid RAG retrieval
       -> KG expansion
       -> agent reasoning
       -> evidence report + graph path
```

Query-time flow:

```text
User question
  -> work mode selection
  -> Hybrid RAG retrieval
  -> KG entity matching and graph expansion
  -> mode-specific agent workflow
  -> structured answer
  -> UI render with evidence cards and graph path
```

## Data Model

### Core Entities

- `Project`
- `Module`
- `Directory`
- `File`
- `Class`
- `Function`
- `API`
- `Config`
- `Concept`
- `Decision`
- `Risk`
- `Evidence`
- `ArchiveHall`
- `AgentRun`
- `GraphPath`

Future entities:

- `ImageArtifact`
- `Diagram`
- `Commit`
- `Issue`
- `Task`
- `Person`
- `TimelineEvent`

### Core Relationships

- `Project CONTAINS Module`
- `Module CONTAINS File`
- `Directory CONTAINS File`
- `File DEFINES Class`
- `File DEFINES Function`
- `Function CALLS Function`
- `File IMPORTS File`
- `Config CONFIGURES Module`
- `Document MENTIONS Concept`
- `Evidence SUPPORTS Decision`
- `Evidence SUPPORTS Answer`
- `Risk AFFECTS Module`
- `Decision AFFECTS Module`
- `Entity DERIVED_FROM Evidence`
- `Entity BELONGS_TO ArchiveHall`
- `Entity RELATED_TO Concept`
- `Evidence CONTRADICTS Evidence`

### Evidence Card

Evidence cards are the atomic source of trust.

```json
{
  "id": "ev_001",
  "source_type": "code",
  "source_path": "src/mcp_server/server.py",
  "title": "MCP stdio server entry",
  "snippet": "async with mcp.server.stdio.stdio_server()...",
  "line_start": 55,
  "line_end": 70,
  "linked_entities": ["MCPServer", "ProtocolHandler"],
  "confidence": 0.92
}
```

Every important conclusion should be linked to one or more evidence cards.

### Archive Hall

Archive halls are both UI groups and graph groupings.

```json
{
  "id": "hall_retrieval",
  "name": "Retrieval Hall",
  "description": "Dense, BM25, RRF, and rerank modules",
  "entities": ["HybridSearch", "DenseRetriever", "SparseRetriever"],
  "risks": ["BM25 index freshness", "rerank disabled by default"]
}
```

### Agent Result

Agent results must be structured for UI rendering and tests.

```json
{
  "mode": "impact_analysis",
  "question": "If I add a knowledge graph, which modules are affected?",
  "summary": "...",
  "affected_entities": ["IngestionPipeline", "QueryKnowledgeHubTool"],
  "graph_paths": [
    ["IngestionPipeline", "produces", "Chunk", "feeds", "KGExtractor"]
  ],
  "evidence_cards": ["ev_001", "ev_002"],
  "risks": ["Graph extraction should not block the ingestion pipeline"],
  "next_actions": ["Add KGExtractionTransform", "Extend MCP response schema"]
}
```

## Multi-Language Support

The architecture should not be Python-only.

Use a language adapter layer:

```text
ProjectScanner
  -> LanguageDetector
  -> LanguageAdapter
       -> PythonAdapter
       -> JavaAdapter
       -> CppAdapter
       -> TypeScriptAdapter
       -> GenericTextAdapter
```

Support levels:

- Level 1: generic recognition for all languages. File, directory, comments, imports/includes, rough class/function names, RAG evidence cards.
- Level 2: structured parsing. Python via `ast`; Java, C++, TypeScript later via Tree-sitter.
- Level 3: semantic understanding. LLM-assisted module responsibility, design intent, risks, and concepts.

MVP:

- Deep support for Python because the base project is Python.
- Generic adapter fallback for other languages.
- Public adapter interface so Java/C++/TypeScript support can be added later.

Example language-neutral function entity:

```json
{
  "id": "fn_123",
  "type": "Function",
  "name": "run_stdio_server",
  "language": "python",
  "signature": "run_stdio_server() -> int",
  "source_path": "src/mcp_server/server.py",
  "range": {"start": 86, "end": 93},
  "adapter": "PythonAdapter"
}
```

## Agent Workflows

### Architecture Tour Workflow

```text
User question
  -> Archivist retrieves README, DEV_SPEC, entry files, config, and core code
  -> Cartographer creates module map and archive hall structure
  -> Curator writes architecture tour report
```

### Impact Analysis Workflow

```text
User change intent
  -> Archivist retrieves relevant modules and design evidence
  -> Cartographer locates graph nodes and paths
  -> Detective expands via DEPENDS_ON, CALLS, CONFIGURES, and AFFECTS
  -> Skeptic checks risks and missing evidence
  -> Curator writes impact analysis report
```

### Risk Audit Workflow

```text
Audit target
  -> Archivist retrieves documentation claims and implementation evidence
  -> Detective compares expected and actual implementation paths
  -> Skeptic marks contradictions, missing implementations, and config risks
  -> Curator writes audit report
```

### Evidence Q&A Workflow

```text
User question
  -> Archivist performs hybrid RAG retrieval
  -> Cartographer optionally expands graph context
  -> Curator writes short answer with evidence cards
```

## Technical Choices

### Retrieval

Use the existing RAG stack:

- ChromaDB for vector storage.
- Existing BM25 indexing.
- Existing RRF fusion.
- Existing optional reranker.
- Existing provider factories for LLM, embedding, and reranker.

### Graph Storage

Use a pluggable `GraphStore`:

- MVP default: `KuzuGraphStore`.
- Fallback: `SQLiteGraphStore`.
- Phase 2: `Neo4jGraphStore`.

Rationale:

- Kuzu provides embedded graph database behavior with a local-first developer experience.
- SQLite fallback keeps the system easy to run.
- Neo4j is valuable for advanced graph querying and production-like deployments, but it adds service and configuration overhead.

### Code Parsing

MVP:

- Python: `ast`.
- Markdown: Markdown structure parser or simple heading-aware parser.
- TOML: `tomllib`.
- YAML: `pyyaml`.
- Unknown languages: `GenericTextAdapter`.

Later:

- Tree-sitter for Java, C++, TypeScript, Go, and other languages.

### Entity and Relationship Extraction

Use a hybrid approach:

- Rule-based extraction for files, directories, functions, classes, imports, and config items.
- LLM extraction for module responsibilities, design decisions, risks, and concept relationships.
- Human confirmation for low-confidence graph output.

### Agent Orchestration

Use lightweight internal orchestration first:

- `AgentWorkflow`
- `AgentContext`
- `AgentResult`
- `ArchivistAgent`
- `CartographerAgent`
- `DetectiveAgent`
- `SkepticAgent`
- `CuratorAgent`

Do not introduce a heavy agent framework in MVP. LangGraph or similar tools can be evaluated later.

### MCP Tools

Existing tools:

- `query_knowledge_hub`
- `list_collections`
- `get_document_summary`

Proposed new tools:

- `ingest_project_archive`
- `query_project_twin`
- `inspect_graph_path`
- `list_archive_halls`
- `run_project_audit`

Primary new tool:

```json
{
  "name": "query_project_twin",
  "arguments": {
    "question": "If I add a knowledge graph, which modules are affected?",
    "mode": "impact_analysis",
    "project_id": "modular-rag-mcp-server"
  }
}
```

## Human-in-the-Loop Correction

Knowledge graph extraction is probabilistic, so TwinMind Archive should present a draft archive instead of pretending to be fully automatic.

After import, the system generates:

- Draft archive halls.
- Entity list.
- Relationship list.
- Evidence cards.
- Candidate risks or contradictions.
- Low-confidence items requiring confirmation.

Users can:

- Merge duplicate entities.
- Delete incorrect relationships.
- Edit archive hall assignment.
- Mark false-positive risks.
- Confirm key entities and relationships.

This is core to making the system credible.

## Error Handling

Ingestion:

- A single file parse failure must not block the whole project import.
- Unsupported languages fall back to `GenericTextAdapter`.
- LLM extraction failure preserves rule-based extraction results.
- Graph write failure does not invalidate completed RAG indexing; the archive is marked `kg_degraded`.

Query:

- If RAG retrieves no evidence, the answer should say there is insufficient evidence.
- If KG expansion returns no path, the system falls back to evidence-chain RAG.
- If an agent conclusion has no evidence card, Curator must mark it as speculation or remove it.
- If Skeptic finds conflicts, the final answer should show conflicting sources rather than hide the conflict.

## Observability

Add trace types:

- `ProjectIngestionTrace`: scanned files, skipped files, loader outcomes, parsing failures.
- `KGExtractionTrace`: extracted entities, relationships, confidence, evidence bindings.
- `AgentRunTrace`: agent inputs, outputs, evidence cards, graph paths, final report.

These should follow the current project's trace and dashboard style.

## Testing Strategy

Unit tests:

- Language detector.
- Python adapter.
- Markdown adapter.
- Config adapter.
- Entity schema validation.
- GraphStore CRUD.
- Evidence card generation.
- Agent output validation.

Integration tests:

- Import a small Python fixture project.
- Generate archive halls and graph entities.
- Run architecture tour.
- Run impact analysis.
- Run risk audit.
- Assert responses include evidence cards and graph paths.

E2E tests:

- Import `MODULAR-RAG-MCP-SERVER`.
- Ask where the MCP server entry point is.
- Ask which modules are affected by adding a knowledge graph.
- Ask whether README and code have inconsistencies.
- Verify evidence cards, graph paths, and agent timeline are returned.

## Success Criteria

MVP is successful when:

- A real project can be imported.
- The system generates understandable archive halls.
- Architecture tour explains module collaboration.
- Impact analysis returns a plausible change path.
- Risk audit finds at least one real inconsistency in the base project.
- Important conclusions include evidence cards.
- Users can see which agents contributed to the result.
- Low-confidence graph output can be corrected.

## Roadmap

### Phase 1: TwinMind Archive MVP

Goal: make the project archive work.

Scope:

- Project directory import.
- Python, Markdown, YAML, TOML parsing.
- RAG indexing.
- Kuzu graph store with SQLite fallback.
- Draft archive generation.
- Human confirmation report.
- Four work modes.
- Streamlit archive workspace.
- Basic MCP tools for project twin querying.

Demo:

- Import `MODULAR-RAG-MCP-SERVER`.
- Ask: What is this project's core architecture?
- Ask: If I add a knowledge graph layer, which modules are affected?
- Ask: Does the README match the implementation?

### Phase 2: Multimodal + Neo4j Enhanced

Goal: strengthen multimodal evidence and graph database capabilities.

Scope:

- Architecture diagrams, flowcharts, screenshots, and PDF image captions.
- `Neo4jGraphStore`.
- More complex Cypher-backed graph queries.
- Star map view.
- Git commit and changelog parsing.
- More complete risk audit rules.

Demo:

- Trace from a diagram to related code and config.
- Use Neo4j-backed graph expansion for module dependency and risk paths.
- View cross-hall concept relationships in the star map.

### Phase 3: Knowledge Metaverse Workspace

Goal: strengthen the archive and star-map experience.

Scope:

- React workspace.
- React Flow or Cytoscape graph canvas.
- 2.5D archive space.
- Three.js star map or concept universe.
- Agent exploration visualization.
- Saved exploration routes.
- Multi-project knowledge space comparison.

### Phase 4: Collaborative Project Twin

Goal: move toward real team usage.

Scope:

- Multi-user project spaces.
- Issue, PR, and commit integration.
- CI risk reports.
- Project evolution timeline.
- Permissions.
- Production graph deployment options.

## Future Enhancements

These ideas are not required for the MVP, but they capture the stronger version of the product that the architecture should leave room for.

### React Archive Workspace

Move the first Streamlit prototype into a richer React workspace when the core RAG, graph, and agent contracts are stable.

Potential upgrades:

- React-based archive shell with persistent project navigation.
- React Flow or Cytoscape graph canvas for entity paths and module maps.
- Resizable panels for halls, graph paths, evidence cards, and agent traces.
- Inline correction UX for merging entities, deleting bad relations, and confirming low-confidence graph output.
- Saved workspaces for different projects and query sessions.

### Knowledge Metaverse Visual Layer

Make the archive feel more spatial and memorable without weakening the evidence-first workflow.

Potential upgrades:

- 2.5D archive or museum layout where modules become halls and evidence becomes artifacts.
- Three.js star map for cross-hall concepts, hidden dependencies, and multi-hop relationships.
- Animated evidence paths that show how an answer travels through documents, code, graph nodes, and agents.
- Agent exploration visualization, where Archivist, Cartographer, Detective, Skeptic, and Curator appear as roles moving through the knowledge space.
- Saved exploration routes that users can replay, share, or compare across questions.

### Autonomous Agent Loop

The MVP should use deterministic workflows for reliability. A later version can add a more autonomous planning loop for deeper investigation.

Potential upgrades:

- Planner agent that decomposes complex questions into retrieval, graph, audit, and synthesis subtasks.
- ReAct-style tool use for iterative evidence gathering.
- LangGraph or a similar workflow engine if the internal orchestrator becomes too limited.
- Agent memory for prior investigations, confirmed corrections, and recurring project risks.
- Budget-aware execution so autonomous loops stop when evidence is weak or when confidence no longer improves.
- Critic-and-retry loops where Skeptic can send weak conclusions back to Archivist or Detective for more evidence.

### Neo4j Production Graph Mode

Kuzu is the recommended local-first MVP graph backend. Neo4j should become the advanced graph mode.

Potential upgrades:

- `Neo4jGraphStore` adapter with Bolt connection settings.
- Cypher-backed graph expansion for deeper dependency, impact, and risk queries.
- Optional Neo4j Browser compatibility for graph inspection.
- Migration or export path from Kuzu/SQLite graph stores to Neo4j.
- Production deployment profile using Docker Compose.

### Multimodal Evidence Expansion

The first version focuses on code, Markdown, and config. Later versions should make visual and temporal project evidence first-class.

Potential upgrades:

- Architecture diagram ingestion with image captioning and entity linking.
- Screenshot and UI state evidence cards.
- PDF diagrams and tables linked to code and concepts.
- Audio or meeting transcript ingestion for design discussions.
- Commit, issue, PR, changelog, and task timeline extraction.
- Visual contradiction detection, such as diagrams that describe flows not implemented in code.

### Multi-Project Knowledge Universe

Once single-project archives work, multiple project twins can form a larger knowledge universe.

Potential upgrades:

- Cross-project concept search.
- Shared architecture pattern library.
- Reusable risk and decision catalog.
- Project-to-project comparison mode.
- Organization-level star map showing common modules, repeated design decisions, and recurring risks.
- Personal or team knowledge memory across projects.

### Stronger Evaluation and Benchmarking

The project should eventually measure whether the archive is actually useful, not just visually interesting.

Potential upgrades:

- Golden project-analysis question set.
- Impact-analysis hit-rate against manually labeled affected modules.
- Risk-audit benchmark with seeded documentation/code contradictions.
- Evidence coverage score for every answer.
- Graph quality metrics such as duplicate entity rate, unsupported relation rate, and correction rate.
- Regression dashboard comparing different graph extraction prompts, graph stores, and retrieval strategies.

## Open Decisions

These decisions are intentionally deferred until implementation planning:

- Exact Kuzu schema and query helpers.
- Whether the MVP graph canvas uses Streamlit-native components, PyVis, NetworkX export, or another lightweight visual component.
- Exact LLM prompt contracts for each agent.
- Which source file extensions are included by default in the first scanner pass.
- Whether MCP tools and Streamlit pages share one service layer or use separate orchestration wrappers.
