"""Tests for TwinMind graph explorer projections."""

from __future__ import annotations

from src.project_archive.graph_explorer import (
    build_graph_neighborhood,
    build_graph_summary,
)
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    GraphNeighborhood,
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
                entity_ids=["orphan:note"],
            ),
        ],
        entities=[
            ProjectEntity(
                id="file:main.py",
                type="File",
                name="main.py",
                source_path="main.py",
                evidence_ids=["ev:main"],
            ),
            ProjectEntity(
                id="class:ArchiveBuilder",
                type="Class",
                name="ArchiveBuilder",
                source_path="src/archive_builder.py",
                evidence_ids=["ev:builder"],
            ),
            ProjectEntity(
                id="config:llm",
                type="Config",
                name="llm",
                source_path="config/settings.yaml",
                evidence_ids=["ev:config"],
            ),
            ProjectEntity(
                id="doc:readme",
                type="Markdown",
                name="README.md",
                source_path="README.md",
                evidence_ids=["ev:readme"],
            ),
            ProjectEntity(
                id="orphan:note",
                type="Concept",
                name="Orphan Note",
                evidence_ids=[],
            ),
        ],
        relations=[
            ProjectRelation(
                id="rel:defines",
                source_id="file:main.py",
                target_id="class:ArchiveBuilder",
                type="DEFINES",
                evidence_ids=["ev:builder"],
            ),
            ProjectRelation(
                id="rel:configures",
                source_id="class:ArchiveBuilder",
                target_id="config:llm",
                type="CONFIGURES",
                evidence_ids=["ev:config"],
            ),
            ProjectRelation(
                id="rel:mentions",
                source_id="doc:readme",
                target_id="file:main.py",
                type="MENTIONS",
                evidence_ids=["ev:readme"],
            ),
        ],
        evidence_cards=[
            EvidenceCard(
                id="ev:main",
                source_type="code",
                source_path="main.py",
                title="main",
                snippet="def main(): pass",
            ),
            EvidenceCard(
                id="ev:builder",
                source_type="code",
                source_path="src/archive_builder.py",
                title="ArchiveBuilder",
                snippet="class ArchiveBuilder: pass",
            ),
            EvidenceCard(
                id="ev:config",
                source_type="config",
                source_path="config/settings.yaml",
                title="llm",
                snippet="llm:",
            ),
            EvidenceCard(
                id="ev:readme",
                source_type="markdown",
                source_path="README.md",
                title="README",
                snippet="# Demo",
            ),
        ],
    )


def test_graph_summary_recommends_starts_with_reasons() -> None:
    summary = build_graph_summary(_draft())

    assert summary.project_id == "demo"
    assert summary.metrics == {"entities": 5, "relations": 3, "evidence": 4}
    assert summary.recommended_starts[0].entity_id in {
        "file:main.py",
        "class:ArchiveBuilder",
    }
    assert summary.recommended_starts[0].reason
    assert {item.group for item in summary.recommended_starts} >= {
        "entry_file",
        "high_degree",
    }


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
    assert {node.id for node in neighborhood.nodes} == {
        "class:ArchiveBuilder",
        "config:llm",
    }
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
    assert {node.id for node in neighborhood.nodes} == {
        "file:main.py",
        "class:ArchiveBuilder",
        "config:llm",
    }
    assert {relation.id for relation in neighborhood.relations} == {
        "rel:defines",
        "rel:configures",
    }


def test_node_limit_zero_returns_no_visible_graph() -> None:
    neighborhood = build_graph_neighborhood(
        _draft(),
        hall_id=None,
        focus_entity_id="class:ArchiveBuilder",
        depth=1,
        relation_types=[],
        node_limit=0,
        relation_limit=20,
    )

    assert neighborhood.nodes == []
    assert neighborhood.relations == []
    assert neighborhood.is_sparse is True


def test_relation_type_filter_strips_whitespace_and_ignores_case() -> None:
    neighborhood = build_graph_neighborhood(
        _draft(),
        hall_id="hall_config",
        focus_entity_id=None,
        depth=1,
        relation_types=[" configures "],
        node_limit=20,
        relation_limit=20,
    )

    assert {relation.id for relation in neighborhood.relations} == {"rel:configures"}
    assert {node.id for node in neighborhood.nodes} == {
        "class:ArchiveBuilder",
        "config:llm",
    }


def test_graph_neighborhood_serialization_round_trip() -> None:
    neighborhood = build_graph_neighborhood(
        _draft(),
        hall_id="hall_config",
        focus_entity_id=None,
        depth=1,
        relation_types=[],
        node_limit=20,
        relation_limit=20,
    )

    restored = GraphNeighborhood.from_dict(neighborhood.to_dict())

    assert restored == neighborhood
    assert restored.to_dict() == neighborhood.to_dict()
