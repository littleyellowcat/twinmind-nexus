import json
from importlib.util import find_spec
from pathlib import Path

import pytest

from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import (
    ArchiveHall,
    EvidenceCard,
    ProjectArchiveDraft,
    ProjectEntity,
    QueryMode,
)

FIXTURE = Path("tests/fixtures/project_archive_sample")


def test_service_ingests_and_queries_project_archive(tmp_path):
    service = ProjectArchiveService(storage_dir=tmp_path)

    draft = service.ingest_project(project_root=FIXTURE, project_id="sample")
    result = service.query_project(
        project_id="sample",
        question="What is the architecture?",
        mode=QueryMode.ARCHITECTURE_TOUR,
    )

    assert draft.project_id == "sample"
    assert draft.halls
    assert result.mode == QueryMode.ARCHITECTURE_TOUR
    assert result.evidence_card_ids


def test_service_rejects_unknown_project(tmp_path):
    service = ProjectArchiveService(storage_dir=tmp_path)

    try:
        service.query_project(
            project_id="missing",
            question="What is this?",
            mode=QueryMode.EVIDENCE_QA,
        )
    except ValueError as exc:
        assert "Project archive not found" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown project")


def test_service_query_can_scope_to_selected_hall(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.project_archive.service.create_archive_llm_enhancer_from_config",
        lambda: None,
    )
    draft = ProjectArchiveDraft(
        project_id="scoped",
        halls=[
            ArchiveHall(
                id="hall_architecture",
                name="Architecture Hall",
                description="General README context.",
                entity_ids=["file:readme"],
            ),
            ArchiveHall(
                id="hall_retrieval",
                name="Retrieval Hall",
                description="Retrieval components and hybrid search.",
                entity_ids=["retriever:hybrid"],
            ),
        ],
        entities=[
            ProjectEntity(
                id="file:readme",
                type="File",
                name="README.md",
                evidence_ids=["ev_readme"],
            ),
            ProjectEntity(
                id="retriever:hybrid",
                type="Retriever",
                name="HybridRetriever",
                evidence_ids=["ev_retrieval"],
            ),
        ],
        evidence_cards=[
            EvidenceCard(
                id="ev_readme",
                source_type="markdown",
                source_path="README.md",
                title="Project overview",
                snippet="General overview.",
                linked_entities=["file:readme"],
            ),
            EvidenceCard(
                id="ev_retrieval",
                source_type="code",
                source_path="src/retrieval/hybrid.py",
                title="Hybrid retriever",
                snippet="class HybridRetriever: pass",
                linked_entities=["retriever:hybrid"],
            ),
        ],
    )
    archive_dir = tmp_path / draft.project_id
    archive_dir.mkdir()
    (archive_dir / "draft_archive.json").write_text(
        json.dumps(draft.to_dict()),
        encoding="utf-8",
    )
    service = ProjectArchiveService(storage_dir=tmp_path)

    result = service.query_project(
        project_id="scoped",
        question="Analyze the selected hall.",
        mode=QueryMode.ARCHITECTURE_TOUR,
        hall_id="hall_retrieval",
    )

    assert result.evidence_card_ids == ["ev_retrieval"]
    assert result.affected_entities == ["retriever:hybrid"]
    assert "Selected archive hall: Retrieval Hall" in result.question


@pytest.mark.skipif(
    find_spec("kuzu") is None,
    reason="Kuzu optional dependency is not installed",
)
def test_service_can_ingest_with_kuzu_graph_provider(tmp_path):
    service = ProjectArchiveService(storage_dir=tmp_path, graph_provider="kuzu")

    draft = service.ingest_project(project_root=FIXTURE, project_id="sample-kuzu")

    assert draft.entities
    assert (tmp_path / "sample-kuzu" / "graph.kuzu").exists()
