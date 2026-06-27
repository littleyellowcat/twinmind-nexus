import pytest

from src.project_archive.agent_tools import (
    MAX_EVIDENCE_CARDS,
    MAX_GRAPH_SEARCH_LIMIT,
    MAX_NEIGHBORHOOD_NODES,
    MAX_NEIGHBORHOOD_RELATIONS,
    AgentToolRegistry,
    ToolExecutionError,
)
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    ProjectRelation,
)


class FakeGraphResult:
    def __init__(self, index):
        self.entity_id = f"entity_{index}"
        self.evidence_ids = [f"ev_bulk_{index}"]

    def to_dict(self):
        return {
            "entity_id": self.entity_id,
            "label": self.entity_id,
            "type": "Class",
            "evidence_ids": self.evidence_ids,
        }


class FakeService:
    def __init__(self):
        bulk_evidence = [
            EvidenceCard(
                id=f"ev_bulk_{index}",
                source_type="code",
                source_path=f"bulk_{index}.py",
                title=f"Bulk {index}",
                snippet=f"class Bulk{index}: pass",
                linked_entities=["class_service"],
            )
            for index in range(30)
        ]
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
                *bulk_evidence,
            ],
        )
        self.last_graph_search_limit = None
        self.last_neighborhood_kwargs = None

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
        self.last_graph_search_limit = limit
        return [FakeGraphResult(index) for index in range(limit + 5)]

    def graph_neighborhood(self, project_id, **kwargs):
        self.last_neighborhood_kwargs = kwargs
        return type(
            "Neighborhood",
            (),
            {
                "to_dict": lambda self: {
                    "project_id": project_id,
                    "nodes": [
                        {"id": f"node_{index}", "label": f"Node {index}", "type": "Class"}
                        for index in range(MAX_NEIGHBORHOOD_NODES + 5)
                    ],
                    "relations": [
                        {
                            "id": f"rel_{index}",
                            "source_id": "file_main",
                            "target_id": "class_service",
                            "type": "DEFINES",
                        }
                        for index in range(MAX_NEIGHBORHOOD_RELATIONS + 5)
                    ],
                    "evidence_ids": [
                        f"ev_bulk_{index}" for index in range(MAX_EVIDENCE_CARDS + 5)
                    ],
                    "is_sparse": True,
                }
            },
        )()


def test_tool_names_are_exact_allowlist():
    registry = AgentToolRegistry(FakeService())

    assert registry.tool_names() == [
        "get_evidence",
        "graph_neighborhood",
        "graph_search",
        "graph_summary",
        "hybrid_search",
        "inspect_entity",
        "list_halls",
        "run_specialist_agent",
    ]


def test_tool_registry_lists_and_executes_graph_summary():
    registry = AgentToolRegistry(FakeService())

    result = registry.execute("graph_summary", {"project_id": "demo"})

    assert "graph_summary" in registry.tool_names()
    assert result.tool_name == "graph_summary"
    assert result.summary == "Graph summary returned 2 entities and 1 relations."
    assert result.payload["metrics"]["entities"] == 2


def test_list_halls_returns_counts_not_entity_ids():
    registry = AgentToolRegistry(FakeService())

    result = registry.execute("list_halls", {"project_id": "demo"})

    assert result.entity_ids == []
    assert result.payload["halls"] == [
        {
            "id": "hall_architecture",
            "name": "Architecture Hall",
            "description": "Architecture",
            "entity_count": 2,
        }
    ]


def test_oversized_graph_search_limit_is_capped():
    service = FakeService()
    registry = AgentToolRegistry(service)

    result = registry.execute(
        "graph_search",
        {"project_id": "demo", "query": "service", "limit": 999},
    )

    assert service.last_graph_search_limit == MAX_GRAPH_SEARCH_LIMIT
    assert len(result.payload["results"]) == MAX_GRAPH_SEARCH_LIMIT
    assert result.payload["metadata"]["requested_limit"] == 999
    assert result.payload["metadata"]["effective_limit"] == MAX_GRAPH_SEARCH_LIMIT
    assert result.payload["metadata"]["truncated"] is True


def test_oversized_graph_neighborhood_limits_are_capped():
    service = FakeService()
    registry = AgentToolRegistry(service)

    result = registry.execute(
        "graph_neighborhood",
        {
            "project_id": "demo",
            "node_limit": 999,
            "relation_limit": 999,
            "relation_types": ["DEFINES"],
        },
    )

    assert service.last_neighborhood_kwargs["node_limit"] == MAX_NEIGHBORHOOD_NODES
    assert service.last_neighborhood_kwargs["relation_limit"] == MAX_NEIGHBORHOOD_RELATIONS
    assert len(result.payload["nodes"]) == MAX_NEIGHBORHOOD_NODES
    assert len(result.payload["relations"]) == MAX_NEIGHBORHOOD_RELATIONS
    assert len(result.evidence_ids) == MAX_EVIDENCE_CARDS
    assert result.payload["metadata"]["truncated"] is True


def test_get_evidence_returns_selected_cards():
    registry = AgentToolRegistry(FakeService())

    result = registry.execute(
        "get_evidence",
        {"project_id": "demo", "evidence_ids": ["ev_service"]},
    )

    assert result.evidence_ids == ["ev_service"]
    assert result.payload["evidence_cards"][0]["title"] == "QueryService"


def test_oversized_evidence_ids_list_is_truncated():
    registry = AgentToolRegistry(FakeService())
    evidence_ids = [f"ev_bulk_{index}" for index in range(MAX_EVIDENCE_CARDS + 5)]

    result = registry.execute(
        "get_evidence",
        {"project_id": "demo", "evidence_ids": evidence_ids},
    )

    assert len(result.evidence_ids) == MAX_EVIDENCE_CARDS
    assert result.evidence_ids == evidence_ids[:MAX_EVIDENCE_CARDS]
    assert result.payload["metadata"]["requested_count"] == MAX_EVIDENCE_CARDS + 5
    assert result.payload["metadata"]["effective_count"] == MAX_EVIDENCE_CARDS
    assert result.payload["metadata"]["truncated"] is True


def test_string_evidence_ids_is_rejected():
    registry = AgentToolRegistry(FakeService())

    with pytest.raises(ToolExecutionError, match="list of strings: evidence_ids"):
        registry.execute(
            "get_evidence",
            {"project_id": "demo", "evidence_ids": "ev_service"},
        )


def test_inspect_entity_returns_neighbors_and_evidence():
    registry = AgentToolRegistry(FakeService())

    result = registry.execute(
        "inspect_entity",
        {"project_id": "demo", "entity_id": "class_service"},
    )

    assert result.entity_ids == ["class_service"]
    assert result.relation_ids == ["rel_defines"]
    assert result.evidence_ids == ["ev_service"]


def test_unknown_specialist_role_is_rejected_by_registry():
    registry = AgentToolRegistry(FakeService())

    with pytest.raises(ToolExecutionError, match="Unknown specialist role"):
        registry.execute(
            "run_specialist_agent",
            {"project_id": "demo", "role": "shell"},
        )


def test_unknown_tool_is_rejected():
    registry = AgentToolRegistry(FakeService())

    with pytest.raises(ToolExecutionError, match="Unknown Agent tool"):
        registry.execute("shell", {"cmd": "ls"})
