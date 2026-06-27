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
