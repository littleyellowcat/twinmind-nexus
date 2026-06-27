# Graph-Grounded Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bounded Plan-and-Execute Agent runtime where each task can run Graph-grounded ReAct tool calls, verify evidence, persist traces, and show the mission trajectory in the frontend.

**Architecture:** Keep ingestion deterministic and add a new Agent mission runtime beside the existing autonomous mission and multi-agent report pipeline. The runtime will use explicit dataclasses, a tool registry wrapping existing graph/RAG/evidence services, a deterministic planner, a bounded ReAct runner with optional DeepSeek next-action JSON, and a verifier that marks unsupported findings as uncertain.

**Tech Stack:** Python 3.12, FastAPI, dataclasses, existing `ProjectArchiveService`, existing graph explorer and Hybrid RAG modules, DeepSeek LLM adapter through `src.project_archive.llm`, React 19 + Vite frontend.

---

## File Structure

Create these backend files:

- `src/project_archive/agent_mission.py`: Mission planner, mission store, task runner, verifier orchestration, and service-facing runtime.
- `src/project_archive/agent_tools.py`: Tool registry and tool functions wrapping graph summary, graph search, graph neighborhood, Hybrid RAG, evidence lookup, entity inspection, and specialist agent execution.
- `tests/unit/test_project_archive_agent_mission.py`: Mission planner, runner, verifier, and persistence tests.
- `tests/unit/test_project_archive_agent_tools.py`: Tool registry and tool behavior tests.

Modify these backend files:

- `src/project_archive/types.py`: Add Agent mission dataclasses while preserving existing `AutonomousMission`.
- `src/project_archive/service.py`: Add methods to start, load, trace, and update Agent missions.
- `src/project_archive/api.py`: Add Agent mission request models and endpoints.
- `src/project_archive/multi_agent.py`: Add a small helper to run one specialist role deterministically.

Modify these frontend files:

- `frontend/src/types.ts`: Add Agent mission, task, trace, and verifier types.
- `frontend/src/api.ts`: Add Agent mission API functions.
- `frontend/src/App.tsx`: Add a ReAct mission panel to Agent Analysis and wire start/load/trace actions.
- `frontend/src/styles.css`: Add styles for plan, trace, verifier, and evidence timeline.

No existing ingestion, Tree-sitter, Hybrid RAG indexing, or graph explorer behavior should be rewritten in this feature.

---

### Task 1: Add Agent Mission Dataclasses

**Files:**
- Modify: `src/project_archive/types.py`
- Test: `tests/unit/test_project_archive_agent_mission.py`

- [ ] **Step 1: Write failing dataclass serialization tests**

Create `tests/unit/test_project_archive_agent_mission.py` with:

```python
from src.project_archive.types import (
    AgentMission,
    AgentMissionBudget,
    AgentMissionFinalReport,
    AgentMissionTask,
    AgentMissionVerifierResult,
    AgentTraceEvent,
)


def test_agent_mission_round_trips_trace_and_verifier_result():
    mission = AgentMission(
        id="mission-1",
        project_id="demo",
        goal="Understand architecture",
        status="complete",
        created_at="2026-06-27T00:00:00+00:00",
        completed_at="2026-06-27T00:00:10+00:00",
        budget=AgentMissionBudget(max_tasks=3, max_steps_per_task=4, max_tool_calls=10),
        tasks=[
            AgentMissionTask(
                id="task-1",
                mission_id="mission-1",
                task_type="find_entry_points",
                objective="Find likely entry points.",
                status="complete",
                allowed_tools=["graph_summary", "inspect_entity"],
                max_steps=3,
                steps_used=2,
                evidence_ids=["ev_1"],
                findings=[{"summary": "main.py is an entry point.", "evidence_ids": ["ev_1"]}],
                confidence=0.82,
            )
        ],
        trace_events=[
            AgentTraceEvent(
                id="trace-1",
                mission_id="mission-1",
                task_id="task-1",
                sequence=1,
                event_type="action",
                tool_name="graph_summary",
                tool_input={"project_id": "demo"},
                observation_summary="Found one entry point.",
                evidence_ids=["ev_1"],
                entity_ids=["file_main"],
            )
        ],
        verifier_result=AgentMissionVerifierResult(
            status="accepted",
            supported_finding_count=1,
            uncertain_finding_count=0,
            warnings=[],
        ),
        final_report=AgentMissionFinalReport(
            summary="Architecture understood with cited evidence.",
            evidence_ids=["ev_1"],
            confidence=0.82,
        ),
    )

    restored = AgentMission.from_dict(mission.to_dict())

    assert restored == mission
    assert restored.tasks[0].allowed_tools == ["graph_summary", "inspect_entity"]
    assert restored.trace_events[0].tool_input == {"project_id": "demo"}
    assert restored.verifier_result.status == "accepted"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_agent_mission.py -v
```

Expected: fail with `ImportError` for the new dataclasses.

- [ ] **Step 3: Add dataclasses to `types.py`**

Append these dataclasses after `AutonomousMission` in `src/project_archive/types.py`:

```python
@dataclass(frozen=True)
class AgentMissionBudget:
    max_tasks: int = 5
    max_steps_per_task: int = 4
    max_tool_calls: int = 16
    timeout_seconds: int = 90

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMissionBudget:
        return cls(
            max_tasks=int(data.get("max_tasks", 5)),
            max_steps_per_task=int(data.get("max_steps_per_task", 4)),
            max_tool_calls=int(data.get("max_tool_calls", 16)),
            timeout_seconds=int(data.get("timeout_seconds", 90)),
        )


@dataclass(frozen=True)
class AgentMissionTask:
    id: str
    mission_id: str
    task_type: str
    objective: str
    status: str
    allowed_tools: list[str] = field(default_factory=list)
    max_steps: int = 4
    steps_used: int = 0
    input_entity_ids: list[str] = field(default_factory=list)
    output_entity_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMissionTask:
        return cls(
            id=data["id"],
            mission_id=data["mission_id"],
            task_type=data["task_type"],
            objective=data["objective"],
            status=data.get("status", "pending"),
            allowed_tools=list(data.get("allowed_tools", [])),
            max_steps=int(data.get("max_steps", 4)),
            steps_used=int(data.get("steps_used", 0)),
            input_entity_ids=list(data.get("input_entity_ids", [])),
            output_entity_ids=list(data.get("output_entity_ids", [])),
            evidence_ids=list(data.get("evidence_ids", [])),
            findings=list(data.get("findings", [])),
            risks=list(data.get("risks", [])),
            confidence=float(data.get("confidence", 0.0)),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
        )


@dataclass(frozen=True)
class AgentTraceEvent:
    id: str
    mission_id: str
    task_id: str
    sequence: int
    event_type: str
    tool_name: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    observation_summary: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    relation_ids: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTraceEvent:
        return cls(
            id=data["id"],
            mission_id=data["mission_id"],
            task_id=data["task_id"],
            sequence=int(data["sequence"]),
            event_type=data["event_type"],
            tool_name=data.get("tool_name"),
            tool_input=dict(data.get("tool_input", {})),
            observation_summary=data.get("observation_summary", ""),
            evidence_ids=list(data.get("evidence_ids", [])),
            entity_ids=list(data.get("entity_ids", [])),
            relation_ids=list(data.get("relation_ids", [])),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
            error=data.get("error"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AgentMissionVerifierResult:
    status: str
    supported_finding_count: int = 0
    uncertain_finding_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMissionVerifierResult:
        return cls(
            status=data.get("status", "uncertain"),
            supported_finding_count=int(data.get("supported_finding_count", 0)),
            uncertain_finding_count=int(data.get("uncertain_finding_count", 0)),
            warnings=list(data.get("warnings", [])),
        )


@dataclass(frozen=True)
class AgentMissionFinalReport:
    summary: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMissionFinalReport:
        return cls(
            summary=data.get("summary", ""),
            findings=list(data.get("findings", [])),
            evidence_ids=list(data.get("evidence_ids", [])),
            confidence=float(data.get("confidence", 0.0)),
        )


@dataclass(frozen=True)
class AgentMission:
    id: str
    project_id: str
    goal: str
    status: str
    created_at: str
    completed_at: str = ""
    budget: AgentMissionBudget = field(default_factory=AgentMissionBudget)
    tasks: list[AgentMissionTask] = field(default_factory=list)
    trace_events: list[AgentTraceEvent] = field(default_factory=list)
    verifier_result: AgentMissionVerifierResult | None = None
    final_report: AgentMissionFinalReport | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "goal": self.goal,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "budget": self.budget.to_dict(),
            "tasks": [task.to_dict() for task in self.tasks],
            "trace_events": [event.to_dict() for event in self.trace_events],
            "verifier_result": self.verifier_result.to_dict()
            if self.verifier_result
            else None,
            "final_report": self.final_report.to_dict() if self.final_report else None,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMission:
        return cls(
            id=data["id"],
            project_id=data["project_id"],
            goal=data["goal"],
            status=data.get("status", "pending"),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at", ""),
            budget=AgentMissionBudget.from_dict(data.get("budget", {})),
            tasks=[
                AgentMissionTask.from_dict(task)
                for task in data.get("tasks", [])
            ],
            trace_events=[
                AgentTraceEvent.from_dict(event)
                for event in data.get("trace_events", [])
            ],
            verifier_result=AgentMissionVerifierResult.from_dict(
                data["verifier_result"]
            )
            if data.get("verifier_result")
            else None,
            final_report=AgentMissionFinalReport.from_dict(data["final_report"])
            if data.get("final_report")
            else None,
            metadata=dict(data.get("metadata", {})),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_agent_mission.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/project_archive/types.py tests/unit/test_project_archive_agent_mission.py
git commit -m "feat: add agent mission data model"
```

---

### Task 2: Add Tool Registry

**Files:**
- Create: `src/project_archive/agent_tools.py`
- Test: `tests/unit/test_project_archive_agent_tools.py`

- [ ] **Step 1: Write failing registry tests**

Create `tests/unit/test_project_archive_agent_tools.py` with:

```python
import pytest

from src.project_archive.agent_tools import AgentToolRegistry, ToolExecutionError
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)


class FakeService:
    def __init__(self):
        self.draft = ProjectArchiveDraft(
            project_id="demo",
            halls=[
                ArchiveHall(
                    id="hall_architecture",
                    name="Architecture Hall",
                    description="Architecture",
                    entity_ids=["file_main", "class_service"],
                )
            ],
            entities=[
                ProjectEntity(
                    id="file_main",
                    type="File",
                    name="main.py",
                    source_path="main.py",
                    evidence_ids=["ev_main"],
                ),
                ProjectEntity(
                    id="class_service",
                    type="Class",
                    name="QueryService",
                    source_path="main.py",
                    evidence_ids=["ev_service"],
                ),
            ],
            relations=[
                ProjectRelation(
                    id="rel_defines",
                    source_id="file_main",
                    target_id="class_service",
                    type="DEFINES",
                    evidence_ids=["ev_service"],
                )
            ],
            evidence_cards=[
                EvidenceCard(
                    id="ev_main",
                    source_type="code",
                    source_path="main.py",
                    title="main.py",
                    snippet="from service import QueryService",
                    linked_entities=["file_main"],
                ),
                EvidenceCard(
                    id="ev_service",
                    source_type="code",
                    source_path="main.py",
                    title="QueryService",
                    snippet="class QueryService: pass",
                    linked_entities=["class_service"],
                ),
            ],
        )

    def load_draft(self, project_id):
        assert project_id == "demo"
        return self.draft

    def graph_summary(self, project_id):
        return type(
            "Summary",
            (),
            {
                "to_dict": lambda self: {
                    "project_id": project_id,
                    "metrics": {"entities": 2, "relations": 1, "evidence": 2},
                    "recommended_starts": [],
                }
            },
        )()

    def search_graph_entities(self, project_id, *, query, limit=20):
        return []

    def graph_neighborhood(self, project_id, **kwargs):
        return type(
            "Neighborhood",
            (),
            {
                "to_dict": lambda self: {
                    "project_id": project_id,
                    "nodes": [],
                    "relations": [],
                    "evidence_ids": [],
                    "is_sparse": True,
                }
            },
        )()


def test_tool_registry_lists_and_executes_graph_summary():
    registry = AgentToolRegistry(FakeService())

    result = registry.execute("graph_summary", {"project_id": "demo"})

    assert "graph_summary" in registry.tool_names()
    assert result.tool_name == "graph_summary"
    assert result.summary == "Graph summary returned 2 entities and 1 relations."
    assert result.payload["metrics"]["entities"] == 2


def test_get_evidence_returns_selected_cards():
    registry = AgentToolRegistry(FakeService())

    result = registry.execute(
        "get_evidence",
        {"project_id": "demo", "evidence_ids": ["ev_service"]},
    )

    assert result.evidence_ids == ["ev_service"]
    assert result.payload["evidence_cards"][0]["title"] == "QueryService"


def test_inspect_entity_returns_neighbors_and_evidence():
    registry = AgentToolRegistry(FakeService())

    result = registry.execute(
        "inspect_entity",
        {"project_id": "demo", "entity_id": "class_service"},
    )

    assert result.entity_ids == ["class_service"]
    assert result.relation_ids == ["rel_defines"]
    assert result.evidence_ids == ["ev_service"]


def test_unknown_tool_is_rejected():
    registry = AgentToolRegistry(FakeService())

    with pytest.raises(ToolExecutionError, match="Unknown Agent tool"):
        registry.execute("shell", {"cmd": "ls"})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_agent_tools.py -v
```

Expected: fail with `ModuleNotFoundError` for `src.project_archive.agent_tools`.

- [ ] **Step 3: Implement tool registry**

Create `src/project_archive/agent_tools.py`:

```python
"""Bounded tool registry for graph-grounded Agent missions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from src.project_archive.hybrid_rag import ProjectHybridRAGIndex
from src.project_archive.multi_agent import run_specialist_role
from src.project_archive.types import EvidenceCard, ProjectArchiveDraft


class ToolExecutionError(ValueError):
    """Raised when an Agent tool cannot be executed safely."""


@dataclass(frozen=True)
class AgentToolResult:
    tool_name: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)
    entity_ids: list[str] = field(default_factory=list)
    relation_ids: list[str] = field(default_factory=list)


ToolHandler = Callable[[dict[str, Any]], AgentToolResult]


class AgentToolRegistry:
    """Expose approved project-analysis tools to the Agent runtime."""

    def __init__(self, service: Any) -> None:
        self.service = service
        self._tools: dict[str, ToolHandler] = {
            "list_halls": self._list_halls,
            "graph_summary": self._graph_summary,
            "graph_search": self._graph_search,
            "graph_neighborhood": self._graph_neighborhood,
            "hybrid_search": self._hybrid_search,
            "get_evidence": self._get_evidence,
            "inspect_entity": self._inspect_entity,
            "run_specialist_agent": self._run_specialist_agent,
        }

    def tool_names(self) -> list[str]:
        return sorted(self._tools)

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> AgentToolResult:
        handler = self._tools.get(tool_name)
        if handler is None:
            raise ToolExecutionError(f"Unknown Agent tool: {tool_name}")
        return handler(dict(tool_input))

    def _draft(self, project_id: str) -> ProjectArchiveDraft:
        return self.service.load_draft(project_id)

    def _list_halls(self, payload: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(payload, "project_id")
        draft = self._draft(project_id)
        halls = [
            {
                "id": hall.id,
                "name": hall.name,
                "description": hall.description,
                "entity_count": len(hall.entity_ids),
            }
            for hall in draft.halls
        ]
        return AgentToolResult(
            tool_name="list_halls",
            summary=f"Listed {len(halls)} archive halls.",
            payload={"halls": halls},
        )

    def _graph_summary(self, payload: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(payload, "project_id")
        summary = self.service.graph_summary(project_id).to_dict()
        metrics = summary.get("metrics", {})
        return AgentToolResult(
            tool_name="graph_summary",
            summary=(
                "Graph summary returned "
                f"{metrics.get('entities', 0)} entities and "
                f"{metrics.get('relations', 0)} relations."
            ),
            payload=summary,
        )

    def _graph_search(self, payload: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(payload, "project_id")
        query = _required_str(payload, "query")
        limit = int(payload.get("limit", 10))
        results = self.service.search_graph_entities(
            project_id,
            query=query,
            limit=limit,
        )
        serialized = [result.to_dict() for result in results]
        return AgentToolResult(
            tool_name="graph_search",
            summary=f"Graph search found {len(serialized)} entities for {query!r}.",
            payload={"results": serialized},
            entity_ids=[item["entity_id"] for item in serialized],
        )

    def _graph_neighborhood(self, payload: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(payload, "project_id")
        neighborhood = self.service.graph_neighborhood(
            project_id,
            hall_id=payload.get("hall_id"),
            focus_entity_id=payload.get("focus_entity_id"),
            depth=int(payload.get("depth", 1)),
            relation_types=list(payload.get("relation_types", [])),
            node_limit=int(payload.get("node_limit", 80)),
            relation_limit=int(payload.get("relation_limit", 120)),
        ).to_dict()
        return AgentToolResult(
            tool_name="graph_neighborhood",
            summary=(
                f"Neighborhood returned {len(neighborhood.get('nodes', []))} nodes "
                f"and {len(neighborhood.get('relations', []))} relations."
            ),
            payload=neighborhood,
            evidence_ids=list(neighborhood.get("evidence_ids", [])),
            entity_ids=[node["id"] for node in neighborhood.get("nodes", [])],
            relation_ids=[relation["id"] for relation in neighborhood.get("relations", [])],
        )

    def _hybrid_search(self, payload: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(payload, "project_id")
        query = _required_str(payload, "query")
        top_k = int(payload.get("top_k", 6))
        hall_id = payload.get("hall_id")
        result = ProjectHybridRAGIndex(self.service.storage_dir).search(
            project_id=project_id,
            query=query,
            hall_id=hall_id,
            top_k=top_k,
        )
        items = [item.to_dict() for item in result.results]
        evidence_ids = [
            str(item.get("metadata", {}).get("evidence_id", ""))
            for item in items
            if item.get("metadata", {}).get("evidence_id")
        ]
        return AgentToolResult(
            tool_name="hybrid_search",
            summary=f"Hybrid search returned {len(items)} result(s) for {query!r}.",
            payload={"results": items, "metadata": result.to_metadata()},
            evidence_ids=evidence_ids,
        )

    def _get_evidence(self, payload: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(payload, "project_id")
        evidence_ids = [str(item) for item in payload.get("evidence_ids", [])]
        draft = self._draft(project_id)
        cards = [
            card
            for card in draft.evidence_cards
            if not evidence_ids or card.id in set(evidence_ids)
        ][:20]
        return AgentToolResult(
            tool_name="get_evidence",
            summary=f"Loaded {len(cards)} evidence card(s).",
            payload={"evidence_cards": [card.to_dict() for card in cards]},
            evidence_ids=[card.id for card in cards],
            entity_ids=_unique_id_list(
                entity_id
                for card in cards
                for entity_id in card.linked_entities
            ),
        )

    def _inspect_entity(self, payload: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(payload, "project_id")
        entity_id = _required_str(payload, "entity_id")
        draft = self._draft(project_id)
        entity = next((item for item in draft.entities if item.id == entity_id), None)
        if entity is None:
            raise ToolExecutionError(f"Entity not found: {entity_id}")
        relations = [
            relation
            for relation in draft.relations
            if relation.source_id == entity_id or relation.target_id == entity_id
        ][:50]
        evidence_ids = _unique_id_list(
            [*entity.evidence_ids, *[eid for relation in relations for eid in relation.evidence_ids]]
        )
        cards = _evidence_by_ids(draft.evidence_cards, evidence_ids)
        return AgentToolResult(
            tool_name="inspect_entity",
            summary=f"Inspected {entity.type} {entity.name} with {len(relations)} relation(s).",
            payload={
                "entity": entity.to_dict(),
                "relations": [relation.to_dict() for relation in relations],
                "evidence_cards": [card.to_dict() for card in cards],
            },
            evidence_ids=evidence_ids,
            entity_ids=[entity_id],
            relation_ids=[relation.id for relation in relations],
        )

    def _run_specialist_agent(self, payload: dict[str, Any]) -> AgentToolResult:
        project_id = _required_str(payload, "project_id")
        role = _required_str(payload, "role")
        draft = self._draft(project_id)
        result = run_specialist_role(draft=draft, role=role)
        return AgentToolResult(
            tool_name="run_specialist_agent",
            summary=f"Specialist {role} returned {result.status}.",
            payload={"result": result.to_dict()},
            evidence_ids=list(result.evidence_card_ids),
            entity_ids=list(result.entity_ids),
            relation_ids=list(result.relation_ids),
        )


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolExecutionError(f"Tool input requires non-empty string: {key}")
    return value.strip()


def _evidence_by_ids(cards: list[EvidenceCard], evidence_ids: list[str]) -> list[EvidenceCard]:
    wanted = set(evidence_ids)
    return [card for card in cards if card.id in wanted]


def _unique_id_list(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
```

- [ ] **Step 4: Add single-role specialist helper**

Modify `src/project_archive/multi_agent.py` by adding this function near the bottom, after `MultiAgentPipeline`:

```python
def run_specialist_role(
    draft: ProjectArchiveDraft,
    role: str,
    prior_agents: dict[str, AgentRoleResult] | None = None,
) -> AgentRoleResult:
    """Run one deterministic specialist role for tool-call usage."""

    pipeline = MultiAgentPipeline()
    agents = dict(prior_agents or {})
    runners = {
        "archivist": pipeline._run_archivist,
        "cartographer": pipeline._run_cartographer,
        "detective": pipeline._run_detective,
        "skeptic": pipeline._run_skeptic,
        "curator": pipeline._run_curator,
    }
    runner = runners.get(role)
    if runner is None:
        raise ValueError(f"Unknown specialist role: {role}")
    return runner(draft, agents)
```

- [ ] **Step 5: Run tool tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_agent_tools.py -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/project_archive/agent_tools.py src/project_archive/multi_agent.py tests/unit/test_project_archive_agent_tools.py
git commit -m "feat: add graph grounded agent tools"
```

---

### Task 3: Add Mission Planner, Store, Runner, and Verifier

**Files:**
- Create: `src/project_archive/agent_mission.py`
- Modify: `tests/unit/test_project_archive_agent_mission.py`

- [ ] **Step 1: Add failing runtime tests**

Append to `tests/unit/test_project_archive_agent_mission.py`:

```python
from pathlib import Path

from src.project_archive.agent_mission import (
    AgentMissionRuntime,
    EvidenceVerifier,
    MissionStore,
    plan_agent_mission,
)
from src.project_archive.agent_tools import AgentToolRegistry
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)


class RuntimeFakeService:
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.draft = ProjectArchiveDraft(
            project_id="demo",
            halls=[
                ArchiveHall(
                    id="hall_architecture",
                    name="Architecture Hall",
                    description="Architecture",
                    entity_ids=["file_main", "class_service"],
                )
            ],
            entities=[
                ProjectEntity(
                    id="file_main",
                    type="File",
                    name="main.py",
                    source_path="main.py",
                    evidence_ids=["ev_main"],
                ),
                ProjectEntity(
                    id="class_service",
                    type="Class",
                    name="QueryService",
                    source_path="main.py",
                    evidence_ids=["ev_service"],
                ),
            ],
            relations=[
                ProjectRelation(
                    id="rel_defines",
                    source_id="file_main",
                    target_id="class_service",
                    type="DEFINES",
                    evidence_ids=["ev_service"],
                )
            ],
            evidence_cards=[
                EvidenceCard(
                    id="ev_main",
                    source_type="code",
                    source_path="main.py",
                    title="main.py",
                    snippet="from service import QueryService",
                    linked_entities=["file_main"],
                ),
                EvidenceCard(
                    id="ev_service",
                    source_type="code",
                    source_path="main.py",
                    title="QueryService",
                    snippet="class QueryService: pass",
                    linked_entities=["class_service"],
                ),
            ],
        )

    def load_draft(self, project_id):
        assert project_id == "demo"
        return self.draft

    def graph_summary(self, project_id):
        return type(
            "Summary",
            (),
            {
                "to_dict": lambda self: {
                    "project_id": project_id,
                    "metrics": {"entities": 2, "relations": 1, "evidence": 2},
                    "recommended_starts": [],
                }
            },
        )()

    def search_graph_entities(self, project_id, *, query, limit=20):
        return []

    def graph_neighborhood(self, project_id, **kwargs):
        return type(
            "Neighborhood",
            (),
            {
                "to_dict": lambda self: {
                    "project_id": project_id,
                    "nodes": [],
                    "relations": [],
                    "evidence_ids": ["ev_service"],
                    "is_sparse": False,
                }
            },
        )()


def test_plan_agent_mission_creates_bounded_tasks():
    draft = RuntimeFakeService(Path(".")).draft

    mission = plan_agent_mission(
        draft=draft,
        goal="Understand architecture",
        max_tasks=3,
        max_steps_per_task=4,
    )

    assert mission.status == "planned"
    assert len(mission.tasks) == 3
    assert mission.tasks[0].task_type == "find_entry_points"
    assert mission.tasks[0].allowed_tools
    assert mission.budget.max_tasks == 3


def test_evidence_verifier_marks_missing_evidence_uncertain():
    draft = RuntimeFakeService(Path(".")).draft
    verifier = EvidenceVerifier()
    mission = plan_agent_mission(draft=draft, goal="Understand architecture")
    unsupported = mission.tasks[0].to_dict()
    unsupported["findings"] = [{"summary": "This claim has no citations."}]
    task = mission.tasks[0].from_dict(unsupported)

    result = verifier.verify_task(task=task, draft=draft)

    assert result.status == "uncertain"
    assert result.uncertain_finding_count == 1
    assert result.warnings


def test_runtime_runs_tools_and_persists_trace(tmp_path):
    service = RuntimeFakeService(tmp_path)
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=None,
    )

    mission = runtime.start(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=2,
        max_steps_per_task=2,
    )
    restored = runtime.load(mission.id)

    assert restored.status == "complete"
    assert restored.trace_events
    assert restored.final_report is not None
    assert restored.verifier_result is not None
    assert runtime.trace(mission.id) == restored.trace_events
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_agent_mission.py -v
```

Expected: fail with `ModuleNotFoundError` for `agent_mission`.

- [ ] **Step 3: Implement deterministic planner, store, verifier, and runner**

Create `src/project_archive/agent_mission.py`:

```python
"""Graph-grounded Agent mission runtime."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from src.libs.llm import BaseLLM
from src.project_archive.agent_tools import AgentToolRegistry
from src.project_archive.types import (
    AgentMission,
    AgentMissionBudget,
    AgentMissionFinalReport,
    AgentMissionTask,
    AgentMissionVerifierResult,
    AgentTraceEvent,
    ProjectArchiveDraft,
)

DEFAULT_AGENT_GOAL = "Understand project architecture"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def plan_agent_mission(
    draft: ProjectArchiveDraft,
    goal: str,
    max_tasks: int = 5,
    max_steps_per_task: int = 4,
    max_tool_calls: int = 16,
) -> AgentMission:
    mission_id = uuid4().hex
    specs = [
        (
            "find_entry_points",
            "Find likely entry points and startup paths.",
            ["graph_summary", "graph_search", "inspect_entity"],
        ),
        (
            "map_core_modules",
            "Map high-degree modules, halls, and graph neighborhoods.",
            ["graph_summary", "list_halls", "graph_neighborhood", "inspect_entity"],
        ),
        (
            "trace_dependencies",
            "Trace dependency hubs and important relation paths.",
            ["graph_search", "graph_neighborhood", "get_evidence"],
        ),
        (
            "explain_architecture",
            "Produce an evidence-backed architecture explanation.",
            ["hybrid_search", "get_evidence", "run_specialist_agent"],
        ),
        (
            "verify_claims",
            "Check unsupported claims and sparse evidence coverage.",
            ["get_evidence", "run_specialist_agent"],
        ),
    ][: max(1, int(max_tasks))]
    tasks = [
        AgentMissionTask(
            id=f"{mission_id}:task:{index}",
            mission_id=mission_id,
            task_type=task_type,
            objective=objective,
            status="pending",
            allowed_tools=tools,
            max_steps=max(1, int(max_steps_per_task)),
            created_at=utc_now(),
        )
        for index, (task_type, objective, tools) in enumerate(specs, start=1)
    ]
    return AgentMission(
        id=mission_id,
        project_id=draft.project_id,
        goal=goal.strip() or DEFAULT_AGENT_GOAL,
        status="planned",
        created_at=utc_now(),
        budget=AgentMissionBudget(
            max_tasks=len(tasks),
            max_steps_per_task=max(1, int(max_steps_per_task)),
            max_tool_calls=max(1, int(max_tool_calls)),
        ),
        tasks=tasks,
        metadata={
            "draft_metrics": {
                "halls": len(draft.halls),
                "entities": len(draft.entities),
                "relations": len(draft.relations),
                "evidence": len(draft.evidence_cards),
            }
        },
    )


class MissionStore:
    """Persist Agent missions under the project archive storage directory."""

    def __init__(self, storage_dir: Path | str) -> None:
        self.storage_dir = Path(storage_dir)

    def save(self, mission: AgentMission) -> AgentMission:
        path = self._path(mission.project_id, mission.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(mission.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return mission

    def load(self, mission_id: str) -> AgentMission:
        for project_dir in self.storage_dir.iterdir():
            path = project_dir / "agent_missions" / f"{mission_id}.json"
            if path.exists():
                return AgentMission.from_dict(json.loads(path.read_text(encoding="utf-8")))
        raise ValueError(f"Agent mission not found: {mission_id}")

    def update_status(self, mission_id: str, status: str) -> AgentMission:
        mission = self.load(mission_id)
        updated = replace(mission, status=status)
        return self.save(updated)

    def _path(self, project_id: str, mission_id: str) -> Path:
        safe_project_id = project_id.replace("/", "_").replace(" ", "_")
        return self.storage_dir / safe_project_id / "agent_missions" / f"{mission_id}.json"


class EvidenceVerifier:
    """Validate that Agent findings point at real project evidence."""

    def verify_task(
        self,
        task: AgentMissionTask,
        draft: ProjectArchiveDraft,
    ) -> AgentMissionVerifierResult:
        valid_evidence_ids = {card.id for card in draft.evidence_cards}
        supported = 0
        uncertain = 0
        warnings: list[str] = []
        for finding in task.findings:
            evidence_ids = [
                str(item)
                for item in finding.get("evidence_ids", [])
                if str(item) in valid_evidence_ids
            ]
            if evidence_ids:
                supported += 1
            else:
                uncertain += 1
                warnings.append(
                    f"Task {task.task_type} has an unsupported finding: "
                    f"{finding.get('summary', finding.get('title', 'unnamed finding'))}"
                )
        if not task.findings:
            warnings.append(f"Task {task.task_type} produced no findings.")
        status = "accepted" if warnings == [] else "uncertain"
        return AgentMissionVerifierResult(
            status=status,
            supported_finding_count=supported,
            uncertain_finding_count=uncertain,
            warnings=warnings,
        )


class AgentMissionRuntime:
    """Run bounded graph-grounded Agent missions."""

    def __init__(
        self,
        service,
        store: MissionStore,
        tool_registry: AgentToolRegistry,
        llm: BaseLLM | None = None,
        verifier: EvidenceVerifier | None = None,
    ) -> None:
        self.service = service
        self.store = store
        self.tool_registry = tool_registry
        self.llm = llm
        self.verifier = verifier or EvidenceVerifier()

    def create(
        self,
        draft: ProjectArchiveDraft,
        goal: str,
        max_tasks: int = 5,
        max_steps_per_task: int = 4,
    ) -> AgentMission:
        return plan_agent_mission(
            draft=draft,
            goal=goal,
            max_tasks=max_tasks,
            max_steps_per_task=max_steps_per_task,
        )

    def start(
        self,
        project_id: str,
        goal: str,
        max_tasks: int = 5,
        max_steps_per_task: int = 4,
    ) -> AgentMission:
        draft = self.service.load_draft(project_id)
        mission = self.create(
            draft=draft,
            goal=goal,
            max_tasks=max_tasks,
            max_steps_per_task=max_steps_per_task,
        )
        self.store.save(mission)
        completed = self._run_to_completion(mission, draft)
        return self.store.save(completed)

    def run(self, mission_id: str) -> AgentMission:
        mission = self.store.load(mission_id)
        draft = self.service.load_draft(mission.project_id)
        running = replace(mission, status="running")
        self.store.save(running)
        completed = self._run_to_completion(running, draft)
        return self.store.save(completed)

    def load(self, mission_id: str) -> AgentMission:
        return self.store.load(mission_id)

    def trace(self, mission_id: str) -> list[AgentTraceEvent]:
        return self.load(mission_id).trace_events

    def update_status(self, mission_id: str, status: str) -> AgentMission:
        return self.store.update_status(mission_id, status)

    def _run_to_completion(
        self,
        mission: AgentMission,
        draft: ProjectArchiveDraft,
    ) -> AgentMission:
        trace_events: list[AgentTraceEvent] = []
        completed_tasks: list[AgentMissionTask] = []
        sequence = 1
        for task in mission.tasks:
            task_start = utc_now()
            tool_calls = self._default_tool_calls(mission.project_id, task)
            task_evidence_ids: list[str] = []
            task_entity_ids: list[str] = []
            task_relation_ids: list[str] = []
            findings: list[dict[str, object]] = []
            for tool_name, tool_input in tool_calls[: task.max_steps]:
                started_at = utc_now()
                result = self.tool_registry.execute(tool_name, tool_input)
                completed_at = utc_now()
                trace_events.append(
                    AgentTraceEvent(
                        id=f"{mission.id}:trace:{sequence}",
                        mission_id=mission.id,
                        task_id=task.id,
                        sequence=sequence,
                        event_type="action",
                        tool_name=tool_name,
                        tool_input=tool_input,
                        observation_summary=result.summary,
                        evidence_ids=result.evidence_ids,
                        entity_ids=result.entity_ids,
                        relation_ids=result.relation_ids,
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                )
                sequence += 1
                task_evidence_ids.extend(result.evidence_ids)
                task_entity_ids.extend(result.entity_ids)
                task_relation_ids.extend(result.relation_ids)
                findings.append(
                    {
                        "summary": result.summary,
                        "evidence_ids": result.evidence_ids,
                        "entity_ids": result.entity_ids,
                        "relation_ids": result.relation_ids,
                    }
                )
            completed = replace(
                task,
                status="complete",
                steps_used=len(tool_calls[: task.max_steps]),
                output_entity_ids=_unique(task_entity_ids),
                evidence_ids=_unique(task_evidence_ids),
                findings=findings,
                confidence=0.78 if task_evidence_ids else 0.42,
                completed_at=utc_now(),
                created_at=task.created_at or task_start,
            )
            completed_tasks.append(completed)
        verifier_result = self._verify_mission(completed_tasks, draft)
        final_report = self._final_report(completed_tasks, verifier_result)
        return replace(
            mission,
            status="complete",
            completed_at=utc_now(),
            tasks=completed_tasks,
            trace_events=trace_events,
            verifier_result=verifier_result,
            final_report=final_report,
        )

    def _default_tool_calls(
        self,
        project_id: str,
        task: AgentMissionTask,
    ) -> list[tuple[str, dict[str, object]]]:
        if task.task_type == "find_entry_points":
            return [
                ("graph_summary", {"project_id": project_id}),
                ("graph_search", {"project_id": project_id, "query": "main app server cli", "limit": 8}),
            ]
        if task.task_type == "map_core_modules":
            return [
                ("list_halls", {"project_id": project_id}),
                ("graph_neighborhood", {"project_id": project_id, "depth": 1, "node_limit": 40}),
            ]
        if task.task_type == "trace_dependencies":
            return [
                ("graph_search", {"project_id": project_id, "query": "import dependency module", "limit": 8}),
                ("get_evidence", {"project_id": project_id, "evidence_ids": []}),
            ]
        if task.task_type == "explain_architecture":
            return [
                ("hybrid_search", {"project_id": project_id, "query": "project architecture entry point core modules", "top_k": 6}),
                ("run_specialist_agent", {"project_id": project_id, "role": "detective"}),
            ]
        return [
            ("run_specialist_agent", {"project_id": project_id, "role": "skeptic"}),
            ("get_evidence", {"project_id": project_id, "evidence_ids": []}),
        ]

    def _verify_mission(
        self,
        tasks: list[AgentMissionTask],
        draft: ProjectArchiveDraft,
    ) -> AgentMissionVerifierResult:
        results = [self.verifier.verify_task(task=task, draft=draft) for task in tasks]
        warnings = [warning for result in results for warning in result.warnings]
        supported = sum(result.supported_finding_count for result in results)
        uncertain = sum(result.uncertain_finding_count for result in results)
        return AgentMissionVerifierResult(
            status="accepted" if not warnings else "uncertain",
            supported_finding_count=supported,
            uncertain_finding_count=uncertain,
            warnings=warnings,
        )

    def _final_report(
        self,
        tasks: list[AgentMissionTask],
        verifier_result: AgentMissionVerifierResult,
    ) -> AgentMissionFinalReport:
        evidence_ids = _unique(
            evidence_id
            for task in tasks
            for evidence_id in task.evidence_ids
        )
        summary = (
            f"Agent mission completed {len(tasks)} task(s). "
            f"Verifier status: {verifier_result.status}."
        )
        return AgentMissionFinalReport(
            summary=summary,
            findings=[finding for task in tasks for finding in task.findings],
            evidence_ids=evidence_ids,
            confidence=0.78 if verifier_result.status == "accepted" else 0.55,
        )


def _unique(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
```

- [ ] **Step 4: Run runtime tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_agent_mission.py tests/unit/test_project_archive_agent_tools.py -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/project_archive/agent_mission.py tests/unit/test_project_archive_agent_mission.py
git commit -m "feat: add graph grounded agent mission runtime"
```

---

### Task 4: Add Optional LLM Next-Action Selection

**Files:**
- Modify: `src/project_archive/agent_mission.py`
- Modify: `tests/unit/test_project_archive_agent_mission.py`

- [ ] **Step 1: Add failing LLM action-selection tests**

Append to `tests/unit/test_project_archive_agent_mission.py`:

```python
from src.libs.llm import ChatResponse, Message


class FakeActionLLM:
    model = "fake-action-model"

    def __init__(self, content: str):
        self.content = content
        self.messages: list[list[Message]] = []

    def chat(self, messages, trace=None, **kwargs):
        self.messages.append(messages)
        return ChatResponse(content=self.content, model=self.model, usage={"total_tokens": 12})


def test_runtime_uses_llm_next_action_when_json_is_valid(tmp_path):
    service = RuntimeFakeService(tmp_path)
    llm = FakeActionLLM(
        '{"thought_summary":"Inspect graph first",'
        '"action":{"tool":"graph_summary","input":{"project_id":"demo"}},'
        '"stop":false}'
    )
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=llm,
    )

    mission = runtime.start(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=1,
    )

    assert llm.messages
    assert mission.trace_events[0].tool_name == "graph_summary"
    assert mission.trace_events[0].metadata["thought_summary"] == "Inspect graph first"
    assert mission.trace_events[0].metadata["model"] == "fake-action-model"


def test_runtime_falls_back_when_llm_action_is_invalid(tmp_path):
    service = RuntimeFakeService(tmp_path)
    llm = FakeActionLLM("this is not json")
    runtime = AgentMissionRuntime(
        service=service,
        store=MissionStore(tmp_path),
        tool_registry=AgentToolRegistry(service),
        llm=llm,
    )

    mission = runtime.start(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=1,
        max_steps_per_task=1,
    )

    assert mission.trace_events[0].tool_name == "graph_summary"
    assert mission.trace_events[0].metadata["llm_fallback"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/test_project_archive_agent_mission.py::test_runtime_uses_llm_next_action_when_json_is_valid \
  tests/unit/test_project_archive_agent_mission.py::test_runtime_falls_back_when_llm_action_is_invalid \
  -v
```

Expected: fail because trace metadata does not include LLM action details yet.

- [ ] **Step 3: Add structured action parsing helpers**

In `src/project_archive/agent_mission.py`, add imports:

```python
import json
from typing import Any

from src.libs.llm import Message
```

If `json` is already imported in the file, keep one import only. Add these helpers near the bottom of the file:

```python
def _parse_action_response(content: str) -> tuple[str, str, dict[str, object], bool]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM action response was not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("LLM action response must be a JSON object.")
    action = payload.get("action")
    if not isinstance(action, dict):
        raise ValueError("LLM action response must include an action object.")
    tool = action.get("tool")
    tool_input = action.get("input", {})
    if not isinstance(tool, str) or not tool.strip():
        raise ValueError("LLM action tool must be a non-empty string.")
    if not isinstance(tool_input, dict):
        raise ValueError("LLM action input must be an object.")
    thought_summary = str(payload.get("thought_summary", "")).strip()
    return thought_summary, tool.strip(), dict(tool_input), bool(payload.get("stop", False))


def _action_messages(
    mission: AgentMission,
    task: AgentMissionTask,
    allowed_tools: list[str],
    trace_events: list[AgentTraceEvent],
) -> list[Message]:
    recent_observations = [
        {
            "tool": event.tool_name,
            "summary": event.observation_summary,
            "evidence_ids": event.evidence_ids[:5],
            "entity_ids": event.entity_ids[:5],
        }
        for event in trace_events[-4:]
    ]
    return [
        Message(
            role="system",
            content=(
                "You are TwinMind Archive's graph-grounded ReAct controller. "
                "Choose exactly one next tool call from the allowed tools. "
                "Return one JSON object only with keys thought_summary, action, and stop. "
                "Do not include Markdown fences or hidden reasoning."
            ),
        ),
        Message(
            role="user",
            content=json.dumps(
                {
                    "project_id": mission.project_id,
                    "goal": mission.goal,
                    "task_type": task.task_type,
                    "task_objective": task.objective,
                    "allowed_tools": allowed_tools,
                    "recent_observations": recent_observations,
                },
                ensure_ascii=False,
            ),
        ),
    ]
```

- [ ] **Step 4: Add LLM action selection to the runtime**

In `AgentMissionRuntime`, add this method:

```python
    def _select_tool_call(
        self,
        mission: AgentMission,
        task: AgentMissionTask,
        trace_events: list[AgentTraceEvent],
        fallback_tool_calls: list[tuple[str, dict[str, object]]],
        step_index: int,
    ) -> tuple[str, dict[str, object], dict[str, object]]:
        fallback_tool, fallback_input = fallback_tool_calls[step_index]
        if self.llm is None:
            return fallback_tool, fallback_input, {"llm_fallback": False, "selection": "deterministic"}
        try:
            response = self.llm.chat(
                _action_messages(
                    mission=mission,
                    task=task,
                    allowed_tools=task.allowed_tools,
                    trace_events=trace_events,
                )
            )
            thought_summary, tool_name, tool_input, stop = _parse_action_response(response.content)
            if stop:
                return fallback_tool, fallback_input, {
                    "thought_summary": thought_summary,
                    "model": response.model,
                    "llm_stop_requested": True,
                    "llm_fallback": True,
                }
            if tool_name not in task.allowed_tools:
                raise ValueError(f"Tool {tool_name} is not allowed for task {task.task_type}.")
            tool_input.setdefault("project_id", mission.project_id)
            return tool_name, tool_input, {
                "thought_summary": thought_summary,
                "model": response.model,
                "usage": response.usage,
                "llm_fallback": False,
                "selection": "llm",
            }
        except Exception as exc:
            return fallback_tool, fallback_input, {
                "llm_fallback": True,
                "selection": "deterministic",
                "error": str(exc),
            }
```

Then modify `_run_to_completion` so each step calls `_select_tool_call` instead of directly using `tool_name, tool_input` from `tool_calls`. The inner loop should look like this:

```python
            for step_index, _fallback in enumerate(tool_calls[: task.max_steps]):
                tool_name, tool_input, selection_metadata = self._select_tool_call(
                    mission=mission,
                    task=task,
                    trace_events=trace_events,
                    fallback_tool_calls=tool_calls,
                    step_index=step_index,
                )
                started_at = utc_now()
                result = self.tool_registry.execute(tool_name, tool_input)
                completed_at = utc_now()
                trace_events.append(
                    AgentTraceEvent(
                        id=f"{mission.id}:trace:{sequence}",
                        mission_id=mission.id,
                        task_id=task.id,
                        sequence=sequence,
                        event_type="action",
                        tool_name=tool_name,
                        tool_input=tool_input,
                        observation_summary=result.summary,
                        evidence_ids=result.evidence_ids,
                        entity_ids=result.entity_ids,
                        relation_ids=result.relation_ids,
                        started_at=started_at,
                        completed_at=completed_at,
                        metadata=selection_metadata,
                    )
                )
```

- [ ] **Step 5: Run LLM action-selection tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/test_project_archive_agent_mission.py::test_runtime_uses_llm_next_action_when_json_is_valid \
  tests/unit/test_project_archive_agent_mission.py::test_runtime_falls_back_when_llm_action_is_invalid \
  -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/project_archive/agent_mission.py tests/unit/test_project_archive_agent_mission.py
git commit -m "feat: add llm guided react tool selection"
```

---

### Task 5: Add ProjectArchiveService Integration

**Files:**
- Modify: `src/project_archive/service.py`
- Test: `tests/unit/test_project_archive_agent_mission.py`

- [ ] **Step 1: Add failing service integration test**

Append to `tests/unit/test_project_archive_agent_mission.py`:

```python
import json

from src.project_archive.service import ProjectArchiveService


def test_service_starts_loads_traces_and_updates_agent_mission(tmp_path):
    service = ProjectArchiveService(storage_dir=tmp_path)
    archive_dir = tmp_path / "demo"
    archive_dir.mkdir()
    draft = RuntimeFakeService(tmp_path).draft
    (archive_dir / "draft_archive.json").write_text(
        json.dumps(draft.to_dict()),
        encoding="utf-8",
    )

    planned = service.create_agent_mission(
        project_id="demo",
        goal="Understand architecture",
        max_tasks=2,
        max_steps_per_task=2,
    )
    mission = service.run_agent_mission(planned.id)
    loaded = service.load_agent_mission(mission.id)
    trace = service.agent_mission_trace(mission.id)
    stopped = service.update_agent_mission_status(mission.id, "stopped")

    assert planned.status == "planned"
    assert loaded.id == mission.id
    assert trace
    assert stopped.status == "stopped"
    assert (tmp_path / "demo" / "agent_missions" / f"{mission.id}.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_agent_mission.py::test_service_starts_loads_traces_and_updates_agent_mission -v
```

Expected: fail because `ProjectArchiveService.start_agent_mission` does not exist.

- [ ] **Step 3: Add service methods**

Modify imports in `src/project_archive/service.py`:

```python
from src.project_archive.agent_mission import AgentMissionRuntime, MissionStore
from src.project_archive.agent_tools import AgentToolRegistry
```

Add `AgentMission` and `AgentTraceEvent` to the `types` import list:

```python
    AgentMission,
    AgentTraceEvent,
```

Add methods to `ProjectArchiveService` after `update_mission_status`:

```python
    def create_agent_mission(
        self,
        project_id: str,
        *,
        goal: str,
        max_tasks: int = 5,
        max_steps_per_task: int = 4,
    ) -> AgentMission:
        draft = self.load_draft(project_id)
        runtime = self._agent_mission_runtime()
        mission = runtime.create(
            draft=draft,
            goal=goal,
            max_tasks=max_tasks,
            max_steps_per_task=max_steps_per_task,
        )
        return runtime.store.save(mission)

    def run_agent_mission(self, mission_id: str) -> AgentMission:
        self._validate_mission_id(mission_id)
        return self._agent_mission_runtime().run(mission_id)

    def start_agent_mission(
        self,
        project_id: str,
        *,
        goal: str,
        max_tasks: int = 5,
        max_steps_per_task: int = 4,
    ) -> AgentMission:
        planned = self.create_agent_mission(
            project_id=project_id,
            goal=goal,
            max_tasks=max_tasks,
            max_steps_per_task=max_steps_per_task,
        )
        return self.run_agent_mission(planned.id)

    def load_agent_mission(self, mission_id: str) -> AgentMission:
        self._validate_mission_id(mission_id)
        return self._agent_mission_runtime().load(mission_id)

    def agent_mission_trace(self, mission_id: str) -> list[AgentTraceEvent]:
        self._validate_mission_id(mission_id)
        return self._agent_mission_runtime().trace(mission_id)

    def update_agent_mission_status(self, mission_id: str, status: str) -> AgentMission:
        self._validate_mission_id(mission_id)
        return self._agent_mission_runtime().update_status(mission_id, status)

    def _agent_mission_runtime(self) -> AgentMissionRuntime:
        return AgentMissionRuntime(
            service=self,
            store=MissionStore(self.storage_dir),
            tool_registry=AgentToolRegistry(self),
        )
```

- [ ] **Step 4: Run service integration test**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_agent_mission.py::test_service_starts_loads_traces_and_updates_agent_mission -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/project_archive/service.py tests/unit/test_project_archive_agent_mission.py
git commit -m "feat: integrate agent mission runtime with service"
```

---

### Task 6: Add FastAPI Endpoints

**Files:**
- Modify: `src/project_archive/api.py`
- Test: `tests/unit/test_project_archive_api.py`

- [ ] **Step 1: Add failing API tests**

Append to `tests/unit/test_project_archive_api.py`:

```python
def test_agent_mission_endpoints_return_mission_and_trace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TWINMIND_AGENT_LLM_ENABLED", "false")
    client = _client(tmp_path)

    response = client.post(
        "/api/archives/sample/agent-missions",
        json={
            "goal": "Understand project architecture",
            "max_tasks": 2,
            "max_steps_per_task": 2,
        },
    )

    assert response.status_code == 202
    mission = response.json()
    assert mission["project_id"] == "sample"
    assert mission["tasks"]

    loaded = client.get(f"/api/agent-missions/{mission['id']}")
    trace = client.get(f"/api/agent-missions/{mission['id']}/trace")
    stopped = client.post(f"/api/agent-missions/{mission['id']}/stop")

    assert loaded.status_code == 200
    assert loaded.json()["status"] in {"planned", "running", "complete"}
    assert trace.status_code == 200
    assert "trace_events" in trace.json()
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_api.py::test_agent_mission_endpoints_return_mission_and_trace -v
```

Expected: fail with HTTP 404 for `/agent-missions`.

- [ ] **Step 3: Add API request model**

In `src/project_archive/api.py`, add after `MissionStartRequest`:

```python
class AgentMissionStartRequest(BaseModel):
    goal: str = Field(default="Understand project architecture", min_length=1)
    max_tasks: int = Field(default=5, ge=1, le=8)
    max_steps_per_task: int = Field(default=4, ge=1, le=8)
```

- [ ] **Step 4: Add API endpoints**

Inside `create_app()`, after the existing mission endpoints, add:

```python
    @app.post("/api/archives/{project_id}/agent-missions", status_code=202)
    def start_agent_mission(
        project_id: str,
        request: AgentMissionStartRequest,
        background_tasks: BackgroundTasks,
        service: ServiceDep,
    ) -> dict:
        try:
            mission = service.create_agent_mission(
                project_id=project_id,
                goal=request.goal,
                max_tasks=request.max_tasks,
                max_steps_per_task=request.max_steps_per_task,
            )
            background_tasks.add_task(service.run_agent_mission, mission.id)
            return mission.to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/agent-missions/{mission_id}")
    def get_agent_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.load_agent_mission(mission_id).to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/agent-missions/{mission_id}/trace")
    def get_agent_mission_trace(mission_id: str, service: ServiceDep) -> dict:
        try:
            return {
                "mission_id": mission_id,
                "trace_events": [
                    event.to_dict()
                    for event in service.agent_mission_trace(mission_id)
                ],
            }
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/agent-missions/{mission_id}/pause")
    def pause_agent_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.update_agent_mission_status(mission_id, "paused").to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/agent-missions/{mission_id}/resume")
    def resume_agent_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.update_agent_mission_status(mission_id, "complete").to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/agent-missions/{mission_id}/stop")
    def stop_agent_mission(mission_id: str, service: ServiceDep) -> dict:
        try:
            return service.update_agent_mission_status(mission_id, "stopped").to_dict()
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 5: Run API tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_api.py::test_agent_mission_endpoints_return_mission_and_trace -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/project_archive/api.py tests/unit/test_project_archive_api.py
git commit -m "feat: expose agent mission api"
```

---

### Task 7: Add Frontend API Types and Client Calls

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add TypeScript types**

Append to `frontend/src/types.ts`:

```ts
export type AgentMissionBudget = {
  max_tasks: number;
  max_steps_per_task: number;
  max_tool_calls: number;
  timeout_seconds: number;
};

export type AgentMissionTask = {
  id: string;
  mission_id: string;
  task_type: string;
  objective: string;
  status: string;
  allowed_tools: string[];
  max_steps: number;
  steps_used: number;
  input_entity_ids: string[];
  output_entity_ids: string[];
  evidence_ids: string[];
  findings: Array<Record<string, unknown>>;
  risks: Array<Record<string, unknown>>;
  confidence: number;
  created_at: string;
  completed_at: string;
};

export type AgentTraceEvent = {
  id: string;
  mission_id: string;
  task_id: string;
  sequence: number;
  event_type: "plan" | "action" | "observation" | "verification" | "final" | string;
  tool_name?: string | null;
  tool_input: Record<string, unknown>;
  observation_summary: string;
  evidence_ids: string[];
  entity_ids: string[];
  relation_ids: string[];
  started_at: string;
  completed_at: string;
  error?: string | null;
  metadata: Record<string, unknown>;
};

export type AgentMissionVerifierResult = {
  status: string;
  supported_finding_count: number;
  uncertain_finding_count: number;
  warnings: string[];
};

export type AgentMissionFinalReport = {
  summary: string;
  findings: Array<Record<string, unknown>>;
  evidence_ids: string[];
  confidence: number;
};

export type AgentMission = {
  id: string;
  project_id: string;
  goal: string;
  status: string;
  created_at: string;
  completed_at: string;
  budget: AgentMissionBudget;
  tasks: AgentMissionTask[];
  trace_events: AgentTraceEvent[];
  verifier_result?: AgentMissionVerifierResult | null;
  final_report?: AgentMissionFinalReport | null;
  metadata: Record<string, unknown>;
};
```

- [ ] **Step 2: Add API functions**

Modify imports in `frontend/src/api.ts` to include:

```ts
  AgentMission,
  AgentTraceEvent,
```

Add functions near existing mission API functions:

```ts
export async function startAgentMission(
  projectId: string,
  payload: { goal: string; max_tasks?: number; max_steps_per_task?: number },
): Promise<AgentMission> {
  const response = await fetch(`${API_BASE_URL}/api/archives/${encodeURIComponent(projectId)}/agent-missions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Agent mission start failed: ${response.status}`);
  }
  return (await response.json()) as AgentMission;
}

export async function fetchAgentMission(missionId: string): Promise<AgentMission> {
  const response = await fetch(`${API_BASE_URL}/api/agent-missions/${encodeURIComponent(missionId)}`);
  if (!response.ok) {
    throw new Error(`Agent mission fetch failed: ${response.status}`);
  }
  return (await response.json()) as AgentMission;
}

export async function fetchAgentMissionTrace(missionId: string): Promise<AgentTraceEvent[]> {
  const response = await fetch(`${API_BASE_URL}/api/agent-missions/${encodeURIComponent(missionId)}/trace`);
  if (!response.ok) {
    throw new Error(`Agent mission trace failed: ${response.status}`);
  }
  const payload = (await response.json()) as { trace_events: AgentTraceEvent[] };
  return payload.trace_events;
}

export async function updateAgentMissionStatus(
  missionId: string,
  action: "pause" | "resume" | "stop",
): Promise<AgentMission> {
  const response = await fetch(`${API_BASE_URL}/api/agent-missions/${encodeURIComponent(missionId)}/${action}`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Agent mission ${action} failed: ${response.status}`);
  }
  return (await response.json()) as AgentMission;
}
```

- [ ] **Step 3: Run TypeScript build**

Run:

```bash
npm --prefix frontend run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts
git commit -m "feat: add frontend agent mission client"
```

---

### Task 8: Add Agent Mission Panel to Frontend

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Import new API and types**

In `frontend/src/App.tsx`, extend API imports:

```ts
  fetchAgentMissionTrace,
  startAgentMission,
  updateAgentMissionStatus,
```

Extend type imports:

```ts
  AgentMission,
  AgentTraceEvent,
```

- [ ] **Step 2: Add state in `TwinMindApp`**

Near existing mission state:

```ts
  const [reactMission, setReactMission] = useState<AgentMission | null>(null);
  const [reactTrace, setReactTrace] = useState<AgentTraceEvent[]>([]);
  const [reactMissionError, setReactMissionError] = useState("");
  const [isStartingReactMission, setIsStartingReactMission] = useState(false);
```

- [ ] **Step 3: Reset state when archive changes**

In `resetArchiveView`, add:

```ts
    setReactMission(null);
    setReactTrace([]);
    setReactMissionError("");
```

In the branch that clears archive state, add the same three setters.

- [ ] **Step 4: Add handlers**

Add inside `TwinMindApp`:

```ts
  const handleStartReactMission = async () => {
    if (!archiveDraft || isStartingReactMission) return;
    setIsStartingReactMission(true);
    setReactMissionError("");
    try {
      const nextMission = await startAgentMission(archiveDraft.projectId, {
        goal: "Understand project architecture with graph-grounded evidence",
        max_tasks: 5,
        max_steps_per_task: 4,
      });
      setReactMission(nextMission);
      setReactTrace(nextMission.trace_events);
      const latestTrace = await fetchAgentMissionTrace(nextMission.id);
      setReactTrace(latestTrace);
      notify(locale === "zh" ? "ReAct Agent 任务已完成" : "ReAct Agent mission complete");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setReactMissionError(message);
      notify(`${copy[locale].missionError}: ${message}`);
    } finally {
      setIsStartingReactMission(false);
    }
  };

  const handleReactMissionAction = async (action: "pause" | "resume" | "stop") => {
    if (!reactMission) return;
    setReactMissionError("");
    try {
      const updated = await updateAgentMissionStatus(reactMission.id, action);
      setReactMission(updated);
      setReactTrace(updated.trace_events);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setReactMissionError(message);
    }
  };
```

- [ ] **Step 5: Add panel component**

Add this component near `MissionControlPanel`:

```tsx
function ReactAgentMissionPanel({
  locale,
  mission,
  trace,
  error,
  isStarting,
  onStart,
  onAction,
}: {
  locale: Locale;
  mission: AgentMission | null;
  trace: AgentTraceEvent[];
  error: string;
  isStarting: boolean;
  onStart: () => void;
  onAction: (action: "pause" | "resume" | "stop") => void;
}) {
  const title = locale === "zh" ? "Graph-grounded ReAct Agent" : "Graph-grounded ReAct Agent";
  const startLabel = isStarting
    ? locale === "zh" ? "启动中" : "Starting"
    : locale === "zh" ? "启动 ReAct 任务" : "Start ReAct mission";
  return (
    <section className="react-agent-panel panel" aria-label={title}>
      <div className="mission-control-head">
        <div>
          <span className="eyebrow">ReAct</span>
          <h2>{title}</h2>
          <p>
            {locale === "zh"
              ? "使用计划-执行、图谱工具调用和证据校验来分析当前项目。"
              : "Uses plan-and-execute, graph tool calls, and evidence verification for this archive."}
          </p>
        </div>
        <div className="mission-actions">
          <span className={`pipeline-status ${mission?.status ?? "pending"}`}>
            {mission ? missionStatusLabel(mission.status, locale) : locale === "zh" ? "未启动" : "Not started"}
          </span>
          <button className="primary-action" disabled={isStarting} onClick={onStart} type="button">
            {startLabel}
          </button>
          <button disabled={!mission || isStarting} onClick={() => onAction("stop")} type="button">
            {locale === "zh" ? "停止" : "Stop"}
          </button>
        </div>
      </div>
      {error ? <div className="mission-error" role="alert">{error}</div> : null}
      {mission ? (
        <>
          <div className="mission-meta-grid">
            <span>{locale === "zh" ? "目标" : "Goal"}</span>
            <strong>{mission.goal}</strong>
            <span>{locale === "zh" ? "任务" : "Tasks"}</span>
            <strong>{mission.tasks.length}</strong>
            <span>{locale === "zh" ? "工具调用" : "Tool calls"}</span>
            <strong>{trace.length}</strong>
            <span>{locale === "zh" ? "校验" : "Verifier"}</span>
            <strong>{mission.verifier_result?.status ?? "pending"}</strong>
          </div>
          <div className="react-plan-grid">
            {mission.tasks.map((task) => (
              <article className={`mission-task ${task.status}`} key={task.id}>
                <div className="mission-task-head">
                  <strong>{task.objective}</strong>
                  <span className={`pipeline-status ${task.status}`}>{missionStatusLabel(task.status, locale)}</span>
                </div>
                <div className="mission-task-metrics">
                  <span>{locale === "zh" ? "步骤" : "Steps"}: {task.steps_used} / {task.max_steps}</span>
                  <span>{locale === "zh" ? "证据" : "Evidence"}: {task.evidence_ids.length}</span>
                </div>
              </article>
            ))}
          </div>
          <div className="react-trace-list">
            <strong>{locale === "zh" ? "工具轨迹" : "Tool timeline"}</strong>
            {trace.map((event) => (
              <article className="react-trace-event" key={event.id}>
                <span>#{event.sequence}</span>
                <strong>{event.tool_name ?? event.event_type}</strong>
                <p>{event.observation_summary || (locale === "zh" ? "无观察摘要" : "No observation summary")}</p>
                <small>
                  {locale === "zh" ? "证据" : "Evidence"} {event.evidence_ids.length} · {locale === "zh" ? "实体" : "Entities"} {event.entity_ids.length}
                </small>
              </article>
            ))}
          </div>
          {mission.final_report ? (
            <div className="react-final-report">
              <strong>{locale === "zh" ? "最终报告" : "Final report"}</strong>
              <p>{mission.final_report.summary}</p>
            </div>
          ) : null}
        </>
      ) : (
        <p className="empty-note mission-empty">
          {locale === "zh"
            ? "还没有 ReAct Agent 任务。启动后会显示计划、工具轨迹、证据链和校验结果。"
            : "No ReAct Agent mission yet. Start one to see plan, tool trace, evidence chain, and verifier results."}
        </p>
      )}
    </section>
  );
}
```

- [ ] **Step 6: Render panel on Agent page**

In the Agent Analysis page render block, place before `MissionControlPanel`:

```tsx
            <ReactAgentMissionPanel
              locale={locale}
              mission={reactMission}
              trace={reactTrace}
              error={reactMissionError}
              isStarting={isStartingReactMission}
              onStart={handleStartReactMission}
              onAction={handleReactMissionAction}
            />
```

- [ ] **Step 7: Add CSS**

Append to `frontend/src/styles.css`:

```css
.react-agent-panel {
  display: grid;
  gap: 16px;
}

.react-plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}

.react-trace-list {
  display: grid;
  gap: 10px;
  max-height: 360px;
  overflow: auto;
  padding-right: 4px;
}

.react-trace-event {
  display: grid;
  grid-template-columns: auto 140px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: var(--surface-soft);
}

.react-trace-event p {
  margin: 0;
  min-width: 0;
}

.react-trace-event small {
  color: var(--text-muted);
  white-space: nowrap;
}

.react-final-report {
  padding: 12px;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: var(--surface-raised);
}

@media (max-width: 760px) {
  .react-trace-event {
    grid-template-columns: 1fr;
  }

  .react-trace-event small {
    white-space: normal;
  }
}
```

- [ ] **Step 8: Run frontend build**

Run:

```bash
npm --prefix frontend run build
```

Expected: build succeeds.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: show graph grounded agent mission trace"
```

---

### Task 9: End-to-End Verification and Regression Tests

**Files:**
- Modify: `tests/unit/test_project_archive_api.py`
- Review only: `docs/superpowers/specs/2026-06-27-graph-grounded-agent-design.md`

- [ ] **Step 1: Run targeted backend test suite**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/test_project_archive_agent_mission.py \
  tests/unit/test_project_archive_agent_tools.py \
  tests/unit/test_project_archive_api.py::test_agent_mission_endpoints_return_mission_and_trace \
  tests/unit/test_project_archive_api.py::test_start_architecture_mission_returns_completed_bounded_mission \
  -v
```

Expected: all selected tests pass.

- [ ] **Step 2: Run project archive unit tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_project_archive_*.py -v
```

Expected: all project archive unit tests pass, except environment-dependent Hybrid RAG provider assertions if the local embedding provider differs from test assumptions. If that known provider mismatch appears, record it in the final handoff and run the narrower agent mission tests from Step 1 as the blocking validation.

- [ ] **Step 3: Run lint on touched backend files**

Run:

```bash
.venv/bin/ruff check \
  src/project_archive/agent_mission.py \
  src/project_archive/agent_tools.py \
  src/project_archive/types.py \
  src/project_archive/service.py \
  src/project_archive/api.py \
  src/project_archive/multi_agent.py \
  tests/unit/test_project_archive_agent_mission.py \
  tests/unit/test_project_archive_agent_tools.py \
  tests/unit/test_project_archive_api.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Run frontend build**

Run:

```bash
npm --prefix frontend run build
```

Expected: build succeeds.

- [ ] **Step 5: Restart local app**

Run:

```bash
python3 ../start_twinmind_archive.py restart
```

from `/Users/kitten/MultimodalRAG/TwinMind Archive`, or:

```bash
python3 start_twinmind_archive.py restart
```

from `/Users/kitten/MultimodalRAG`.

Expected:

```text
Backend is ready: http://127.0.0.1:8010/api/health
Frontend is ready: http://127.0.0.1:5174
```

- [ ] **Step 6: Smoke test API with an existing archive**

Run:

```bash
curl -sS -X POST http://127.0.0.1:8010/api/archives/MODULAR-RAG-MCP-SERVER/agent-missions \
  -H 'Content-Type: application/json' \
  -d '{"goal":"Understand project architecture","max_tasks":2,"max_steps_per_task":2}' \
  | python -m json.tool | sed -n '1,80p'
```

Expected: JSON includes `id`, `project_id`, `tasks`, `trace_events`, and `final_report`.

- [ ] **Step 7: Manual frontend check**

Open:

```text
http://127.0.0.1:5174
```

Select an archive, open Agent Analysis, start the ReAct Agent mission, and verify:

- Plan cards render.
- Tool timeline renders.
- Verifier status renders.
- Final report renders.
- No raw chain-of-thought is displayed.

- [ ] **Step 8: Final commit**

If Steps 1, 3, 4, and 6 pass, commit any remaining frontend or test adjustments:

```bash
git status --short
git add   src/project_archive/agent_mission.py   src/project_archive/agent_tools.py   src/project_archive/types.py   src/project_archive/service.py   src/project_archive/api.py   src/project_archive/multi_agent.py   frontend/src/types.ts   frontend/src/api.ts   frontend/src/App.tsx   frontend/src/styles.css   tests/unit/test_project_archive_agent_mission.py   tests/unit/test_project_archive_agent_tools.py   tests/unit/test_project_archive_api.py
git commit -m "test: verify graph grounded agent mission runtime"
```

Use `git status --short` before staging so unrelated dirty files are not included.

---

## Self-Review Notes

Spec coverage:

- Mission planning is covered by Tasks 1, 3, and 4.
- Graph-grounded tool actions are covered by Tasks 2 and 3.
- Verification is covered by Task 3.
- API integration is covered by Tasks 5 and 6.
- Frontend trace display is covered by Tasks 7 and 8.
- Regression and manual validation are covered by Task 9.

Scope control:

- This plan does not rewrite ingestion, graph extraction, Hybrid RAG indexing, or the existing report pipeline.
- This plan implements optional DeepSeek next-action JSON in Task 4 and keeps deterministic tool-call defaults as the fallback path.

Known implementation choice:

- The API queues Agent missions through FastAPI `BackgroundTasks`, matching the existing upload and report job style. The service keeps a synchronous `start_agent_mission()` helper for unit tests and internal reuse.
