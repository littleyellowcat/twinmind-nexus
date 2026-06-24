# TwinMind Archive Graph Explorer and Autonomous Agent Design

Date: 2026-06-24

## Summary

TwinMind Archive needs a real graph exploration experience, not a small decorative Star Map. The graph should help a user understand an unfamiliar project without knowing what to search for first.

This design adds a dedicated Graph Explorer page and upgrades the current Agent workflow into an autonomous, bounded GraphRAG exploration loop. The default mission is "understand project architecture." The agent automatically plans and executes a limited task queue, highlights explored entities and relations in the graph, verifies evidence, and writes findings back to the project archive.

## Current Problems

The current overview Star Map is useful as an entry point but has several product and technical gaps:

- It is too small for serious graph exploration.
- Selecting a relation does not visibly highlight the selected edge and endpoints strongly enough.
- Some halls can appear visually identical because the view falls back to generic relations when hall-specific relations are sparse.
- Search assumes the user already knows which entity to look for.
- The Agent workflow is too report-centered; it does not yet behave like an autonomous project explorer that plans, investigates, verifies, and updates the graph.

## Product Direction

The chosen direction is:

- Add a dedicated Graph Explorer page.
- Keep the overview Star Map as a compact preview and entry point.
- Make the graph canvas the main surface.
- Use collapsible drawers instead of fixed three-column layout so the graph remains readable.
- Start with recommended exploration entities instead of search.
- Use click-to-focus graph navigation: click an entity, center it, show one-hop neighbors, and allow manual two-hop expansion.
- Add an autonomous Agent mission loop that plans and executes architecture exploration with a bounded step limit.

## Page Structure

TwinMind Archive should have three primary pages:

- Archive Overview: upload, archive selector, metrics, halls, evidence preview, compact Star Map.
- Graph Explorer: full graph exploration, entity focus, relation browsing, autonomous Agent playback.
- Agent Analysis: mission history, Agent work proof, model status, generated reports, task audit trail.

The overview page should not try to contain the full graph experience. It should show a preview and provide an "expand graph" action that opens Graph Explorer.

## Graph Explorer Layout

Graph Explorer uses a full-canvas layout:

- Top toolbar:
  - archive selector
  - hall selector
  - graph depth control
  - relation type filters
  - layout mode
  - search
  - autonomous mission controls
- Main graph canvas:
  - large interactive graph surface
  - focused center entity
  - one-hop neighbors by default
  - optional two-hop expansion
  - highlighted Agent-explored paths
- Left collapsible drawer:
  - recommended exploration starting points
  - entry files
  - high-degree entities
  - config hotspots
  - document centers
  - Agent-recommended entities
- Right collapsible drawer:
  - selected entity details
  - relation distribution
  - evidence cards
  - risks and importance
  - next actions
- Bottom strip:
  - exploration breadcrumb
  - visible graph counts
  - total archive counts
  - mission status

The left and right drawers must be closeable. When both are closed, the graph canvas should occupy nearly the full page.

## Entity Exploration Flow

The graph should support progressive exploration:

1. Initial state:
   - show recommended starting entities
   - do not require the user to search
   - default to the current hall or the full-project architecture mission
2. Entity click:
   - selected entity becomes the center node
   - selected entity receives strong visual emphasis
   - one-hop neighbors appear around it
   - right drawer opens with entity details
3. Relation click:
   - selected relation edge becomes bright and thicker
   - source and target nodes are highlighted
   - unrelated nodes and edges are dimmed
   - right drawer shows relation evidence and source snippets
4. One-hop view:
   - default view after selecting an entity
   - relation filters can narrow the neighborhood
5. Two-hop expansion:
   - available by explicit action
   - does not happen automatically in the basic interaction
   - should show newly added nodes with a distinct visual state
6. Breadcrumb:
   - records focus path, such as Project Overview -> README.md -> settings.yaml
   - allows backtracking to prior focus entities

## Hall Behavior

Each hall must show real hall-specific relations. The graph should not silently fall back to global generic relations.

If a hall has few or no relations, show an honest empty or sparse state:

- "This hall has no visible relations yet."
- "View hall entities."
- "Switch to full-project graph."
- "Ask Agent why this hall has sparse relations."

This prevents the architecture, retrieval, config, concept, and dependency halls from appearing identical.

## Recommended Exploration Starts

The left drawer should provide ranked starting points because users may not know what to search for.

First-version scoring can combine:

- entity degree
- entity type
- file name patterns
- evidence count
- hall membership
- known entrypoint names
- config key importance
- Agent risk or importance tags

Recommended groups:

- Entry files: `main.py`, `app.py`, `server.py`, CLI files.
- High-degree entities: nodes with many relations.
- Config hotspots: `llm`, `retrieval`, `vector_store`, `embedding`, `database`.
- Document centers: `README.md`, architecture docs, deployment docs.
- Core code entities: important classes and functions.
- Agent picks: entities marked as important, risky, ambiguous, or under-evidenced.

Each recommendation should include a short reason, such as "highly connected," "entry point," "configuration hotspot," or "Agent flagged risk."

## Entity Detail Drawer

The entity detail drawer should answer "why should I care about this entity?"

It should include:

- entity name
- entity type
- hall membership
- source path and line range when available
- relation count
- relation type distribution
- direct neighbors grouped by relation type
- evidence cards
- Agent notes
- risk tags
- recommended next actions

Available next actions:

- expand one-hop
- expand two-hop
- isolate relation type
- ask Agent to explain this entity
- trace impact
- find risks
- add current subgraph to report

## Autonomous Agent Loop

The selected autonomous mode is full-auto bounded execution.

Default mission:

- Understand project architecture.

Default limit:

- maximum 12 steps per mission run.

The Agent should automatically create and execute a task queue, but it must remain bounded, inspectable, and stoppable.

### Agent Components

Mission Planner:

- converts the user goal and archive state into an exploration plan
- chooses initial entities and task sequence

Task Queue:

- stores planned, running, completed, failed, and skipped tasks
- exposes progress to the frontend

Specialist Agents:

- Cartographer: maps project structure and architecture boundaries
- Detective: traces impact paths and dependencies
- Skeptic: checks risk, weak evidence, and suspicious coupling
- Librarian: gathers evidence and source snippets
- Curator: summarizes findings into a readable report

Critic / Verifier:

- checks whether each finding has evidence
- detects unsupported claims
- decides whether another exploration step is needed
- flags conflicts or uncertainty

Graph Memory:

- stores Agent findings back into the archive
- marks important entities
- marks explored paths
- attaches risk labels
- records mission history

UI Playback:

- shows current task
- shows visited entities and paths
- highlights Agent-selected entities and relations
- allows pause, continue, stop, and rerun

### Default Architecture Mission Queue

The initial architecture mission can generate tasks like:

1. Find project entry points.
2. Identify top-level modules.
3. Identify core service boundaries.
4. Expand configuration chain.
5. Trace dependency and import hubs.
6. Find retrieval, model, vector store, and Agent-related modules.
7. Verify evidence for key architecture claims.
8. Find sparse or under-evidenced areas.
9. Ask Skeptic to check architecture risks.
10. Produce key paths.
11. Produce project architecture summary.
12. Recommend next exploration missions.

The planner can stop early if enough evidence has been gathered.

### Stop Conditions

The autonomous loop stops when any of these conditions are met:

- 12 steps are reached.
- two consecutive steps discover no new entity, relation, evidence, or useful conclusion.
- required architecture tasks are complete.
- model or backend failures exceed a configured threshold.
- the user pauses or stops the mission.
- the Critic determines that additional exploration is unlikely to improve the answer.

### Task Record

Every task should persist an auditable record:

- task id
- mission id
- status
- assigned Agent
- task type
- input entities
- input relations
- retrieved evidence ids
- graph paths considered
- prompt or deterministic rule summary
- output findings
- risks
- confidence
- verifier result
- created and completed timestamps

## GraphRAG Data Flow

For each autonomous task:

1. Read the current mission goal and graph focus.
2. Retrieve graph neighborhood from the project archive.
3. Retrieve evidence through hybrid retrieval:
   - graph relations
   - evidence cards
   - BM25 keyword search
   - vector search where available
4. Run the assigned Agent.
5. Verify claims against evidence.
6. Write accepted findings to Graph Memory.
7. Update task queue.
8. Stream progress to the frontend.
9. Highlight newly explored entities and relations in Graph Explorer.

## API Requirements

The backend needs graph exploration and mission APIs:

- `GET /api/archives/{project_id}/graph`
  - returns graph summary, entities, relations, and recommended starts
- `GET /api/archives/{project_id}/graph/neighborhood`
  - query by entity id, hall, depth, relation types, and limits
- `POST /api/archives/{project_id}/missions`
  - starts an autonomous mission
- `GET /api/missions/{mission_id}`
  - returns mission status and current step
- `GET /api/missions/{mission_id}/tasks`
  - returns task queue and task history
- `POST /api/missions/{mission_id}/pause`
  - pauses execution
- `POST /api/missions/{mission_id}/resume`
  - resumes execution
- `POST /api/missions/{mission_id}/stop`
  - stops execution
- `GET /api/missions/{mission_id}/graph-overlay`
  - returns highlighted paths, risk tags, explored nodes, and Agent annotations

Existing upload, archive, Agent status, and report endpoints can remain.

## Frontend Requirements

Frontend should add:

- a new Graph Explorer page tab
- expand action from overview Star Map
- interactive graph state:
  - focused entity
  - selected relation
  - depth
  - relation filters
  - visible neighborhood
  - drawer visibility
  - mission overlay
- recommended entity drawer
- entity detail drawer
- mission control panel
- task playback strip
- strong selected-edge and selected-node styling
- honest sparse-state behavior for halls

The graph should eventually use a real graph/canvas library if SVG becomes too limited. The first implementation can keep SVG if scoped carefully, but the architecture should allow swapping the rendering layer.

## Visual Behavior

Selection states must be obvious:

- focused entity: bright center node, larger size, visible label
- selected relation: thicker glowing edge
- relation endpoints: bright highlighted nodes
- one-hop neighbors: normal brightness
- two-hop additions: secondary brightness
- unrelated nodes: dimmed
- Agent-explored paths: distinct overlay color or badge
- risk paths: warning accent and explanation tooltip

The graph counter should distinguish:

- visible nodes
- visible relations
- matching relations
- total archive entities
- total archive relations

## Error Handling

Graph Explorer should handle:

- no archive selected
- graph not built yet
- hall has no relations
- entity has no neighbors
- mission failed
- model unavailable
- task verifier rejected claims
- backend timeout

Failures should be visible and specific. The UI should never pretend a graph or Agent result exists when it does not.

## Testing Strategy

Backend tests:

- neighborhood query returns hall-specific relations only
- no silent global fallback for sparse halls
- recommended starts are ranked and stable
- autonomous mission respects max step limit
- mission stops after repeated no-new-information steps
- task records include evidence references
- verifier can reject unsupported findings

Frontend tests:

- switching halls changes the graph or shows honest sparse state
- clicking entity centers and highlights it
- clicking relation highlights edge and endpoints
- drawers can open and close
- mission progress renders task history
- pause, resume, and stop controls update state
- graph counter reflects visible and total counts

Manual verification:

- upload or select a real project archive
- open Graph Explorer
- run default architecture mission
- confirm Agent steps update graph overlays
- confirm evidence links match source files

## Open Implementation Notes

This design intentionally avoids the lightweight "one-shot DeepSeek explanation only" approach. The first implementation should still be incremental, but every increment should fit the autonomous mission architecture:

1. Add graph-focused data structures and neighborhood API.
2. Add Graph Explorer page and real entity focus behavior.
3. Add mission and task persistence.
4. Add bounded autonomous mission runner.
5. Add Agent verification and graph memory writes.
6. Add graph overlays and task playback in the UI.

## Success Criteria

The feature is successful when:

- a user can open an unfamiliar project and see recommended starting entities
- clicking an entity makes the graph reorganize around it
- relation and entity selection are visually obvious
- each hall shows real hall-specific data or an honest sparse state
- the autonomous Agent can run a bounded architecture mission
- every Agent finding has evidence or is marked uncertain
- Agent-discovered paths appear in the graph, not only in a report
- the user can pause, resume, stop, and inspect the mission history

