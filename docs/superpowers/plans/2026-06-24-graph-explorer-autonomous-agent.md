# Graph Explorer Autonomous Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated Graph Explorer page with real entity-focused graph exploration and a bounded autonomous Agent mission loop for understanding project architecture.

**Architecture:** Add focused backend graph contracts and pure graph-neighborhood functions first, expose them through FastAPI, then add mission/task persistence and a bounded architecture mission runner. The frontend adds a new Graph Explorer page, API client methods, graph focus state, collapsible drawers, mission controls, and task playback while keeping Archive Overview as a compact entry point.

**Tech Stack:** Python dataclasses, FastAPI, pytest, React 19, TypeScript, Vite, SVG graph rendering for the first implementation, existing DeepSeek-enhanced Agent utilities where available.

---

## Scope Split

This plan implements the approved spec as one vertical product feature, but it is split into independently testable slices:

1. Backend graph summary and neighborhood data.
2. Backend graph API.
3. Backend mission/task contracts and autonomous runner.
4. Backend mission API and persistence.
5. Frontend API/types.
6. Frontend Graph Explorer page and routing.
7. Frontend entity focus, drawers, and visual states.
8. Frontend mission playback and end-to-end verification.

## File Structure

Create or modify these files:

- Create: `src/project_archive/graph_explorer.py`
  - Pure functions for graph summaries, hall-specific neighborhoods, recommended starts, and graph overlays.
- Create: `src/project_archive/autonomous_mission.py`
  - Bounded architecture mission planner, task runner, verifier, and graph-memory overlay generation.
- Modify: `src/project_archive/types.py`
  - Add graph explorer and mission dataclasses.
- Modify: `src/project_archive/service.py`
  - Add service methods for graph summary, graph neighborhood, mission start/load/update, and mission persistence.
- Modify: `src/project_archive/api.py`
  - Add graph and mission endpoints.
- Create: `tests/unit/test_project_archive_graph_explorer.py`
  - Tests for recommendations, hall-specific neighborhoods, focus behavior, and sparse hall behavior.
- Create: `tests/unit/test_project_archive_autonomous_mission.py`
  - Tests for bounded mission execution, task records, stop conditions, verifier fields, and graph overlay.
- Modify: `tests/unit/test_project_archive_api.py`
  - API tests for graph endpoints and mission endpoints.
- Modify: `frontend/src/types.ts`
  - Add graph explorer and mission TypeScript contracts.
- Modify: `frontend/src/api.ts`
  - Add graph and mission API client methods.
- Modify: `frontend/src/App.tsx`
  - Add Graph Explorer page tab, overview expand action, mission controls, graph focus state, drawers, and playback.
- Modify: `frontend/src/styles.css`
  - Add Graph Explorer layout, strong selection states, drawers, toolbar, mission timeline, sparse states.

## Task 1: Backend Graph Explorer Contracts and Pure Functions

**Files:**
- Modify: `src/project_archive/types.py`
- Create: `src/project_archive/graph_explorer.py`
- Create: `tests/unit/test_project_archive_graph_explorer.py`

- [ ] **Step 1: Write failing graph explorer tests**

Add `tests/unit/test_project_archive_graph_explorer.py`:

```python
"""Tests for TwinMind graph explorer projections."""

from __future__ import annotations

from src.project_archive.graph_explorer import (
    build_graph_neighborhood,
    build_graph_summary,
)
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)


def _draft() -> ProjectArchiveDraft:
    return ProjectArchiveDraft(
        project_id="demo",
        halls=[
            ArchiveHall(
                id="hall_architecture",
                name="Architecture Hall",
                description="Architecture",
                entity_ids=["file:main.py", "class:ArchiveBuilder", "config:llm"],
            ),
            ArchiveHall(
                id="hall_config",
                name="Configuration Hall",
                description="Configuration",
                entity_ids=["config:llm"],
            ),
            ArchiveHall(
                id="hall_empty",
                name="Empty Hall",
                description="No relations",
                entity_ids=["doc:readme"],
            ),
        ],
        entities=[
            ProjectEntity(id="file:main.py", type="File", name="main.py", source_path="main.py", evidence_ids=["ev:main"]),
            ProjectEntity(id="class:ArchiveBuilder", type="Class", name="ArchiveBuilder", source_path="src/archive_builder.py", evidence_ids=["ev:builder"]),
            ProjectEntity(id="config:llm", type="Config", name="llm", source_path="config/settings.yaml", evidence_ids=["ev:config"]),
            ProjectEntity(id="doc:readme", type="Markdown", name="README.md", source_path="README.md", evidence_ids=["ev:readme"]),
        ],
        relations=[
            ProjectRelation(id="rel:defines", source_id="file:main.py", target_id="class:ArchiveBuilder", type="DEFINES", evidence_ids=["ev:builder"]),
            ProjectRelation(id="rel:configures", source_id="class:ArchiveBuilder", target_id="config:llm", type="CONFIGURES", evidence_ids=["ev:config"]),
            ProjectRelation(id="rel:mentions", source_id="doc:readme", target_id="file:main.py", type="MENTIONS", evidence_ids=["ev:readme"]),
        ],
        evidence_cards=[
            EvidenceCard(id="ev:main", source_type="code", source_path="main.py", title="main", snippet="def main(): pass"),
            EvidenceCard(id="ev:builder", source_type="code", source_path="src/archive_builder.py", title="ArchiveBuilder", snippet="class ArchiveBuilder: pass"),
            EvidenceCard(id="ev:config", source_type="config", source_path="config/settings.yaml", title="llm", snippet="llm:"),
            EvidenceCard(id="ev:readme", source_type="markdown", source_path="README.md", title="README", snippet="# Demo"),
        ],
    )


def test_graph_summary_recommends_starts_with_reasons() -> None:
    summary = build_graph_summary(_draft())

    assert summary.project_id == "demo"
    assert summary.metrics == {"entities": 4, "relations": 3, "evidence": 4}
    assert summary.recommended_starts[0].entity_id in {"file:main.py", "class:ArchiveBuilder"}
    assert summary.recommended_starts[0].reason
    assert {item.group for item in summary.recommended_starts} >= {"entry_file", "high_degree"}


def test_neighborhood_uses_hall_specific_relations_without_global_fallback() -> None:
    neighborhood = build_graph_neighborhood(
        _draft(),
        hall_id="hall_config",
        focus_entity_id=None,
        depth=1,
        relation_types=[],
        node_limit=20,
        relation_limit=20,
    )

    assert {relation.id for relation in neighborhood.relations} == {"rel:configures"}
    assert {node.id for node in neighborhood.nodes} == {"class:ArchiveBuilder", "config:llm"}
    assert neighborhood.is_sparse is False


def test_sparse_hall_returns_honest_empty_state() -> None:
    neighborhood = build_graph_neighborhood(
        _draft(),
        hall_id="hall_empty",
        focus_entity_id=None,
        depth=1,
        relation_types=[],
        node_limit=20,
        relation_limit=20,
    )

    assert neighborhood.nodes == []
    assert neighborhood.relations == []
    assert neighborhood.is_sparse is True
    assert neighborhood.sparse_reason == "No relations are visible for this hall."


def test_focus_entity_centers_one_hop_neighbors() -> None:
    neighborhood = build_graph_neighborhood(
        _draft(),
        hall_id=None,
        focus_entity_id="class:ArchiveBuilder",
        depth=1,
        relation_types=[],
        node_limit=20,
        relation_limit=20,
    )

    assert neighborhood.focus_entity_id == "class:ArchiveBuilder"
    assert {node.id for node in neighborhood.nodes} == {"file:main.py", "class:ArchiveBuilder", "config:llm"}
    assert {relation.id for relation in neighborhood.relations} == {"rel:defines", "rel:configures"}
```

- [ ] **Step 2: Run graph explorer tests and verify they fail**

Run:

```bash
pytest tests/unit/test_project_archive_graph_explorer.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.project_archive.graph_explorer'`.

- [ ] **Step 3: Add graph explorer dataclasses**

Append these dataclasses to `src/project_archive/types.py` after `ProjectAgentReport`:

```python
@dataclass(frozen=True)
class GraphExplorerNode:
    id: str
    label: str
    type: str
    hall_ids: list[str] = field(default_factory=list)
    source_path: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    degree: int = 0
    importance: float = 0.0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GraphExplorerRelation:
    id: str
    source_id: str
    target_id: str
    type: str
    evidence_ids: list[str] = field(default_factory=list)
    hall_ids: list[str] = field(default_factory=list)
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecommendedGraphStart:
    entity_id: str
    label: str
    group: str
    reason: str
    score: float
    hall_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GraphSummary:
    project_id: str
    metrics: dict[str, int]
    recommended_starts: list[RecommendedGraphStart] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "metrics": self.metrics,
            "recommended_starts": [
                item.to_dict() for item in self.recommended_starts
            ],
        }


@dataclass(frozen=True)
class GraphNeighborhood:
    project_id: str
    hall_id: str | None
    focus_entity_id: str | None
    depth: int
    nodes: list[GraphExplorerNode] = field(default_factory=list)
    relations: list[GraphExplorerRelation] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    is_sparse: bool = False
    sparse_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "hall_id": self.hall_id,
            "focus_entity_id": self.focus_entity_id,
            "depth": self.depth,
            "nodes": [node.to_dict() for node in self.nodes],
            "relations": [relation.to_dict() for relation in self.relations],
            "evidence_ids": self.evidence_ids,
            "is_sparse": self.is_sparse,
            "sparse_reason": self.sparse_reason,
        }
```

- [ ] **Step 4: Implement pure graph explorer functions**

Create `src/project_archive/graph_explorer.py`:

```python
"""Graph Explorer projections for TwinMind project archives."""

from __future__ import annotations

from collections import Counter, defaultdict, deque

from src.project_archive.types import (
    GraphExplorerNode,
    GraphExplorerRelation,
    GraphNeighborhood,
    GraphSummary,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
    RecommendedGraphStart,
)

ENTRY_FILE_NAMES = {"main.py", "app.py", "server.py", "cli.py", "index.js", "index.ts"}
CONFIG_NAMES = {"llm", "retrieval", "vector_store", "embedding", "database", "agent"}


def build_graph_summary(draft: ProjectArchiveDraft) -> GraphSummary:
    return GraphSummary(
        project_id=draft.project_id,
        metrics={
            "entities": len(draft.entities),
            "relations": len(draft.relations),
            "evidence": len(draft.evidence_cards),
        },
        recommended_starts=_recommended_starts(draft),
    )


def build_graph_neighborhood(
    draft: ProjectArchiveDraft,
    *,
    hall_id: str | None,
    focus_entity_id: str | None,
    depth: int,
    relation_types: list[str],
    node_limit: int,
    relation_limit: int,
) -> GraphNeighborhood:
    normalized_depth = max(1, min(depth, 3))
    entity_by_id = {entity.id: entity for entity in draft.entities}
    hall_entity_ids = _hall_entity_ids(draft)
    selected_hall_entities = set(hall_entity_ids.get(hall_id, [])) if hall_id else set()
    allowed_relation_types = {value.upper() for value in relation_types if value}
    candidate_relations = [
        relation
        for relation in draft.relations
        if _relation_matches_hall(relation, selected_hall_entities)
        and (
            not allowed_relation_types
            or relation.type.upper() in allowed_relation_types
        )
    ]

    if focus_entity_id:
        visible_relations = _relations_for_focus(
            focus_entity_id=focus_entity_id,
            relations=candidate_relations,
            depth=normalized_depth,
            relation_limit=relation_limit,
        )
    else:
        visible_relations = _rank_relations(candidate_relations)[:relation_limit]

    visible_node_ids: set[str] = set()
    for relation in visible_relations:
        visible_node_ids.add(relation.source_id)
        visible_node_ids.add(relation.target_id)
    if focus_entity_id in entity_by_id:
        visible_node_ids.add(focus_entity_id)

    if len(visible_node_ids) > node_limit:
        ranked_node_ids = _rank_node_ids(visible_node_ids, visible_relations)
        visible_node_ids = set(ranked_node_ids[:node_limit])
        visible_relations = [
            relation
            for relation in visible_relations
            if relation.source_id in visible_node_ids and relation.target_id in visible_node_ids
        ]

    degrees = _degree_counts(draft.relations)
    graph_relations = [
        _to_graph_relation(relation, hall_entity_ids)
        for relation in visible_relations
        if relation.source_id in entity_by_id and relation.target_id in entity_by_id
    ]
    graph_nodes = [
        _to_graph_node(entity_by_id[entity_id], hall_entity_ids, degrees)
        for entity_id in sorted(visible_node_ids)
        if entity_id in entity_by_id
    ]
    evidence_ids = sorted(
        {
            evidence_id
            for relation in visible_relations
            for evidence_id in relation.evidence_ids
        }
    )
    is_sparse = not graph_relations
    sparse_reason = "No relations are visible for this hall." if is_sparse else ""

    return GraphNeighborhood(
        project_id=draft.project_id,
        hall_id=hall_id,
        focus_entity_id=focus_entity_id,
        depth=normalized_depth,
        nodes=graph_nodes,
        relations=graph_relations,
        evidence_ids=evidence_ids,
        is_sparse=is_sparse,
        sparse_reason=sparse_reason,
    )


def _recommended_starts(draft: ProjectArchiveDraft) -> list[RecommendedGraphStart]:
    degrees = _degree_counts(draft.relations)
    hall_entity_ids = _hall_entity_ids(draft)
    starts: list[RecommendedGraphStart] = []
    for entity in draft.entities:
        hall_ids = _entity_halls(entity.id, hall_entity_ids)
        name_lower = entity.name.lower()
        entity_type = entity.type.lower()
        degree = degrees[entity.id]
        if name_lower in ENTRY_FILE_NAMES:
            starts.append(_start(entity, "entry_file", "Entry file", 100 + degree, hall_ids))
        if degree:
            starts.append(_start(entity, "high_degree", "Highly connected entity", 70 + degree, hall_ids))
        if entity_type == "config" or name_lower in CONFIG_NAMES:
            starts.append(_start(entity, "config_hotspot", "Configuration hotspot", 90 + degree, hall_ids))
        if entity_type in {"markdown", "concept"} or "readme" in name_lower:
            starts.append(_start(entity, "document_center", "Documentation center", 60 + degree, hall_ids))

    deduped: dict[tuple[str, str], RecommendedGraphStart] = {}
    for start in starts:
        key = (start.entity_id, start.group)
        current = deduped.get(key)
        if current is None or start.score > current.score:
            deduped[key] = start
    return sorted(deduped.values(), key=lambda item: (-item.score, item.label))[:16]


def _start(
    entity: ProjectEntity,
    group: str,
    reason: str,
    score: float,
    hall_ids: list[str],
) -> RecommendedGraphStart:
    return RecommendedGraphStart(
        entity_id=entity.id,
        label=entity.name,
        group=group,
        reason=reason,
        score=score,
        hall_ids=hall_ids,
    )


def _relations_for_focus(
    *,
    focus_entity_id: str,
    relations: list[ProjectRelation],
    depth: int,
    relation_limit: int,
) -> list[ProjectRelation]:
    adjacency: dict[str, list[ProjectRelation]] = defaultdict(list)
    for relation in relations:
        adjacency[relation.source_id].append(relation)
        adjacency[relation.target_id].append(relation)

    visited_nodes = {focus_entity_id}
    visited_relations: dict[str, ProjectRelation] = {}
    queue: deque[tuple[str, int]] = deque([(focus_entity_id, 0)])
    while queue and len(visited_relations) < relation_limit:
        entity_id, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for relation in _rank_relations(adjacency.get(entity_id, [])):
            if len(visited_relations) >= relation_limit:
                break
            visited_relations[relation.id] = relation
            next_id = relation.target_id if relation.source_id == entity_id else relation.source_id
            if next_id not in visited_nodes:
                visited_nodes.add(next_id)
                queue.append((next_id, current_depth + 1))
    return list(visited_relations.values())


def _rank_relations(relations: list[ProjectRelation]) -> list[ProjectRelation]:
    return sorted(
        relations,
        key=lambda relation: (
            -len(relation.evidence_ids),
            relation.type,
            relation.source_id,
            relation.target_id,
        ),
    )


def _rank_node_ids(
    node_ids: set[str],
    relations: list[ProjectRelation],
) -> list[str]:
    counts: Counter[str] = Counter()
    for relation in relations:
        counts[relation.source_id] += 1
        counts[relation.target_id] += 1
    return sorted(node_ids, key=lambda entity_id: (-counts[entity_id], entity_id))


def _degree_counts(relations: list[ProjectRelation]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for relation in relations:
        counts[relation.source_id] += 1
        counts[relation.target_id] += 1
    return counts


def _hall_entity_ids(draft: ProjectArchiveDraft) -> dict[str, set[str]]:
    return {hall.id: set(hall.entity_ids) for hall in draft.halls}


def _relation_matches_hall(
    relation: ProjectRelation,
    hall_entities: set[str],
) -> bool:
    if not hall_entities:
        return True
    return relation.source_id in hall_entities or relation.target_id in hall_entities


def _entity_halls(
    entity_id: str,
    hall_entity_ids: dict[str, set[str]],
) -> list[str]:
    return sorted(
        hall_id for hall_id, entity_ids in hall_entity_ids.items() if entity_id in entity_ids
    )


def _relation_halls(
    relation: ProjectRelation,
    hall_entity_ids: dict[str, set[str]],
) -> list[str]:
    return sorted(
        hall_id
        for hall_id, entity_ids in hall_entity_ids.items()
        if relation.source_id in entity_ids or relation.target_id in entity_ids
    )


def _to_graph_node(
    entity: ProjectEntity,
    hall_entity_ids: dict[str, set[str]],
    degrees: Counter[str],
) -> GraphExplorerNode:
    degree = degrees[entity.id]
    return GraphExplorerNode(
        id=entity.id,
        label=entity.name,
        type=entity.type,
        hall_ids=_entity_halls(entity.id, hall_entity_ids),
        source_path=entity.source_path,
        evidence_ids=entity.evidence_ids,
        degree=degree,
        importance=float(degree),
        tags=[],
    )


def _to_graph_relation(
    relation: ProjectRelation,
    hall_entity_ids: dict[str, set[str]],
) -> GraphExplorerRelation:
    return GraphExplorerRelation(
        id=relation.id,
        source_id=relation.source_id,
        target_id=relation.target_id,
        type=relation.type,
        evidence_ids=relation.evidence_ids,
        hall_ids=_relation_halls(relation, hall_entity_ids),
        weight=max(1.0, float(len(relation.evidence_ids))),
    )
```

- [ ] **Step 5: Run graph explorer tests and verify they pass**

Run:

```bash
pytest tests/unit/test_project_archive_graph_explorer.py -v
```

Expected: PASS with 4 tests.

- [ ] **Step 6: Commit graph explorer foundation**

Run:

```bash
git add src/project_archive/types.py src/project_archive/graph_explorer.py tests/unit/test_project_archive_graph_explorer.py
git commit -m "feat: add graph explorer projections"
```

## Task 2: Backend Graph Explorer API

**Files:**
- Modify: `src/project_archive/service.py`
- Modify: `src/project_archive/api.py`
- Modify: `tests/unit/test_project_archive_api.py`

- [ ] **Step 1: Add failing API tests**

Append to `tests/unit/test_project_archive_api.py`:

```python
def test_get_graph_summary_returns_recommended_starts(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives/sample/graph")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "sample"
    assert payload["metrics"]["entities"] == 2
    assert payload["recommended_starts"]
    assert payload["recommended_starts"][0]["entity_id"]


def test_get_graph_neighborhood_filters_by_hall(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get(
        "/api/archives/sample/graph/neighborhood",
        params={"hall_id": "hall_architecture", "depth": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "sample"
    assert payload["hall_id"] == "hall_architecture"
    assert payload["relations"][0]["id"] == "rel:defines"
    assert payload["is_sparse"] is False


def test_get_graph_neighborhood_returns_404_for_unknown_archive(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/archives/missing/graph/neighborhood")

    assert response.status_code == 404
```

- [ ] **Step 2: Run API tests and verify graph endpoints fail**

Run:

```bash
pytest tests/unit/test_project_archive_api.py::test_get_graph_summary_returns_recommended_starts tests/unit/test_project_archive_api.py::test_get_graph_neighborhood_filters_by_hall tests/unit/test_project_archive_api.py::test_get_graph_neighborhood_returns_404_for_unknown_archive -v
```

Expected: FAIL with 404 responses for missing graph routes.

- [ ] **Step 3: Add service methods**

Modify imports in `src/project_archive/service.py`:

```python
from src.project_archive.graph_explorer import (
    build_graph_neighborhood,
    build_graph_summary,
)
from src.project_archive.types import (
    AgentResult,
    GraphNeighborhood,
    GraphSummary,
    ProjectAgentReport,
    ProjectArchiveDraft,
    QueryMode,
)
```

Add methods inside `ProjectArchiveService` after `load_agent_report`:

```python
    def graph_summary(self, project_id: str) -> GraphSummary:
        draft = self.load_draft(project_id)
        return build_graph_summary(draft)

    def graph_neighborhood(
        self,
        project_id: str,
        *,
        hall_id: str | None = None,
        focus_entity_id: str | None = None,
        depth: int = 1,
        relation_types: list[str] | None = None,
        node_limit: int = 80,
        relation_limit: int = 120,
    ) -> GraphNeighborhood:
        draft = self.load_draft(project_id)
        return build_graph_neighborhood(
            draft,
            hall_id=hall_id,
            focus_entity_id=focus_entity_id,
            depth=depth,
            relation_types=relation_types or [],
            node_limit=node_limit,
            relation_limit=relation_limit,
        )
```

- [ ] **Step 4: Add FastAPI graph endpoints**

Modify FastAPI imports in `src/project_archive/api.py`:

```python
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
```

Add routes after `get_archive`:

```python
    @app.get("/api/archives/{project_id}/graph")
    def get_graph_summary(project_id: str, service: ServiceDep) -> dict:
        try:
            return service.graph_summary(project_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/archives/{project_id}/graph/neighborhood")
    def get_graph_neighborhood(
        project_id: str,
        service: ServiceDep,
        hall_id: str | None = None,
        focus_entity_id: str | None = None,
        depth: int = 1,
        relation_types: Annotated[list[str], Query()] = [],
        node_limit: int = 80,
        relation_limit: int = 120,
    ) -> dict:
        try:
            return service.graph_neighborhood(
                project_id,
                hall_id=hall_id,
                focus_entity_id=focus_entity_id,
                depth=depth,
                relation_types=relation_types,
                node_limit=node_limit,
                relation_limit=relation_limit,
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 5: Run API tests**

Run:

```bash
pytest tests/unit/test_project_archive_api.py -v
```

Expected: PASS for the full API test file.

- [ ] **Step 6: Commit graph API**

Run:

```bash
git add src/project_archive/service.py src/project_archive/api.py tests/unit/test_project_archive_api.py
git commit -m "feat: expose graph explorer api"
```

## Task 3: Backend Autonomous Mission Contracts and Runner

**Files:**
- Modify: `src/project_archive/types.py`
- Create: `src/project_archive/autonomous_mission.py`
- Create: `tests/unit/test_project_archive_autonomous_mission.py`

- [ ] **Step 1: Write failing mission runner tests**

Create `tests/unit/test_project_archive_autonomous_mission.py`:

```python
"""Tests for bounded autonomous GraphRAG missions."""

from __future__ import annotations

from tests.unit.test_project_archive_graph_explorer import _draft

from src.project_archive.autonomous_mission import run_architecture_mission


def test_architecture_mission_runs_bounded_task_queue() -> None:
    mission = run_architecture_mission(_draft(), max_steps=4)

    assert mission.project_id == "demo"
    assert mission.goal == "understand_project_architecture"
    assert mission.status == "complete"
    assert len(mission.tasks) <= 4
    assert mission.tasks[0].task_type == "find_entry_points"
    assert mission.tasks[0].evidence_ids
    assert mission.graph_overlay.explored_node_ids


def test_architecture_mission_records_verifier_results() -> None:
    mission = run_architecture_mission(_draft(), max_steps=3)

    assert all(task.verifier_status in {"accepted", "uncertain"} for task in mission.tasks)
    assert all(task.confidence >= 0 for task in mission.tasks)


def test_architecture_mission_respects_max_steps() -> None:
    mission = run_architecture_mission(_draft(), max_steps=2)

    assert len(mission.tasks) == 2
    assert mission.stop_reason == "max_steps_reached"
```

- [ ] **Step 2: Run mission tests and verify they fail**

Run:

```bash
pytest tests/unit/test_project_archive_autonomous_mission.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.project_archive.autonomous_mission'`.

- [ ] **Step 3: Add mission dataclasses**

Append to `src/project_archive/types.py`:

```python
@dataclass(frozen=True)
class MissionGraphOverlay:
    mission_id: str
    explored_node_ids: list[str] = field(default_factory=list)
    explored_relation_ids: list[str] = field(default_factory=list)
    risk_node_ids: list[str] = field(default_factory=list)
    risk_relation_ids: list[str] = field(default_factory=list)
    annotations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MissionGraphOverlay:
        return cls(**data)


@dataclass(frozen=True)
class MissionTask:
    id: str
    mission_id: str
    status: str
    agent: str
    task_type: str
    title: str
    input_entity_ids: list[str] = field(default_factory=list)
    input_relation_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    verifier_status: str = "uncertain"
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MissionTask:
        return cls(**data)


@dataclass(frozen=True)
class AutonomousMission:
    id: str
    project_id: str
    goal: str
    status: str
    max_steps: int
    stop_reason: str
    created_at: str
    completed_at: str
    tasks: list[MissionTask] = field(default_factory=list)
    graph_overlay: MissionGraphOverlay | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "goal": self.goal,
            "status": self.status,
            "max_steps": self.max_steps,
            "stop_reason": self.stop_reason,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "tasks": [task.to_dict() for task in self.tasks],
            "graph_overlay": self.graph_overlay.to_dict()
            if self.graph_overlay
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomousMission:
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            goal=data["goal"],
            status=data["status"],
            max_steps=int(data["max_steps"]),
            stop_reason=data.get("stop_reason", ""),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
            tasks=[MissionTask.from_dict(task) for task in data.get("tasks", [])],
            graph_overlay=MissionGraphOverlay.from_dict(data["graph_overlay"])
            if data.get("graph_overlay")
            else None,
        )
```

- [ ] **Step 4: Implement bounded mission runner**

Create `src/project_archive/autonomous_mission.py`:

```python
"""Bounded autonomous GraphRAG missions for TwinMind Archive."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime

from src.project_archive.graph_explorer import build_graph_summary
from src.project_archive.types import (
    AutonomousMission,
    MissionGraphOverlay,
    MissionTask,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)

ARCHITECTURE_GOAL = "understand_project_architecture"


def run_architecture_mission(
    draft: ProjectArchiveDraft,
    *,
    max_steps: int = 12,
) -> AutonomousMission:
    mission_id = uuid.uuid4().hex
    created_at = _now()
    task_specs = _architecture_task_specs(draft)
    tasks: list[MissionTask] = []
    explored_nodes: set[str] = set()
    explored_relations: set[str] = set()

    for index, spec in enumerate(task_specs[: max(1, max_steps)], start=1):
        task = _run_task(
            mission_id=mission_id,
            index=index,
            spec=spec,
            draft=draft,
        )
        tasks.append(task)
        explored_nodes.update(task.input_entity_ids)
        explored_relations.update(task.input_relation_ids)

    stop_reason = "max_steps_reached" if len(task_specs) >= max_steps else "architecture_tasks_complete"
    completed_at = _now()
    overlay = MissionGraphOverlay(
        mission_id=mission_id,
        explored_node_ids=sorted(explored_nodes),
        explored_relation_ids=sorted(explored_relations),
        risk_node_ids=[],
        risk_relation_ids=[
            relation_id
            for task in tasks
            for relation_id in task.input_relation_ids
            if task.risks
        ],
        annotations=[
            {
                "task_id": task.id,
                "title": task.title,
                "entity_ids": task.input_entity_ids,
                "relation_ids": task.input_relation_ids,
            }
            for task in tasks
        ],
    )
    return AutonomousMission(
        id=mission_id,
        project_id=draft.project_id,
        goal=ARCHITECTURE_GOAL,
        status="complete",
        max_steps=max_steps,
        stop_reason=stop_reason,
        created_at=created_at,
        completed_at=completed_at,
        tasks=tasks,
        graph_overlay=overlay,
    )


def _architecture_task_specs(draft: ProjectArchiveDraft) -> list[dict[str, str]]:
    return [
        {"type": "find_entry_points", "agent": "cartographer", "title": "Find project entry points"},
        {"type": "identify_top_modules", "agent": "cartographer", "title": "Identify top-level modules"},
        {"type": "expand_configuration_chain", "agent": "detective", "title": "Expand configuration chain"},
        {"type": "trace_dependency_hubs", "agent": "detective", "title": "Trace dependency and import hubs"},
        {"type": "find_model_and_retrieval_modules", "agent": "detective", "title": "Find model and retrieval modules"},
        {"type": "verify_architecture_evidence", "agent": "librarian", "title": "Verify architecture evidence"},
        {"type": "check_architecture_risks", "agent": "skeptic", "title": "Check architecture risks"},
        {"type": "summarize_architecture", "agent": "curator", "title": "Summarize architecture"},
        {"type": "recommend_next_missions", "agent": "curator", "title": "Recommend next missions"},
    ]


def _run_task(
    *,
    mission_id: str,
    index: int,
    spec: dict[str, str],
    draft: ProjectArchiveDraft,
) -> MissionTask:
    entities = _entities_for_task(draft, spec["type"])
    relations = _relations_for_entities(draft.relations, [entity.id for entity in entities])
    evidence_ids = _evidence_for_entities_and_relations(entities, relations)
    has_evidence = bool(evidence_ids)
    risks = _risks_for_task(draft, spec["type"])
    return MissionTask(
        id=f"{mission_id}:task:{index}",
        mission_id=mission_id,
        status="complete",
        agent=spec["agent"],
        task_type=spec["type"],
        title=spec["title"],
        input_entity_ids=[entity.id for entity in entities],
        input_relation_ids=[relation.id for relation in relations],
        evidence_ids=evidence_ids,
        findings=[
            {
                "title": spec["title"],
                "detail": _finding_detail(draft, spec["type"], entities, relations),
                "evidence_ids": evidence_ids[:5],
            }
        ],
        risks=risks,
        confidence=0.78 if has_evidence else 0.42,
        verifier_status="accepted" if has_evidence else "uncertain",
        created_at=_now(),
        completed_at=_now(),
    )


def _entities_for_task(
    draft: ProjectArchiveDraft,
    task_type: str,
) -> list[ProjectEntity]:
    summary = build_graph_summary(draft)
    by_id = {entity.id: entity for entity in draft.entities}
    if task_type == "find_entry_points":
        ids = [start.entity_id for start in summary.recommended_starts if start.group == "entry_file"]
        return [by_id[entity_id] for entity_id in ids if entity_id in by_id][:6] or draft.entities[:3]
    if task_type == "expand_configuration_chain":
        return [
            entity
            for entity in draft.entities
            if entity.type.lower() == "config"
            or entity.name.lower() in {"llm", "retrieval", "vector_store", "embedding"}
        ][:8]
    if task_type == "trace_dependency_hubs":
        degree = Counter[str]()
        for relation in draft.relations:
            degree[relation.source_id] += 1
            degree[relation.target_id] += 1
        ranked_ids = [entity_id for entity_id, _count in degree.most_common(8)]
        return [by_id[entity_id] for entity_id in ranked_ids if entity_id in by_id]
    return draft.entities[:8]


def _relations_for_entities(
    relations: list[ProjectRelation],
    entity_ids: list[str],
) -> list[ProjectRelation]:
    selected = set(entity_ids)
    return [
        relation
        for relation in relations
        if relation.source_id in selected or relation.target_id in selected
    ][:12]


def _evidence_for_entities_and_relations(
    entities: list[ProjectEntity],
    relations: list[ProjectRelation],
) -> list[str]:
    evidence_ids: list[str] = []
    for entity in entities:
        evidence_ids.extend(entity.evidence_ids)
    for relation in relations:
        evidence_ids.extend(relation.evidence_ids)
    return sorted(set(evidence_ids))


def _risks_for_task(
    draft: ProjectArchiveDraft,
    task_type: str,
) -> list[dict[str, str]]:
    if task_type == "check_architecture_risks" and len(draft.relations) < 10:
        return [
            {
                "title": "Sparse relation coverage",
                "severity": "medium",
                "detail": "Architecture exploration has limited relation evidence.",
            }
        ]
    return []


def _finding_detail(
    draft: ProjectArchiveDraft,
    task_type: str,
    entities: list[ProjectEntity],
    relations: list[ProjectRelation],
) -> str:
    return (
        f"{task_type} inspected {len(entities)} entities and "
        f"{len(relations)} relations in {draft.project_id}."
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
```

- [ ] **Step 5: Run mission tests**

Run:

```bash
pytest tests/unit/test_project_archive_autonomous_mission.py -v
```

Expected: PASS with 3 tests.

- [ ] **Step 6: Commit mission runner foundation**

Run:

```bash
git add src/project_archive/types.py src/project_archive/autonomous_mission.py tests/unit/test_project_archive_autonomous_mission.py
git commit -m "feat: add bounded autonomous mission runner"
```

## Task 4: Backend Mission Persistence and API

**Files:**
- Modify: `src/project_archive/service.py`
- Modify: `src/project_archive/api.py`
- Modify: `tests/unit/test_project_archive_api.py`

- [ ] **Step 1: Add failing mission API tests**

Append to `tests/unit/test_project_archive_api.py`:

```python
def test_start_architecture_mission_returns_completed_bounded_mission(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/api/archives/sample/missions",
        json={"goal": "understand_project_architecture", "max_steps": 3},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["project_id"] == "sample"
    assert payload["goal"] == "understand_project_architecture"
    assert len(payload["tasks"]) == 3
    assert payload["graph_overlay"]["explored_node_ids"]

    mission_id = payload["id"]
    mission_response = client.get(f"/api/missions/{mission_id}")
    assert mission_response.status_code == 200
    assert mission_response.json()["id"] == mission_id


def test_get_mission_tasks_and_overlay(tmp_path: Path) -> None:
    client = _client(tmp_path)

    created = client.post(
        "/api/archives/sample/missions",
        json={"goal": "understand_project_architecture", "max_steps": 2},
    ).json()
    mission_id = created["id"]

    tasks_response = client.get(f"/api/missions/{mission_id}/tasks")
    overlay_response = client.get(f"/api/missions/{mission_id}/graph-overlay")

    assert tasks_response.status_code == 200
    assert len(tasks_response.json()["tasks"]) == 2
    assert overlay_response.status_code == 200
    assert overlay_response.json()["mission_id"] == mission_id


def test_pause_resume_stop_mission_update_status(tmp_path: Path) -> None:
    client = _client(tmp_path)
    mission_id = client.post(
        "/api/archives/sample/missions",
        json={"goal": "understand_project_architecture", "max_steps": 2},
    ).json()["id"]

    pause_response = client.post(f"/api/missions/{mission_id}/pause")
    resume_response = client.post(f"/api/missions/{mission_id}/resume")
    stop_response = client.post(f"/api/missions/{mission_id}/stop")

    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "complete"
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"
```

- [ ] **Step 2: Run mission API tests and verify they fail**

Run:

```bash
pytest tests/unit/test_project_archive_api.py::test_start_architecture_mission_returns_completed_bounded_mission tests/unit/test_project_archive_api.py::test_get_mission_tasks_and_overlay tests/unit/test_project_archive_api.py::test_pause_resume_stop_mission_update_status -v
```

Expected: FAIL with 404 responses for missing mission routes.

- [ ] **Step 3: Add service mission methods**

Modify imports in `src/project_archive/service.py`:

```python
from dataclasses import replace
from src.project_archive.autonomous_mission import ARCHITECTURE_GOAL, run_architecture_mission
from src.project_archive.types import (
    AgentResult,
    AutonomousMission,
    GraphNeighborhood,
    GraphSummary,
    ProjectAgentReport,
    ProjectArchiveDraft,
    QueryMode,
)
```

Add methods inside `ProjectArchiveService` after `graph_neighborhood`:

```python
    def start_architecture_mission(
        self,
        project_id: str,
        *,
        max_steps: int = 12,
    ) -> AutonomousMission:
        draft = self.load_draft(project_id)
        mission = run_architecture_mission(draft, max_steps=max(1, min(max_steps, 12)))
        self._mission_path(project_id, mission.id).write_text(
            json.dumps(mission.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return mission

    def load_mission(self, mission_id: str) -> AutonomousMission:
        for project_dir in self.storage_dir.iterdir():
            path = project_dir / "missions" / f"{mission_id}.json"
            if path.exists():
                return AutonomousMission.from_dict(json.loads(path.read_text(encoding="utf-8")))
        raise ValueError(f"Mission not found: {mission_id}")

    def update_mission_status(self, mission_id: str, status: str) -> AutonomousMission:
        mission = self.load_mission(mission_id)
        updated = replace(mission, status=status)
        self._mission_path(updated.project_id, updated.id).write_text(
            json.dumps(updated.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return updated
```

Add helper method:

```python
    def _mission_path(self, project_id: str, mission_id: str) -> Path:
        path = self._project_dir(project_id) / "missions"
        path.mkdir(parents=True, exist_ok=True)
        return path / f"{mission_id}.json"
```

- [ ] **Step 4: Add mission request model and routes**

Modify `src/project_archive/api.py` imports:

```python
from pydantic import BaseModel, Field
from src.project_archive.autonomous_mission import ARCHITECTURE_GOAL
```

Add request model after `ArchiveQueryRequest`:

```python
class MissionStartRequest(BaseModel):
    goal: str = ARCHITECTURE_GOAL
    max_steps: int = Field(default=12, ge=1, le=12)
```

Add routes after graph routes:

```python
    @app.post("/api/archives/{project_id}/missions", status_code=202)
    def start_mission(
        project_id: str,
        request: MissionStartRequest,
        service: ServiceDep,
    ) -> dict:
        if request.goal != ARCHITECTURE_GOAL:
            raise HTTPException(status_code=400, detail=f"Unsupported mission goal: {request.goal}")
        try:
            return service.start_architecture_mission(
                project_id,
                max_steps=request.max_steps,
            ).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/missions/{mission_id}")
    def get_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_mission(mission_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/missions/{mission_id}/tasks")
    def get_mission_tasks(mission_id: str, service: ServiceDep) -> dict:
        try:
            mission = service.load_mission(mission_id)
            return {"mission_id": mission.id, "tasks": [task.to_dict() for task in mission.tasks]}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/missions/{mission_id}/graph-overlay")
    def get_mission_graph_overlay(mission_id: str, service: ServiceDep) -> dict:
        try:
            mission = service.load_mission(mission_id)
            if mission.graph_overlay is None:
                return {"mission_id": mission.id, "explored_node_ids": [], "explored_relation_ids": [], "risk_node_ids": [], "risk_relation_ids": [], "annotations": []}
            return mission.graph_overlay.to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/pause")
    def pause_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.update_mission_status(mission_id, "paused").to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/resume")
    def resume_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.update_mission_status(mission_id, "complete").to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/missions/{mission_id}/stop")
    def stop_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.update_mission_status(mission_id, "stopped").to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 5: Run API tests**

Run:

```bash
pytest tests/unit/test_project_archive_api.py tests/unit/test_project_archive_autonomous_mission.py -v
```

Expected: PASS for both files.

- [ ] **Step 6: Commit mission API**

Run:

```bash
git add src/project_archive/service.py src/project_archive/api.py tests/unit/test_project_archive_api.py
git commit -m "feat: expose autonomous mission api"
```

## Task 5: Frontend API Types and Client Methods

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add TypeScript graph and mission types**

Append to `frontend/src/types.ts`:

```ts
export type GraphExplorerNode = {
  id: string;
  label: string;
  type: string;
  hall_ids: string[];
  source_path: string | null;
  evidence_ids: string[];
  degree: number;
  importance: number;
  tags: string[];
};

export type GraphExplorerRelation = {
  id: string;
  source_id: string;
  target_id: string;
  type: string;
  evidence_ids: string[];
  hall_ids: string[];
  weight: number;
};

export type RecommendedGraphStart = {
  entity_id: string;
  label: string;
  group: string;
  reason: string;
  score: number;
  hall_ids: string[];
};

export type GraphSummary = {
  project_id: string;
  metrics: {
    entities: number;
    relations: number;
    evidence: number;
  };
  recommended_starts: RecommendedGraphStart[];
};

export type GraphNeighborhood = {
  project_id: string;
  hall_id: string | null;
  focus_entity_id: string | null;
  depth: number;
  nodes: GraphExplorerNode[];
  relations: GraphExplorerRelation[];
  evidence_ids: string[];
  is_sparse: boolean;
  sparse_reason: string;
};

export type MissionGraphOverlay = {
  mission_id: string;
  explored_node_ids: string[];
  explored_relation_ids: string[];
  risk_node_ids: string[];
  risk_relation_ids: string[];
  annotations: Record<string, unknown>[];
};

export type MissionTask = {
  id: string;
  mission_id: string;
  status: string;
  agent: string;
  task_type: string;
  title: string;
  input_entity_ids: string[];
  input_relation_ids: string[];
  evidence_ids: string[];
  findings: Record<string, unknown>[];
  risks: Record<string, unknown>[];
  confidence: number;
  verifier_status: string;
  created_at: string;
  completed_at: string;
};

export type AutonomousMission = {
  id: string;
  project_id: string;
  goal: string;
  status: string;
  max_steps: number;
  stop_reason: string;
  created_at: string;
  completed_at: string;
  tasks: MissionTask[];
  graph_overlay: MissionGraphOverlay | null;
};
```

- [ ] **Step 2: Add API client methods**

Modify imports in `frontend/src/api.ts`:

```ts
import type {
  AgentReport,
  AgentStatus,
  ArchiveJob,
  ArchiveDraft,
  ArchiveHall,
  ArchiveRelation,
  AutonomousMission,
  EvidenceCard,
  GraphNeighborhood,
  GraphSummary,
  MissionGraphOverlay,
  MissionTask,
  ProjectAgentReport,
} from "./types";
```

Add these functions before `pollArchiveJob`:

```ts
export async function fetchGraphSummary(projectId: string): Promise<GraphSummary> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/graph`);
  if (!response.ok) {
    throw new Error(`Graph summary failed: ${response.status}`);
  }
  return (await response.json()) as GraphSummary;
}

export async function fetchGraphNeighborhood({
  projectId,
  hallId,
  focusEntityId,
  depth,
  relationTypes,
  nodeLimit = 80,
  relationLimit = 120,
}: {
  projectId: string;
  hallId?: string | null;
  focusEntityId?: string | null;
  depth: number;
  relationTypes: string[];
  nodeLimit?: number;
  relationLimit?: number;
}): Promise<GraphNeighborhood> {
  const params = new URLSearchParams({
    depth: String(depth),
    node_limit: String(nodeLimit),
    relation_limit: String(relationLimit),
  });
  if (hallId) params.set("hall_id", hallId);
  if (focusEntityId) params.set("focus_entity_id", focusEntityId);
  relationTypes.forEach((type) => params.append("relation_types", type));
  const response = await fetch(
    `${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/graph/neighborhood?${params.toString()}`,
  );
  if (!response.ok) {
    throw new Error(`Graph neighborhood failed: ${response.status}`);
  }
  return (await response.json()) as GraphNeighborhood;
}

export async function startArchitectureMission(
  projectId: string,
  maxSteps = 12,
): Promise<AutonomousMission> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/missions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      goal: "understand_project_architecture",
      max_steps: maxSteps,
    }),
  });
  if (!response.ok) {
    throw new Error(`Mission start failed: ${response.status}`);
  }
  return (await response.json()) as AutonomousMission;
}

export async function fetchMission(missionId: string): Promise<AutonomousMission> {
  const response = await fetch(`${API_BASE_URL}/api/missions/${encodeURIComponent(missionId)}`);
  if (!response.ok) {
    throw new Error(`Mission load failed: ${response.status}`);
  }
  return (await response.json()) as AutonomousMission;
}

export async function fetchMissionTasks(missionId: string): Promise<MissionTask[]> {
  const response = await fetch(`${API_BASE_URL}/api/missions/${encodeURIComponent(missionId)}/tasks`);
  if (!response.ok) {
    throw new Error(`Mission tasks failed: ${response.status}`);
  }
  const payload = (await response.json()) as { tasks?: MissionTask[] };
  return payload.tasks ?? [];
}

export async function fetchMissionGraphOverlay(missionId: string): Promise<MissionGraphOverlay> {
  const response = await fetch(`${API_BASE_URL}/api/missions/${encodeURIComponent(missionId)}/graph-overlay`);
  if (!response.ok) {
    throw new Error(`Mission overlay failed: ${response.status}`);
  }
  return (await response.json()) as MissionGraphOverlay;
}

export async function updateMissionStatus(
  missionId: string,
  action: "pause" | "resume" | "stop",
): Promise<AutonomousMission> {
  const response = await fetch(`${API_BASE_URL}/api/missions/${encodeURIComponent(missionId)}/${action}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Mission ${action} failed: ${response.status}`);
  }
  return (await response.json()) as AutonomousMission;
}
```

- [ ] **Step 3: Run frontend type build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS with Vite production build output.

- [ ] **Step 4: Commit frontend API contracts**

Run:

```bash
git add frontend/src/types.ts frontend/src/api.ts
git commit -m "feat: add graph explorer frontend contracts"
```

## Task 6: Frontend Graph Explorer Page and Navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Extend page type and copy**

Modify `frontend/src/App.tsx`:

```ts
type AppPage = "overview" | "graph" | "agents";
```

Add these copy keys to both `zh` and `en` entries:

```ts
graphPage: "图谱探索",
expandGraph: "放大图谱",
graphExplorer: "图谱探索",
missionControl: "自主任务",
recommendedStarts: "推荐起点",
entityDetails: "实体详情",
closeDrawer: "关闭面板",
openDrawer: "打开面板",
```

Use English values in `en`:

```ts
graphPage: "Graph Explorer",
expandGraph: "Expand graph",
graphExplorer: "Graph Explorer",
missionControl: "Mission control",
recommendedStarts: "Recommended starts",
entityDetails: "Entity details",
closeDrawer: "Close panel",
openDrawer: "Open panel",
```

- [ ] **Step 2: Update page tabs**

Modify `PageTabs` in `frontend/src/App.tsx` so it renders three buttons:

```tsx
const tabs = [
  { id: "overview" as AppPage, label: copy[locale].overviewPage, icon: Archive },
  { id: "graph" as AppPage, label: copy[locale].graphPage, icon: Network },
  { id: "agents" as AppPage, label: copy[locale].agentPage, icon: Sparkles },
];
```

- [ ] **Step 3: Add overview expand action**

Pass `onExpandGraph={() => setActivePage("graph")}` into `StarMap`. Add a button near the Star Map heading:

```tsx
<button className="secondary-action" onClick={onExpandGraph} type="button">
  <Network size={15} />
  {t.expandGraph}
</button>
```

Add `onExpandGraph: () => void` to `StarMap` props.

- [ ] **Step 4: Add Graph Explorer page shell component**

Add this component before `AgentPipelinePanel`:

```tsx
function GraphExplorerPage({
  archiveDraft,
  locale,
}: {
  archiveDraft: ArchiveDraft;
  locale: Locale;
}) {
  const t = copy[locale];
  return (
    <section className="graph-explorer-page">
      <div className="graph-explorer-toolbar panel">
        <div>
          <span className="eyebrow">{t.graphExplorer}</span>
          <h2>{archiveDraft.projectId}</h2>
        </div>
        <div className="toolbar-actions">
          <button className="secondary-action" type="button">
            <CircleDot size={15} />
            {t.missionControl}
          </button>
        </div>
      </div>
      <div className="graph-explorer-shell panel">
        <div className="graph-explorer-canvas">
          <Network size={28} />
          <strong>{t.graphExplorer}</strong>
        </div>
      </div>
    </section>
  );
}
```

Modify main render:

```tsx
{activePage === "overview" ? (
  <>
    ...
  </>
) : activePage === "graph" ? (
  <GraphExplorerPage archiveDraft={archiveDraft} locale={locale} />
) : (
  <div className="agent-analysis-page">
    ...
  </div>
)}
```

- [ ] **Step 5: Add Graph Explorer base styles**

Append to `frontend/src/styles.css`:

```css
.graph-explorer-page {
  display: grid;
  gap: 14px;
}

.graph-explorer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 82px;
  padding: 18px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.secondary-action {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid rgba(59, 77, 99, 0.78);
  border-radius: 8px;
  padding: 0 12px;
  color: var(--text);
  background: rgba(12, 20, 31, 0.76);
}

.secondary-action:hover {
  border-color: rgba(53, 208, 186, 0.55);
  color: var(--accent);
}

.graph-explorer-shell {
  position: relative;
  min-height: calc(100vh - 250px);
  overflow: hidden;
}

.graph-explorer-canvas {
  min-height: calc(100vh - 280px);
  display: grid;
  place-items: center;
  gap: 10px;
  color: var(--muted);
  background:
    linear-gradient(rgba(53, 208, 186, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(53, 208, 186, 0.045) 1px, transparent 1px),
    radial-gradient(circle at 50% 45%, rgba(53, 208, 186, 0.12), transparent 38%),
    #07101a;
  background-size: 52px 52px, 52px 52px, auto, auto;
}
```

- [ ] **Step 6: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit Graph Explorer page shell**

Run:

```bash
git add frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: add graph explorer page"
```

## Task 7: Frontend Real Graph Focus, Drawers, and Selection Styling

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Import graph API methods and types**

Modify imports in `frontend/src/App.tsx`:

```ts
import {
  fetchAgentStatus,
  fetchArchiveDraft,
  fetchGraphNeighborhood,
  fetchGraphSummary,
  fetchProjectAgentReport,
  fetchProjectArchive,
  runArchiveQuery,
  runProjectAgentReportJob,
  uploadProjectArchive,
} from "./api";
```

Add types:

```ts
  GraphExplorerNode,
  GraphExplorerRelation,
  GraphNeighborhood,
  GraphSummary,
```

- [ ] **Step 2: Replace GraphExplorerPage shell with stateful implementation**

Replace `GraphExplorerPage` with:

```tsx
function GraphExplorerPage({
  archiveDraft,
  locale,
}: {
  archiveDraft: ArchiveDraft;
  locale: Locale;
}) {
  const t = copy[locale];
  const [summary, setSummary] = useState<GraphSummary | null>(null);
  const [neighborhood, setNeighborhood] = useState<GraphNeighborhood | null>(null);
  const [focusedEntityId, setFocusedEntityId] = useState<string | null>(null);
  const [selectedRelationId, setSelectedRelationId] = useState<string | null>(null);
  const [selectedHallId, setSelectedHallId] = useState<string | null>(archiveDraft.halls[0]?.id ?? null);
  const [depth, setDepth] = useState(1);
  const [isLeftOpen, setIsLeftOpen] = useState(true);
  const [isRightOpen, setIsRightOpen] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    fetchGraphSummary(archiveDraft.projectId)
      .then((nextSummary) => {
        if (mounted) setSummary(nextSummary);
      })
      .catch((nextError) => {
        if (mounted) setError(nextError instanceof Error ? nextError.message : String(nextError));
      });
    return () => {
      mounted = false;
    };
  }, [archiveDraft.projectId]);

  useEffect(() => {
    let mounted = true;
    fetchGraphNeighborhood({
      projectId: archiveDraft.projectId,
      hallId: selectedHallId,
      focusEntityId: focusedEntityId,
      depth,
      relationTypes: [],
      nodeLimit: 80,
      relationLimit: 120,
    })
      .then((nextNeighborhood) => {
        if (mounted) setNeighborhood(nextNeighborhood);
      })
      .catch((nextError) => {
        if (mounted) setError(nextError instanceof Error ? nextError.message : String(nextError));
      });
    return () => {
      mounted = false;
    };
  }, [archiveDraft.projectId, selectedHallId, focusedEntityId, depth]);

  const focusedNode = neighborhood?.nodes.find((node) => node.id === focusedEntityId) ?? null;

  return (
    <section className="graph-explorer-page">
      <div className="graph-explorer-toolbar panel">
        <div>
          <span className="eyebrow">{t.graphExplorer}</span>
          <h2>{archiveDraft.projectId}</h2>
        </div>
        <div className="toolbar-actions">
          <select value={selectedHallId ?? ""} onChange={(event) => setSelectedHallId(event.currentTarget.value || null)}>
            <option value="">{locale === "zh" ? "全项目" : "Full project"}</option>
            {archiveDraft.halls.map((hall) => (
              <option key={hall.id} value={hall.id}>
                {hallTitle(hall, locale)}
              </option>
            ))}
          </select>
          <button className="secondary-action" onClick={() => setDepth(depth === 1 ? 2 : 1)} type="button">
            <CircleDot size={15} />
            {locale === "zh" ? `${depth} 跳` : `${depth} hop`}
          </button>
          <button className="secondary-action" onClick={() => setIsLeftOpen((value) => !value)} type="button">
            {isLeftOpen ? t.closeDrawer : t.openDrawer}
          </button>
          <button className="secondary-action" onClick={() => setIsRightOpen((value) => !value)} type="button">
            {isRightOpen ? t.closeDrawer : t.openDrawer}
          </button>
        </div>
      </div>
      <div className="graph-explorer-shell panel">
        {isLeftOpen ? (
          <GraphStartsDrawer
            locale={locale}
            onFocusEntity={(entityId) => {
              setFocusedEntityId(entityId);
              setSelectedRelationId(null);
            }}
            summary={summary}
          />
        ) : null}
        <GraphExplorerCanvas
          focusedEntityId={focusedEntityId}
          locale={locale}
          neighborhood={neighborhood}
          onFocusEntity={(entityId) => {
            setFocusedEntityId(entityId);
            setSelectedRelationId(null);
          }}
          onSelectRelation={setSelectedRelationId}
          selectedRelationId={selectedRelationId}
        />
        {isRightOpen ? (
          <GraphEntityDrawer
            focusedNode={focusedNode}
            locale={locale}
            neighborhood={neighborhood}
            selectedRelationId={selectedRelationId}
          />
        ) : null}
        <div className="graph-explorer-status">
          {error || (neighborhood ? `${neighborhood.nodes.length} nodes / ${neighborhood.relations.length} relations` : "Loading graph")}
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Add drawer and canvas components**

Add these components after `GraphExplorerPage`:

```tsx
function GraphStartsDrawer({
  locale,
  onFocusEntity,
  summary,
}: {
  locale: Locale;
  onFocusEntity: (entityId: string) => void;
  summary: GraphSummary | null;
}) {
  return (
    <aside className="graph-drawer graph-drawer-left">
      <span className="eyebrow">{copy[locale].recommendedStarts}</span>
      {(summary?.recommended_starts ?? []).map((start) => (
        <button className="graph-start-item" key={`${start.group}-${start.entity_id}`} onClick={() => onFocusEntity(start.entity_id)} type="button">
          <strong>{start.label}</strong>
          <span>{start.reason}</span>
        </button>
      ))}
    </aside>
  );
}

function GraphEntityDrawer({
  focusedNode,
  locale,
  neighborhood,
  selectedRelationId,
}: {
  focusedNode: GraphExplorerNode | null;
  locale: Locale;
  neighborhood: GraphNeighborhood | null;
  selectedRelationId: string | null;
}) {
  const selectedRelation = neighborhood?.relations.find((relation) => relation.id === selectedRelationId) ?? null;
  return (
    <aside className="graph-drawer graph-drawer-right">
      <span className="eyebrow">{copy[locale].entityDetails}</span>
      {focusedNode ? (
        <div className="entity-detail-stack">
          <h3>{focusedNode.label}</h3>
          <span>{focusedNode.type}</span>
          <span>{focusedNode.source_path}</span>
          <span>{focusedNode.degree} relations</span>
        </div>
      ) : (
        <p>{locale === "zh" ? "选择一个实体查看详情。" : "Select an entity to inspect it."}</p>
      )}
      {selectedRelation ? (
        <div className="entity-detail-stack">
          <strong>{selectedRelation.type}</strong>
          <span>{selectedRelation.source_id}</span>
          <span>{selectedRelation.target_id}</span>
        </div>
      ) : null}
    </aside>
  );
}

function GraphExplorerCanvas({
  focusedEntityId,
  locale,
  neighborhood,
  onFocusEntity,
  onSelectRelation,
  selectedRelationId,
}: {
  focusedEntityId: string | null;
  locale: Locale;
  neighborhood: GraphNeighborhood | null;
  onFocusEntity: (entityId: string) => void;
  onSelectRelation: (relationId: string) => void;
  selectedRelationId: string | null;
}) {
  const layout = useMemo(() => layoutGraph(neighborhood?.nodes ?? []), [neighborhood]);
  const nodeMap = new Map(layout.map((node) => [node.id, node]));
  if (!neighborhood) {
    return <div className="graph-explorer-canvas">{locale === "zh" ? "正在加载图谱" : "Loading graph"}</div>;
  }
  if (neighborhood.is_sparse) {
    return <div className="graph-explorer-canvas">{neighborhood.sparse_reason}</div>;
  }
  return (
    <div className="graph-explorer-canvas">
      <svg viewBox="0 0 1100 620" role="img">
        {neighborhood.relations.map((relation) => {
          const source = nodeMap.get(relation.source_id);
          const target = nodeMap.get(relation.target_id);
          if (!source || !target) return null;
          const isSelected = relation.id === selectedRelationId;
          const isConnectedToFocus = focusedEntityId && (relation.source_id === focusedEntityId || relation.target_id === focusedEntityId);
          return (
            <line
              className={`explorer-edge ${isSelected ? "is-selected" : ""} ${isConnectedToFocus ? "is-focus-edge" : ""}`}
              key={relation.id}
              onClick={() => onSelectRelation(relation.id)}
              x1={source.x}
              x2={target.x}
              y1={source.y}
              y2={target.y}
            />
          );
        })}
        {layout.map((node) => (
          <g
            className={`explorer-node ${node.id === focusedEntityId ? "is-focused" : ""}`}
            key={node.id}
            onClick={() => onFocusEntity(node.id)}
          >
            <circle cx={node.x} cy={node.y} r={node.id === focusedEntityId ? 24 : 16} />
            <text x={node.x} y={node.y + 34} textAnchor="middle">
              {compactGraphLabel(node.label, 22)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function layoutGraph(nodes: GraphExplorerNode[]) {
  const centerX = 550;
  const centerY = 310;
  return nodes.map((node, index) => {
    if (index === 0) return { ...node, x: centerX, y: centerY };
    const angle = -Math.PI / 2 + ((index - 1) / Math.max(1, nodes.length - 1)) * Math.PI * 2;
    return {
      ...node,
      x: centerX + Math.cos(angle) * 360,
      y: centerY + Math.sin(angle) * 210,
    };
  });
}
```

- [ ] **Step 4: Add graph explorer interaction styles**

Append to `frontend/src/styles.css`:

```css
.graph-drawer {
  position: absolute;
  z-index: 5;
  top: 14px;
  bottom: 54px;
  width: min(280px, 32vw);
  overflow: auto;
  border: 1px solid rgba(59, 77, 99, 0.78);
  border-radius: 8px;
  padding: 14px;
  background: rgba(8, 13, 20, 0.86);
  backdrop-filter: blur(14px);
}

.graph-drawer-left {
  left: 14px;
}

.graph-drawer-right {
  right: 14px;
}

.graph-start-item {
  width: 100%;
  display: grid;
  gap: 5px;
  margin-top: 10px;
  border: 1px solid rgba(59, 77, 99, 0.58);
  border-radius: 8px;
  padding: 10px;
  color: var(--text);
  text-align: left;
  background: rgba(13, 23, 36, 0.82);
}

.graph-start-item span,
.entity-detail-stack span {
  color: var(--muted);
  font-size: 12px;
}

.entity-detail-stack {
  display: grid;
  gap: 6px;
  margin-top: 12px;
  border-top: 1px solid rgba(59, 77, 99, 0.58);
  padding-top: 12px;
}

.graph-explorer-canvas svg {
  width: 100%;
  height: 100%;
  min-height: calc(100vh - 280px);
}

.explorer-edge {
  stroke: rgba(154, 169, 186, 0.26);
  stroke-width: 1.5;
}

.explorer-edge.is-focus-edge {
  stroke: rgba(53, 208, 186, 0.58);
  stroke-width: 2.2;
}

.explorer-edge.is-selected {
  stroke: rgba(255, 190, 92, 0.95);
  stroke-width: 4;
  filter: drop-shadow(0 0 8px rgba(255, 190, 92, 0.64));
}

.explorer-node circle {
  fill: var(--blue);
  stroke: rgba(238, 246, 255, 0.74);
  stroke-width: 1.5;
}

.explorer-node.is-focused circle {
  fill: var(--accent);
  stroke: rgba(238, 246, 255, 0.96);
  stroke-width: 3;
  filter: drop-shadow(0 0 16px rgba(53, 208, 186, 0.68));
}

.explorer-node text {
  fill: var(--text);
  font-size: 12px;
  paint-order: stroke;
  stroke: rgba(7, 16, 26, 0.94);
  stroke-width: 4px;
}

.graph-explorer-status {
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 12px;
  min-height: 34px;
  display: flex;
  align-items: center;
  border: 1px solid rgba(59, 77, 99, 0.62);
  border-radius: 8px;
  padding: 0 12px;
  color: var(--subtle);
  background: rgba(8, 13, 20, 0.82);
}
```

- [ ] **Step 5: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit real graph explorer interactions**

Run:

```bash
git add frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: add interactive graph explorer"
```

## Task 8: Frontend Autonomous Mission Playback

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Import mission API methods and type**

Modify `frontend/src/App.tsx` imports:

```ts
import {
  fetchAgentStatus,
  fetchArchiveDraft,
  fetchGraphNeighborhood,
  fetchGraphSummary,
  fetchMissionGraphOverlay,
  fetchProjectAgentReport,
  fetchProjectArchive,
  runArchiveQuery,
  runProjectAgentReportJob,
  startArchitectureMission,
  updateMissionStatus,
  uploadProjectArchive,
} from "./api";
```

Add `AutonomousMission` to type imports.

- [ ] **Step 2: Add mission state to GraphExplorerPage**

Inside `GraphExplorerPage`, add:

```tsx
  const [mission, setMission] = useState<AutonomousMission | null>(null);
  const [isMissionRunning, setIsMissionRunning] = useState(false);
```

Add handler:

```tsx
  const runMission = async () => {
    setIsMissionRunning(true);
    setError("");
    try {
      const nextMission = await startArchitectureMission(archiveDraft.projectId, 12);
      setMission(nextMission);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : String(nextError));
    } finally {
      setIsMissionRunning(false);
    }
  };

  const changeMissionStatus = async (action: "pause" | "resume" | "stop") => {
    if (!mission) return;
    const nextMission = await updateMissionStatus(mission.id, action);
    setMission(nextMission);
  };
```

Replace mission toolbar button:

```tsx
<button className="secondary-action" disabled={isMissionRunning} onClick={runMission} type="button">
  <Sparkles size={15} />
  {isMissionRunning ? (locale === "zh" ? "运行中" : "Running") : t.missionControl}
</button>
```

- [ ] **Step 3: Render mission playback panel**

Inside `graph-explorer-shell`, before status:

```tsx
{mission ? (
  <MissionPlayback
    locale={locale}
    mission={mission}
    onPause={() => changeMissionStatus("pause")}
    onResume={() => changeMissionStatus("resume")}
    onStop={() => changeMissionStatus("stop")}
  />
) : null}
```

Add component:

```tsx
function MissionPlayback({
  locale,
  mission,
  onPause,
  onResume,
  onStop,
}: {
  locale: Locale;
  mission: AutonomousMission;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
}) {
  return (
    <section className="mission-playback">
      <div className="mission-playback-head">
        <div>
          <span className="eyebrow">{copy[locale].missionControl}</span>
          <strong>{mission.goal}</strong>
        </div>
        <div className="mission-actions">
          <button className="icon-button" onClick={onPause} title="Pause" type="button">
            <CircleDot size={14} />
          </button>
          <button className="icon-button" onClick={onResume} title="Resume" type="button">
            <Sparkles size={14} />
          </button>
          <button className="icon-button" onClick={onStop} title="Stop" type="button">
            <X size={14} />
          </button>
        </div>
      </div>
      <div className="mission-task-list">
        {mission.tasks.map((task, index) => (
          <div className="mission-task" key={task.id}>
            <span>{index + 1}</span>
            <strong>{task.title}</strong>
            <small>{task.agent} · {task.verifier_status} · {Math.round(task.confidence * 100)}%</small>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add mission overlay to graph canvas**

Pass `mission?.graph_overlay ?? null` to `GraphExplorerCanvas`.

Extend props:

```ts
missionOverlay: MissionGraphOverlay | null;
```

Change edge class:

```tsx
const isExplored = missionOverlay?.explored_relation_ids.includes(relation.id);
className={`explorer-edge ${isSelected ? "is-selected" : ""} ${isConnectedToFocus ? "is-focus-edge" : ""} ${isExplored ? "is-agent-explored" : ""}`}
```

Change node class:

```tsx
const isExplored = missionOverlay?.explored_node_ids.includes(node.id);
className={`explorer-node ${node.id === focusedEntityId ? "is-focused" : ""} ${isExplored ? "is-agent-explored" : ""}`}
```

- [ ] **Step 5: Add mission playback styles**

Append to `frontend/src/styles.css`:

```css
.mission-playback {
  position: absolute;
  z-index: 6;
  left: 50%;
  bottom: 56px;
  width: min(620px, calc(100% - 32px));
  max-height: 260px;
  overflow: auto;
  transform: translateX(-50%);
  border: 1px solid rgba(53, 208, 186, 0.34);
  border-radius: 8px;
  padding: 12px;
  background: rgba(8, 13, 20, 0.88);
  backdrop-filter: blur(16px);
}

.mission-playback-head,
.mission-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mission-task-list {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.mission-task {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  border: 1px solid rgba(59, 77, 99, 0.5);
  border-radius: 8px;
  padding: 8px;
  color: var(--muted);
  background: rgba(13, 23, 36, 0.78);
}

.mission-task strong {
  min-width: 0;
  overflow: hidden;
  color: var(--text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mission-task small {
  color: var(--subtle);
}

.explorer-edge.is-agent-explored {
  stroke: rgba(148, 126, 255, 0.74);
  stroke-width: 2.6;
}

.explorer-node.is-agent-explored circle {
  stroke: rgba(148, 126, 255, 0.95);
  stroke-width: 2.4;
}
```

- [ ] **Step 6: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit mission playback UI**

Run:

```bash
git add frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: add mission playback to graph explorer"
```

## Task 9: Full Verification and Polish Pass

**Files:**
- Modify only files that fail verification from Tasks 1-8.

- [ ] **Step 1: Run backend unit and integration tests**

Run:

```bash
pytest tests/unit/test_project_archive_graph_explorer.py tests/unit/test_project_archive_autonomous_mission.py tests/unit/test_project_archive_api.py tests/unit/test_project_archive_llm.py tests/integration/test_project_archive_service.py -v
```

Expected: PASS.

- [ ] **Step 2: Run backend lint on touched Python files**

Run:

```bash
ruff check src/project_archive/types.py src/project_archive/graph_explorer.py src/project_archive/autonomous_mission.py src/project_archive/service.py src/project_archive/api.py tests/unit/test_project_archive_graph_explorer.py tests/unit/test_project_archive_autonomous_mission.py tests/unit/test_project_archive_api.py
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Start or verify backend**

Run:

```bash
curl -s http://127.0.0.1:8000/api/health
```

Expected:

```json
{"status":"ok"}
```

If a different service responds, find the process and restart TwinMind:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

Then run:

```bash
.venv/bin/python -m uvicorn src.project_archive.api:app --host 127.0.0.1 --port 8000
```

- [ ] **Step 5: Verify frontend manually**

Run frontend if it is not already running:

```bash
cd frontend && npm run dev
```

Open `http://127.0.0.1:5173` and verify:

- Graph Explorer tab is visible.
- Overview Star Map has an expand action.
- Graph Explorer loads recommended starts.
- Hall switching does not show identical fallback data for sparse halls.
- Clicking an entity focuses it and opens the detail drawer.
- Clicking a relation makes the edge and endpoints visibly brighter.
- Depth toggle changes visible neighborhood.
- Running the architecture mission shows mission tasks.
- Mission overlay marks explored entities and relations.
- Pause, resume, and stop controls update status.

- [ ] **Step 6: Capture Playwright screenshot**

Run:

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PWCLI="$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"
"$PWCLI" open http://127.0.0.1:5173 --browser msedge
"$PWCLI" screenshot --filename output/playwright/twinmind-graph-explorer-autonomous-agent.png
rm -rf .playwright-cli
```

Expected: screenshot exists at `output/playwright/twinmind-graph-explorer-autonomous-agent.png`.

- [ ] **Step 7: Commit verification fixes**

If verification required code changes, commit only those fixes:

```bash
git add src/project_archive/types.py src/project_archive/graph_explorer.py src/project_archive/autonomous_mission.py src/project_archive/service.py src/project_archive/api.py tests/unit/test_project_archive_graph_explorer.py tests/unit/test_project_archive_autonomous_mission.py tests/unit/test_project_archive_api.py frontend/src/types.ts frontend/src/api.ts frontend/src/App.tsx frontend/src/styles.css
git commit -m "fix: polish graph explorer autonomous mission"
```

If no verification fixes were required, do not create an empty commit.
