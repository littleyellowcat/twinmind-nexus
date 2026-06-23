from importlib.util import find_spec
from pathlib import Path

import pytest

from src.project_archive.service import ProjectArchiveService
from src.project_archive.types import QueryMode

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


@pytest.mark.skipif(
    find_spec("kuzu") is None,
    reason="Kuzu optional dependency is not installed",
)
def test_service_can_ingest_with_kuzu_graph_provider(tmp_path):
    service = ProjectArchiveService(storage_dir=tmp_path, graph_provider="kuzu")

    draft = service.ingest_project(project_root=FIXTURE, project_id="sample-kuzu")

    assert draft.entities
    assert (tmp_path / "sample-kuzu" / "graph.kuzu").exists()
